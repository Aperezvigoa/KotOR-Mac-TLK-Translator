"""GL scene package: camera, render objects, frustum culling, and module designer scene."""

from __future__ import annotations

from typing import Any

from pykotor.gl.scene.camera import Camera
from pykotor.gl.scene.frustum import CullingStats, Frustum
from pykotor.gl.models.mdl import Boundary
from pykotor.gl.scene.render_object import RenderObject

__all__ = ["Boundary", "Camera", "CullingStats", "Frustum", "RenderObject", "Scene"]


def __getattr__(name: str) -> Any:
    """Lazy-import Scene so lightweight imports (e.g. Camera-only tests) avoid PyOpenGL/extract deps."""
    if name == "Scene":
        from pykotor.gl.scene.scene import Scene

        return Scene
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
