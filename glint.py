"""
Glint - simple CLI for screenshot capture.

Usage:
    python glint.py check          Verify ADB is installed
    python glint.py devices        List connected Android devices
    python glint.py capture        Capture one screenshot
    python glint.py batch 5        Capture 5 screenshots
    python glint.py start          Start server (connect to Glint-Web)
    python glint.py crawl com.app  Auto-crawl an app
    python glint.py crawl com.app --ai
    python glint.py crawl-web https://example.com --ai
    python glint.py inspect --template blink
    python glint.py inspect --pack project.glint
    python glint.py extract-theme output/
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
    "crawl-web": "crawl-web",
    "web": "crawl-web",
    "inspect": "inspect",
    "extract-theme": "extract-theme",
    "theme": "extract-theme",
    "help": None,
}

USAGE = """
Glint Bridge - Android / web screenshot capture

Commands:
  python glint.py check                 Check ADB (+ AI key status)
  python glint.py devices               List connected Android devices
  python glint.py capture               Capture one screenshot
  python glint.py batch 5               Capture 5 screenshots
  python glint.py start                 WebSocket server for Glint-Web
  python glint.py crawl com.app         Heuristic Appium crawl
  python glint.py crawl com.app --ai    Intelligent crawl (your API key)
  python glint.py crawl-web URL --ai    Intelligent web crawl (Playwright)
  python glint.py inspect --template blink   Template palette + headlines (JSON)
  python glint.py inspect --pack file.glint  Read exported .glint project
  python glint.py extract-theme output/      Dominant colors from screenshots
  python glint.py theme output/ --template blink   Map colors to template slots

AI (local-first, your key):
  export GLINT_AI_API_KEY=sk-...
  # or OPENAI_API_KEY / ANTHROPIC_API_KEY
  # optional: GLINT_AI_PROVIDER=openai|anthropic|compatible
  #           GLINT_AI_MODEL=gpt-4o-mini
  #           GLINT_AI_BASE_URL=https://...   # compatible endpoints

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
        if "." in cmd and not cmd.startswith("http"):
            return ["crawl", "--package", cmd] + args[1:]
        if cmd.startswith("http://") or cmd.startswith("https://"):
            return ["crawl-web", "--url", cmd] + args[1:]
        print(f"Unknown command: {cmd}")
        print(USAGE)
        sys.exit(1)

    mode = ALIASES[cmd]
    if mode is None:
        print(USAGE)
        sys.exit(0)

    remaining = args[1:]

    if mode == "batch" and remaining and not remaining[0].startswith("-"):
        return ["batch", "--count", remaining[0]] + remaining[1:]

    if mode == "crawl" and remaining and not remaining[0].startswith("-"):
        return ["crawl", "--package", remaining[0]] + remaining[1:]

    if mode == "crawl-web" and remaining and not remaining[0].startswith("-"):
        return ["crawl-web", "--url", remaining[0]] + remaining[1:]

    return [mode] + remaining


if __name__ == "__main__":
    sys.argv = ["glint-bridge"] + resolve_command(sys.argv[1:])
    main()
