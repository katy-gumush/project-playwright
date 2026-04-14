from __future__ import annotations

import re
import time
from pathlib import Path

import allure
from playwright.sync_api import BrowserContext, Page, expect

from src.pages.base_page import BasePage
from src.pages.ebay.challenge import challenge_like_visible, pause_if_challenge_visible
from src.utils.artifact_stem import artifact_path
from src.utils.money import parse_money

_ARTIFACTS_DIR = Path("artifacts")

_EMPTY_CART_PATTERNS = re.compile(
    r"cart is empty|your bag is empty|no items in your cart|start shopping",
    re.I,
)

_VERIFICATION_PATTERNS = re.compile(
    r"verify yourself|unusual traffic|security check|prove you.re human",
    re.I,
)


class EbayCartPage(BasePage):
    CART_URL = "https://cart.ebay.com/"

    def __init__(self, page: Page, *, artifact_stem: str = "") -> None:
        super().__init__(page)
        self._artifact_stem = artifact_stem

    def open(self) -> None:
        self.goto(self.CART_URL)

    def assert_loaded(self) -> None:
        expect(self.page).to_have_url(re.compile(r"cart\.ebay\.com"), timeout=60_000)

    def _cart_body_suggests_empty(self) -> bool:
        try:
            body = self.page.locator("body").inner_text(timeout=5_000)
        except Exception:
            return False
        return bool(_EMPTY_CART_PATTERNS.search(body))

    def _remove_line_buttons(self):
        # Line rows: accessible name is typically "Remove - <item title>".
        return self.page.get_by_role("button", name=re.compile(r"^Remove", re.I))

    def _wait_remove_buttons_decreased(self, before: int, *, timeout_ms: int = 25_000) -> bool:
        """
        Wait until this locator matches fewer nodes than ``before``, or the cart reads empty.

        eBay often exposes **more than one** matching Remove button per line (e.g. duplicate
        layout nodes). A single line removal can drop the count by 2+
        """
        deadline = time.monotonic() + timeout_ms / 1000.0
        while time.monotonic() < deadline:
            if self._cart_body_suggests_empty():
                return True
            if self._remove_line_buttons().count() < before:
                return True
            self.page.wait_for_timeout(120)
        return self._cart_body_suggests_empty() or self._remove_line_buttons().count() < before

    def clear_cart(self) -> int:
        """
        Remove every line item from the cart (multiple removes in a loop).

        After each click, waits until the Remove control count drops (or empty-cart
        copy appears). The last row often repaints slowly or sits under a sticky bar,
        so we scroll into view and retry with ``force=True`` when needed.
        """
        self.open()
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=15_000)
        except Exception:
            pass
        try:
            self.page.keyboard.press("Escape")
        except Exception:
            pass

        removed = 0
        consecutive_failures = 0
        max_consecutive_failures = 8

        while True:
            remove_btn = self._remove_line_buttons()
            before = remove_btn.count()
            if before == 0 or self._cart_body_suggests_empty():
                break

            target = remove_btn.first
            try:
                target.scroll_into_view_if_needed(timeout=10_000)
            except Exception:
                pass

            def _click_remove(*, force: bool) -> None:
                target.click(timeout=10_000, force=force)

            try:
                _click_remove(force=False)
            except Exception:
                try:
                    _click_remove(force=True)
                except Exception:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        break
                    self.page.wait_for_timeout(700)
                    continue

            progressed = self._wait_remove_buttons_decreased(before, timeout_ms=25_000)
            if not progressed:
                if self._cart_body_suggests_empty():
                    removed += 1
                    consecutive_failures = 0
                    break
                try:
                    rb = self._remove_line_buttons()
                    rb.first.scroll_into_view_if_needed(timeout=10_000)
                    rb.first.click(timeout=10_000, force=True)
                except Exception:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        break
                    self.page.wait_for_timeout(700)
                    continue
                if not self._wait_remove_buttons_decreased(before, timeout_ms=25_000):
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        break
                    self.page.wait_for_timeout(700)
                    continue

            removed += 1
            consecutive_failures = 0

        return removed

    def _save_cart_screenshot(self) -> None:
        _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        path = artifact_path(self._artifact_stem, "cart_summary.png")
        try:
            self.page.screenshot(path=str(path), full_page=True)
            with open(path, "rb") as f:
                allure.attach(
                    f.read(),
                    name="cart_summary",
                    attachment_type=allure.attachment_type.PNG,
                )
        except Exception:
            pass

    def _dump_cart_body(self, body: str) -> None:
        _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        path = artifact_path(self._artifact_stem, "cart_body_debug.txt")
        try:
            path.write_text(body[:50_000], encoding="utf-8")
            allure.attach(
                body[:10_000],
                name="cart_body_debug",
                attachment_type=allure.attachment_type.TEXT,
            )
        except Exception:
            pass

    def get_subtotal(self) -> float:
        """
        Parse the cart subtotal from the page body text.
        Prefers US $ amounts; falls back to any local currency (ILS, GBP, €, etc.).
        Screenshot is taken before parsing so the page state is always captured.
        """
        self.assert_loaded()

        if challenge_like_visible(self.page):
            pause_if_challenge_visible(self.page)

        self._save_cart_screenshot()

        body = self.page.locator("body").inner_text(timeout=8_000)
        sub = self._parse_subtotal_from_blob(body)
        if sub is not None:
            return sub

        self._dump_cart_body(body)

        if _VERIFICATION_PATTERNS.search(body):
            raise AssertionError(
                "eBay returned a human-verification page instead of the cart. "
                "Run with HEADLESS=0, complete the challenge, "
                "then click Resume in the Playwright Inspector."
            )

        if _EMPTY_CART_PATTERNS.search(body):
            raise AssertionError(
                "Cart appears empty — add-to-cart likely failed silently. "
                f"Check {artifact_path(self._artifact_stem, 'cart_summary.png')} for the page state."
            )

        raise AssertionError(
            "Could not parse cart subtotal. "
            f"See {artifact_path(self._artifact_stem, 'cart_summary.png')} "
            f"and {artifact_path(self._artifact_stem, 'cart_body_debug.txt')}."
        )

    @staticmethod
    def _parse_subtotal_from_blob(blob: str) -> float | None:
        """
        Extract the cart subtotal from a body text dump.

        Priority:
          1. US $ amount near a subtotal keyword (eBay.com base currency)
          2. Any currency amount near a subtotal keyword (ILS, GBP, €, etc.)
          3. First US $ amount anywhere in the blob (Israeli cart only shows
             the USD item price; local currency is in the order summary)
        """
        usd = r"[0-9][0-9,]*\.[0-9]{2}"
        any_price = r"(?:US\s*\$|\$|ILS|GBP|₪|€|£|AU\$|CA\$)?\s*[0-9][0-9,]*\.[0-9]{2}"

        usd_near_subtotal = [
            rf"(?i)(?:Item\s+)?subtotal[\s\S]{{0,120}}?US\s*\$\s*({usd})",
            rf"(?i)Order\s+(?:subtotal|total)[\s\S]{{0,120}}?US\s*\$\s*({usd})",
            rf"(?i)(?:summary|checkout|order)[\s\S]{{0,300}}?US\s*\$\s*({usd})",
        ]
        for pat in usd_near_subtotal:
            m = re.search(pat, blob)
            if m:
                try:
                    return parse_money(m.group(1))
                except Exception:
                    continue

        local_near_subtotal = [
            rf"(?i)Subtotal[\s\S]{{0,60}}?({any_price})",
            rf"(?i)(?:Item\s+)?subtotal[\s\S]{{0,60}}?({any_price})",
            rf"(?i)Order\s+(?:subtotal|total)[\s\S]{{0,60}}?({any_price})",
            rf"(?i)Items?\s*\(\d+\)[\s\S]{{0,60}}?({any_price})",
            rf"(?i)(?:total|subtotal)[\s\S]{{0,80}}?({any_price})",
        ]
        for pat in local_near_subtotal:
            m = re.search(pat, blob)
            if m:
                try:
                    return parse_money(m.group(1))
                except Exception:
                    continue

        m = re.search(rf"US\s*\$\s*({usd})", blob)
        if m:
            try:
                return parse_money(m.group(1))
            except Exception:
                pass

        return None

    def assert_cart_total_not_exceeds(
        self,
        budget_per_item: float,
        items_count: int,
        *,
        context: BrowserContext | None = None,
        trace_path: str | None = None,
    ) -> float:
        """Assert cart subtotal ≤ budget_per_item * items_count."""
        max_total = budget_per_item * items_count

        if context is not None and trace_path is not None:
            try:
                _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
                context.tracing.stop(path=trace_path)
                allure.attach.file(
                    trace_path,
                    name="cart_trace",
                    attachment_type=allure.attachment_type.ZIP,
                )
            except Exception:
                pass

        sub = self.get_subtotal()

        assert sub <= max_total, (
            f"Cart subtotal ${sub:.2f} exceeds allowed total ${max_total:.2f} "
            f"(budget_per_item=${budget_per_item:.2f} × {items_count})."
        )
        return sub
