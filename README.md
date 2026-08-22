# Glint Bridge

ADB-based screenshot capture for Android devices. Part of the [Glint](https://github.com/darkmintis/Glint-Org) ecosystem.

> **Android only.** For Flutter apps (both Android + iOS), use [Glint-Capture](../Glint-Capture) instead.

## Install

```bash
pip install -r requirements.txt
```

Also requires [ADB](https://developer.android.com/tools/releases/platform-tools):

```bash
# Windows
winget install Google.PlatformTools

# macOS
brew install android-platform-tools

# Linux
sudo apt install android-tools-adb
```

## Commands

```bash
# First time — check everything works
python glint.py check

# List connected devices
python glint.py devices

# Capture one screenshot
python glint.py capture

# Capture 5 screenshots
python glint.py batch 5

# Start server (connect to Glint-Web)
python glint.py start

# Auto-crawl an app
python glint.py crawl com.example.app
```

### Shortcuts

```bash
python glint.py snap      # same as capture
python glint.py ls        # same as devices
python glint.py multi 5   # same as batch 5
```

## How It Works

1. Connect your Android phone via USB
2. Run `python glint.py start`
3. Note the pairing token in the console
4. Open Glint-Web → enter the token
5. Screenshots stream live to the editor

## Output

```
output/
├── screenshot_0001.png
├── batch_0001.png
└── session.json
```

Import `output/` into [Glint-Web](../Glint-Web) to apply templates and export.

## License

MIT
