import subprocess


def _run_adb(args: list[str]) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["adb"] + args, capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        return None


def list_usb_devices() -> list[dict]:
    result = _run_adb(["devices", "-l"])
    if result is None:
        return []
    devices = []
    for line in result.stdout.strip().splitlines():
        if line.startswith("List") or "device" not in line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1].startswith("device"):
            devices.append({"serial": parts[0], "model": _extract_model(parts)})
    return devices


def _extract_model(parts: list[str]) -> str:
    for p in parts[2:]:
        if p.startswith("model:"):
            return p.replace("model:", "").replace("_", " ")
    return "Unknown"


def connect_usb() -> bool:
    devices = list_usb_devices()
    return len(devices) > 0


def disconnect(serial: str | None = None) -> bool:
    cmd = ["disconnect"]
    if serial:
        cmd.append(serial)
    result = _run_adb(cmd)
    return result is not None and result.returncode == 0
