import cv2
import torch
import numpy as np
import easyocr
from ultralytics import YOLO

# 1. Select GPU (CUDA) if available, otherwise fall back to CPU
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"--- IBVAP: Running inference pipeline on [{device.upper()}] ---")

# 2. Load YOLO model and send it to the GPU device
yolo_model = YOLO('yolov8n.pt').to(device)

# 3. Initialize EasyOCR with GPU acceleration
use_gpu = True if device == 'cuda' else False
ocr_reader = easyocr.Reader(['en'], gpu=use_gpu)

cap = cv2.VideoCapture(0)

print("Press 'q' to exit.")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # 1. PERSON & FACE DETECTION (COCO Class 0) on GPU
    person_results = yolo_model(frame, classes=[0], conf=0.5, device=device, verbose=False)[0]

    for box in person_results.boxes:
        px1, py1, px2, py2 = map(int, box.xyxy[0])
        
        # Upper 35% bounding region for Face
        head_height = int((py2 - py1) * 0.35)
        fx1, fy1, fx2, fy2 = px1, py1, px2, py1 + head_height

        # Render overlays
        cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 255, 0), 2)
        cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), (255, 0, 0), 2)
        
        cv2.rectangle(frame, (fx1, fy1 - 20), (fx1 + 110, fy1), (255, 0, 0), -1)
        cv2.putText(frame, "FACE REGION", (fx1 + 5, fy1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    # 2. VEHICLE & ANPR DETECTION (COCO Classes: 2, 3, 5, 7) on GPU
    vehicle_results = yolo_model(frame, classes=[2, 3, 5, 7], conf=0.4, device=device, verbose=False)[0]

    for box in vehicle_results.boxes:
        vx1, vy1, vx2, vy2 = map(int, box.xyxy[0])
        vehicle_roi = frame[vy1:vy2, vx1:vx2]
        
        if vehicle_roi.size > 0:
            # EasyOCR execution on GPU
            ocr_results = ocr_reader.readtext(vehicle_roi)
            plate_text = ""
            for res in ocr_results:
                text = res[1].strip()
                if len(text) >= 4 and any(c.isdigit() for c in text):
                    plate_text = text
                    break

            cv2.rectangle(frame, (vx1, vy1), (vx2, vy2), (0, 255, 255), 2)
            label = f"VEHICLE | PLATE: {plate_text}" if plate_text else "VEHICLE DETECTED"
            cv2.rectangle(frame, (vx1, vy1 - 25), (vx1 + 220, vy1), (0, 255, 255), -1)
            cv2.putText(frame, label, (vx1 + 5, vy1 - 7),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)

    # Status Banner
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 35), (40, 40, 40), -1)
    cv2.putText(frame, f"IBVAP - MODULE 2 (HARDWARE ACCELERATION: {device.upper()})", (15, 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0) if device == 'cuda' else (0, 165, 255), 2)

    cv2.imshow('IBVAP - FRS & ANPR (GPU Mode)', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()