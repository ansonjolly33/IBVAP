import cv2
import numpy as np
import easyocr
import torch

class PrecisionANPR:
    def __init__(self):
        use_gpu = torch.cuda.is_available()
        print(f"[ANPR ENGINE]: Initializing Precision Reader (GPU={use_gpu})...")
        self.reader = easyocr.Reader(['en'], gpu=use_gpu)

    def locate_and_crop_plate(self, vehicle_crop):
        """Uses OpenCV Canny edge detection & contours to extract the exact 4-corner plate polygon."""
        if vehicle_crop is None or vehicle_crop.size == 0:
            return None

        h, w = vehicle_crop.shape[:2]
        gray = cv2.cvtColor(vehicle_crop, cv2.COLOR_BGR2GRAY)
        
        # Noise reduction while keeping plate character edges sharp
        bfilter = cv2.bilateralFilter(gray, 11, 17, 17)
        edged = cv2.Canny(bfilter, 30, 200)

        # Search for top rectangular contours
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

        location = None
        for contour in contours:
            approx = cv2.approxPolyDP(contour, 10, True)
            if len(approx) == 4:
                location = approx
                break

        if location is not None:
            mask = np.zeros(gray.shape, np.uint8)
            cv2.drawContours(mask, [location], 0, 255, -1)
            (x_pts, y_pts) = np.where(mask == 255)
            if len(x_pts) > 0 and len(y_pts) > 0:
                (y1, x1) = (np.min(x_pts), np.min(y_pts))
                (y2, x2) = (np.max(x_pts), np.max(y_pts))
                plate_crop = vehicle_crop[y1:y2+1, x1:x2+1]
                if plate_crop.size > 0:
                    return plate_crop

        # Fallback: Crop bottom-center region of vehicle box where plates typically sit
        return vehicle_crop[int(h * 0.55):h, int(w * 0.10):int(w * 0.90)]

    def preprocess_for_ocr(self, plate_crop):
        """Upscales and applies contrast binarization for clean OCR recognition."""
        if plate_crop is None or plate_crop.size == 0:
            return None

        h, w = plate_crop.shape[:2]
        if w < 200:
            scale = 220.0 / w
            plate_crop = cv2.resize(plate_crop, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        contrast = clahe.apply(gray)
        _, thresh = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresh

    def scan_vehicle(self, vehicle_crop):
        """Extracts license plate crop and recognized text string."""
        if vehicle_crop is None or vehicle_crop.size == 0:
            return "", None

        plate_crop = self.locate_and_crop_plate(vehicle_crop)
        if plate_crop is None or plate_crop.size == 0:
            plate_crop = vehicle_crop

        processed = self.preprocess_for_ocr(plate_crop)

        # Run EasyOCR with strict alphanumeric filter
        results = self.reader.readtext(processed, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
        if not results:
            results = self.reader.readtext(plate_crop, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')

        best_text = ""
        max_prob = 0.0

        for bbox, text, prob in results:
            clean_text = "".join(e for e in text if e.isalnum()).upper()
            if prob > max_prob and 3 <= len(clean_text) <= 10:
                max_prob = prob
                best_text = clean_text

        return best_text, plate_crop