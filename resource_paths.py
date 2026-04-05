"""Helpers for resolving bundled resources in source and frozen builds."""

from __future__ import annotations

import sys
from pathlib import Path


def get_runtime_base_dir() -> Path:
    """Return the directory that contains bundled app resources."""

    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent
