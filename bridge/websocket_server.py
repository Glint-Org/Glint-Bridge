import asyncio
import json
import struct
import time
from pathlib import Path

try:
    import websockets
except ImportError:
    msg = "websockets is required. Install with: pip install websockets"
    raise ImportError(msg)

from .capture import capture_screenshot, batch_capture
from .adb_usb import list_usb_devices
from .adb_wifi import connect_wifi, list_wifi_devices

WS_PORT = 7700
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

connected_clients = set()


async def handler(websocket):
    connected_clients.add(websocket)
    try:
        async for raw in websocket:
            data = json.loads(raw)
            action = data.get("action")

            if action == "ping":
                await websocket.send(json.dumps({"type": "pong"}))

            elif action == "capture_single":
                path = capture_screenshot()
                await websocket.send(json.dumps({
                    "type": "screenshot",
                    "path": path,
                }))

            elif action == "capture_batch":
                count = data.get("count", 5)
                paths = batch_capture(count=count)
                await websocket.send(json.dumps({
                    "type": "batch_result",
                    "paths": paths,
                }))

            elif action == "list_devices":
                usb = list_usb_devices()
                wifi = list_wifi_devices()
                await websocket.send(json.dumps({
                    "type": "devices",
                    "usb": usb,
                    "wifi": wifi,
                }))

            elif action == "connect_wifi":
                ip = data["ip"]
                port = data.get("port", 5555)
                ok = connect_wifi(ip, port)
                await websocket.send(json.dumps({
                    "type": "connect_result",
                    "success": ok,
                }))

            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"Unknown action: {action}",
                }))
    finally:
        connected_clients.discard(websocket)


async def start_server(host: str = "0.0.0.0", port: int = WS_PORT):
    print(f"Telor Bridge WebSocket server on ws://{host}:{port}")
    async with websockets.serve(handler, host, port):
        await asyncio.Future()


def run():
    asyncio.run(start_server())


if __name__ == "__main__":
    run()
