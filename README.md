# Telor Bridge

Telor Bridge — local capture engine for automated Android screenshot collection (ADB, optional Appium).

What this repo does
- Connects to Android devices (USB/WiFi), captures single or batch screenshots, and emits images plus a session JSON.

Core tech
- Python 3.10+
- ADB (adb, adb shell)
- Optional: Appium for automated crawling
- WebSocket server for local integration (ws://localhost:7700)

Quick start (Windows)
1. `python -m venv venv`
2. `venv\\Scripts\\activate`
3. `pip install -r requirements.txt`
4. `scripts\\run.bat` or `python bridge/main.py`

Output
- Images: `output/` — Session JSON describes the capture (app id, filenames, order).

License
- MIT
