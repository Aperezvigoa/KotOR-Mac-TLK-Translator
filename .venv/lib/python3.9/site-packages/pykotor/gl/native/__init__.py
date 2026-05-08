"""Native GL helpers: optional C extensions for rendering acceleration.

Modules:
    fastmath  - CFFI-based transform_bounds (legacy)
    gl_accel  - Compiled C extension for batch frustum culling, plane extraction,
                transform bounds, and matrix operations (preferred)
    _gl_accel - Low-level C extension (imported by gl_accel)
"""

from __future__ import annotations

try:
    from .fastmath import available, transform_bounds
except Exception:  # noqa: BLE001

    def available() -> bool:  # type: ignore[override]
        return False

    def transform_bounds(*args, **kwargs):  # type: ignore[override]
        raise RuntimeError("pykotor.gl.native.fastmath is unavailable")


__all__ = ["available", "transform_bounds"]
