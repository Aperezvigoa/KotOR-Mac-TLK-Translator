"""PyKotorGL – OpenGL rendering module for PyKotor. Requires PyGLM."""

from __future__ import annotations

import glm as glm  # noqa: PLC0414  # PyGLM (package: PyGLM, import: glm)

from glm import (
    cross,
    decompose,
    eulerAngles,
    inverse,
    length,
    mat4,
    mat4_cast,
    normalize,
    ortho,
    perspective,
    quat,
    rotate,
    translate,
    unProject,
    value_ptr,
    vec2,
    vec3,
    vec4,
)

GLM_AVAILABLE = True  # kept for any external callers that check this flag

__all__ = [
    "GLM_AVAILABLE",
    "cross",
    "decompose",
    "eulerAngles",
    "glm",
    "inverse",
    "length",
    "mat4",
    "mat4_cast",
    "normalize",
    "ortho",
    "perspective",
    "quat",
    "rotate",
    "translate",
    "unProject",
    "value_ptr",
    "vec2",
    "vec3",
    "vec4",
]
