"""
Optional web crawl (Playwright) with the same AI planner as Android.

Captures real browser screenshots only — never fabricates UI.
"""

from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .ai_config import resolve_ai_settings
from .ai_planner import heuristic_decision, plan_next_step, summarize_dom_snapshot
from .capture import OUTPUT_DIR

try:
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def crawl_web(
    start_url: str,
    max_screens: int = 12,
    output_dir: str | Path | None = None,
    *,
    use_ai: bool | None = None,
    ai_api_key: str | None = None,
    ai_provider: str | None = None,
    ai_model: str | None = None,
    viewport: tuple[int, int] = (1080, 1920),
    verbose: bool = True,
) -> list[str]:
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright is not installed. Install with: "
            "pip install playwright && playwright install chromium"
        )

    out = Path(output_dir) if output_dir else OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    settings = resolve_ai_settings(
        use_ai=use_ai,
        api_key=ai_api_key,
        provider=ai_provider,
        model=ai_model,
    )

    def log(msg: str) -> None:
        if verbose:
            print(msg)

    kept: list[str] = []
    kept_labels: list[str] = []
    visited: set[str] = set()
    host = urlparse(start_url).netloc

    mode = f"AI ({settings.provider}/{settings.model})" if settings else "heuristic"
    log(f"Web crawl mode: {mode}  url={start_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
        page.goto(start_url, wait_until="networkidle", timeout=45000)
        time.sleep(0.5)

        for step in range(max_screens):
            if settings and len(kept) >= settings.max_keep:
                break

            url = page.url
            if url in visited and step > 0:
                log("Revisited URL; stopping.")
                break
            visited.add(url)

            filename = f"web_{step + 1:04d}.png"
            dest = out / filename
            page.screenshot(path=str(dest), full_page=False)

            html = page.content()
            summary = summarize_dom_snapshot(html, url=url)

            if settings:
                decision = plan_next_step(
                    settings,
                    summary=summary,
                    screenshot_path=dest,
                    kept_labels=kept_labels,
                    step=step,
                    max_screens=max_screens,
                    goal="Marketing screenshots of this real website / web app UI",
                )
                if decision.source == "fallback":
                    decision = heuristic_decision(summary, step)
            else:
                decision = heuristic_decision(summary, step)
                decision.keep = step == 0 or step % 2 == 0

            if decision.keep:
                label = decision.label or f"web_{step + 1}"
                nice = out / f"{label}.png"
                if nice.exists():
                    nice = out / f"{label}_{step + 1}.png"
                dest.replace(nice)
                kept.append(str(nice))
                kept_labels.append(nice.stem)
                log(f"  KEEP  {nice.name}  score={decision.score:.2f}  ({decision.reason})")
            else:
                if dest.exists():
                    dest.unlink(missing_ok=True)
                log(f"  skip  {url}  score={decision.score:.2f}")

            if decision.action == "done":
                break
            if decision.action == "scroll":
                page.mouse.wheel(0, 900 if decision.scroll_direction != "backward" else -900)
                time.sleep(0.6)
                continue
            if decision.action == "back":
                page.go_back(wait_until="domcontentloaded")
                time.sleep(0.6)
                continue

            # tap → click matching target / first same-host link
            clicked = False
            target = None
            if decision.target_id is not None:
                by_id = {t.id: t for t in summary.targets}
                target = by_id.get(decision.target_id)
            candidates = [target] if target else summary.targets
            for t in candidates:
                if not t or not t.clickable:
                    continue
                try:
                    if t.kind == "link" and t.label:
                        href = urljoin(url, t.label)
                        if urlparse(href).netloc and urlparse(href).netloc != host:
                            continue
                        page.goto(href, wait_until="domcontentloaded", timeout=30000)
                        clicked = True
                        break
                    loc = page.get_by_text(t.label, exact=False).first
                    loc.click(timeout=3000)
                    clicked = True
                    break
                except Exception:
                    continue
            if not clicked:
                log("No further navigation; stopping.")
                break
            time.sleep(0.7)

        browser.close()

    if not kept:
        log("No store-worthy web screens kept.")
    return kept
