# gesture_drop.py
"""
GestureDrop single-file final:
- Runs Flask server endpoints: /get_clipboard, /ip
- Runs camera-based gestures: scroll up/down, tab switch left/right, copy (fist), paste (open palm), screenshot (thumb+index pinch)
- Laptop -> Phone clipboard sync (phone cannot upload to laptop)
- Improved gesture smoothing & stability
"""

import os
import time
import socket
import threading
import base64
import io
import sys

# --- third-party libs ---
import cv2
import numpy as np
import pyautogui
import pyperclip
from flask import Flask, jsonify, request
import mediapipe as mp

# ------------- CONFIG -------------
CAMERA_INDEX = 0
SMOOTHING_WINDOW = 6          # number of recent points for smoothing
EMA_ALPHA = 0.25              # exponential moving average weight (for smoothing dx/dy)
SCROLL_THRESHOLD = 0.06       # vertical motion threshold (lower = more sensitive)
TAB_THRESHOLD = 0.09          # horizontal motion threshold
COOLDOWN = 0.9                # seconds between recognized motion actions
GESTURE_HOLD_TIME = 0.45      # sec to hold fist/open to confirm copy/paste
SCREENSHOT_COOLDOWN = 2.5     # sec between screenshots
OVERLAY_LABEL_TIME = 1.6      # seconds to display gesture label on screen

# ------------- SHARED STATE -------------
shared_clipboard = {'type': 'empty', 'value': ''}   # laptop -> phone only
last_action_time = 0.0

# smoothing trackers
pos_history = []   # list of (x,y) last points (index tip)
ema_dx = 0.0
ema_dy = 0.0

# gesture state
fist_start = None
open_start = None
copy_confirmed = False
last_screenshot_time = 0.0
gesture_label = "None"
label_set_time = 0.0

# ------------- FLASK (server endpoints only GET) -------------
app = Flask(__name__)

@app.route('/get_clipboard', methods=['GET'])
def api_get_clipboard():
    # returns {"type":"text"/"image"/"empty", "value": "<text>" or base64 image string}
    return jsonify({"type": shared_clipboard.get("type","empty"), "value": shared_clipboard.get("value","")})

@app.route('/ip', methods=['GET'])
def api_ip():
    return jsonify({"ip": get_local_ip()})

# purposely DO NOT implement upload endpoints (phone->laptop disabled)

def run_server():
    # run flask server
    # Note: If firewall blocks, allow python through firewall
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# ------------- UTIL -------------
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def safe_copy_to_shared(text):
    global shared_clipboard
    if not text:
        return
    shared_clipboard['type'] = 'text'
    shared_clipboard['value'] = text

def safe_set_local_clipboard(text):
    try:
        pyperclip.copy(text)
    except Exception as e:
        print("[WARN] pyperclip.copy failed:", e)

# ------------- MEDIA PIPE INIT -------------
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.6)

# ------------- GESTURE HELPERS -------------
def finger_states_from_landmarks(lm):
    # returns list of five ints 1=open, 0=closed (thumb,index,middle,ring,pinky)
    tips = [4,8,12,16,20]
    fingers = []
    try:
        # thumb: compare x to its lower joint (works for front camera mirrored)
        fingers.append(1 if lm.landmark[tips[0]].x < lm.landmark[tips[0]-2].x else 0)
    except:
        fingers.append(0)
    for i in range(1,5):
        try:
            fingers.append(1 if lm.landmark[tips[i]].y < lm.landmark[tips[i]-2].y else 0)
        except:
            fingers.append(0)
    return fingers

def update_motion_and_detect(dx, dy):
    # uses EMA smoothing to reduce jitter and detect motion gestures
    global ema_dx, ema_dy, last_action_time, gesture_label, label_set_time
    ema_dx = (EMA_ALPHA * dx) + (1 - EMA_ALPHA) * ema_dx
    ema_dy = (EMA_ALPHA * dy) + (1 - EMA_ALPHA) * ema_dy

    now = time.time()
    if now - last_action_time < COOLDOWN:
        return None

    # Use magnitude of EMA values for decisions
    abs_dx = abs(ema_dx)
    abs_dy = abs(ema_dy)

    # vertical scroll
    if abs_dy > SCROLL_THRESHOLD and abs_dy > abs_dx:
        if ema_dy < 0:
            pyautogui.scroll(1200)   # scroll up
            gesture_label = "Scroll Up"
        else:
            pyautogui.scroll(-1200)  # scroll down
            gesture_label = "Scroll Down"
        label_set_time = now
        last_action_time = now
        return gesture_label

    # horizontal -> tab switch
    if abs_dx > TAB_THRESHOLD and abs_dx > abs_dy:
        if ema_dx > 0:
            pyautogui.hotkey('ctrl', 'tab')
            gesture_label = "Next Tab"
        else:
            pyautogui.hotkey('ctrl', 'shift', 'tab')
            gesture_label = "Previous Tab"
        label_set_time = now
        last_action_time = now
        return gesture_label

    return None

# ------------- MAIN (camera loop) -------------
def main_loop():
    global pos_history, ema_dx, ema_dy, fist_start, open_start, copy_confirmed
    global last_screenshot_time, gesture_label, label_set_time

    local_ip = get_local_ip()
    print("\nGestureDrop running. Phone UI: http://{}:5000 (open mobile HTML and press Connect)".format(local_ip))
    print("Press 'q' in camera window to quit.")

    # start server thread
    threading.Thread(target=run_server, daemon=True).start()

    # ensure screenshots dir
    os.makedirs("screenshots", exist_ok=True)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("[ERROR] Cannot open camera.")
        return

    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.05)
            continue

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        if results.multi_hand_landmarks:
            lm = results.multi_hand_landmarks[0]
            mp_drawing.draw_landmarks(frame, lm, mp_hands.HAND_CONNECTIONS)

            idx = lm.landmark[8]
            th = lm.landmark[4]
            x, y = float(idx.x), float(idx.y)

            # update position history and compute dx,dy over window
            pos_history.append((x,y))
            if len(pos_history) > SMOOTHING_WINDOW:
                pos_history.pop(0)

            if len(pos_history) >= 2:
                dx = pos_history[-1][0] - pos_history[0][0]
                dy = pos_history[-1][1] - pos_history[0][1]
            else:
                dx = dy = 0.0

            # detect motion gestures using EMA smoothing
            g = update_motion_and_detect(dx, dy)
            # label will be set inside update_motion_and_detect

            # finger states
            fingers = finger_states_from_landmarks(lm)
            total_f = sum(fingers)
            now = time.time()

            # COPY gesture: fist (all fingers closed)
            if total_f == 0:
                if fist_start is None:
                    fist_start = now
                elif (now - fist_start) > GESTURE_HOLD_TIME and not copy_confirmed:
                    # execute copy and sync
                    try:
                        pyautogui.hotkey('ctrl', 'c')
                        time.sleep(0.18)
                        text = ""
                        try:
                            text = pyperclip.paste()
                        except Exception as e:
                            print("[WARN] pyperclip.paste failed:", e)
                        if text:
                            safe_copy_to_shared(text)
                            print("[INFO] Copied & synced (len={}): {}".format(len(text), repr(text[:80])))
                        else:
                            print("[INFO] Copy gesture detected but clipboard empty or non-text")
                        gesture_label = "Copy"
                        label_set_time = now
                        copy_confirmed = True
                    except Exception as e:
                        print("[ERROR] Copy action failed:", e)
                    fist_start = None
            else:
                fist_start = None

            # PASTE gesture: open palm (all fingers open)
            if total_f == 5:
                if open_start is None:
                    open_start = now
                elif (now - open_start) > GESTURE_HOLD_TIME and copy_confirmed:
                    try:
                        # place shared text into OS clipboard before paste
                        if shared_clipboard.get('type') == 'text' and shared_clipboard.get('value'):
                            safe_set_local_clipboard(shared_clipboard['value'])
                        pyautogui.hotkey('ctrl', 'v')
                        gesture_label = "Paste"
                        label_set_time = now
                        print("[INFO] Performed paste of shared clipboard")
                        copy_confirmed = False
                    except Exception as e:
                        print("[ERROR] Paste failed:", e)
                    open_start = None
            else:
                open_start = None

            # Screenshot gesture: thumb+index pinch (thumb open, index open, others closed) and small distance
            if fingers[0] == 1 and fingers[1] == 1 and sum(fingers[2:]) == 0:
                pinch_dist = np.linalg.norm(np.array([th.x, th.y]) - np.array([idx.x, idx.y]))
                if pinch_dist < 0.05 and (now - last_screenshot_time) > SCREENSHOT_COOLDOWN:
                    try:
                        fname = os.path.join("screenshots", f"screenshot_{int(time.time())}.png")
                        pyautogui.screenshot(fname)
                        with open(fname, "rb") as f:
                            b = f.read()
                            shared_clipboard['type'] = 'image'
                            shared_clipboard['value'] = base64.b64encode(b).decode('utf-8')
                        gesture_label = "Screenshot"
                        label_set_time = now
                        last_screenshot_time = now
                        print("[INFO] Screenshot saved & synced:", fname)
                    except Exception as e:
                        print("[ERROR] Screenshot action failed:", e)

        else:
            # no hand
            pos_history.clear()
            # reset interim starts but keep copy_confirmed until used
            fist_start = None
            open_start = None

        # overlay label and server IP
        now = time.time()
        if now - label_set_time < OVERLAY_LABEL_TIME:
            cv2.putText(frame, gesture_label, (20,50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)
        else:
            cv2.putText(frame, "Gesture: None", (20,50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (150,150,150), 2)

        info = f"Server: http://{get_local_ip()}:5000"
        cv2.putText(frame, info, (20, frame.shape[0]-20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)

        cv2.imshow("GestureDrop – Cross-device", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Exiting GestureDrop.")

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting.")
        try: sys.exit(0)
        except: pass
