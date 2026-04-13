"""Parse primary / range listing prices from eBay SERP row text."""

from __future__ import annotations

import re

from src.utils.money import parse_money

# Currency-prefixed amounts as they appear on eBay search rows (locale-dependent).
_PRICE_TOKEN = re.compile(
    r"(?:US\s*\$|\$|ILS|₪|€|£|GBP)\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
    re.I,
)


def lowest_price_in_listing_text(text: str) -> float | None:
    """
    Return the lowest numeric price found in a result-row text blob.
    Handles simple prices and ranges like \"ILS 13.46 to ILS 14.27\".
    """
    values: list[float] = []
    for m in _PRICE_TOKEN.finditer(text):
        try:
            values.append(parse_money(m.group(1)))
        except ValueError:
            continue
    return min(values) if values else None
