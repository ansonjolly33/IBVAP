import os
import cv2
import csv
import torch
import sys
import threading
from datetime import datetime
import numpy as np
from ultralytics import YOLO

# 1. Setup Storage Directories
LOG_DIR = "security_logs"
SNAPSHOT_DIR = os.path.join(LOG_DIR, "snapshots")
CSV_FILE = os.path.join(LOG_DIR, "incident_log.csv")

os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# Initialize CSV log with header if missing
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Target_ID", "Class_Name", "Snapshot_Path"])

# 2. Setup GPU Model
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"--- IBVAP: Module 4 Logger Running on [{device.upper()}] ---")

model = YOLO('yolov8n.pt').to(device)

polygon_pts = []
drawing_complete = False
logged_ids = set()  # Prevent duplicate logging for the same object
alarm_playing = False

def play_alarm():
    global alarm_playing
    alarm_playing = True
    try:
        if sys.platform == "win32":
            import winsound
            winsound.Beep(2200, 250)
    except Exception:
        pass
    alarm_playing = False

def trigger_alarm():
    global alarm_playing
    if not alarm_playing:
        threading.Thread(target=play_alarm, daemon=True).start()

def draw_polygon_event(event, x, y, flags, param):
    global polygon_pts, drawing_complete
    if drawing_complete:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        polygon_pts.append((x, y))
        print(f"[FENCE]: Vertex added ({x}, {y})")
    elif event == cv2.EVENT_RBUTTONDOWN and len(polygon_pts) >= 3:
        drawing_complete = True
        print("[FENCE]: Safe zone locked!")

cap = cv2.VideoCapture(0)
cv2.namedWindow("IBVAP Module 4 - Event Logger")
cv2.setMouseCallback("IBVAP Module 4 - Event Logger", draw_polygon_event)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.resize(frame, (800, 600))
    intrusion_detected = False

    results = model.track(frame, classes=[0, 2, 3, 5, 7], conf=0.35, device=device, persist=True, verbose=False)[0]

    if results.boxes is not None:
        boxes = results.boxes.xyxy.cpu().numpy()
        clss = results.boxes.cls.cpu().numpy().astype(int)
        track_ids = results.boxes.id.cpu().numpy().astype(int) if results.boxes.id is not None else range(len(boxes))

        for box, track_id, cls in zip(boxes, track_ids, clss):
            x1, y1, x2, y2 = map(int, box)
            cx, cy = int((x1 + x2) / 2), int(y2)

            is_inside_zone = True

            if drawing_complete and len(polygon_pts) >= 3:
                pts_array = np.array(polygon_pts, np.int32)
                dist = cv2.pointPolygonTest(pts_array, (cx, cy), False)
                
                # Out of bounds breach
                if dist < 0:
                    is_inside_zone = False
                    intrusion_detected = True

                    # LOG BREACH ONCE PER TARGET ID
                    if track_id not in logged_ids:
                        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                        class_name = model.names[cls].upper()
                        
                        # Save cropped snapshot of intruder
                        crop = frame[max(0, y1):min(600, y2), max(0, x1):min(800, x2)]
                        snap_filename = f"INCIDENT_{class_name}_ID{track_id}_{timestamp}.jpg"
                        snap_path = os.path.join(SNAPSHOT_DIR, snap_filename)
                        
                        if crop.size > 0:
                            cv2.imwrite(snap_path, crop)

                        # Write metadata row to CSV
                        with open(CSV_FILE, mode='a', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow([timestamp, track_id, class_name, snap_path])

                        print(f"[LOG STORED]: {class_name} ID #{track_id} saved to {snap_filename}")
                        logged_ids.add(track_id)

            class_name = model.names[cls].upper()
            color = (0, 255, 0) if is_inside_zone else (0, 0, 255)
            label = f"{class_name} #{track_id}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # Fence Visualization
    if len(polygon_pts) > 0:
        pts = np.array(polygon_pts, np.int32).reshape((-1, 1, 2))
        if drawing_complete:
            overlay = frame.copy()
            cv2.fillPoly(overlay, [pts], (0, 255, 0))
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
            cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
        else:
            cv2.polylines(frame, [pts], False, (255, 255, 0), 2)

    if intrusion_detected:
        trigger_alarm()

    cv2.imshow("IBVAP Module 4 - Event Logger", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('r'):
        polygon_pts = []
        drawing_complete = False
        logged_ids.clear()
        print("[RESET]: Safe zone cleared.")
    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()