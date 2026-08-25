# Glint Bridge

ADB screenshot capture for **Android** devices. Part of [Glint](https://github.com/Glint-Org).

> For Flutter (Android + iOS store sizes without a device), use [Glint-Capture](../Glint-Capture).

## Install

```bash
pip install -r requirements.txt
```

Requires [ADB](https://developer.android.com/tools/releases/platform-tools):

```bash
# Linux
sudo apt install android-tools-adb
# macOS
brew install android-platform-tools
# Windows
winget install Google.PlatformTools
```

## Commands

```bash
python glint.py check      # ADB + deps
python glint.py devices    # list USB / Wi‑Fi
python glint.py capture    # one PNG → output/
python glint.py batch 5    # five PNGs + session.json
python glint.py start      # WebSocket for Glint Web
```

### Crawl (optional)

Needs Appium. Uncomment `Appium-Python-Client` in `requirements.txt`, then:

```bash
python glint.py crawl com.example.app
```

## Security (WebSocket)

- Binds to **`127.0.0.1:7700` only** (loopback)
- Prints a **pairing token** on start; Glint Web must pair before capture
- Capture responses include **`data_url`** (base64 PNG) so the browser can display shots

Never bind `0.0.0.0` in production use.

## Glint Web

1. `python glint.py start` — copy the token
2. In Web editor, paste token if prompted → Pair
3. **Capture from Device** in Assets

## License

MIT
