"""Local-first AI settings for intelligent crawl (user-owned API keys)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AiSettings:
    enabled: bool
    provider: str  # openai | anthropic | compatible
    api_key: str
    model: str
    base_url: str | None
    keep_threshold: float
    max_keep: int
    vision: bool


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_ai_settings(
    *,
    use_ai: bool | None = None,
    api_key: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> AiSettings | None:
    """
    Resolve AI settings from args + env.

    Env:
      GLINT_AI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY
      GLINT_AI_PROVIDER=openai|anthropic|compatible  (default: auto)
      GLINT_AI_MODEL
      GLINT_AI_BASE_URL  (OpenAI-compatible endpoints)
      GLINT_AI_ENABLED=1
      GLINT_AI_KEEP_THRESHOLD=0.65
      GLINT_AI_MAX_KEEP=8
      GLINT_AI_VISION=1
    """
    key = (
        api_key
        or os.getenv("GLINT_AI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or ""
    ).strip()

    enabled_flag = _truthy(os.getenv("GLINT_AI_ENABLED"))
    if use_ai is False:
        return None

    want_ai = bool(use_ai) or enabled_flag
    if not want_ai:
        return None

    if not key:
        raise RuntimeError(
            "AI crawl requested but no API key found. "
            "Set GLINT_AI_API_KEY (or OPENAI_API_KEY / ANTHROPIC_API_KEY)."
        )

    prov = (provider or os.getenv("GLINT_AI_PROVIDER") or "").strip().lower()
    if not prov:
        if os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY") and not os.getenv("GLINT_AI_API_KEY"):
            prov = "anthropic"
        elif os.getenv("GLINT_AI_BASE_URL"):
            prov = "compatible"
        else:
            prov = "openai"

    if prov in {"openai-compatible", "openrouter", "groq"}:
        prov = "compatible"

    default_models = {
        "openai": "gpt-4o-mini",
        "compatible": "gpt-4o-mini",
        "anthropic": "claude-3-5-haiku-latest",
    }
    mdl = (model or os.getenv("GLINT_AI_MODEL") or default_models.get(prov, "gpt-4o-mini")).strip()
    base = (os.getenv("GLINT_AI_BASE_URL") or "").strip() or None
    if prov == "compatible" and not base:
        raise RuntimeError("GLINT_AI_PROVIDER=compatible requires GLINT_AI_BASE_URL")

    try:
        threshold = float(os.getenv("GLINT_AI_KEEP_THRESHOLD", "0.65"))
    except ValueError:
        threshold = 0.65
    try:
        max_keep = int(os.getenv("GLINT_AI_MAX_KEEP", "8"))
    except ValueError:
        max_keep = 8

    vision = _truthy(os.getenv("GLINT_AI_VISION", "1"))

    return AiSettings(
        enabled=True,
        provider=prov,
        api_key=key,
        model=mdl,
        base_url=base,
        keep_threshold=max(0.0, min(1.0, threshold)),
        max_keep=max(1, max_keep),
        vision=vision,
    )
