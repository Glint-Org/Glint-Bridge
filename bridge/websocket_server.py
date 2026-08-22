import asyncio
import json
import secrets
from pathlib import Path

try:
    import websockets
except ImportError:
    msg = "websockets is required. Install with: pip install websockets"
    raise ImportError(msg)

from .capture import capture_screenshot, batch_capture
from .adb_usb import list_usb_devices
from .adb_wifi import connect_wifi, list_wifi_devices
from .crawler import crawl_app
from .session import write_session, load_session

WS_PORT = 7700
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

connected_clients = set()
_PAIRING_TOKEN: str | None = None


def _generate_token() -> str:
    return secrets.token_hex(4)


async def handler(websocket):
    global _PAIRING_TOKEN

    # First message must be a valid pairing token
    try:
        raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        data = json.loads(raw)
        if data.get("action") != "pair" or data.get("token") != _PAIRING_TOKEN:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Invalid pairing token. Request denied.",
            }))
            await websocket.close(1008, "Unauthorized")
            return
    except (asyncio.TimeoutError, json.JSONDecodeError):
        await websocket.close(1008, "Pairing required")
        return

    await websocket.send(json.dumps({"type": "paired", "success": True}))
    connected_clients.add(websocket)
    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            action = data.get("action")

            if action == "ping":
                await websocket.send(json.dumps({"type": "pong"}))

            elif action == "capture_single":
                path = capture_screenshot()
                session = load_session()
                await websocket.send(json.dumps({
                    "type": "screenshot",
                    "path": path,
                    "session": session,
                }))

            elif action == "capture_batch":
                count = data.get("count", 5)
                paths = batch_capture(count=count)
                app = data.get("app", "Captured App")
                tagline = data.get("tagline")
                if paths:
                    write_session(
                        screens=[Path(p).name for p in paths],
                        app=app,
                        tagline=tagline,
                        output_dir=OUTPUT_DIR,
                    )
                session = load_session()
                await websocket.send(json.dumps({
                    "type": "batch_result",
                    "paths": paths,
                    "session": session,
                }))

            elif action == "crawl":
                package = data.get("package")
                max_screens = data.get("max_screens", 20)
                app = data.get("app", "Captured App")
                tagline = data.get("tagline")
                if not package:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "package is required for crawl action",
                    }))
                else:
                    try:
                        paths = crawl_app(package, max_screens=max_screens)
                        write_session(
                            screens=[Path(p).name for p in paths],
                            app=app,
                            tagline=tagline,
                            output_dir=OUTPUT_DIR,
                        )
                        session = load_session()
                        await websocket.send(json.dumps({
                            "type": "crawl_result",
                            "paths": paths,
                            "session": session,
                        }))
                    except RuntimeError as e:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": str(e),
                        }))

            elif action == "get_session":
                session = load_session()
                await websocket.send(json.dumps({
                    "type": "session",
                    "session": session,
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
                ip = data.get("ip")
                if not ip:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "ip is required for connect_wifi action",
                    }))
                else:
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


async def start_server(host: str = "127.0.0.1", port: int = WS_PORT):
    global _PAIRING_TOKEN
    _PAIRING_TOKEN = _generate_token()
    print(f"Glint Bridge WebSocket server on ws://{host}:{port}")
    print(f"Pairing token: {_PAIRING_TOKEN}")
    print("Clients must send {\"action\":\"pair\",\"token\":\"<token>\"} as first message.")
    async with websockets.serve(handler, host, port):
        await asyncio.Future()


def run():
    asyncio.run(start_server())


if __name__ == "__main__":
    run()
