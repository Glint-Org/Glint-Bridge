"""ADB-only sense/act primitives for agentic IDEs.

The IDE agent IS the planner (it already has a model), so these do no LLM
calls and need no GLINT_AI_API_KEY. Loop: launch → screenshot → hierarchy
→ tap/scroll/back → keep best PNGs → write_session in Glint-Web step.

Usage from MCP or shell, JSON on stdout:
  python bridge/agent.py screenshot [--serial S] [--filename F]
  python bridge/agent.py hierarchy [--serial S] [--package PKG]
  python bridge/agent.py tap X Y [--serial S]
  python bridge/agent.py scroll [forward|backward] [--serial S]
  python bridge/agent.py back [--serial S]
  python bridge/agent.py launch PKG [--serial S]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def _adb(serial: str | None, *args: str) -> subprocess.CompletedProcess:
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, check=False)


def cmd_screenshot(serial: str | None, filename: str | None) -> dict:
    from .capture import capture_screenshot

    path = capture_screenshot(serial=serial, filename=filename)
    if not path:
        return {"ok": False, "error": "screenshot failed - check device + USB debugging"}
    return {"ok": True, "path": path}


def cmd_hierarchy(serial: str | None, package: str = "") -> dict:
    from .ai_planner import summarize_android_hierarchy

    r = _adb(serial, "exec-out", "uiautomator", "dump", "/dev/tty")
    raw = (r.stdout or b"").decode("utf-8", "replace")
    start = raw.find("<?xml")
    xml = raw[start:] if start >= 0 else raw
    if not xml.strip().startswith("<?xml") and "<node" not in xml:
        return {"ok": False, "error": "hierarchy dump failed", "stderr": (r.stderr or b"").decode()[-500:]}
    summary = summarize_android_hierarchy(xml, package=package)
    return {"ok": True, "hierarchy": summary.compact(), "targets": len(summary.targets)}


def cmd_tap(serial: str | None, x: int, y: int) -> dict:
    r = _adb(serial, "shell", "input", "tap", str(x), str(y))
    return {"ok": r.returncode == 0}


def _window_size(serial: str | None) -> tuple[int, int]:
    r = _adb(serial, "shell", "wm", "size")
    out = ((r.stdout or b"").decode() or "") + ((r.stderr or b"").decode() or "")
    # e.g. "Physical size: 1080x2400"
    import re

    m = re.search(r"(\d+)\s*x\s*(\d+)", out)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 1080, 2400


def cmd_scroll(serial: str | None, direction: str = "forward") -> dict:
    w, h = _window_size(serial)
    x = w // 2
    if direction == "backward":
        args = ["shell", "input", "swipe", str(x), str(int(h * 0.25)), str(x), str(int(h * 0.75)), "400"]
    else:
        args = ["shell", "input", "swipe", str(x), str(int(h * 0.75)), str(x), str(int(h * 0.25)), "400"]
    r = _adb(serial, *args)
    return {"ok": r.returncode == 0, "direction": direction}


def cmd_back(serial: str | None) -> dict:
    r = _adb(serial, "shell", "input", "keyevent", "4")
    return {"ok": r.returncode == 0}


def cmd_launch(serial: str | None, package: str) -> dict:
    r = _adb(serial, "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
    out = ((r.stdout or b"").decode() or "")[-300:]
    return {"ok": r.returncode == 0, "package": package, "output": out}


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="glint-bridge-agent")
    p.add_argument("--serial", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("screenshot")
    s.add_argument("--filename", default=None)
    h = sub.add_parser("hierarchy")
    h.add_argument("--package", default="")
    t = sub.add_parser("tap")
    t.add_argument("x", type=int)
    t.add_argument("y", type=int)
    sc = sub.add_parser("scroll")
    sc.add_argument("direction", nargs="?", default="forward", choices=["forward", "backward"])
    sub.add_parser("back")
    la = sub.add_parser("launch")
    la.add_argument("package")
    args = p.parse_args(argv)

    if args.cmd == "screenshot":
        res = cmd_screenshot(args.serial, args.filename)
    elif args.cmd == "hierarchy":
        res = cmd_hierarchy(args.serial, args.package)
    elif args.cmd == "tap":
        res = cmd_tap(args.serial, args.x, args.y)
    elif args.cmd == "scroll":
        res = cmd_scroll(args.serial, args.direction)
    elif args.cmd == "back":
        res = cmd_back(args.serial)
    elif args.cmd == "launch":
        res = cmd_launch(args.serial, args.package)
    else:
        res = {"ok": False, "error": "unknown command"}
    print(json.dumps(res))
    sys.exit(0 if res.get("ok") else 1)


if __name__ == "__main__":
    main()
