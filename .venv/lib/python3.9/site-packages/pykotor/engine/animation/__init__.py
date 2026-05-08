"""Abstract animation system interfaces.

This module provides abstract base classes for animation that can be implemented
by different rendering backends.

References:
----------

"""

from __future__ import annotations

from pykotor.engine.animation.base import (
    IAnimationController,
    IAnimationState,
    IAnimationManager,
)

__all__ = [
    "IAnimationController",
    "IAnimationManager",
    "IAnimationState",
]
