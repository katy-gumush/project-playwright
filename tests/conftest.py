import os
import sys
from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def playwright() -> Playwright:
    with sync_playwright() as p:
        yield p


def _headless() -> bool:
    return os.getenv("HEADLESS", "1") not in {"0", "false", "False"}


def _slow_mo() -> int:
    return int(os.getenv("SLOWMO_MS", "0"))


def _navigation_timeout_ms() -> int:
    return int(os.getenv("NAVIGATION_TIMEOUT_MS", "90000"))


def _browser_launch_kwargs() -> dict:
    """Headed Chromium on macOS can show a white tab until first paint; reduce background throttling."""
    kwargs: dict = {"headless": _headless(), "slow_mo": _slow_mo()}
    channel = os.getenv("PLAYWRIGHT_CHANNEL", "").strip()
    if channel:
        kwargs["channel"] = channel
    if os.getenv("BROWSER", "chromium") == "chromium" and sys.platform == "darwin":
        kwargs["args"] = [
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
        ]
    return kwargs


def _context_kwargs() -> dict:
    return {
        "locale": os.getenv("LOCALE", "en-US"),
        "user_agent": os.getenv(
            "USER_AGENT",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        ),
        "viewport": {"width": 1400, "height": 900},
    }


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Browser:
    browser_name = os.getenv("BROWSER", "chromium")
    b = getattr(playwright, browser_name).launch(**_browser_launch_kwargs())
    yield b
    b.close()


@pytest.fixture()
def context(browser: Browser) -> BrowserContext:
    ctx = browser.new_context(**_context_kwargs())
    yield ctx
    ctx.close()


@pytest.fixture()
def page(context: BrowserContext) -> Page:
    p = context.new_page()
    p.set_default_navigation_timeout(_navigation_timeout_ms())
    yield p
    p.close()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call":
        setattr(item, "rep_call", rep)


@pytest.fixture(autouse=True)
def screenshot_on_failure(request, page: Page):
    yield
    rep = getattr(request.node, "rep_call", None)
    if rep and rep.failed:
        try:
            page.screenshot(path="artifacts/failure.png", full_page=True)
        except Exception:
            pass
