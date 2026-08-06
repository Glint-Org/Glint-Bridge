import subprocess
import re


def connect_wifi(ip: str, port: int = 5555) -> bool:
    addr = f"{ip}:{port}"
    result = subprocess.run(
        ["adb", "connect", addr], capture_output=True, text=True, check=False
    )
    return "connected" in result.stdout.lower()


def list_wifi_devices() -> list[dict]:
    result = subprocess.run(
        ["adb", "devices"], capture_output=True, text=True, check=False
    )
    devices = []
    for line in result.stdout.strip().splitlines():
        if ":" in line and "device" in line:
            parts = line.split()
            devices.append({"serial": parts[0], "transport": "wifi"})
    return devices


def disconnect(ip: str, port: int = 5555) -> bool:
    result = subprocess.run(
        ["adb", "disconnect", f"{ip}:{port}"],
        capture_output=True, text=True, check=False
    )
    return result.returncode == 0
