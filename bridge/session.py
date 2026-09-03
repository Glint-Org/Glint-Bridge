import json
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
SESSION_FILE = "session.json"


def _screen_basename(path: str) -> str:
    """Basename for posix or Windows-style capture paths."""
    return Path(str(path).replace("\\", "/")).name


def write_session(
    screens: list[str],
    store: str = "play/phone",
    output_dir: Path | None = None,
) -> str:
    """Write session.json to output directory per Glint schema."""
    out = output_dir or OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    session = {
        "screens": [_screen_basename(s) for s in screens],
        "store": _normalize_store(store),
        "version": "1.0",
        "exportedAt": datetime.now(timezone.utc).isoformat(),
    }

    dest = out / SESSION_FILE
    dest.write_text(json.dumps(session, indent=2))
    return str(dest)


def update_session_with_capture(filename: str, output_dir: Path | None = None) -> str:
    """Append a new screenshot to session.json or create a new session."""
    out = output_dir or OUTPUT_DIR
    session_path = out / SESSION_FILE

    screens = []
    store = "play/phone"

    if session_path.exists():
        data = json.loads(session_path.read_text())
        screens = data.get("screens", [])
        store = data.get("store", store)

    basename = _screen_basename(filename)
    if basename not in screens:
        screens.append(basename)

    return write_session(screens, store=store, output_dir=out)


def load_session(output_dir: Path | None = None) -> dict | None:
    out = output_dir or OUTPUT_DIR
    session_path = out / SESSION_FILE
    if not session_path.exists():
        return None
    return json.loads(session_path.read_text())


def _normalize_store(raw: str) -> str:
    """Normalize legacy store shortcuts to canonical Glint-Web format."""
    return {
        "play": "play/phone",
        "android": "play/phone",
        "ios": "ios/iphone",
        "ios-tablet": "ios/ipad",
    }.get(raw, raw)
