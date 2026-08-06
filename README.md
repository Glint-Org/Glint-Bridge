# Telor Bridge

Local capture engine that connects to Android devices via ADB (USB/WiFi), captures screenshots, and streams them to [Telor Web](https://github.com/Telor-Org/Telor-Web) over WebSocket.

## Features

- **Device connection** — USB and WiFi ADB (auto-detect connected devices)
- **Single & batch capture** — grab one screenshot or a sequence
- **Auto-crawl** (optional) — Appium-driven screen navigation with sequential capture
- **WebSocket server** — streams screenshots to Telor Web at `ws://localhost:7700`
- **Metadata JSON** — each session produces a structured manifest

## Quick Start

```bash
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt

# Start server mode
python -m bridge.main

# List connected devices
python -m bridge.main devices

# Single capture
python -m bridge.main capture

# Batch capture (10 screenshots)
python -m bridge.main batch --count 10
```

## WebSocket API

| Action | Payload | Response |
|--------|---------|----------|
| `capture_single` | `{}` | `{ "type": "screenshot", "path": "..." }` |
| `capture_batch` | `{ "count": 5 }` | `{ "type": "batch_result", "paths": [...] }` |
| `list_devices` | `{}` | `{ "type": "devices", "usb": [...], "wifi": [...] }` |
| `connect_wifi` | `{ "ip": "...", "port": 5555 }` | `{ "type": "connect_result", "success": bool }` |

## Requirements

- Python 3.10+
- Android Debug Bridge (ADB) — included in Android SDK Platform Tools
- Appium (optional, for crawl mode) — `pip install Appium-Python-Client`

## Output

Captured images go to `output/`. A session JSON is generated alongside:

```json
{
  "app": "com.example.app",
  "screens": ["home.png", "profile.png"]
}
```

## License

MIT
