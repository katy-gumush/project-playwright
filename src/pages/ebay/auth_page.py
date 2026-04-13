from __future__ import annotations

import re

from playwright.sync_api import expect

from src.pages.base_page import BasePage
from src.pages.ebay.challenge import challenge_like_visible, pause_if_challenge_visible

_SIGN_IN_URL = "https://signin.ebay.com/ws/eBayISAPI.dll?SignIn"

# eBay sign-in is a two-step form: username first, then password on the next screen.
_USERNAME_SELECTOR = (
    "#userid, input[name='userid'], input[name='email'], #email, "
    "input[type='email'], input[placeholder*='Email'], input[placeholder*='email'], "
    "input[placeholder*='Phone']"
)
_PASSWORD_SELECTOR = "#pass, input[name='pass'], input[type='password']"
_CONTINUE_BTN = "#signin-continue-btn, button[id*='continue'], input[id*='continue']"
_SIGNIN_BTN = "#sgnBt, button[id*='sign'], input[id*='sign'], button[type='submit']"

# Selectors that confirm a successful login (account menu / username indicator).
_LOGGED_IN_INDICATORS = [
    "#gh-ug",           # username greeting element
    "a[href*='/mye/myebay']",
    "[aria-label*='My eBay']",
    "[data-testid*='account']",
]


class EbayAuthPage(BasePage):
    """
    Handles eBay authentication.

    Uses a two-step sign-in flow (username → Continue → password → Sign in).
    If a CAPTCHA or challenge appears at any point, execution pauses via
    page.pause() so the user can solve it manually in the headed browser,
    then click Resume in the Playwright Inspector to continue.

    Credentials are loaded from data/ebay/credentials.json (gitignored).
    Copy data/ebay/credentials.example.json and fill in your details.
    """

    @staticmethod
    def _is_challenge_or_captcha_url(url: str) -> bool:
        u = url.lower()
        return any(
            x in u
            for x in ("splashui/captcha", "/captcha", "challenge", "verify", "riskanalytics")
        )

    def login(self, username: str, password: str, *, home_url: str = "https://www.ebay.com/") -> None:
        """
        Full eBay sign-in: navigate to the sign-in page, fill credentials,
        pause for any CAPTCHA, then verify the account menu is visible.
        """
        self.goto(_SIGN_IN_URL)

        if self._is_challenge_or_captcha_url(self.page.url):
            pause_if_challenge_visible(self.page)
            self.page.pause()

        # ── Step 1: username field ───────────────────────────────────────────
        user_field = self.page.locator(_USERNAME_SELECTOR).first
        try:
            expect(user_field).to_be_visible(timeout=12_000)
        except AssertionError:
            if self._is_challenge_or_captcha_url(self.page.url) or challenge_like_visible(self.page):
                self.page.pause()
            expect(user_field).to_be_visible(timeout=45_000)
        user_field.fill(username)

        if challenge_like_visible(self.page):
            self.page.pause()

        # Click the Continue button (eBay separates username and password screens).
        continue_btn = self.page.locator(_CONTINUE_BTN).first
        if continue_btn.count() > 0 and continue_btn.is_visible():
            continue_btn.click()
        else:
            user_field.press("Enter")

        # ── Step 2: password field (may be on a new screen) ─────────────────
        pass_field = self.page.locator(_PASSWORD_SELECTOR).first
        expect(pass_field).to_be_visible(timeout=30_000)

        if challenge_like_visible(self.page):
            self.page.pause()

        pass_field.fill(password)

        signin_btn = self.page.locator(_SIGNIN_BTN).first
        if signin_btn.count() > 0 and signin_btn.is_visible():
            signin_btn.click()
        else:
            pass_field.press("Enter")

        # ── Step 3: handle post-login challenge / 2FA ────────────────────────
        # Pause for any verification step (2FA code, SMS, CAPTCHA).
        try:
            self.page.wait_for_url(re.compile(r"ebay\.com(?!/signin)"), timeout=15_000)
        except Exception:
            # Still on sign-in domain — likely a 2FA / challenge screen.
            self.page.pause()
            self.page.wait_for_url(re.compile(r"ebay\.com(?!/signin)"), timeout=120_000)

        if challenge_like_visible(self.page):
            self.page.pause()

        # ── Step 4: verify sign-in succeeded ────────────────────────────────
        self._assert_logged_in()

    def _assert_logged_in(self) -> None:
        """Verify at least one account-menu indicator is visible on the page."""
        for sel in _LOGGED_IN_INDICATORS:
            loc = self.page.locator(sel).first
            try:
                loc.wait_for(state="visible", timeout=8_000)
                return
            except Exception:
                continue
        # If no indicator found, pause so the user can inspect the state.
        self.page.pause()

    def login_as_guest(self, home_url: str = "https://www.ebay.com/") -> None:
        """
        Navigate to the eBay homepage without signing in (guest session).
        Kept for backwards compatibility; prefer login() with credentials.
        """
        self.goto(home_url)
        expect(self.page).to_have_url(re.compile(r"ebay\.com", re.I), timeout=60_000)
        self.page.locator("#gh-la, header a[href*='ebay.com']").first.wait_for(
            state="visible",
            timeout=45_000,
        )
