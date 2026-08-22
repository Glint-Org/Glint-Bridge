# Glint Bridge

ADB-based screenshot capture for Android devices. Part of the [Glint](https://github.com/darkmintis/Glint-Org) ecosystem.

> **Android only.** For Flutter apps (both Android + iOS), use [Glint-Capture](../Glint-Capture) instead — no device needed.

## Requirements

- Python 3.10+
- [ADB](https://developer.android.com/tools/releases/platform-tools) (Android Debug Bridge)
- Android device with USB debugging enabled

### Install ADB

```bash
# Windows
winget install Google.PlatformTools

# macOS
brew install android-platform-tools

# Linux
sudo apt install android-tools-adb
```

### Check setup

```bash
python -m bridge.main check
```

## Quick Start

```bash
pip install -r requirements.txt

# List connected devices
python -m bridge.main devices

# Capture single screenshot
python -m bridge.main capture --app "My App"

# Capture 5 screenshots
python -m bridge.main batch --count 5

# Start WebSocket server (connects to Glint-Web)
python -m bridge.main server
```

## Output

Screenshots and `session.json` are written to `output/`:

```
output/
├── screenshot_0001.png
├── batch_0001.png
└── session.json
```

Import the `output/` folder into Glint-Web to apply templates and export store-ready assets.

## WebSocket

When running `server` mode, Bridge starts a WebSocket on `ws://localhost:7700`.

1. Start the server: `python -m bridge.main server`
2. Note the pairing token printed in the console
3. Open Glint-Web → Editor → enter the token to connect
4. Screenshots stream live to the editor

See [Glint-Docs/reference/websocket-protocol.md](../Glint-Docs/reference/websocket-protocol.md) for the full protocol.

## License

MIT
