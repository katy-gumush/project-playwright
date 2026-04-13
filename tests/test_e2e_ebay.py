"""
eBay E2E: sign in with credentials, search + price filter (or use pinned item URLs),
add to cart with variant selection, assert cart subtotal.

Opt-in: EBAY_MANUAL=1  (HEADLESS=0 strongly recommended).
If a CAPTCHA / 2FA screen appears, the test pauses via page.pause() — solve it
manually in the headed browser, then click Resume in the Playwright Inspector.

Credentials: copy data/ebay/credentials.example.json → data/ebay/credentials.json
and fill in your eBay username and password. The credentials file is gitignored.

Core APIs (see page objects): ``search_items_by_name_under_price``,
``EbayItemPage.add_items_to_cart``, ``EbayCartPage.assert_cart_total_not_exceeds``.

Use eBay only in line with their terms and policies.
"""

from __future__ import annotations

import os
from pathlib import Path

import allure
import pytest
from playwright.sync_api import BrowserContext, Page

from src.pages.ebay import (
    EbayAuthPage,
    EbayCartPage,
    EbayItemPage,
    EbaySearchResultsPage,
    optional_first_checkpoint_pause,
    pause_if_challenge_visible,
)
from src.utils.data_loader import load_credentials, load_test_data

_TRACE_PATH = str(Path("artifacts") / "cart_trace.zip")
_CREDENTIALS_PATH = "data/ebay/credentials.json"

DEFAULT_ADD_LIMIT = 5


def _cases():
    data = load_test_data("data/ebay/cases.json")
    base_url = data["base_url"]
    for c in data["cases"]:
        yield base_url, c


_EBAY_PARAMS = list(_cases())


@pytest.mark.ebay
@pytest.mark.skipif(
    os.getenv("EBAY_MANUAL") != "1",
    reason="Set EBAY_MANUAL=1 (HEADLESS=0 recommended) for eBay E2E",
)
@pytest.mark.parametrize(
    "base_url,case",
    _EBAY_PARAMS,
    ids=[c["name"] for _, c in _EBAY_PARAMS],
)
def test_ebay_search_filter_cart_assert_total(
    page: Page, context: BrowserContext, base_url: str, case: dict
) -> None:
    auth = EbayAuthPage(page)
    search = EbaySearchResultsPage(page)
    item = EbayItemPage(page)
    cart = EbayCartPage(page)

    add_limit: int = int(case.get("add_limit", DEFAULT_ADD_LIMIT))
    max_price: float = float(case["max_price"])
    cart_total_max: float | None = (
        float(case["cart_total_max"]) if case.get("cart_total_max") is not None else None
    )

    # ── 1. Authentication ──────────────────────────────────────────────────
    with allure.step("Authentication — sign in to eBay"):
        username, password = load_credentials(_CREDENTIALS_PATH)
        auth.login(username, password, home_url=base_url)
        optional_first_checkpoint_pause(page)
        pause_if_challenge_visible(page)

    # ── 1b. Clear cart (avoid "already in cart" blocking Add to cart) ──────
    with allure.step("Clear cart before test"):
        removed = cart.clear_cart()
        allure.attach(
            f"Removed {removed} item(s) from cart.",
            name="cart_cleared",
            attachment_type=allure.attachment_type.TEXT,
        )

    # ── 2–3. searchItemsByNameUnderPrice (URL filter + sidebar + XPath rows + price) ──
    with allure.step(
        f"searchItemsByNameUnderPrice({case['search_text']!r}, {max_price}, {add_limit})"
    ):
        urls = search.search_items_by_name_under_price(
            case["search_text"],
            max_price,
            limit=add_limit,
            min_price=float(case["min_price"]) if case.get("min_price") is not None else None,
            buy_it_now_only=bool(case.get("buy_it_now_only", True)),
        )
        assert urls, "No item URLs under max_price — widen search or raise max_price in cases.json."
        assert len(urls) >= add_limit, (
            f"searchItemsByNameUnderPrice returned {len(urls)} URL(s) but add_limit is {add_limit}. "
            "Raise max_price, try another search_text, or lower add_limit in data/ebay/cases.json."
        )
        allure.attach(
            "\n".join(urls),
            name="collected_item_urls",
            attachment_type=allure.attachment_type.TEXT,
        )
        pause_if_challenge_visible(page)

    # ── 4. Add all items to cart (addItemsToCart) ──────────────────────────
    with allure.step(f"addItemsToCart — {len(urls)} item(s), variant selection + screenshot each"):
        Path("artifacts").mkdir(parents=True, exist_ok=True)
        tracing_enabled = os.getenv("EBAY_TRACE") == "1"
        if tracing_enabled:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
        added_urls = item.add_items_to_cart(urls)
        pause_if_challenge_visible(page)
        assert added_urls, (
            "No items were added to cart — listings skipped (unavailable) or blocked. "
            "Try another search term or a higher max_price in data/ebay/cases.json."
        )
        assert len(added_urls) == len(urls), (
            f"Only {len(added_urls)} of {len(urls)} collected item(s) were added — "
            "unavailable listings or checkout blocks. Raise max_price / change search_text, "
            "or lower add_limit in data/ebay/cases.json."
        )
        allure.attach(
            f"Candidates: {len(urls)}  |  Added: {len(added_urls)}  |  Skipped: {len(urls) - len(added_urls)}",
            name="add_to_cart_summary",
            attachment_type=allure.attachment_type.TEXT,
        )

    # ── 5. Assert cart total (assertCartTotalNotExceeds) ───────────────────
    _cap = min(max_price * len(added_urls), cart_total_max) if cart_total_max is not None else max_price * len(added_urls)
    with allure.step(
        f"assertCartTotalNotExceeds — cap ${_cap:.2f} "
        f"(per-item ${max_price:.2f} × {len(added_urls)}"
        + (f", cart_total_max ${cart_total_max:.2f})" if cart_total_max is not None else ")")
    ):
        cart.open()
        pause_if_challenge_visible(page)
        sub = cart.assert_cart_total_not_exceeds(
            budget_per_item=max_price,
            items_count=len(added_urls),
            cart_total_max=cart_total_max,
            context=context if tracing_enabled else None,
            trace_path=_TRACE_PATH if tracing_enabled else None,
        )
        allure.attach(
            str(sub),
            name="cart_subtotal",
            attachment_type=allure.attachment_type.TEXT,
        )
