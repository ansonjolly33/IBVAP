import cv2
import numpy as np
from ultralytics import YOLO
import sys
import threading

# --- Alarm Helper ---
alarm_playing = False

def play_alarm_sound():
    global alarm_playing
    alarm_playing = True
    try:
        if sys.platform == "win32":
            import winsound
            winsound.Beep(2000, 300)
        else:
            print('\a')
    except Exception:
        pass
    alarm_playing = False

def trigger_alarm():
    global alarm_playing
    if not alarm_playing:
        threading.Thread(target=play_alarm_sound, daemon=True).start()

# Load YOLO Model
model = YOLO('yolov8n.pt')

polygon_pts = []
drawing_complete = False

def draw_polygon(event, x, y, flags, param):
    global polygon_pts, drawing_complete
    if event == cv2.EVENT_LBUTTONDOWN and not drawing_complete:
        polygon_pts.append((x, y))
        print(f"Point added: ({x}, {y})")
    elif event == cv2.EVENT_RBUTTONDOWN and len(polygon_pts) >= 3:
        drawing_complete = True
        print("Safe zone locked!")

cap = cv2.VideoCapture(0)
cv2.namedWindow('IBVAP - Virtual Fence Intrusion')
cv2.setMouseCallback('IBVAP - Virtual Fence Intrusion', draw_polygon)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    intrusion_detected = False
    
    # Run YOLO tracking (using standard predict fallback if tracker warm-up)
    results = model.track(frame, classes=[0], conf=0.4, persist=True, verbose=False)[0]

    if results.boxes is not None:
        boxes = results.boxes.xyxy.cpu().numpy()
        
        # Get tracking IDs if available, else standard indices
        if results.boxes.id is not None:
            track_ids = results.boxes.id.cpu().numpy().astype(int)
        else:
            track_ids = list(range(len(boxes)))

        for box, track_id in zip(boxes, track_ids):
            x1, y1, x2, y2 = map(int, box)
            
            # Anchor point (bottom-center of human bounding box)
            cx, cy = int((x1 + x2) / 2), int(y2)

            is_inside_safe_zone = True
            
            if drawing_complete and len(polygon_pts) >= 3:
                pts_array = np.array(polygon_pts, np.int32)
                # Check point against polygon
                dist = cv2.pointPolygonTest(pts_array, (cx, cy), False)
                if dist >= 0:
                    is_inside_safe_zone = True
                else:
                    is_inside_safe_zone = False
                    intrusion_detected = True

            # Box Color: Green inside safe zone, Red outside (Intruder)
            box_color = (0, 255, 0) if is_inside_safe_zone else (0, 0, 255)
            label = f"ID #{track_id} SAFE" if is_inside_safe_zone else f"ID #{track_id} INTRUDER!"
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
            cv2.circle(frame, (cx, cy), 5, (255, 255, 0), -1)
            
            # Text badge
            t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            cv2.rectangle(frame, (x1, y1 - 20), (x1 + t_size[0], y1), box_color, -1)
            cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

    # Render Polygon
    if len(polygon_pts) > 0:
        pts = np.array(polygon_pts, np.int32).reshape((-1, 1, 2))
        if drawing_complete:
            zone_color = (0, 255, 0)
            overlay = frame.copy()
            cv2.fillPoly(overlay, [pts], zone_color)
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
            cv2.polylines(frame, [pts], True, zone_color, 2)
        else:
            cv2.polylines(frame, [pts], False, (255, 255, 0), 2)
            for pt in polygon_pts:
                cv2.circle(frame, pt, 4, (0, 255, 255), -1)

    # On-Screen Instructions (when polygon is not complete)
    if not drawing_complete:
        cv2.putText(frame, "Left-click: Add Points | Right-click: Lock Safe Zone | R: Reset", 
                    (10, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    # Alarm Banner
    if intrusion_detected:
        trigger_alarm()
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 45), (0, 0, 255), -1)
        cv2.putText(frame, "ALERT: PERSON OUTSIDE SAFE ZONE DETECTED!", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    cv2.imshow('IBVAP - Virtual Fence Intrusion', frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('r'):
        polygon_pts = []
        drawing_complete = False
        print("Zone reset.")

cap.release()
cv2.destroyAllWindows()