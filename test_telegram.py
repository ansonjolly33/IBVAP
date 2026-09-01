import os
import cv2
import requests

TELEGRAM_BOT_TOKEN = "8819059111:AAGhHpKuz95z9BEdGon7okWtoXqWF2rkypQ"
TELEGRAM_CHAT_ID = "1235837706"

# Create a sample test image
img_path = "test_alert.jpg"
frame = cv2.imread(cv2.samples.findFile("lena.jpg")) if os.path.exists("lena.jpg") else None

if frame is None:
    # Create dummy green image if no sample image exists
    import numpy as np
    frame = np.zeros((400, 400, 3), dtype=np.uint8)
    frame[:] = (0, 255, 0)
    cv2.putText(frame, "TEST ALERT", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

cv2.imwrite(img_path, frame)

print("Sending test photo to Telegram...")
url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

try:
    with open(img_path, 'rb') as photo:
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'caption': '🔔 TEST ALERT: Telegram Bot is fully connected!'}
        files = {'photo': photo}
        response = requests.post(url, data=payload, files=files, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")