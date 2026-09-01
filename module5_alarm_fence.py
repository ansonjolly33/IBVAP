import cv2
import numpy as np
import torch
import sys
import threading
import time
from ultralytics import YOLO

# Device Selection
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"--- IBVAP: Module 5 Running on [{device.upper()}] ---")

# Load YOLO model
model = YOLO('yolov8n.pt').to(device)

polygon_pts = []
drawing_complete = False
alarm_active = False

def continuous_alarm():
    global alarm_active
    while alarm_active:
        try:
            if sys.platform == "win32":
                import winsound
                # Frequency: 2500Hz (sharp alarm tone), Duration: 150ms
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

def draw_polygon_event(event, x, y, flags, param):
    global polygon_pts, drawing_complete
    if drawing_complete:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        polygon_pts.append((x, y))
        print(f"[POINT ADDED]: ({x}, {y})")
    elif event == cv2.EVENT_RBUTTONDOWN and len(polygon_pts) >= 3:
        drawing_complete = True
        print("[FENCE LOCKED]: Perimeter active.")

cap = cv2.VideoCapture(0)
cv2.namedWindow("IBVAP - Module 5: Continuous Alarm Engine")
cv2.setMouseCallback("IBVAP - Module 5: Continuous Alarm Engine", draw_polygon_event)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.resize(frame, (800, 600))
    intrusion_detected = False

    # Classes: 0: Person, 2: Car, 3: Motorcycle, 5: Bus, 7: Truck
    results = model.track(frame, classes=[0, 2, 3, 5, 7], conf=0.30, device=device, persist=True, verbose=False)[0]

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
                if dist < 0:
                    is_inside_zone = False
                    intrusion_detected = True

            class_name = model.names[cls].upper()
            box_color = (0, 255, 0) if is_inside_zone else (0, 0, 255)
            label = f"{class_name} #{track_id} | SAFE" if is_inside_zone else f"{class_name} #{track_id} | OUTSIDE!"

            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
            cv2.circle(frame, (cx, cy), 5, (255, 255, 0), -1)
            cv2.putText(frame, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)

    set_alarm_state(intrusion_detected)

    # Polygon Rendering
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
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 40), (0, 0, 255), -1)
        cv2.putText(frame, "ALARM ACTIVE: TARGET OUTSIDE SAFE ZONE!", (20, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

    cv2.imshow("IBVAP - Module 5: Continuous Alarm Engine", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('r'):
        polygon_pts = []
        drawing_complete = False
        set_alarm_state(False)
    elif key == ord('q'):
        set_alarm_state(False)
        break

cap.release()
cv2.destroyAllWindows()