import json
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
SESSION_FILE = "session.json"


def write_session(
    screens: list[str],
    app: str = "Captured App",
    tagline: str | None = None,
    store: str = "play",
    output_dir: Path | None = None,
) -> str:
    """Write session.json to output directory per Telor schema."""
    out = output_dir or OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    session = {
        "app": app,
        "screens": [Path(s).name if "/" in s or "\\" in s else s for s in screens],
        "store": store,
        "version": "1.0",
        "exportedAt": datetime.now(timezone.utc).isoformat(),
    }
    if tagline:
        session["tagline"] = tagline

    dest = out / SESSION_FILE
    dest.write_text(json.dumps(session, indent=2))
    return str(dest)


def update_session_with_capture(filename: str, output_dir: Path | None = None) -> str:
    """Append a new screenshot to session.json or create a new session."""
    out = output_dir or OUTPUT_DIR
    session_path = out / SESSION_FILE

    screens = []
    app = "Captured App"
    tagline = None
    store = "play"

    if session_path.exists():
        data = json.loads(session_path.read_text())
        screens = data.get("screens", [])
        app = data.get("app", app)
        tagline = data.get("tagline")
        store = data.get("store", store)

    basename = Path(filename).name
    if basename not in screens:
        screens.append(basename)

    return write_session(screens, app=app, tagline=tagline, store=store, output_dir=out)


def load_session(output_dir: Path | None = None) -> dict | None:
    out = output_dir or OUTPUT_DIR
    session_path = out / SESSION_FILE
    if not session_path.exists():
        return None
    return json.loads(session_path.read_text())
