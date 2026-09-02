"""Read Glint templates, .glint packs, and extract theme colors from PNG screenshots."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

GLINT_MAGIC = b"GLINT"
DEFAULT_SLOTS = ("primary", "secondary", "accent", "soft", "background")

SKIP_TOP = 0.10
SKIP_BOTTOM = 0.12
SKIP_SIDE = 0.08


def find_templates_root() -> Path | None:
    root = Path(__file__).resolve().parent.parent.parent / "Glint-Web" / "public" / "templates"
    return root if root.is_dir() else None


def read_glint(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    payload = data[6:] if data[:5] == GLINT_MAGIC else data
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        return json.loads(zf.read("project.json"))


def load_template_family(family_id: str, templates_root: Path | None = None) -> dict[str, Any]:
    root = templates_root or find_templates_root()
    if not root:
        raise FileNotFoundError("Glint-Web template folder not found (expected ../Glint-Web/public/templates)")
    common = root / family_id / "common.json"
    if not common.is_file():
        raise FileNotFoundError(f"Unknown template family: {family_id}")
    return json.loads(common.read_text(encoding="utf-8"))


def template_summary(template: dict[str, Any]) -> dict[str, Any]:
    palette = template.get("palette") or []
    headlines = (template.get("preview") or {}).get("headlines") or []
    slide_titles = []
    for slide in template.get("slides") or []:
        for layer in slide.get("layers") or []:
            if layer.get("type") in ("headline", "subheadline") and layer.get("placeholder"):
                slide_titles.append(layer["placeholder"])
    return {
        "familyId": template.get("familyId"),
        "name": template.get("name"),
        "description": template.get("description"),
        "palette": {slot.get("id") or f"c{i}": slot.get("color") for i, slot in enumerate(palette)},
        "fontFamily": (template.get("style") or {}).get("fontFamily"),
        "headlines": headlines,
        "slideTitles": slide_titles,
    }


def pack_summary(project: dict[str, Any]) -> dict[str, Any]:
    frames = []
    for i, frame in enumerate(project.get("frames") or []):
        titles = []
        design = frame.get("design") or {}
        for layer in design.get("layers") or []:
            if layer.get("type") in ("headline", "subheadline"):
                text = layer.get("placeholder") or layer.get("text")
                if text:
                    titles.append(text)
        frames.append(
            {
                "index": i,
                "id": frame.get("id"),
                "screenshot": frame.get("screenshot"),
                "titles": titles,
            }
        )
    return {
        "format": project.get("format"),
        "store": project.get("store"),
        "template": project.get("template"),
        "editor": project.get("editor"),
        "frames": frames,
    }


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def _parse_key(key: str) -> tuple[int, int, int]:
    return tuple(int(x) for x in key.split(","))  # type: ignore[return-value]


def _saturation(r: int, g: int, b: int) -> float:
    mx, mn = max(r, g, b), min(r, g, b)
    return 0.0 if mx == 0 else (mx - mn) / mx


def _luminance(r: int, g: int, b: int) -> float:
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def _rgb_to_hue(r: int, g: int, b: int) -> float:
    rn, gn, bn = r / 255, g / 255, b / 255
    mx, mn = max(rn, gn, bn), min(rn, gn, bn)
    d = mx - mn
    if d < 0.01:
        return -1.0
    if mx == rn:
        h = ((gn - bn) / d) % 6
    elif mx == gn:
        h = (bn - rn) / d + 2
    else:
        h = (rn - gn) / d + 4
    return ((h * 60) + 360) % 360


def _hue_distance(a: float, b: float) -> float:
    if a < 0 or b < 0:
        return 180.0
    d = abs(a - b)
    return min(d, 360 - d)


def is_neutral_rgb(r: int, g: int, b: int) -> bool:
    if r > 248 and g > 248 and b > 248:
        return True
    if r < 20 and g < 20 and b < 20:
        return True
    sat = _saturation(r, g, b)
    lum = _luminance(r, g, b)
    if sat < 0.14 and 0.12 < lum < 0.9:
        return True
    return False


def _bucket_key(r: int, g: int, b: int, bits: int = 4) -> str:
    shift = 8 - bits
    q = lambda v: (v >> shift) << shift  # noqa: E731
    return f"{q(r)},{q(g)},{q(b)}"


def _mix_hex(a: str, b: str, t: float) -> str:
    def parse(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#").upper()
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    r1, g1, b1 = parse(a)
    r2, g2, b2 = parse(b)
    lerp = lambda x, y: int(round(x + (y - x) * t))  # noqa: E731
    return _rgb_to_hex(lerp(r1, r2), lerp(g1, g2), lerp(b1, b2))


def _sample_weight(x: int, y: int, width: int, height: int) -> float:
    cx, cy = width / 2, height / 2
    nx, ny = (x - cx) / cx, (y - cy) / cy
    dist = (nx * nx + ny * ny) ** 0.5
    return max(0.15, 1 - dist * 0.85)


def _in_content_region(x: int, y: int, width: int, height: int) -> bool:
    return (
        width * SKIP_SIDE <= x <= width * (1 - SKIP_SIDE)
        and height * SKIP_TOP <= y <= height * (1 - SKIP_BOTTOM)
    )


def _counts_to_entries(counts: dict[str, int], accents_only: bool) -> list[dict[str, Any]]:
    entries = []
    for key, weight in counts.items():
        r, g, b = _parse_key(key)
        sat = _saturation(r, g, b)
        lum = _luminance(r, g, b)
        if accents_only and is_neutral_rgb(r, g, b):
            continue
        score = weight * ((0.35 + sat * 0.65) if accents_only else (0.5 + lum * 0.5))
        entries.append(
            {
                "r": r,
                "g": g,
                "b": b,
                "hex": _rgb_to_hex(r, g, b),
                "weight": weight,
                "sat": sat,
                "lum": lum,
                "hue": _rgb_to_hue(r, g, b),
                "score": score,
            }
        )
    entries.sort(key=lambda e: e["score"], reverse=True)
    return entries


def _pick_distinct(entries: list[dict[str, Any]], used: list[dict[str, Any]], min_hue: float = 22) -> dict[str, Any] | None:
    for entry in entries:
        if any(u["hex"] == entry["hex"] for u in used):
            continue
        if used and entry["hue"] >= 0 and all(
            u["hue"] >= 0 and _hue_distance(u["hue"], entry["hue"]) < min_hue for u in used
        ):
            continue
        return entry
    return None


def _pick_background(neutral_entries: list[dict[str, Any]]) -> str:
    light = sorted([e for e in neutral_entries if e["lum"] >= 0.78], key=lambda e: e["weight"], reverse=True)
    if light:
        return light[0]["hex"]
    any_sorted = sorted(neutral_entries, key=lambda e: e["weight"], reverse=True)
    if any_sorted and any_sorted[0]["lum"] >= 0.55:
        return any_sorted[0]["hex"]
    return "#FFFFFF"


def build_theme_from_counts(
    accent_counts: dict[str, int],
    neutral_counts: dict[str, int],
    slot_ids: list[str] | None = None,
) -> dict[str, str]:
    slots = list(slot_ids or DEFAULT_SLOTS)
    accents = _counts_to_entries(accent_counts, accents_only=True)
    neutrals = _counts_to_entries(neutral_counts, accents_only=False)

    primary_entry = _pick_distinct(accents, [], 0) or (accents[0] if accents else None)
    primary = primary_entry["hex"] if primary_entry else "#611AB4"
    used = [primary_entry] if primary_entry else []

    secondary_entry = _pick_distinct(accents, used, 22)
    secondary = secondary_entry["hex"] if secondary_entry else _mix_hex(primary, "#000000", 0.22)
    if secondary_entry:
        used.append(secondary_entry)

    accent_entry = _pick_distinct(accents, used, 18)
    accent = accent_entry["hex"] if accent_entry else _mix_hex(primary, "#FFFFFF", 0.28)

    soft = _mix_hex(primary, "#FFFFFF", 0.58)
    background = _pick_background(neutrals)

    theme = {
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
        "soft": soft,
        "background": background,
    }
    return {slot: theme.get(slot, primary) for slot in slots}


def pick_theme_colors(counts: dict[str, int], max_colors: int = 5) -> list[str]:
    theme = build_theme_from_counts(counts, counts, list(DEFAULT_SLOTS[:max_colors]))
    return [theme[slot] for slot in DEFAULT_SLOTS[:max_colors]]


def extract_theme_from_png(path: Path, max_side: int = 200) -> tuple[dict[str, int], dict[str, int]]:
    try:
        from PIL import Image
    except ImportError as e:
        raise RuntimeError("Pillow required for theme extraction (pip install Pillow)") from e

    accent_counts: dict[str, int] = {}
    neutral_counts: dict[str, int] = {}

    with Image.open(path) as im:
        im = im.convert("RGBA")
        scale = min(1.0, max_side / max(im.width, im.height))
        if scale < 1:
            im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))))
        pixels = im.load()
        w, h = im.size
        step = max(1, min(w, h) // 64)
        for y in range(0, h, step):
            for x in range(0, w, step):
                if not _in_content_region(x, y, w, h):
                    continue
                r, g, b, a = pixels[x, y]
                if a < 140:
                    continue
                bucket = max(1, round(_sample_weight(x, y, w, h) * 10))
                key = _bucket_key(r, g, b)
                neutral_counts[key] = neutral_counts.get(key, 0) + bucket
                if not is_neutral_rgb(r, g, b):
                    accent_counts[key] = accent_counts.get(key, 0) + bucket
    return accent_counts, neutral_counts


def extract_theme_from_paths(paths: list[Path], max_colors: int = 5, slot_ids: list[str] | None = None) -> dict[str, str]:
    accent_merged: dict[str, int] = {}
    neutral_merged: dict[str, int] = {}
    for path in paths:
        if not path.is_file():
            continue
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        try:
            accents, neutrals = extract_theme_from_png(path)
        except RuntimeError:
            raise
        except OSError:
            continue
        for key, count in accents.items():
            accent_merged[key] = accent_merged.get(key, 0) + count
        for key, count in neutrals.items():
            neutral_merged[key] = neutral_merged.get(key, 0) + count
    slots = slot_ids or list(DEFAULT_SLOTS[:max_colors])
    return build_theme_from_counts(accent_merged, neutral_merged, slots)


def map_colors_to_palette(template_palette: list[dict[str, Any]], theme: dict[str, str]) -> dict[str, str]:
    if not template_palette or not theme:
        return {}
    out: dict[str, str] = {}
    for slot in template_palette:
        slot_id = slot.get("id") or f"c{len(out)}"
        if slot_id in theme:
            out[slot_id] = theme[slot_id]
    return out


def resolve_image_paths(args: list[str]) -> list[Path]:
    paths: list[Path] = []
    for raw in args:
        p = Path(raw)
        if p.is_dir():
            for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                paths.extend(sorted(p.glob(ext)))
        elif p.is_file():
            paths.append(p)
    return paths
