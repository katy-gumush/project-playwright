from __future__ import annotations

import os
import re

from playwright.sync_api import Error, Page

# Very short probes — most pages have no CAPTCHA, so timeouts must not add up.
_IFRAME_PROBE_MS = 50
_TEXT_PROBE_MS = 50

_CAPTCHA_IFRAME_SELECTORS = [
    "iframe[title*='reCAPTCHA']",
    "iframe[title*='recaptcha']",
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
]

_CAPTCHA_TEXT_PATTERNS = re.compile(
    r"captcha|prove you.re human|security check|unusual traffic"
    r"|verify (?:that )?you.re human|verify yourself|please verify yourself"
    r"|unauthorized users",
    re.I,
)


def challenge_like_visible(page: Page) -> bool:
    """
    Quick heuristic check for CAPTCHA / bot-challenge UI.
    Uses very short probe timeouts so it does not slow down normal page flows.
    """
    for sel in _CAPTCHA_IFRAME_SELECTORS:
        try:
            page.locator(sel).first.wait_for(state="visible", timeout=_IFRAME_PROBE_MS)
            return True
        except Error:
            continue

    try:
        body = page.locator("body").inner_text(timeout=500)
        if _CAPTCHA_TEXT_PATTERNS.search(body):
            return True
    except Exception:
        pass

    return False


def pause_if_challenge_visible(page: Page) -> None:
    """Pause for manual CAPTCHA; resume from Playwright Inspector."""
    if challenge_like_visible(page):
        page.pause()


def optional_first_checkpoint_pause(page: Page) -> None:
    """If EBAY_ALWAYS_PAUSE=1, pause once after first navigation (cookies / late challenge)."""
    if os.getenv("EBAY_ALWAYS_PAUSE") == "1":
        page.pause()
