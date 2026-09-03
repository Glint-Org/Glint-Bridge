import subprocess
import re
import time
from pathlib import Path

from .session import write_session

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _run_adb(args: list[str], capture: bool = True) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["adb"] + args,
            capture_output=capture,
            text=not capture,
            check=False,
        )
    except FileNotFoundError:
        return None


def capture_screenshot(
    serial: str | None = None,
    filename: str | None = None,
) -> str | None:
    """Capture a single screenshot via ADB. Returns the file path or None."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if filename is None:
        existing = list(OUTPUT_DIR.glob("screenshot_*.png"))
        num = len(existing) + 1
        filename = f"screenshot_{num:04d}.png"

    dest = OUTPUT_DIR / filename

    cmd = ["exec-out", "screencap", "-p"]
    if serial:
        cmd = ["-s", serial, "exec-out", "screencap", "-p"]
    with open(dest, "wb") as f:
        result = _run_adb(cmd)
        if result is None:
            dest.unlink(missing_ok=True)
            return None
        f.write(result.stdout if isinstance(result.stdout, bytes) else b"")

    if result.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        return None

    return str(dest)


def batch_capture(serial: str | None = None, count: int = 5, delay: float = 1.0) -> list[str]:
    """Capture N screenshots with delay between each. Returns list of file paths."""
    paths = []
    for i in range(count):
        path = capture_screenshot(serial, f"batch_{i+1:04d}.png")
        if path:
            paths.append(path)
        if i < count - 1:
            time.sleep(delay)
    return paths
