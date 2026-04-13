import re


def parse_money(text: str) -> float:
    """
    Extract the first numeric amount from a string.
    Supports thousands separators and decimals.
    Examples: "$1,234.56", "ILS 55.64", "₪2,992.46"
    """
    t = text.strip()
    m = re.search(r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)", t)
    if not m:
        raise ValueError(f"Could not parse money from: {text!r}")
    return float(m.group(1).replace(",", ""))

