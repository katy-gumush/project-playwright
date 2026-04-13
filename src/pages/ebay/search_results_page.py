from __future__ import annotations

import re
from urllib.parse import urlencode

from playwright.sync_api import Page, expect

from src.pages.base_page import BasePage
from src.utils.listing_price import lowest_price_in_listing_text


def build_ebay_search_url(
    query: str,
    *,
    max_price: float | None = None,
    min_price: float | None = None,
    buy_it_now_only: bool = True,
) -> str:
    """Search URL with price bounds via eBay query params (_udlo / _udhi) and optional Buy It Now."""
    params: dict[str, str] = {"_nkw": query}
    if max_price is not None:
        params["_udhi"] = str(int(max_price)) if float(max_price).is_integer() else str(max_price)
    if min_price is not None:
        params["_udlo"] = str(int(min_price)) if float(min_price).is_integer() else str(min_price)
    if buy_it_now_only:
        params["LH_BIN"] = "1"
    return "https://www.ebay.com/sch/i.html?" + urlencode(params)


def _next_page_href(page: Page) -> str | None:
    """Next SERP page (eBay standard pagination control)."""
    loc = page.locator("a.pagination__next").first
    try:
        loc.wait_for(state="visible", timeout=2_000)
        href = loc.get_attribute("href")
        return href or None
    except Exception:
        return None


class EbaySearchResultsPage(BasePage):
    """eBay search results (SERP)."""

    # Legacy ``s-item`` rows; current SERP uses ``s-card`` (same ``ul.srp-results`` list).
    _RESULT_ROWS = "ul.srp-results li.s-item, ul.srp-results li.s-card"
    _ITEM_LINK = 'a[href*="/itm/"]'
    _PRICE_CELL = ".s-item__price, .s-card__price"

    def goto_filtered_search(
        self,
        query: str,
        *,
        max_price: float | None = None,
        min_price: float | None = None,
        buy_it_now_only: bool = True,
    ) -> None:
        url = build_ebay_search_url(
            query,
            max_price=max_price,
            min_price=min_price,
            buy_it_now_only=buy_it_now_only,
        )
        self.goto(url)
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=20_000)
        except Exception:
            pass

    def _wait_result_rows(self) -> None:
        """SERPs paint cards after DCL; ``/itm/`` in the header is not enough."""
        self.page.locator(self._RESULT_ROWS).first.wait_for(state="visible", timeout=45_000)

    def assert_results_loaded(self) -> None:
        expect(self.page).to_have_url(re.compile(r"sch/i\.html"), timeout=60_000)
        h1 = self.page.locator("h1").first
        expect(h1).to_be_visible(timeout=30_000)
        expect(h1).to_contain_text(re.compile(r"result", re.I), timeout=30_000)
        self._wait_result_rows()

    @staticmethod
    def _canonical_itm_url(href: str) -> str | None:
        m = re.search(r"(https?://[^?#]*?/itm/\d+)", href)
        return m.group(1) if m else None

    def _price_from_row(self, row) -> float | None:
        """Main listing price from the price cell only (validated on live SERP via browser)."""
        cell = row.locator(self._PRICE_CELL).first
        if cell.count() == 0:
            return None
        try:
            text = cell.inner_text(timeout=2_000)
        except Exception:
            return None
        return lowest_price_in_listing_text(text)

    def search_items_by_name_under_price(
        self,
        query: str,
        max_price: float,
        limit: int = 5,
        *,
        min_price: float | None = None,
        buy_it_now_only: bool = True,
    ) -> list[str]:
        """
        Search with URL price cap, walk ``ul.srp-results`` listing rows (``li.s-item`` or ``li.s-card``),
        keep rows whose price cell parses to ≤ ``max_price``, follow ``a.pagination__next``.
        """
        self.goto_filtered_search(
            query,
            max_price=max_price,
            min_price=min_price,
            buy_it_now_only=buy_it_now_only,
        )
        self.assert_results_loaded()

        urls: list[str] = []
        seen: set[str] = set()

        while len(urls) < limit:
            rows = self.page.locator(self._RESULT_ROWS)
            n = rows.count()
            if n == 0:
                break
            for i in range(n):
                if len(urls) >= limit:
                    break
                row = rows.nth(i)
                link = row.locator(self._ITEM_LINK).first
                if link.count() == 0:
                    continue
                href = link.get_attribute("href") or ""
                canonical = self._canonical_itm_url(href)
                if not canonical or canonical in seen:
                    continue

                parsed = self._price_from_row(row)
                if parsed is None or parsed > float(max_price):
                    continue

                seen.add(canonical)
                urls.append(canonical)

            if len(urls) >= limit:
                break

            next_href = _next_page_href(self.page)
            if not next_href:
                break
            self.goto(next_href)
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=15_000)
            except Exception:
                pass
            self._wait_result_rows()

        return urls

    def _listing_links(self):
        return self.page.locator(self._ITEM_LINK)
