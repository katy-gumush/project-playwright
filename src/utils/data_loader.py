from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CREDENTIALS_PATH = Path("data/ebay/credentials.json")
_CREDENTIALS_EXAMPLE = Path("data/ebay/credentials.example.json")


def load_test_data(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_credentials(path: str | Path = _CREDENTIALS_PATH) -> tuple[str, str]:
    """
    Load eBay username and password from a JSON credentials file.

    Expected format:
        { "username": "...", "password": "..." }

    Copy data/ebay/credentials.example.json to data/ebay/credentials.json
    and fill in your details. The real credentials file is gitignored.

    Raises FileNotFoundError with a helpful message if the file is missing.
    Raises ValueError if either field is empty.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Credentials file not found: {p}\n"
            f"Copy {_CREDENTIALS_EXAMPLE} → {p} and fill in your eBay username and password."
        )
    data = load_test_data(p)
    username: str = data.get("username", "").strip()
    password: str = data.get("password", "").strip()
    if not username or not password:
        raise ValueError(
            f"Credentials in {p} are empty. "
            "Fill in 'username' and 'password' before running the test."
        )
    return username, password
