import subprocess


def _run_adb(args: list[str]) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["adb"] + args, capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        return None


def connect_wifi(ip: str, port: int = 5555) -> bool:
    addr = f"{ip}:{port}"
    result = _run_adb(["connect", addr])
    if result is None:
        return False
    return "connected" in result.stdout.lower()


def list_wifi_devices() -> list[dict]:
    result = _run_adb(["devices"])
    if result is None:
        return []
    devices = []
    for line in result.stdout.strip().splitlines():
        if ":" in line and "device" in line:
            parts = line.split()
            devices.append({"serial": parts[0], "transport": "wifi"})
    return devices


def disconnect(ip: str, port: int = 5555) -> bool:
    result = _run_adb(["disconnect", f"{ip}:{port}"])
    return result is not None and result.returncode == 0
