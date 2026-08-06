# Telor Bridge

ADB-based screenshot capture engine for Android devices. Part of the Telor ecosystem.

## Features

- USB and WiFi ADB device connection
- Single and batch screenshot capture
- Appium auto-crawl mode (optional)
- WebSocket server for Telor Web integration
- Automatic `session.json` generation for Telor Web import

## Quick Start

```bash
pip install -r requirements.txt
python -m bridge.main devices          # List connected devices
python -m bridge.main capture --app "My App"
python -m bridge.main batch --count 5
python -m bridge.main crawl --package com.example.app
python -m bridge.main server           # WebSocket on :7700
```

## Output

Screenshots and `session.json` are written to `output/`:

```
output/
├── screenshot_0001.png
├── batch_0001.png
└── session.json
```

Import the `output/` folder into Telor Web to apply templates and export store-ready assets.

## WebSocket

See [Telor-Docs/reference/websocket-protocol.md](../Telor-Docs/reference/websocket-protocol.md) for the full protocol.

## License

MIT
