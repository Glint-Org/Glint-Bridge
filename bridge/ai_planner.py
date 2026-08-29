"""
Intelligent crawl planner — user-owned API keys, navigate + score real screens.

Never fabricates UI. AI only chooses actions and which captures to keep for store frames.
"""

from __future__ import annotations

import base64
import io
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ai_config import AiSettings

SYSTEM_PROMPT = """You are Glint's store-screenshot crawl planner for REAL Android app UI.

Your job: navigate the app and capture 5-8 raw screenshots that will become Play Store / App Store marketing screenshots after polishing in Glint Web.

RULES:
- Never invent or describe fake UI. Only judge the provided screenshot + accessibility tree.
- Screenshots are RAW device pixels — no crop, no resize. Glint Web handles framing/templates later.
- Capture at device native resolution (whatever the phone gives).

SCREEN SELECTION (what to KEEP):
- KEEP: home/feed with content, product/feature screens, settings with toggles, empty states with illustrations, onboarding value screens, profile with avatar, search results with items, any screen with images/cards/grids
- KEEP screens that show the app's CORE VALUE in one glance
- Target 5-8 unique screens (matches template slot count in Glint Web)

SCREEN REJECTION (what to SKIP):
- SKIP: login/signup/auth forms, loading spinners, permission dialogs, crash/error screens
- SKIP: open keyboards covering half the screen, half-scrolled transitional states
- SKIP: system UI chrome only (status bar, nav bar with no app content)
- SKIP: about/debug/settings-info screens with just text
- SKIP: near-duplicate frames (same screen, slightly different scroll position)
- SKIP: splash screens, empty states with no illustration

NAVIGATION:
- Prefer tapping feature-rich areas (bottom nav items, cards, list items with images)
- Scroll to reveal content, not just to move past empty space
- Use back button to return to main flow, don't get stuck in deep sub-screens
- If you have enough good unique screens, action can be "done"

SCORING (0.0 - 1.0):
- 0.8-1.0: Core feature screen with rich visual content (images, cards, grids)
- 0.6-0.7: Good marketing screen (settings with state, profile, search results)
- 0.4-0.5: Decent but not exciting (plain list, text-heavy screen)
- 0.2-0.3: Not store material (auth, loading, error, permission)
- 0.0-0.1: Actively harmful for store listing (crash, blank, keyboard)

Respond with JSON only:
{
  "score": 0.0-1.0,
  "keep": true/false,
  "label": "short_snake_case_name",
  "reason": "one sentence",
  "action": "tap" | "scroll" | "back" | "done",
  "target_id": number or null,
  "scroll_direction": "forward" | "backward" | null
}
"""


@dataclass
class UiTarget:
    id: int
    kind: str
    label: str
    resource_id: str = ""
    clickable: bool = False
    scrollable: bool = False
    bounds: str = ""


@dataclass
class ScreenSummary:
    package: str
    targets: list[UiTarget] = field(default_factory=list)
    text_sample: list[str] = field(default_factory=list)

    def compact(self, limit: int = 40) -> str:
        lines = [f"package={self.package}"]
        if self.text_sample:
            lines.append("text: " + " | ".join(self.text_sample[:12]))
        for t in self.targets[:limit]:
            flags = []
            if t.clickable:
                flags.append("click")
            if t.scrollable:
                flags.append("scroll")
            flag_s = ",".join(flags) or "static"
            lines.append(
                f"[{t.id}] {t.kind} ({flag_s}) \"{t.label}\" rid={t.resource_id} bounds={t.bounds}"
            )
        return "\n".join(lines)


@dataclass
class PlanDecision:
    score: float
    keep: bool
    label: str
    reason: str
    action: str
    target_id: int | None = None
    scroll_direction: str | None = "forward"
    source: str = "ai"  # ai | heuristic | fallback


def summarize_android_hierarchy(page_source: str, package: str = "") -> ScreenSummary:
    """Compress Appium page source into labeled targets the model (and heuristics) can use."""
    summary = ScreenSummary(package=package)
    try:
        root = ET.fromstring(page_source)
    except ET.ParseError:
        return summary

    texts: list[str] = []
    idx = 0
    for node in root.iter():
        text = (node.attrib.get("text") or "").strip()
        desc = (node.attrib.get("content-desc") or "").strip()
        rid = (node.attrib.get("resource-id") or "").strip()
        clickable = node.attrib.get("clickable", "false") == "true"
        scrollable = node.attrib.get("scrollable", "false") == "true"
        cls = (node.attrib.get("class") or node.tag or "node").split(".")[-1]
        bounds = node.attrib.get("bounds") or ""
        label = text or desc
        if label and len(label) < 80 and label not in texts:
            texts.append(label)
        if not (clickable or scrollable):
            continue
        if not label and not rid:
            continue
        summary.targets.append(
            UiTarget(
                id=idx,
                kind=cls,
                label=(label or rid.split("/")[-1])[:80],
                resource_id=rid,
                clickable=clickable,
                scrollable=scrollable,
                bounds=bounds,
            )
        )
        idx += 1
    summary.text_sample = texts[:20]
    return summary


def summarize_dom_snapshot(snapshot: str, url: str = "") -> ScreenSummary:
    """Lightweight HTML → clickable-ish labels for web crawl."""
    summary = ScreenSummary(package=url)
    texts = re.findall(
        r"<(?:a|button|h1|h2|h3|label|option)[^>]*>([^<]{1,60})</",
        snapshot,
        flags=re.I,
    )
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', snapshot, flags=re.I)
    summary.text_sample = [t.strip() for t in texts if t.strip()][:20]
    idx = 0
    for t in summary.text_sample[:30]:
        summary.targets.append(
            UiTarget(id=idx, kind="element", label=t, clickable=True)
        )
        idx += 1
    for h in hrefs[:20]:
        if h.startswith("#") or h.startswith("javascript:"):
            continue
        summary.targets.append(
            UiTarget(id=idx, kind="link", label=h[:80], clickable=True)
        )
        idx += 1
    return summary


def _image_data_url(path: str | Path, max_side: int = 768) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    raw = p.read_bytes()
    mime = "image/png"
    try:
        from PIL import Image  # optional

        im = Image.open(io.BytesIO(raw)).convert("RGB")
        w, h = im.size
        scale = min(1.0, max_side / max(w, h))
        if scale < 1.0:
            im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=72, optimize=True)
        raw = buf.getvalue()
        mime = "image/jpeg"
    except Exception:
        pass
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def _http_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"AI API HTTP {e.code}: {detail}") from e


def _call_openai_compatible(settings: AiSettings, user_text: str, image_url: str | None) -> str:
    base = (settings.base_url or "https://api.openai.com/v1").rstrip("/")
    url = f"{base}/chat/completions"
    content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    if settings.vision and image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    payload = {
        "model": settings.model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    }
    data = _http_json(
        url,
        {
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        },
        payload,
    )
    return data["choices"][0]["message"]["content"]


def _call_anthropic(settings: AiSettings, user_text: str, image_url: str | None) -> str:
    url = "https://api.anthropic.com/v1/messages"
    content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    if settings.vision and image_url and image_url.startswith("data:"):
        # data:image/jpeg;base64,....
        header, b64 = image_url.split(",", 1)
        media = "image/jpeg" if "jpeg" in header else "image/png"
        content.insert(
            0,
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media, "data": b64},
            },
        )
    payload = {
        "model": settings.model,
        "max_tokens": 500,
        "temperature": 0.2,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": content}],
    }
    data = _http_json(
        url,
        {
            "x-api-key": settings.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        payload,
    )
    parts = data.get("content") or []
    texts = [p.get("text", "") for p in parts if p.get("type") == "text"]
    return "\n".join(texts)


def plan_next_step(
    settings: AiSettings,
    *,
    summary: ScreenSummary,
    screenshot_path: str | Path | None,
    kept_labels: list[str],
    step: int,
    max_screens: int,
    goal: str = "Play Store / App Store marketing screenshots of this real product UI",
) -> PlanDecision:
    user_text = (
        f"Goal: {goal}\n"
        f"Step: {step + 1}/{max_screens}\n"
        f"Already kept labels: {kept_labels or ['(none)']}\n"
        f"UI summary:\n{summary.compact()}\n"
    )
    image_url = _image_data_url(screenshot_path) if screenshot_path else None

    try:
        if settings.provider == "anthropic":
            raw = _call_anthropic(settings, user_text, image_url)
        else:
            raw = _call_openai_compatible(settings, user_text, image_url)
        data = _extract_json(raw)
    except Exception as e:
        # Caller falls back to heuristic
        return PlanDecision(
            score=0.4,
            keep=False,
            label=f"step_{step + 1}",
            reason=f"AI unavailable ({e}); use heuristic",
            action="scroll",
            scroll_direction="forward",
            source="fallback",
        )

    action = str(data.get("action") or "scroll").lower()
    if action not in {"tap", "scroll", "back", "done"}:
        action = "scroll"
    score = float(data.get("score") or 0)
    score = max(0.0, min(1.0, score))
    keep = bool(data.get("keep")) and score >= settings.keep_threshold
    label = re.sub(r"[^a-z0-9_]+", "_", str(data.get("label") or f"screen_{step + 1}").lower()).strip("_")
    target = data.get("target_id")
    try:
        target_id = int(target) if target is not None else None
    except (TypeError, ValueError):
        target_id = None
    direction = data.get("scroll_direction") or "forward"
    if direction not in {"forward", "backward"}:
        direction = "forward"

    return PlanDecision(
        score=score,
        keep=keep,
        label=label or f"screen_{step + 1}",
        reason=str(data.get("reason") or ""),
        action=action,
        target_id=target_id,
        scroll_direction=direction,
        source="ai",
    )


def heuristic_decision(summary: ScreenSummary, step: int) -> PlanDecision:
    """No-AI fallback: scroll if possible, else first clickable, else done."""
    scrollables = [t for t in summary.targets if t.scrollable]
    clickables = [t for t in summary.targets if t.clickable]
    # Prefer labeled primary-ish targets
    prefer = [
        t
        for t in clickables
        if re.search(r"home|start|explore|feature|get started|continue|next|menu", t.label, re.I)
    ]
    if scrollables:
        return PlanDecision(
            score=0.45,
            keep=step == 0,
            label=f"crawl_{step + 1:04d}",
            reason="Heuristic scroll",
            action="scroll",
            target_id=scrollables[0].id,
            scroll_direction="forward",
            source="heuristic",
        )
    target = (prefer or clickables[:1] or [None])[0]
    if target is None:
        return PlanDecision(
            score=0.3,
            keep=step == 0,
            label=f"crawl_{step + 1:04d}",
            reason="Heuristic stop",
            action="done",
            source="heuristic",
        )
    return PlanDecision(
        score=0.5 if prefer else 0.4,
        keep=step == 0,
        label=f"crawl_{step + 1:04d}",
        reason="Heuristic tap",
        action="tap",
        target_id=target.id,
        source="heuristic",
    )
