from __future__ import annotations

from typing import Literal

from playwright.sync_api import Page, expect

LoadState = Literal["commit", "domcontentloaded", "load", "networkidle"]

# eBay is heavy; "domcontentloaded" often leaves a white tab before first paint.
_DEFAULT_NAV_TIMEOUT_MS = 90_000


class BasePage:
    def __init__(self, page: Page):
        self.page = page

    def goto(
        self,
        url: str,
        *,
        wait_until: LoadState = "domcontentloaded",
        timeout_ms: float = _DEFAULT_NAV_TIMEOUT_MS,
    ) -> None:
        self.page.goto(url, wait_until=wait_until, timeout=timeout_ms)

    def assert_url_contains(self, part: str) -> None:
        expect(self.page).to_have_url(lambda u: part in u)
