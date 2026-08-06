import time
from pathlib import Path

from .capture import capture_screenshot

try:
    from appium import webdriver
    from appium.webdriver.common.appiumby import AppiumBy

    APPIUM_AVAILABLE = True
except ImportError:
    APPIUM_AVAILABLE = False


DESIRED_CAPS = {
    "platformName": "Android",
    "automationName": "UiAutomator2",
    "noReset": True,
}


def crawl_app(app_package: str, max_screens: int = 20, output_dir: str | None = None) -> list[str]:
    if not APPIUM_AVAILABLE:
        raise RuntimeError("Appium is not installed. Install with: pip install Appium-Python-Client")

    driver = webdriver.Remote("http://localhost:4723", DESIRED_CAPS)
    paths = []

    try:
        for i in range(max_screens):
            path = capture_screenshot(filename=f"crawl_{i+1:04d}.png")
            if path:
                paths.append(path)

            scrollable = driver.find_elements(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().scrollable(true)',
            )
            if scrollable:
                scrollable[0].scroll("forward")
                time.sleep(0.5)
            else:
                clickable = driver.find_elements(
                    AppiumBy.ANDROID_UIAUTOMATOR,
                    "new UiSelector().clickable(true)",
                )
                tapped = False
                for el in clickable:
                    try:
                        el.click()
                        time.sleep(1)
                        tapped = True
                        break
                    except Exception:
                        continue
                if not tapped:
                    break
    finally:
        driver.quit()

    return paths
