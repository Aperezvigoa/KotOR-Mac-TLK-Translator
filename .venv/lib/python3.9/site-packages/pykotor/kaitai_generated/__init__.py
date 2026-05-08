"""Backward compatibility: ``pykotor.kaitai_generated`` mirrors ``bioware_kaitai_formats``.

Prefer ``from bioware_kaitai_formats.MOD import ...`` in new code.
"""

from __future__ import annotations

import importlib
from typing import Any


def __getattr__(name: str) -> Any:
    if name.startswith("_"):
        raise AttributeError(name)
    return importlib.import_module(f"bioware_kaitai_formats.{name}")
