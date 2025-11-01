import cv2
import numpy as np
from pynput.keyboard import Controller, Key
import time

keyboard = Controller()

cap = cv2.VideoCapture(0)

# Read two initial frames for comparison
ret, frame1 = cap.read()
ret, frame2 = cap.read()

prev_x = None
movement_cooldown = 1  # seconds
last_action_time = time.time()

while cap.isOpened():
    diff = cv2.absdiff(frame1, frame2)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    _, thresh = cv2.threshold(blur, 20, 255, cv2.THRESH_BINARY)
    dilated = cv2.dilate(thresh, None, iterations=3)
    contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        if cv2.contourArea(contour) < 2000:
            continue
        (x, y, w, h) = cv2.boundingRect(contour)
        cx = x + w // 2  # Center X of the motion
        cy = y + h // 2
        cv2.rectangle(frame1, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.circle(frame1, (cx, cy), 5, (0, 0, 255), -1)

        # Detect direction of movement
        if prev_x is not None and (time.time() - last_action_time > movement_cooldown):
            if prev_x - cx > 80:
                print("Left movement detected → Pressing Left Arrow")
                keyboard.press(Key.left)
                keyboard.release(Key.left)
                last_action_time = time.time()
            elif cx - prev_x > 80:
                print("Right movement detected → Pressing Right Arrow")
                keyboard.press(Key.right)
                keyboard.release(Key.right)
                last_action_time = time.time()
        prev_x = cx

    cv2.imshow("Motion Tracking", frame1)
    frame1 = frame2
    ret, frame2 = cap.read()

    if cv2.waitKey(10) & 0xFF == 27:  # ESC to exit
        break

cap.release()
cv2.destroyAllWindows()
