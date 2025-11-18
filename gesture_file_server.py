# gesture_server_with_clipboard.py
import cv2
import mediapipe as mp
import pyautogui
import time
import numpy as np
import socket
from flask import Flask, jsonify, request
import threading
import base64
import pyperclip
import os

# ==== CONFIG ====
CAMERA_INDEX = 0
SCROLL_THRESHOLD = 0.08
TAB_THRESHOLD = 0.10
COOLDOWN = 1.0
SMOOTHING_WINDOW = 4
GESTURE_HOLD_TIME = 0.5
SCREENSHOT_COOLDOWN = 3.0

# ==== INIT MEDIA PIPE ====
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.6)

# ==== SHARED CLIPBOARD (single item: text OR image base64) ====
shared_clipboard = {
    "type": "empty",   # "text" | "image" | "empty"
    "value": ""        # text or base64-encoded png string
}

# ==== FLASK APP ====
app = Flask(__name__)

@app.route("/get_clipboard", methods=["GET"])
def get_clipboard():
    # Return unified clipboard object
    return jsonify({"type": shared_clipboard["type"], "value": shared_clipboard["value"]})

@app.route("/upload_clipboard", methods=["POST"])
def upload_clipboard():
    """
    Accept either:
    - JSON { "text": "..." }
    - multipart form with file field name 'image'
    """
    # Try JSON text
    if request.is_json:
        data = request.get_json()
        text = data.get("text")
        if text is not None:
            shared_clipboard["type"] = "text"
            shared_clipboard["value"] = text
            print("[INFO] Uploaded text from phone (len={}):".format(len(text)))
            return jsonify({"status": "ok", "type": "text"})
    # Try file upload (image)
    if 'image' in request.files:
        f = request.files['image']
        img_bytes = f.read()
        try:
            b64 = base64.b64encode(img_bytes).decode('utf-8')
            shared_clipboard["type"] = "image"
            shared_clipboard["value"] = b64
            print("[INFO] Uploaded image from phone (size={} bytes)".format(len(img_bytes)))
            return jsonify({"status": "ok", "type": "image"})
        except Exception as e:
            print("[ERROR] Image encode failed:", e)
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "error", "message": "No valid payload"}), 400

@app.route("/ip", methods=["GET"])
def get_ip():
    # Return local IP for mobile UI convenience
    ip = get_local_ip()
    return jsonify({"ip": ip})

def run_server():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


# ==== UTILS ====
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

# ==== GESTURE DETECTION HELPERS ====
last_action_time = 0
x_history, y_history = [], []
gesture_text = "None"
fist_start_time = None
open_start_time = None
copy_done = False
last_screenshot_time = 0

def get_finger_states(hand_landmarks):
    tips = [4, 8, 12, 16, 20]
    fingers = []
    try:
        fingers.append(1 if hand_landmarks.landmark[tips[0]].x < hand_landmarks.landmark[tips[0]-2].x else 0)
    except:
        fingers.append(0)
    for i in range(1,5):
        try:
            fingers.append(1 if hand_landmarks.landmark[tips[i]].y < hand_landmarks.landmark[tips[i]-2].y else 0)
        except:
            fingers.append(0)
    return fingers

def detect_motion_gesture(x, y):
    global x_history, y_history, last_action_time, gesture_text
    x_history.append(x)
    y_history.append(y)
    if len(x_history) > SMOOTHING_WINDOW:
        x_history.pop(0); y_history.pop(0)

    dx = x_history[-1] - x_history[0]
    dy = y_history[-1] - y_history[0]
    now = time.time()

    if now - last_action_time > COOLDOWN:
        if abs(dy) > SCROLL_THRESHOLD and abs(dy) > abs(dx):
            if dy < 0:
                pyautogui.scroll(1500); gesture_text = "Gesture Detected: Scroll Up"
            else:
                pyautogui.scroll(-1500); gesture_text = "Gesture Detected: Scroll Down"
            last_action_time = now
            return
        if abs(dx) > TAB_THRESHOLD and abs(dx) > abs(dy):
            if dx > 0:
                pyautogui.hotkey("ctrl", "tab"); gesture_text = "Gesture Detected: Next Tab"
            else:
                pyautogui.hotkey("ctrl", "shift", "tab"); gesture_text = "Gesture Detected: Previous Tab"
            last_action_time = now
            return

# ==== MAIN LOOP ====
def main():
    global gesture_text, fist_start_time, open_start_time, copy_done, shared_clipboard, last_screenshot_time

    # show local IP
    ip = get_local_ip()
    print("\n🌐 Open this on your phone (mobile HTML or API): http://{}:5000".format(ip))

    # start flask server in background
    threading.Thread(target=run_server, daemon=True).start()

    # ensure screenshots folder
    os.makedirs("screenshots", exist_ok=True)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("[ERROR] Cannot open camera")
        return

    print("🖐 Gesture Control Active: Scroll + Tabs + CopyPaste + Screenshot + Cross-Device")

    label_display_time = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        if results.multi_hand_landmarks:
            hand = results.multi_hand_landmarks[0]
            mp_drawing.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)

            index_tip = hand.landmark[8]
            thumb_tip = hand.landmark[4]
            x, y = index_tip.x, index_tip.y

            fingers = get_finger_states(hand)
            total_fingers = sum(fingers)
            now = time.time()

            # ---- COPY (fist) ----
            if total_fingers == 0:
                if fist_start_time is None:
                    fist_start_time = now
                elif now - fist_start_time > GESTURE_HOLD_TIME and not copy_done:
                    try:
                        pyautogui.hotkey("ctrl", "c")
                        time.sleep(0.18)  # wait for clipboard to update
                        txt = ""
                        try:
                            txt = pyperclip.paste()
                        except Exception as e:
                            print("[WARN] pyperclip paste failed:", e)
                        if txt:
                            shared_clipboard["type"] = "text"
                            shared_clipboard["value"] = txt
                        else:
                            # if nothing in clipboard, keep previous
                            shared_clipboard["type"] = shared_clipboard.get("type","empty")
                        gesture_text = "Gesture Detected: Copy (synced)"
                        label_display_time = now
                        print("[INFO] Copied and synced (len={}): {}".format(len(txt), repr(txt[:80])))
                        copy_done = True
                    except Exception as e:
                        print("[ERROR] Copy action failed:", e)
                    fist_start_time = None
            else:
                fist_start_time = None

            # ---- PASTE (open palm) ----
            if total_fingers == 5:
                if open_start_time is None:
                    open_start_time = now
                elif now - open_start_time > GESTURE_HOLD_TIME and copy_done:
                    try:
                        # place shared text into local clipboard before pasting
                        if shared_clipboard["type"] == "text" and shared_clipboard["value"]:
                            try:
                                pyperclip.copy(shared_clipboard["value"])
                            except Exception as e:
                                print("[WARN] pyperclip copy failed:", e)
                        pyautogui.hotkey("ctrl", "v")
                        gesture_text = "Gesture Detected: Paste"
                        label_display_time = now
                        print("[INFO] Pasted shared clipboard")
                        copy_done = False
                    except Exception as e:
                        print("[ERROR] Paste failed:", e)
                    open_start_time = None
            else:
                open_start_time = None

            # ---- SCREENSHOT (thumb+index pinch) ----
            thumb_index_distance = np.linalg.norm(np.array([thumb_tip.x, thumb_tip.y]) - np.array([index_tip.x, index_tip.y]))
            if fingers[0] == 1 and fingers[1] == 1 and sum(fingers[2:]) == 0:
                if thumb_index_distance < 0.05 and (now - last_screenshot_time) > SCREENSHOT_COOLDOWN:
                    filename = os.path.join("screenshots", f"screenshot_{int(time.time())}.png")
                    try:
                        pyautogui.screenshot(filename)
                        with open(filename, "rb") as f:
                            b = f.read()
                            b64 = base64.b64encode(b).decode("utf-8")
                            shared_clipboard["type"] = "image"
                            shared_clipboard["value"] = b64
                        gesture_text = f"Gesture Detected: Screenshot Saved ({os.path.basename(filename)})"
                        label_display_time = now
                        last_screenshot_time = now
                        print("[INFO] Screenshot saved and synced:", filename)
                    except Exception as e:
                        print("[ERROR] Screenshot/save failed:", e)

            # ---- Motion gestures ----
            detect_motion_gesture(x, y)

        # show label for short time
        if time.time() - label_display_time < 2:
            cv2.putText(frame, gesture_text, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
        else:
            cv2.putText(frame, "Gesture: None", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (150,150,150), 2)

        cv2.imshow("GestureDrop – Cross-Device Control", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
