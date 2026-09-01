import cv2
import numpy as np
import torch
import sys
import threading
from ultralytics import YOLO

# 1. Device Selection (CUDA Acceleration)
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"--- IBVAP: Module 1 running on [{device.upper()}] ---")

# 2. Load Model
model = YOLO('yolov8n.pt').to(device)

# 3. Global Variables for Mouse Callback
polygon_pts = []
drawing_complete = False
alarm_playing = False

def play_alarm_sound():
    global alarm_playing
    alarm_playing = True
    try:
        if sys.platform == "win32":
            import winsound
            winsound.Beep(2000, 200)
    except Exception:
        pass
    alarm_playing = False

def trigger_alarm():
    global alarm_playing
    if not alarm_playing:
        threading.Thread(target=play_alarm_sound, daemon=True).start()

# Mouse Callback Function
def draw_polygon_event(event, x, y, flags, param):
    global polygon_pts, drawing_complete

    if drawing_complete:
        return

    # Left Click: Add Point
    if event == cv2.EVENT_LBUTTONDOWN:
        polygon_pts.append((x, y))
        print(f"[POINT ADDED]: ({x}, {y})")

    # Right Click: Lock Polygon
    elif event == cv2.EVENT_RBUTTONDOWN:
        if len(polygon_pts) >= 3:
            drawing_complete = True
            print("[FENCE LOCKED]: Perimeter active.")
        else:
            print("[WARNING]: Need at least 3 points to lock fence!")

# 4. Initialize Camera & OpenCV Window
cap = cv2.VideoCapture(0)
window_name = "IBVAP - Module 1: Virtual Fence Engine"
cv2.namedWindow(window_name)
cv2.setMouseCallback(window_name, draw_polygon_event)

print("\n--- INSTRUCTIONS ---")
print("1. LEFT-CLICK on the video window to place fence vertices.")
print("2. RIGHT-CLICK to lock and activate the fence perimeter.")
print("3. Press 'r' to reset the fence.")
print("4. Press 'q' to quit.\n")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Standardize frame resolution
    frame = cv2.resize(frame, (800, 600))
    intrusion_detected = False

    # UPDATED: Detect Persons (0) AND Vehicles (2: Car, 3: Motorcycle, 5: Bus, 7: Truck)
    results = model.track(frame, classes=[0, 2, 3, 5, 7], conf=0.35, device=device, persist=True, verbose=False)[0]

    if results.boxes is not None:
        boxes = results.boxes.xyxy.cpu().numpy()
        clss = results.boxes.cls.cpu().numpy().astype(int)
        track_ids = results.boxes.id.cpu().numpy().astype(int) if results.boxes.id is not None else range(len(boxes))

        for box, track_id, cls in zip(boxes, track_ids, clss):
            x1, y1, x2, y2 = map(int, box)
            
            # Anchor Point: Bottom Center of Bounding Box (Tire / Feet Position)
            cx, cy = int((x1 + x2) / 2), int(y2)

            is_inside_zone = True

            # Perform Exact Point-Polygon Test
            if drawing_complete and len(polygon_pts) >= 3:
                pts_array = np.array(polygon_pts, np.int32)
                dist = cv2.pointPolygonTest(pts_array, (cx, cy), False)
                
                # dist < 0 means object is OUTSIDE the green polygon
                if dist < 0:
                    is_inside_zone = False
                    intrusion_detected = True

            # Get Class Label
            class_name = model.names[cls].upper()

            # Render Bounding Boxes (Green = Safe/Inside, Red = Alert/Outside)
            box_color = (0, 255, 0) if is_inside_zone else (0, 0, 255)
            label = f"{class_name} #{track_id} | SAFE" if is_inside_zone else f"{class_name} #{track_id} | ALERT!"

            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
            cv2.circle(frame, (cx, cy), 5, (255, 255, 0), -1)

            t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            cv2.rectangle(frame, (x1, y1 - 22), (x1 + t_size[0], y1), box_color, -1)
            cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

    # Render Polygon Fence Overlay
    if len(polygon_pts) > 0:
        pts = np.array(polygon_pts, np.int32).reshape((-1, 1, 2))
        
        if drawing_complete:
            # Semi-transparent green highlight for secure zone
            overlay = frame.copy()
            cv2.fillPoly(overlay, [pts], (0, 255, 0))
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
            cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
        else:
            # Draw line segments while drafting
            cv2.polylines(frame, [pts], False, (255, 255, 0), 2)
            for pt in polygon_pts:
                cv2.circle(frame, pt, 4, (0, 255, 255), -1)

    # Intrusion Alert Banner & Audio
    if intrusion_detected:
        trigger_alarm()
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 40), (0, 0, 255), -1)
        cv2.putText(frame, "PERIMETER BREACH / OUT-OF-BOUNDS DETECTED!", (20, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

    cv2.imshow(window_name, frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('r'):
        polygon_pts = []
        drawing_complete = False
        print("[RESET]: Fence cleared.")
    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()