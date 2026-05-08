"""GL shaders and textures: KOTOR/plain/picker vertex and fragment shaders."""

from __future__ import annotations
from pykotor.gl.shader.shader import (
    Shader,
    KOTOR_VSHADER,
    KOTOR_FSHADER,
    PLAIN_VSHADER,
    PLAIN_FSHADER,
    PICKER_VSHADER,
    PICKER_FSHADER,
)
from pykotor.gl.shader.texture import Texture

__all__ = [
    "KOTOR_FSHADER",
    "KOTOR_VSHADER",
    "PICKER_FSHADER",
    "PICKER_VSHADER",
    "PLAIN_FSHADER",
    "PLAIN_VSHADER",
    "Shader",
    "Texture",
]
