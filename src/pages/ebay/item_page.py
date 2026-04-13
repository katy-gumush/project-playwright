from __future__ import annotations

import random
import re
from pathlib import Path

import allure
from playwright.sync_api import expect

from src.pages.base_page import BasePage
from src.pages.ebay.challenge import pause_if_challenge_visible

_ARTIFACTS_DIR = Path("artifacts")

_UNAVAILABLE_PATTERNS = re.compile(
    r"there is an issue with|item is no longer available|this listing has ended"
    r"|out of stock|item not available|currently unavailable|sold out"
    r"|see if this item is available elsewhere|item unavailable",
    re.I,
)


class ItemUnavailableError(Exception):
    """Raised when an eBay listing cannot be added to cart (ended, out of stock, etc.)."""


class EbayItemPage(BasePage):
    def assert_loaded(self) -> None:
        expect(self.page).to_have_url(re.compile(r"/itm/"), timeout=30_000)

    def _check_unavailable(self) -> None:
        """Raise ItemUnavailableError if the page signals the listing cannot be purchased."""
        try:
            body = self.page.locator("body").inner_text(timeout=2_000)
            if _UNAVAILABLE_PATTERNS.search(body):
                raise ItemUnavailableError(
                    f"Listing unavailable: {self.page.url!r}"
                )
        except ItemUnavailableError:
            raise
        except Exception:
            pass

    def _check_for_signin_redirect(self) -> bool:
        """Return True if eBay redirected to a sign-in wall after add-to-cart."""
        if "signin.ebay.com" in self.page.url:
            return True
        try:
            body = self.page.locator("body").inner_text(timeout=1_500)
            return bool(re.search(r"sign in to complete|please sign in", body, re.I))
        except Exception:
            return False

    def select_variants_if_present(self) -> None:
        """
        Best-effort random variant selection for <select> dropdowns and swatch buttons.
        Skips silently when no variants are found or selection fails.
        """
        for sel_el in self.page.locator("select").all():
            try:
                options = sel_el.locator("option").all()
                available = [
                    o for o in options
                    if o.get_attribute("disabled") is None
                    and o.get_attribute("value") not in (None, "", "0", "-1")
                ]
                if available:
                    value = random.choice(available).get_attribute("value")
                    if value:
                        sel_el.select_option(value=value, timeout=3_000)
            except Exception:
                continue

        for sel in (
            '[class*="swatch"] button:not([disabled])',
            '[class*="variation"] button:not([disabled])',
        ):
            buttons = self.page.locator(sel).all()
            if buttons:
                try:
                    random.choice(buttons).click(timeout=3_000)
                except Exception:
                    continue

    def add_to_cart(self) -> None:
        """
        Click 'Add to cart' and wait for the confirmation modal.

        Raises:
            ItemUnavailableError: listing is ended / out-of-stock / auction-only / no button.
            AssertionError: sign-in wall detected after clicking.
        """
        self.assert_loaded()

        pause_if_challenge_visible(self.page)

        self._check_unavailable()
        self.select_variants_if_present()

        # Accessible name is usually "Add to cart"; locale may add punctuation/spacing.
        btn = self.page.get_by_role("button", name=re.compile(r"add\s*to\s*cart", re.I))
        if btn.count() == 0:
            btn = self.page.get_by_role("link", name=re.compile(r"add\s*to\s*cart", re.I))
        if btn.count() == 0:
            self._check_unavailable()
            raise ItemUnavailableError(
                f"'Add to cart' control not found on {self.page.url!r}. "
                "The listing may be auction-only or region-restricted."
            )

        expect(btn.first).to_be_visible(timeout=10_000)
        btn.first.click()

        # eBay shows a "See in cart" / "Checkout N items" dialog after a successful add.
        try:
            self.page.wait_for_selector(
                'a:has-text("See in cart"), a:has-text("Checkout")',
                timeout=5_000,
            )
        except Exception:
            pass  # dialog may not appear on every locale/layout

        if self._check_for_signin_redirect():
            raise AssertionError(
                "eBay redirected to sign-in after 'Add to cart'. "
                "The listing requires a logged-in account."
            )

    def add_items_to_cart(self, urls: list[str]) -> list[str]:
        """
        Navigate to each URL, add it to cart with random variant selection,
        and save a per-item screenshot to artifacts/ + Allure.

        Unavailable listings are skipped (not a test failure).
        Returns the list of URLs that were successfully added.
        """
        _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        added: list[str] = []

        for idx, url in enumerate(urls, start=1):
            with allure.step(f"Add item {idx}/{len(urls)}: {url}"):
                self.goto(url)
                try:
                    self.add_to_cart()
                    added.append(url)
                except ItemUnavailableError as exc:
                    allure.attach(
                        str(exc),
                        name=f"item_{idx:02d}_skipped",
                        attachment_type=allure.attachment_type.TEXT,
                    )
                    continue

                screenshot_path = _ARTIFACTS_DIR / f"item_{idx:02d}_added.png"
                try:
                    self.page.screenshot(path=str(screenshot_path), full_page=True)
                    with open(screenshot_path, "rb") as f:
                        allure.attach(
                            f.read(),
                            name=f"item_{idx:02d}_added",
                            attachment_type=allure.attachment_type.PNG,
                        )
                except Exception:
                    pass

        return added
