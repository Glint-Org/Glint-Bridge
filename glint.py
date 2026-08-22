"""
Glint — simple CLI for screenshot capture.

Usage:
    python glint.py check          Verify ADB is installed
    python glint.py devices        List connected Android devices
    python glint.py capture        Capture one screenshot
    python glint.py batch 5        Capture 5 screenshots
    python glint.py start          Start server (connect to Glint-Web)
    python glint.py crawl com.app  Auto-crawl an app
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from bridge.main import main

ALIASES = {
    "check": "check",
    "devices": "devices",
    "ls": "devices",
    "capture": "capture",
    "screenshot": "capture",
    "snap": "capture",
    "batch": "batch",
    "multi": "batch",
    "start": "server",
    "server": "server",
    "serve": "server",
    "ws": "server",
    "crawl": "crawl",
    "auto": "crawl",
    "help": None,
}

USAGE = """
Glint Bridge — Android screenshot capture

Commands:
  python glint.py check            Check if ADB is installed
  python glint.py devices          List connected Android devices
  python glint.py capture          Capture one screenshot
  python glint.py batch 5          Capture 5 screenshots
  python glint.py start            Start WebSocket server for Glint-Web
  python glint.py crawl com.app    Auto-crawl an app (requires Appium)

Shortcuts:
  python glint.py snap    = capture
  python glint.py ls      = devices
  python glint.py multi 5 = batch 5

First time? Run: python glint.py check
"""


def resolve_command(args: list[str]) -> list[str]:
    if not args:
        print(USAGE)
        sys.exit(0)

    cmd = args[0].lower()

    if cmd in ("help", "--help", "-h"):
        print(USAGE)
        sys.exit(0)

    if cmd not in ALIASES:
        # Might be a package name for crawl mode
        if "." in cmd:
            return ["crawl", "--package", cmd] + args[1:]
        print(f"Unknown command: {cmd}")
        print(USAGE)
        sys.exit(1)

    mode = ALIASES[cmd]
    if mode is None:
        print(USAGE)
        sys.exit(0)

    remaining = args[1:]

    if mode == "batch" and remaining:
        return ["batch", "--count", remaining[0]] + remaining[1:]

    return [mode] + remaining


if __name__ == "__main__":
    sys.argv = ["glint-bridge"] + resolve_command(sys.argv[1:])
    main()
