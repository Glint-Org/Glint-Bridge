import argparse
import os
import shutil
import sys
from pathlib import Path

from .capture import capture_screenshot, batch_capture
from .adb_usb import list_usb_devices
from .crawler import crawl_app
from .session import write_session
from .ai_config import resolve_ai_settings

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

ADB_INSTALL_GUIDE = """
Glint Bridge requires ADB (Android Debug Bridge).

Install it:
  Windows:  winget install Google.PlatformTools
  macOS:    brew install android-platform-tools
  Linux:    sudo apt install android-tools-adb

Or download directly: https://developer.android.com/tools/releases/platform-tools

After install, verify: adb version
"""


def check_adb() -> bool:
    if shutil.which("adb") is None:
        print(ADB_INSTALL_GUIDE)
        return False
    return True


def main():
    parser = argparse.ArgumentParser(prog="glint-bridge")
    parser.add_argument(
        "mode",
        nargs="?",
        default="server",
        choices=["server", "capture", "batch", "devices", "crawl", "crawl-web", "check"],
    )
    parser.add_argument("--count", type=int, default=5, help="Batch capture count")
    parser.add_argument("--app", type=str, default="Captured App", help="App name for session.json")
    parser.add_argument("--tagline", type=str, default=None, help="Tagline for session.json")
    parser.add_argument("--package", type=str, default=None, help="App package for crawl mode")
    parser.add_argument("--url", type=str, default=None, help="Start URL for crawl-web")
    parser.add_argument("--max-screens", type=int, default=20, help="Max explore steps for crawl")
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Enable intelligent crawl (requires API key in env or --ai-key)",
    )
    parser.add_argument("--no-ai", action="store_true", help="Force heuristic crawl even if a key is set")
    parser.add_argument("--ai-key", type=str, default=None, help="API key (prefer GLINT_AI_API_KEY env)")
    parser.add_argument(
        "--ai-provider",
        type=str,
        default=None,
        choices=["openai", "anthropic", "compatible"],
        help="AI provider",
    )
    parser.add_argument("--ai-model", type=str, default=None, help="Model id")

    args = parser.parse_args()

    if args.mode == "check":
        if check_adb():
            print("ADB found:", end=" ")
            import subprocess

            result = subprocess.run(["adb", "version"], capture_output=True, text=True)
            print(result.stdout.strip().splitlines()[0] if result.stdout else "unknown version")
            devices = list_usb_devices()
            print(f"Connected devices: {len(devices)}")
            for d in devices:
                print(f"  {d['serial']}  {d['model']}")
        ai_key = (
            args.ai_key
            or os.getenv("GLINT_AI_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
        )
        if ai_key:
            try:
                ai = resolve_ai_settings(use_ai=True, api_key=ai_key, provider=args.ai_provider, model=args.ai_model)
                print(f"AI: ready — {ai.provider} / {ai.model}")
            except RuntimeError as e:
                print(f"AI: not ready ({e})")
        else:
            print("AI: off (set GLINT_AI_API_KEY and use --ai for intelligent crawl)")
        sys.exit(0 if shutil.which("adb") else 1)

    if args.mode != "crawl-web" and not check_adb():
        sys.exit(1)

    use_ai = False if args.no_ai else (True if args.ai else None)

    if args.mode == "devices":
        devices = list_usb_devices()
        if not devices:
            print("No Android devices connected.")
            print("Connect a device via USB and enable USB debugging.")
            sys.exit(1)
        print(f"Found {len(devices)} device(s):")
        for d in devices:
            print(f"  {d['serial']}  {d['model']}")

    elif args.mode == "capture":
        path = capture_screenshot()
        if path:
            write_session(
                screens=[Path(path).name],
                app=args.app,
                tagline=args.tagline,
                output_dir=OUTPUT_DIR,
            )
            print(f"Saved: {path}")
            print(f"Session: {OUTPUT_DIR / 'session.json'}")
        else:
            print("Capture failed. Check that your device is connected and USB debugging is enabled.")
            sys.exit(1)

    elif args.mode == "batch":
        paths = batch_capture(count=args.count)
        if paths:
            write_session(
                screens=[Path(p).name for p in paths],
                app=args.app,
                tagline=args.tagline,
                output_dir=OUTPUT_DIR,
            )
        print(f"Captured {len(paths)} screenshot(s):")
        for p in paths:
            print(f"  {p}")
        print(f"Session: {OUTPUT_DIR / 'session.json'}")

    elif args.mode == "crawl":
        if not args.package:
            print("Error: --package is required for crawl mode")
            sys.exit(1)
        try:
            paths = crawl_app(
                args.package,
                max_screens=args.max_screens,
                use_ai=use_ai,
                ai_api_key=args.ai_key or os.getenv("GLINT_AI_API_KEY"),
                ai_provider=args.ai_provider,
                ai_model=args.ai_model,
            )
            write_session(
                screens=[Path(p).name for p in paths],
                app=args.app,
                tagline=args.tagline,
                output_dir=OUTPUT_DIR,
            )
            print(f"Crawled {len(paths)} kept screenshot(s):")
            for p in paths:
                print(f"  {p}")
            print(f"Session: {OUTPUT_DIR / 'session.json'}")
            print("Next: import output/ into Glint Web")
        except RuntimeError as e:
            print(f"Crawl failed: {e}")
            sys.exit(1)

    elif args.mode == "crawl-web":
        if not args.url:
            print("Error: --url is required for crawl-web")
            sys.exit(1)
        try:
            from .web_crawler import crawl_web

            paths = crawl_web(
                args.url,
                max_screens=args.max_screens,
                use_ai=use_ai,
                ai_api_key=args.ai_key or os.getenv("GLINT_AI_API_KEY"),
                ai_provider=args.ai_provider,
                ai_model=args.ai_model,
            )
            write_session(
                screens=[Path(p).name for p in paths],
                app=args.app,
                tagline=args.tagline,
                output_dir=OUTPUT_DIR,
            )
            print(f"Web crawl kept {len(paths)} screenshot(s):")
            for p in paths:
                print(f"  {p}")
            print(f"Session: {OUTPUT_DIR / 'session.json'}")
        except RuntimeError as e:
            print(f"Web crawl failed: {e}")
            sys.exit(1)

    else:
        from .websocket_server import run as run_ws

        run_ws()


if __name__ == "__main__":
    main()
