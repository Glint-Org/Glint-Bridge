import argparse
import sys

from .websocket_server import run as run_ws
from .capture import capture_screenshot, batch_capture
from .adb_usb import list_usb_devices


def main():
    parser = argparse.ArgumentParser(prog="telor-bridge")
    parser.add_argument("mode", nargs="?", default="server",
                        choices=["server", "capture", "batch", "devices"])
    parser.add_argument("--count", type=int, default=5, help="Batch capture count")

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
            print(f"Saved: {path}")
        else:
            print("Capture failed.")
            sys.exit(1)

    elif args.mode == "batch":
        paths = batch_capture(count=args.count)
        print(f"Captured {len(paths)} screenshots:")
        for p in paths:
            print(f"  {p}")

    else:
        run_ws()


if __name__ == "__main__":
    main()
