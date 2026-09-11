"""
Android auto-crawl: heuristic by default, optional AI planner (user API key).

Captures real device pixels only - AI navigates and filters, never draws UI.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from .ai_config import AiSettings, resolve_ai_settings
from .ai_planner import (
    PlanDecision,
    heuristic_decision,
    plan_next_step,
    summarize_android_hierarchy,
)
from .capture import OUTPUT_DIR, capture_screenshot

try:
    from appium import webdriver
    from appium.webdriver.common.appiumby import AppiumBy

    APPIUM_AVAILABLE = True
except ImportError:
    APPIUM_AVAILABLE = False


def _build_driver(app_package: str, appium_url: str = "http://localhost:4723"):
    if not APPIUM_AVAILABLE:
        raise RuntimeError(
            "Appium is not installed. Install with: pip install Appium-Python-Client"
        )

    caps = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "noReset": True,
        "appPackage": app_package,
    }

    try:
        from appium.options.common import AppiumOptions

        options = AppiumOptions()
        for k, v in caps.items():
            options.set_capability(k, v)
        driver = webdriver.Remote(appium_url, options=options)
    except Exception:
        try:
            driver = webdriver.Remote(appium_url, caps)
        except Exception as e:
            raise RuntimeError(f"Cannot connect to Appium server: {e}") from e

    try:
        driver.activate_app(app_package)
    except Exception:
        pass
    return driver


def _page_source(driver) -> str:
    try:
        return driver.page_source or ""
    except Exception:
        return ""


def _find_by_target(driver, summary, target_id: int | None):
    if target_id is None:
        return None
    by_id = {t.id: t for t in summary.targets}
    t = by_id.get(target_id)
    if t is None:
        return None
    try:
        if t.resource_id:
            els = driver.find_elements(AppiumBy.ID, t.resource_id)
            if els:
                return els[0]
        if t.label:
            safe = t.label[:40].replace('"', "")
            els = driver.find_elements(
                AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiSelector().textContains("{safe}")',
            )
            if els:
                return els[0]
            els = driver.find_elements(
                AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiSelector().descriptionContains("{safe}")',
            )
            if els:
                return els[0]
    except Exception:
        return None
    return None


def _do_scroll(driver, direction: str = "forward") -> bool:
    try:
        scrollable = driver.find_elements(
            AppiumBy.ANDROID_UIAUTOMATOR,
            "new UiSelector().scrollable(true)",
        )
        if scrollable:
            try:
                scrollable[0].scroll("backward" if direction == "backward" else "forward")
                return True
            except Exception:
                pass
        size = driver.get_window_size()
        x = size["width"] // 2
        top = int(size["height"] * 0.25)
        bottom = int(size["height"] * 0.75)
        if direction == "backward":
            driver.swipe(x, top, x, bottom, 400)
        else:
            driver.swipe(x, bottom, x, top, 400)
        return True
    except Exception:
        return False


def _apply_action(driver, summary, decision: PlanDecision) -> bool:
    if decision.action == "done":
        return False
    if decision.action == "back":
        try:
            driver.back()
            time.sleep(0.6)
            return True
        except Exception:
            return False
    if decision.action == "scroll":
        ok = _do_scroll(driver, decision.scroll_direction or "forward")
        time.sleep(0.5)
        return ok
    if decision.action == "tap":
        el = _find_by_target(driver, summary, decision.target_id)
        if el is not None:
            try:
                el.click()
                time.sleep(0.8)
                return True
            except Exception:
                pass
        try:
            clickable = driver.find_elements(
                AppiumBy.ANDROID_UIAUTOMATOR,
                "new UiSelector().clickable(true)",
            )
            for c in clickable:
                try:
                    c.click()
                    time.sleep(0.8)
                    return True
                except Exception:
                    continue
        except Exception:
            return False
        return False
    return False


def crawl_app(
    app_package: str,
    max_screens: int = 20,
    output_dir: str | Path | None = None,
    *,
    use_ai: bool | None = None,
    ai_api_key: str | None = None,
    ai_provider: str | None = None,
    ai_model: str | None = None,
    appium_url: str = "http://localhost:4723",
    verbose: bool = True,
) -> list[str]:
    """
    Crawl an Android app and return kept screenshot paths.

    With AI (GLINT_AI_API_KEY / --ai): vision+tree planner scores screens and picks actions.
    Without AI: scroll/tap heuristic.
    """
    out = Path(output_dir) if output_dir else OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    settings: AiSettings | None = resolve_ai_settings(
        use_ai=use_ai,
        api_key=ai_api_key,
        provider=ai_provider,
        model=ai_model,
    )

    driver = _build_driver(app_package, appium_url=appium_url)
    kept: list[str] = []
    kept_labels: list[str] = []
    seen_fingerprints: set[str] = set()

    def log(msg: str) -> None:
        if verbose:
            print(msg)

    try:
        mode = f"AI ({settings.provider}/{settings.model})" if settings else "heuristic"
        log(f"Crawl mode: {mode}  package={app_package}  max={max_screens}")

        for step in range(max_screens):
            if settings and len(kept) >= settings.max_keep:
                log(f"Reached max keep ({settings.max_keep}); stopping.")
                break

            filename = f"crawl_{step + 1:04d}.png"
            path = capture_screenshot(filename=filename)
            if not path:
                log("Screenshot failed; stopping.")
                break

            dest = Path(path)
            if out.resolve() != OUTPUT_DIR.resolve():
                target = out / filename
                shutil.copy2(dest, target)
                dest = target
                path = str(dest)

            fp = f"{dest.stat().st_size}"
            try:
                raw = dest.read_bytes()
                stride = max(1, len(raw) // 64)
                fp = f"{len(raw)}:{sum(raw[::stride][:64])}"
            except OSError:
                pass

            page = _page_source(driver)
            summary = summarize_android_hierarchy(page, package=app_package)

            if settings:
                decision = plan_next_step(
                    settings,
                    summary=summary,
                    screenshot_path=path,
                    kept_labels=kept_labels,
                    step=step,
                    max_screens=max_screens,
                )
                if decision.source == "fallback":
                    decision = heuristic_decision(summary, step)
                    decision.reason = f"AI fallback → {decision.reason}"
            else:
                decision = heuristic_decision(summary, step)
                decision.keep = step == 0 or (step % 3 == 0 and fp not in seen_fingerprints)

            duplicate = fp in seen_fingerprints
            seen_fingerprints.add(fp)

            if decision.keep and not duplicate:
                label = decision.label or f"screen_{step + 1}"
                nice = out / f"{label}.png"
                if nice.name != dest.name:
                    if nice.exists():
                        nice = out / f"{label}_{step + 1}.png"
                    dest.replace(nice)
                    path = str(nice)
                    dest = nice
                kept.append(path)
                kept_labels.append(dest.stem)
                log(f"  KEEP  {dest.name}  score={decision.score:.2f}  ({decision.reason})")
            else:
                if dest.name.startswith("crawl_") and dest.exists():
                    try:
                        dest.unlink()
                    except OSError:
                        pass
                why = "duplicate" if duplicate else decision.reason or "low score"
                log(f"  skip  step={step + 1}  score={decision.score:.2f}  ({why})")

            moved = _apply_action(driver, summary, decision)
            if decision.action == "done":
                log("Planner signaled done.")
                break
            if not moved:
                log("No further UI action available; stopping.")
                break
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    if not kept:
        log("No store-worthy screens kept. Try --ai with a vision model, or capture manually.")
    return kept
