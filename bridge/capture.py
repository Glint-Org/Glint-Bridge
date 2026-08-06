import subprocess
import os
import re
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def capture_screenshot(serial: str | None = None, filename: str | None = None) -> str | None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if filename is None:
        existing = list(OUTPUT_DIR.glob("screenshot_*.png"))
        num = len(existing) + 1
        filename = f"screenshot_{num:04d}.png"

    dest = OUTPUT_DIR / filename

    cmd = ["adb", "exec-out", "screencap", "-p"]
    with open(dest, "wb") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, check=False)

    if result.returncode != 0 or dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        return None

    return str(dest)


def batch_capture(serial: str | None = None, count: int = 5, delay: float = 1.0) -> list[str]:
    import time
    paths = []
    for i in range(count):
        path = capture_screenshot(serial, f"batch_{i+1:04d}.png")
        if path:
            paths.append(path)
        if i < count - 1:
            time.sleep(delay)
    return paths


def get_device_resolution(serial: str | None = None) -> tuple[int, int] | None:
    cmd = ["adb", "shell", "wm", "size"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    match = re.search(r"(\d+)x(\d+)", result.stdout)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None
