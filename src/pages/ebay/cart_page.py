from __future__ import annotations

import re
from pathlib import Path

import allure
from playwright.sync_api import BrowserContext, expect

from src.pages.base_page import BasePage
from src.pages.ebay.challenge import challenge_like_visible, pause_if_challenge_visible
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

    def open(self) -> None:
        self.goto(self.CART_URL)

    def assert_loaded(self) -> None:
        expect(self.page).to_have_url(re.compile(r"cart\.ebay\.com"), timeout=60_000)

    def clear_cart(self) -> int:
        """
        Remove every item from the cart before the test run.
        Returns the number of items removed.
        """
        self.open()
        removed = 0
        # Real eBay DOM: role=button, accessible name starts with "Remove - <item title>"
        remove_btn = self.page.get_by_role("button", name=re.compile(r"^Remove", re.I))
        while remove_btn.count() > 0:
            try:
                remove_btn.first.click(timeout=5_000)
                # Wait for the row to be removed from the DOM, not for full network idle.
                self.page.wait_for_load_state("domcontentloaded", timeout=5_000)
                removed += 1
            except Exception:
                break
        return removed

    def _save_cart_screenshot(self) -> None:
        _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        path = _ARTIFACTS_DIR / "cart_summary.png"
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
        path = _ARTIFACTS_DIR / "cart_body_debug.txt"
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
                "Run with HEADLESS=0 and EBAY_MANUAL=1, complete the challenge, "
                "then click Resume in the Playwright Inspector."
            )

        if _EMPTY_CART_PATTERNS.search(body):
            raise AssertionError(
                "Cart appears empty — add-to-cart likely failed silently. "
                "Check artifacts/cart_summary.png for the page state."
            )

        raise AssertionError(
            "Could not parse cart subtotal. "
            "See artifacts/cart_summary.png and artifacts/cart_body_debug.txt."
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
        cart_total_max: float | None = None,
        context: BrowserContext | None = None,
        trace_path: str | None = None,
    ) -> float:
        """
        Assert cart subtotal does not exceed the effective budget.

        ``budget_per_item * items_count`` is the default cap (assignment shape).
        If ``cart_total_max`` is set (from JSON), the cap is the **stricter** of
        that product and ``cart_total_max`` (absolute cart ceiling).
        """
        max_total = budget_per_item * items_count
        if cart_total_max is not None:
            max_total = min(max_total, float(cart_total_max))

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
            f"(budget_per_item=${budget_per_item:.2f} × {items_count}"
            + ("; cart_total_max also applied" if cart_total_max is not None else "")
            + ")."
        )
        return sub
