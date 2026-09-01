import os
import cv2
import time
import torch
import sys
import requests
import threading
import numpy as np
from ultralytics import YOLO

# ==========================================
# PRE-CONFIGURED TELEGRAM CREDENTIALS
# ==========================================
TELEGRAM_BOT_TOKEN = "8819059111:AAGhHpKuz95z9BEdGon7okWtoXqWF2rkypQ"
TELEGRAM_CHAT_ID = "1235837706"

CAPTURE_DIR = "telegram_alerts"
os.makedirs(CAPTURE_DIR, exist_ok=True)

# 1. GPU CUDA Acceleration Selection
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"--- IBVAP: Module 7 Security Engine Running on [{device.upper()}] ---")

# 2. Load YOLO Detection Model
model = YOLO('yolov8n.pt').to(device)

polygon_pts = []
drawing_complete = False
alarm_active = False

outside_timers = {}
already_notified_instant = set()
already_notified_loiter = set()

# 3. Telegram Dispatcher (Runs in background thread)
def send_telegram_alert(image_path, caption_text):
    def _send():
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        try:
            with open(image_path, 'rb') as photo:
                payload = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption_text}
                files = {'photo': photo}
                response = requests.post(url, data=payload, files=files, timeout=10)
                if response.status_code == 200:
                    print(f"[TELEGRAM SENT]: Alert image dispatched successfully.")
                else:
                    print(f"[TELEGRAM ERROR]: {response.text}")
        except Exception as e:
            print(f"[TELEGRAM FAILED]: {e}")

    threading.Thread(target=_send, daemon=True).start()

# 4. Continuous Audio Alarm Thread
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

# 5. Mouse Callback for Native Drawing
def draw_polygon_event(event, x, y, flags, param):
    global polygon_pts, drawing_complete
    if drawing_complete:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        polygon_pts.append((x, y))
        print(f"[POINT ADDED]: ({x}, {y})")
    elif event == cv2.EVENT_RBUTTONDOWN and len(polygon_pts) >= 3:
        drawing_complete = True
        print("[SAFE ZONE LOCKED]: Perimeter active.")

# 6. Initialize Webcam Window
cap = cv2.VideoCapture(0)
window_name = "IBVAP Module 7 - Security Dispatcher"
cv2.namedWindow(window_name)
cv2.setMouseCallback(window_name, draw_polygon_event)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.resize(frame, (800, 600))
    current_time = time.time()
    active_ids_in_frame = set()
    out_of_bounds_detected = False

    # Track Persons (0), Cars (2), Motorcycles (3), Buses (5), Trucks (7)
    results = model.track(frame, classes=[0, 2, 3, 5, 7], conf=0.30, device=device, persist=True, verbose=False)[0]

    if results.boxes is not None:
        boxes = results.boxes.xyxy.cpu().numpy()
        clss = results.boxes.cls.cpu().numpy().astype(int)
        track_ids = results.boxes.id.cpu().numpy().astype(int) if results.boxes.id is not None else range(len(boxes))

        for box, track_id, cls in zip(boxes, track_ids, clss):
            active_ids_in_frame.add(track_id)
            x1, y1, x2, y2 = map(int, box)
            cx, cy = int((x1 + x2) / 2), int(y2)

            is_inside_zone = True

            if drawing_complete and len(polygon_pts) >= 3:
                pts_array = np.array(polygon_pts, np.int32)
                dist = cv2.pointPolygonTest(pts_array, (cx, cy), False)
                if dist < 0:
                    is_inside_zone = False
                    out_of_bounds_detected = True

            class_name = model.names[cls].upper()
            timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")

            # ALERT LOGIC: TARGET IS OUTSIDE THE SAFE ZONE
            if not is_inside_zone and drawing_complete:
                if track_id not in outside_timers:
                    outside_timers[track_id] = current_time

                elapsed = current_time - outside_timers[track_id]

                # ACTION 1: Instant Snapshot on initial breach
                if track_id not in already_notified_instant:
                    crop = frame[max(0, y1):min(600, y2), max(0, x1):min(800, x2)]
                    filename = f"BREACH_{class_name}_ID{track_id}.jpg"
                    img_path = os.path.join(CAPTURE_DIR, filename)

                    if crop.size > 0:
                        cv2.imwrite(img_path, crop)
                        caption = (
                            f"🚨 OUT OF BOUNDS BREACH!\n"
                            f"Entity: {class_name} #{track_id}\n"
                            f"Status: Outside Safe Zone\n"
                            f"Time: {timestamp_str}"
                        )
                        send_telegram_alert(img_path, caption)

                    already_notified_instant.add(track_id)

                # ACTION 2: Extended Loitering Snapshot (>3 seconds outside safe zone)
                if elapsed >= 3.0 and track_id not in already_notified_loiter:
                    crop = frame[max(0, y1):min(600, y2), max(0, x1):min(800, x2)]
                    filename = f"LOITER_OUTSIDE_{class_name}_ID{track_id}.jpg"
                    img_path = os.path.join(CAPTURE_DIR, filename)

                    if crop.size > 0:
                        cv2.imwrite(img_path, crop)
                        caption = (
                            f"⚠️ EXTENDED BREACH WARNING!\n"
                            f"Entity: {class_name} #{track_id}\n"
                            f"Status: Outside Zone (>3s Continuous)\n"
                            f"Time: {timestamp_str}"
                        )
                        send_telegram_alert(img_path, caption)

                    already_notified_loiter.add(track_id)

                color = (0, 0, 255)
                label = f"{class_name} #{track_id} | OUTSIDE: {elapsed:.1f}s"
            else:
                # Target stepped back into the safe zone
                outside_timers.pop(track_id, None)
                already_notified_instant.discard(track_id)
                already_notified_loiter.discard(track_id)
                color = (0, 255, 0)
                label = f"{class_name} #{track_id} | SAFE ZONE"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.circle(frame, (cx, cy), 5, (255, 255, 0), -1)
            cv2.putText(frame, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)

    # Continuous audio alert when outside safe zone
    set_alarm_state(out_of_bounds_detected)

    # Cleanup timers for objects leaving feed
    for tid in list(outside_timers.keys()):
        if tid not in active_ids_in_frame:
            del outside_timers[tid]
            already_notified_instant.discard(tid)
            already_notified_loiter.discard(tid)

    # Render Polygon Safe Zone
    if len(polygon_pts) > 0:
        pts = np.array(polygon_pts, np.int32).reshape((-1, 1, 2))
        if drawing_complete:
            overlay = frame.copy()
            cv2.fillPoly(overlay, [pts], (0, 255, 0))
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
            cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
        else:
            cv2.polylines(frame, [pts], False, (255, 255, 0), 2)

    if out_of_bounds_detected:
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 40), (0, 0, 255), -1)
        cv2.putText(frame, "ALARM: TARGET OUTSIDE SAFE ZONE!", (20, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

    cv2.imshow(window_name, frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('r'):
        polygon_pts = []
        drawing_complete = False
        outside_timers.clear()
        already_notified_instant.clear()
        already_notified_loiter.clear()
        set_alarm_state(False)
    elif key == ord('q'):
        set_alarm_state(False)
        break

cap.release()
cv2.destroyAllWindows()