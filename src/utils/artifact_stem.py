"""Filesystem-safe stems from pytest node names (parametrize-safe artifact prefixes)."""

from __future__ import annotations

import re
from pathlib import Path

_ARTIFACTS_DIR = Path("artifacts")


def artifact_stem_from_pytest_node(node_name: str) -> str:
    """Turn e.g. ``test_ebay[case_a]`` into a short safe filename prefix."""
    s = re.sub(r"[^\w\-\.]+", "_", node_name)
    s = re.sub(r"_+", "_", s).strip("._-")
    return s[:160] or "test"


def artifact_path(stem: str, filename: str, *, base: Path | None = None) -> Path:
    """``artifacts/<stem>_<filename>`` when stem is non-empty, else ``artifacts/<filename>``."""
    root = base or _ARTIFACTS_DIR
    if stem:
        return root / f"{stem}_{filename}"
    return root / filename
