import argparse
import sys

from .websocket_server import run as run_ws
from .capture import capture_screenshot, batch_capture
from .adb_usb import list_usb_devices
from .crawler import crawl_app
from .session import write_session, load_session
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def main():
    parser = argparse.ArgumentParser(prog="telor-bridge")
    parser.add_argument("mode", nargs="?", default="server",
                        choices=["server", "capture", "batch", "devices", "crawl"])
    parser.add_argument("--count", type=int, default=5, help="Batch capture count")
    parser.add_argument("--app", type=str, default="Captured App", help="App name for session.json")
    parser.add_argument("--tagline", type=str, default=None, help="Tagline for session.json")
    parser.add_argument("--package", type=str, default=None, help="App package for crawl mode")
    parser.add_argument("--max-screens", type=int, default=20, help="Max screens for crawl mode")

    args = parser.parse_args()

    if args.mode == "devices":
        devices = list_usb_devices()
        if not devices:
            print("No devices connected.")
            sys.exit(1)
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
            print("Capture failed.")
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
        print(f"Captured {len(paths)} screenshots:")
        for p in paths:
            print(f"  {p}")
        print(f"Session: {OUTPUT_DIR / 'session.json'}")

    elif args.mode == "crawl":
        if not args.package:
            print("Error: --package is required for crawl mode")
            sys.exit(1)
        try:
            paths = crawl_app(args.package, max_screens=args.max_screens)
            write_session(
                screens=[Path(p).name for p in paths],
                app=args.app,
                tagline=args.tagline,
                output_dir=OUTPUT_DIR,
            )
            print(f"Crawled {len(paths)} screenshots:")
            for p in paths:
                print(f"  {p}")
            print(f"Session: {OUTPUT_DIR / 'session.json'}")
        except RuntimeError as e:
            print(f"Crawl failed: {e}")
            sys.exit(1)

    else:
        run_ws()


if __name__ == "__main__":
    main()
