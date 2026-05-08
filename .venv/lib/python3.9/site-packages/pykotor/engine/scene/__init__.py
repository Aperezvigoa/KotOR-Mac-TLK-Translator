"""Abstract scene graph interfaces for rendering backends.

Scene graph contracts used by PyKotor tooling (area load, VIS-driven room sets, etc.).
Executable-specific scene internals are documented only in ``wiki/reverse_engineering_findings.md``.
"""

from __future__ import annotations

from pykotor.engine.scene.base import ISceneGraph, FogProperties

__all__ = [
    "FogProperties",
    "ISceneGraph",
]
