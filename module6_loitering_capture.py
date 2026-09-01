import os
import cv2
import time
import torch
import numpy as np
from ultralytics import YOLO

# Folder setup
CAPTURE_DIR = "loitering_captures"
os.makedirs(CAPTURE_DIR, exist_ok=True)

device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"--- IBVAP: Module 6 Loitering Capture on [{device.upper()}] ---")

model = YOLO('yolov8n.pt').to(device)

polygon_pts = []
drawing_complete = False

# Dictionaries to track entrance time and capture status per ID
inside_timers = {}
already_captured = set()

def draw_polygon_event(event, x, y, flags, param):
    global polygon_pts, drawing_complete
    if drawing_complete:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        polygon_pts.append((x, y))
    elif event == cv2.EVENT_RBUTTONDOWN and len(polygon_pts) >= 3:
        drawing_complete = True

cap = cv2.VideoCapture(0)
cv2.namedWindow("IBVAP - Module 6: 3s Loitering Capture Engine")
cv2.setMouseCallback("IBVAP - Module 6: 3s Loitering Capture Engine", draw_polygon_event)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.resize(frame, (800, 600))
    current_time = time.time()
    active_ids_in_frame = set()

    # Persons (0), Cars (2), Motorcycles (3), Buses (5), Trucks (7)
    results = model.track(frame, classes=[0, 2, 3, 5, 7], conf=0.30, device=device, persist=True, verbose=False)[0]

    if results.boxes is not None:
        boxes = results.boxes.xyxy.cpu().numpy()
        clss = results.boxes.cls.cpu().numpy().astype(int)
        track_ids = results.boxes.id.cpu().numpy().astype(int) if results.boxes.id is not None else range(len(boxes))

        for box, track_id, cls in zip(boxes, track_ids, clss):
            active_ids_in_frame.add(track_id)
            x1, y1, x2, y2 = map(int, box)
            cx, cy = int((x1 + x2) / 2), int(y2)

            is_inside_zone = False

            if drawing_complete and len(polygon_pts) >= 3:
                pts_array = np.array(polygon_pts, np.int32)
                dist = cv2.pointPolygonTest(pts_array, (cx, cy), False)
                if dist >= 0:
                    is_inside_zone = True

            class_name = model.names[cls].upper()

            if is_inside_zone:
                # Start tracking loiter time
                if track_id not in inside_timers:
                    inside_timers[track_id] = current_time

                elapsed_seconds = current_time - inside_timers[track_id]
                timer_text = f"INSIDE: {elapsed_seconds:.1f}s"

                # Trigger capture if inside > 3 seconds
                if elapsed_seconds >= 3.0:
                    timer_text = "LOITERING DETECTED (>3s)"
                    if track_id not in already_captured:
                        crop = frame[max(0, y1):min(600, y2), max(0, x1):min(800, x2)]
                        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
                        file_path = os.path.join(CAPTURE_DIR, f"{class_name}_ID{track_id}_{timestamp_str}.jpg")
                        
                        if crop.size > 0:
                            cv2.imwrite(file_path, crop)
                            print(f"[SNAPSHOT SAVED]: {file_path}")
                        
                        already_captured.add(track_id)

                color = (0, 255, 255) if elapsed_seconds < 3.0 else (0, 0, 255)
                label = f"{class_name} #{track_id} | {timer_text}"
            else:
                # Reset timer if target steps out
                inside_timers.pop(track_id, None)
                color = (255, 0, 0)
                label = f"{class_name} #{track_id} | OUTSIDE"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)

    # Clean up timers for objects that left the camera feed entirely
    for tid in list(inside_timers.keys()):
        if tid not in active_ids_in_frame:
            del inside_timers[tid]

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

    cv2.imshow("IBVAP - Module 6: 3s Loitering Capture Engine", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('r'):
        polygon_pts = []
        drawing_complete = False
        inside_timers.clear()
        already_captured.clear()
    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()