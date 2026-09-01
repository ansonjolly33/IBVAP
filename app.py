import os
import cv2
import time
import torch
import sys
import math
import requests
import threading
import numpy as np
from datetime import datetime
from flask import Flask, render_template, Response, jsonify, request
from ultralytics import YOLO
from anpr_engine import PrecisionANPR

app = Flask(__name__)

# --- CONFIGURATION & DIRECTORIES ---
TELEGRAM_BOT_TOKEN = "8819059111:AAGhHpKuz95z9BEdGon7okWtoXqWF2rkypQ"
TELEGRAM_CHAT_ID = "1235837706"

SNAPSHOT_DIR = os.path.join('static', 'breaches')
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# Hardware & AI Engines
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"--- IBVAP: Risk-Engine Active on [{device.upper()}] ---")

model = YOLO('yolov8n.pt').to(device)
anpr_detector = PrecisionANPR()

# Cascade Loader
xml_path = getattr(getattr(cv2, 'data', None), 'haarcascades', '') + 'haarcascade_frontalface_default.xml'
if not os.path.exists(xml_path):
    xml_path = 'haarcascade_frontalface_default.xml'
    if not os.path.exists(xml_path):
        import urllib.request
        url = 'https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml'
        urllib.request.urlretrieve(url, xml_path)

face_cascade = cv2.CascadeClassifier(xml_path)

# System State
safe_zones = []
current_drawing = []
alarm_active = False

stats = {
    "system_status": "MONITORING",
    "total_zones": 0,
    "total_breaches": 0,
    "active_persons": 0,
    "active_vehicles": 0,
    "faces_detected": 0,
    "plates_read": 0,
    "risk_score": 0,
    "risk_level": "LOW",
    "risk_color": "#22c55e"
}

outside_timers = {}
position_history = {}
already_notified_instant = set()

# Persistent Global Video Stream
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)

# --- TELEGRAM DISPATCH ENGINE ---
def send_telegram_alert(image_path, caption_text):
    def _send():
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        try:
            with open(image_path, 'rb') as photo:
                payload = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption_text, 'parse_mode': 'HTML'}
                files = {'photo': photo}
                requests.post(url, data=payload, files=files, timeout=10)
        except Exception as e:
            print(f"[TELEGRAM ERROR]: {e}")
    threading.Thread(target=_send, daemon=True).start()

# --- ALARM BEEP ENGINE ---
def continuous_alarm():
    global alarm_active
    while alarm_active:
        try:
            if sys.platform == "win32":
                import winsound
                winsound.Beep(2500, 150)
            else:
                sys.stdout.write('\a')
                sys.stdout.flush()
                time.sleep(0.15)
        except Exception:
            pass

def set_alarm_state(state):
    global alarm_active
    if state and not alarm_active:
        alarm_active = True
        threading.Thread(target=continuous_alarm, daemon=True).start()
    elif not state:
        alarm_active = False

# --- DYNAMIC RISK COMPUTATION ENGINE ---
def calculate_threat_score(track_id, cx, cy, is_breach, elapsed_time):
    score = 0
    reasons = []

    # 1. Restricted Area Breach (+30)
    if is_breach:
        score += 30
        reasons.append("Restricted Zone Breach (+30)")

    # 2. Night-Time Detection Window (+20) [8 PM - 6 AM]
    current_hour = datetime.now().hour
    if current_hour >= 20 or current_hour < 6:
        score += 20
        reasons.append("Night-Time Activity (+20)")

    # 3. Loitering Time > 2 Minutes / 120 Seconds (+20)
    if elapsed_time >= 120:
        score += 20
        reasons.append("Loitering >2 mins (+20)")

    # 4. Movement Towards Sensitive Area (+30)
    if track_id in position_history and len(position_history[track_id]) >= 5:
        prev_cx, prev_cy = position_history[track_id][0]
        # Vector calculation checking if object is moving deeper into frame center/zones
        movement_dist = math.hypot(cx - prev_cx, cy - prev_cy)
        if movement_dist > 40 and cy > prev_cy:  # Moving inward/towards target
            score += 30
            reasons.append("Approach Motion (+30)")

    # Map Score to Severity Level & Color Theme
    if score <= 25:
        level, color, icon, hex_color = "LOW", "GREEN", "🟢", "#22c55e"
    elif score <= 50:
        level, color, icon, hex_color = "MEDIUM", "YELLOW", "🟡", "#eab308"
    elif score <= 75:
        level, color, icon, hex_color = "HIGH", "ORANGE", "🟠", "#f97316"
    else:
        level, color, icon, hex_color = "CRITICAL", "RED", "🔴", "#ef4444"

    return min(score, 100), level, color, icon, hex_color, reasons

# --- UNIFIED VIDEO PROCESSING LOOP ---
def generate_frames():
    global stats, safe_zones, current_drawing, cap

    while True:
        if not cap.isOpened():
            cap.open(0)
            time.sleep(0.5)

        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.05)
            continue

        frame = cv2.resize(frame, (800, 600))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        current_time = time.time()
        out_of_bounds = False

        person_count = 0
        vehicle_count = 0
        max_frame_risk = 0
        frame_level, frame_color, frame_hex = "LOW", "GREEN", "#22c55e"

        # 1. Face Detection
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(30, 30))
        stats["faces_detected"] = len(faces)
        for (fx, fy, fw, fh) in faces:
            cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), (255, 0, 255), 2)

        # 2. Object Detection & Tracking
        results = model.track(frame, classes=[0, 2, 3, 5, 7], conf=0.30, device=device, persist=True, verbose=False)[0]

        if results.boxes is not None:
            boxes = results.boxes.xyxy.cpu().numpy()
            clss = results.boxes.cls.cpu().numpy().astype(int)
            track_ids = results.boxes.id.cpu().numpy().astype(int) if results.boxes.id is not None else range(len(boxes))

            for box, track_id, cls in zip(boxes, track_ids, clss):
                x1, y1, x2, y2 = map(int, box)
                cx, cy = int((x1 + x2) / 2), int(y2)
                class_name = model.names[cls].upper()

                if cls == 0:
                    person_count += 1
                elif cls in [2, 3, 5, 7]:
                    vehicle_count += 1

                # Track position history for vector approach detection
                if track_id not in position_history:
                    position_history[track_id] = []
                position_history[track_id].append((cx, cy))
                if len(position_history[track_id]) > 10:
                    position_history[track_id].pop(0)

                # ANPR Check
                plate_text, plate_crop = "", None
                if cls in [2, 3, 5, 7]:
                    vehicle_crop = frame[max(0, y1):min(600, y2), max(0, x1):min(800, x2)]
                    if vehicle_crop.size > 0:
                        plate_text, plate_crop = anpr_detector.scan_vehicle(vehicle_crop)
                        if plate_text:
                            stats["plates_read"] += 1

                # Zone Collision Check
                is_inside_any_zone = False
                if len(safe_zones) > 0:
                    for zone_pts in safe_zones:
                        if len(zone_pts) >= 3:
                            pts_array = np.array(zone_pts, np.int32)
                            if cv2.pointPolygonTest(pts_array, (cx, cy), False) >= 0:
                                is_inside_any_zone = True
                                break

                is_breaching = (len(safe_zones) > 0 and not is_inside_any_zone)
                if is_breaching:
                    out_of_bounds = True

                # Elapsed time tracking
                if is_breaching:
                    if track_id not in outside_timers:
                        outside_timers[track_id] = current_time
                    elapsed = current_time - outside_timers[track_id]
                else:
                    elapsed = 0
                    outside_timers.pop(track_id, None)
                    already_notified_instant.discard(track_id)

                # Calculate Risk Matrix
                score, level, color, icon, hex_color, reasons = calculate_threat_score(
                    track_id, cx, cy, is_breaching, elapsed
                )

                if score > max_frame_risk:
                    max_frame_risk = score
                    frame_level, frame_hex = level, hex_color

                # Dispatch Telegram Notification with Theme & Score
                if is_breaching and track_id not in already_notified_instant:
                    vehicle_crop = frame[max(0, y1):min(600, y2), max(0, x1):min(800, x2)]
                    filename = f"BREACH_{int(time.time()*1000)}_{class_name}_ID{track_id}.jpg"
                    img_path = os.path.join(SNAPSHOT_DIR, filename)

                    save_img = plate_crop if (plate_crop is not None and plate_crop.size > 0) else vehicle_crop

                    if save_img is not None and save_img.size > 0:
                        cv2.imwrite(img_path, save_img)

                        # Styled HTML Telegram Message
                        caption = (
                            f"<b>{icon} SECURITY ALERT — {level} RISK</b>\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"<b>Risk Score:</b> {score}/100\n"
                            f"<b>Theme Color:</b> {color}\n"
                            f"<b>Target:</b> {class_name} #{track_id}\n"
                            f"<b>Plate Text:</b> {plate_text if plate_text else 'N/A'}\n"
                            f"<b>Triggers:</b>\n• " + "\n• ".join(reasons) + "\n"
                            f"<b>Timestamp:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        send_telegram_alert(img_path, caption)
                        stats["total_breaches"] += 1

                    already_notified_instant.add(track_id)

                # Visual bounding boxes matching theme color
                box_color = (0, 0, 255) if is_breaching else (0, 255, 0)
                label = f"{class_name} #{track_id} | RISK: {score} ({level})"
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
                cv2.putText(frame, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, box_color, 2)

        stats["active_persons"] = person_count
        stats["active_vehicles"] = vehicle_count
        stats["risk_score"] = max_frame_risk
        stats["risk_level"] = frame_level
        stats["risk_color"] = frame_hex

        set_alarm_state(out_of_bounds)
        stats["system_status"] = f"ALARM ({frame_level})!" if out_of_bounds else "SECURE"
        stats["total_zones"] = len(safe_zones)

        # Draw Zones
        for idx, zone_pts in enumerate(safe_zones):
            if len(zone_pts) >= 3:
                pts = np.array(zone_pts, np.int32).reshape((-1, 1, 2))
                overlay = frame.copy()
                cv2.fillPoly(overlay, [pts], (0, 255, 0))
                cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
                cv2.polylines(frame, [pts], True, (0, 255, 0), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# API Endpoints
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/add_point', methods=['POST'])
def add_point():
    global current_drawing
    data = request.json
    current_drawing.append((data['x'], data['y']))
    return jsonify({"status": "point added", "count": len(current_drawing)})

@app.route('/api/lock_zone', methods=['POST'])
def lock_zone():
    global current_drawing, safe_zones
    if len(current_drawing) >= 3:
        safe_zones.append(list(current_drawing))
        current_drawing.clear()
        return jsonify({"status": "success", "total_zones": len(safe_zones)})
    return jsonify({"status": "error", "message": "Need at least 3 points"})

@app.route('/api/clear_zones', methods=['POST'])
def clear_zones():
    global safe_zones, current_drawing
    safe_zones.clear()
    current_drawing.clear()
    return jsonify({"status": "cleared"})

@app.route('/api/stats')
def get_stats():
    images = [os.path.join(SNAPSHOT_DIR, f) for f in os.listdir(SNAPSHOT_DIR) if f.endswith('.jpg')]
    images.sort(key=os.path.getmtime, reverse=True)
    relative_paths = [f"/static/breaches/{os.path.basename(img)}" for img in images]

    return jsonify({
        "stats": stats,
        "recent_snapshots": relative_paths[:4]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)