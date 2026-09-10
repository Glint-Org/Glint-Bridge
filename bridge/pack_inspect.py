"""Read Glint templates, .glint packs, and extract theme colors from PNG screenshots."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

GLINT_MAGIC = b"GLINT"
DEFAULT_SLOTS = ("primary", "secondary", "accent", "soft", "background")

SKIP_TOP = 0.12
SKIP_BOTTOM = 0.14
SKIP_SIDE = 0.06
HUE_BIN = 24


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
    if r > 245 and g > 245 and b > 245:
        return True
    if r < 18 and g < 18 and b < 18:
        return True
    sat = _saturation(r, g, b)
    lum = _luminance(r, g, b)
    if sat < 0.16 and 0.1 < lum < 0.92:
        return True
    return False


def _brand_score(sat: float, lum: float, weight: float) -> float:
    sat_score = max(0.0, sat) ** 1.35
    lum_score = max(0.12, 1 - abs(lum - 0.42) * 1.55)
    area_score = max(1.0, weight) ** 0.3
    return sat_score * lum_score * area_score


def _bucket_key(r: int, g: int, b: int, bits: int = 5) -> str:
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


def _rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    rn, gn, bn = r / 255, g / 255, b / 255
    mx, mn = max(rn, gn, bn), min(rn, gn, bn)
    lum = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, lum
    d = mx - mn
    sat = d / (2 - mx - mn) if lum > 0.5 else d / (mx + mn)
    if mx == rn:
        h = ((gn - bn) / d + (6 if gn < bn else 0)) / 6
    elif mx == gn:
        h = ((bn - rn) / d + 2) / 6
    else:
        h = ((rn - gn) / d + 4) / 6
    return h, sat, lum


def _hsl_to_rgb(h: float, s: float, lum: float) -> tuple[int, int, int]:
    if s <= 0:
        v = int(round(lum * 255))
        return v, v, v

    def hue2rgb(p: float, q: float, t: float) -> float:
        tt = t
        if tt < 0:
            tt += 1
        if tt > 1:
            tt -= 1
        if tt < 1 / 6:
            return p + (q - p) * 6 * tt
        if tt < 1 / 2:
            return q
        if tt < 2 / 3:
            return p + (q - p) * (2 / 3 - tt) * 6
        return p

    q = lum * (1 + s) if lum < 0.5 else lum + s - lum * s
    p = 2 * lum - q
    return (
        int(round(hue2rgb(p, q, h + 1 / 3) * 255)),
        int(round(hue2rgb(p, q, h) * 255)),
        int(round(hue2rgb(p, q, h - 1 / 3) * 255)),
    )


def _punch_saturation(hex_color: str, amount: float = 0.12) -> str:
    h = hex_color.lstrip("#").upper()
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    hh, ss, ll = _rgb_to_hsl(r, g, b)
    if ss < 0.04:
        return _rgb_to_hex(r, g, b)
    ss = min(1.0, ss + amount * (1 - ss))
    nr, ng, nb = _hsl_to_rgb(hh, ss, ll)
    return _rgb_to_hex(nr, ng, nb)


def _sample_weight(x: int, y: int, width: int, height: int) -> float:
    cx, cy = width / 2, height * 0.38
    nx, ny = (x - cx) / (width * 0.55), (y - cy) / (height * 0.55)
    dist = (nx * nx + ny * ny) ** 0.5
    return max(0.2, 1.15 - dist * 0.95)


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
        if accents_only and sat < 0.18:
            continue
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
                "score": _brand_score(sat, lum, weight),
            }
        )
    entries.sort(key=lambda e: e["score"], reverse=True)
    return entries


def _cluster_accents_by_hue(entries: list[dict[str, Any]], bin_deg: int = HUE_BIN) -> list[dict[str, Any]]:
    bins: dict[int, dict[str, Any]] = {}
    for entry in entries:
        if entry["hue"] < 0:
            continue
        bin_id = int(round(entry["hue"] / bin_deg) * bin_deg) % 360
        cur = bins.get(bin_id) or {"hue": bin_id, "entries": [], "weight": 0.0, "score": 0.0}
        cur["entries"].append(entry)
        cur["weight"] += entry["weight"]
        cur["score"] += entry["score"]
        bins[bin_id] = cur
    return sorted(bins.values(), key=lambda c: c["score"], reverse=True)


def _pick_cluster_representative(cluster: dict[str, Any] | None) -> dict[str, Any] | None:
    if not cluster or not cluster.get("entries"):
        return None
    ranked = sorted(
        cluster["entries"],
        key=lambda e: e["sat"] * (1 - abs(e["lum"] - 0.42)) * (e["weight"] ** 0.25),
        reverse=True,
    )
    return ranked[0]


def _pick_background(neutral_entries: list[dict[str, Any]]) -> str:
    if not neutral_entries:
        return "#FFFFFF"
    total = sum(e["weight"] for e in neutral_entries) or 1
    mean_lum = sum(e["lum"] * e["weight"] for e in neutral_entries) / total
    if mean_lum >= 0.55:
        light = sorted(
            [e for e in neutral_entries if e["lum"] >= 0.82 and e["sat"] < 0.12],
            key=lambda e: e["weight"],
            reverse=True,
        )
        if light:
            return light[0]["hex"]
        return "#FFFFFF"
    dark = sorted(
        [e for e in neutral_entries if e["lum"] <= 0.22 and e["sat"] < 0.15],
        key=lambda e: e["weight"],
        reverse=True,
    )
    if dark:
        return dark[0]["hex"]
    return "#121212"


def _build_harmony_from_primary(primary_hex: str, background_hex: str) -> dict[str, str]:
    primary = _punch_saturation(primary_hex, 0.1)
    bg = background_hex or "#FFFFFF"
    bh = bg.lstrip("#")
    bg_lum = _luminance(int(bh[0:2], 16), int(bh[2:4], 16), int(bh[4:6], 16))
    secondary = _mix_hex(primary, "#000000", 0.2 if bg_lum > 0.5 else 0.12)
    accent = _mix_hex(primary, "#FFFFFF", 0.22 if bg_lum > 0.5 else 0.3)
    soft = _mix_hex(primary, "#FFFFFF" if bg_lum > 0.5 else bg, 0.62)
    return {
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
        "soft": soft,
        "background": bg,
    }


def build_theme_from_counts(
    accent_counts: dict[str, int],
    neutral_counts: dict[str, int],
    slot_ids: list[str] | None = None,
) -> dict[str, str]:
    slots = list(slot_ids or DEFAULT_SLOTS)
    accents = _counts_to_entries(accent_counts, accents_only=True)
    neutrals = _counts_to_entries(neutral_counts, accents_only=False)
    background = _pick_background(neutrals)

    clusters = _cluster_accents_by_hue(accents)
    best = _pick_cluster_representative(clusters[0]) if clusters else (accents[0] if accents else None)
    primary_hex = best["hex"] if best else "#611AB4"
    harmony = _build_harmony_from_primary(primary_hex, background)

    if (
        len(clusters) > 1
        and clusters[1]["score"] >= clusters[0]["score"] * 0.55
        and _hue_distance(clusters[0]["hue"], clusters[1]["hue"]) >= 36
    ):
        second = _pick_cluster_representative(clusters[1])
        if second and second["sat"] >= 0.28:
            harmony["accent"] = _punch_saturation(second["hex"], 0.08)

    return {slot: harmony.get(slot, harmony["primary"]) for slot in slots}


def pick_theme_colors(counts: dict[str, int], max_colors: int = 5) -> list[str]:
    theme = build_theme_from_counts(counts, counts, list(DEFAULT_SLOTS[:max_colors]))
    return [theme[slot] for slot in DEFAULT_SLOTS[:max_colors]]


def extract_theme_from_png(path: Path, max_side: int = 256) -> tuple[dict[str, int], dict[str, int]]:
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
        step = max(1, min(w, h) // 80)
        for y in range(0, h, step):
            for x in range(0, w, step):
                if not _in_content_region(x, y, w, h):
                    continue
                r, g, b, a = pixels[x, y]
                if a < 160:
                    continue
                bucket = max(1, round(_sample_weight(x, y, w, h) * 12))
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
