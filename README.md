✋✨ GESTURE DROP – TOUCHLESS TEXT & IMAGE TRANSFER

Cross-Device Clipboard | Hand-Gesture Controls | Zero-Touch Sharing

GestureDrop is a touchless, AI-powered gesture-controlled system that lets users copy, paste, scroll, switch tabs, and transfer text/images between laptop and mobile — all using hand movements, without touching the screen or keyboard.

Built using OpenCV + MediaPipe + Flask + Web Clipboard Sync, it delivers a futuristic, seamless cross-device experience.

🚀 Key Features
🖐 Gesture-Controlled Actions

Use intuitive hand movements to interact with your system:

Scroll Up / Down

Scroll Left / Right

Switch Browser Tabs

Screenshot Capture (Thumb + Index Pinch)

Copy / Paste Command Gestures

Zero-Overlap Gesture Mode (Highly Optimized)

🔄 Real-Time Cross-Device Clipboard

Share clipboard content across devices instantly:

Copy text on laptop → appears on phone clipboard panel

View and paste text on phone

Supports multi-device pairing

🖼️ Touchless Image Transfer

Take a screenshot using hand gesture → instantly appears on phone
(content delivered as Base64 image)

📱 Mobile Web UI

A clean, minimal, phone-friendly HTML interface:

Live clipboard view (text or image)

Auto laptop IP detection

Tap to connect & sync

Works on any mobile browser (Chrome/Safari)

🎯 Highly Accurate Gesture Recognition

Built on MediaPipe Hands

Optimized landmark smoothing

Gesture overlap protection

Zero false positives

Smooth tracking under most lighting conditions

🧩 Project Structure
GestureDrop/
│
├── gesture_drop.py     # Laptop-side gesture detection & clipboard sync
├── gesture_drop_server.py     # Flask server for receiving clipboard & images
├── gesture_mobile.html        # Mobile UI for viewing/pasting clipboard
│
└── README.md                  # You are here ✨

🛠 Tech Stack
Component	Technology
Gesture Detection	Python, OpenCV, MediaPipe
Backend Sync	Flask REST API
Clipboard Access	Pyperclip / OS handlers
Mobile Interface	HTML, CSS, JavaScript
Communication	HTTP + JSON + Base64
Platform Support	Windows, Android, Linux
⚙️ How It Works
1️⃣ Start the Server
python gesture_drop_server.py

2️⃣ Run Gesture Client
python gesture_drop.py


This opens the laptop webcam and begins gesture recognition.

3️⃣ Open the Mobile UI

Open this HTML on phone:

gesture_mobile.html


Enter laptop IP → Connect → Live clipboard sync begins.

🧪 Core Gestures & Actions
Gesture	Action
✊ Fist	Scroll Up
🖐 Open Palm	Scroll Down
👉 Index Pointing	Switch Tabs
🤏 Thumb + Index Pinch	Take Screenshot
✌ Two Fingers	Copy
🤙 Rock Gesture	Paste
✋ + ✌ (Combo Protections)	No overlap false triggers
🔥 Why GestureDrop?

No Touch Needed → Perfect for hygiene-sensitive environments

Fast → Quicker than using keyboard shortcuts

Cross-Device → Works on laptop + phone combination

Lightweight → No external servers needed

Future-Proof → Expandable gesture sets

🧱 Future Enhancements

Wi-Fi Direct device auto-detection

Multi-user clipboard mesh

Gesture customization UI

Performance tuning for low-end cameras

Encrypted peer-to-peer transfer

🧑‍💻 Developer

Designed & engineered with precision for a futuristic, touchless experience.

If you like this project, ⭐ star this repo on GitHub — it motivates further updates!

📬 Contributions

 Improvements, and new gesture ideas are welcome!
