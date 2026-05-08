"""Python wrapper for _render2d_accel C extension.

Provides batch point-in-triangle, distance calculation, and material
grouping for the 2D walkmesh/map renderer. Falls back to pure-Python
implementations when the C extension is unavailable.
"""

from __future__ import annotations

import array
import struct

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pykotor.resource.formats.bwm.bwm_data import BWM

# Try importing the C extension.
try:
    from pykotor.gl.native._render2d_accel import (
        batch_compute_aabb_2d,
        batch_distances_2d,
        batch_distances_2d_filtered,
        batch_face_at_direct,
        batch_group_faces_by_material,
        batch_point_in_triangles,
    )

    _C_AVAILABLE = True
except ImportError:
    _C_AVAILABLE = False

    def batch_point_in_triangles(
        vertices_flat: bytes, face_indices_flat: bytes, qx: float, qy: float
    ) -> int:  # type: ignore[misc]
        """Pure-Python fallback: find triangle containing point."""
        num_verts = len(vertices_flat) // 8  # 2 floats × 4 bytes
        num_faces = len(face_indices_flat) // 12  # 3 ints × 4 bytes
        verts = struct.unpack(f"<{num_verts * 2}f", vertices_flat)
        faces = struct.unpack(f"<{num_faces * 3}i", face_indices_flat)
        for i in range(num_faces):
            i1 = faces[i * 3]
            i2 = faces[i * 3 + 1]
            i3 = faces[i * 3 + 2]
            if i1 < 0 or i1 >= num_verts or i2 < 0 or i2 >= num_verts or i3 < 0 or i3 >= num_verts:
                continue
            v1x, v1y = verts[i1 * 2], verts[i1 * 2 + 1]
            v2x, v2y = verts[i2 * 2], verts[i2 * 2 + 1]
            v3x, v3y = verts[i3 * 2], verts[i3 * 2 + 1]
            c1 = (v2x - v1x) * (qy - v1y) - (v2y - v1y) * (qx - v1x)
            c2 = (v3x - v2x) * (qy - v2y) - (v3y - v2y) * (qx - v2x)
            c3 = (v1x - v3x) * (qy - v3y) - (v1y - v3y) * (qx - v3x)
            if (c1 < 0 and c2 < 0 and c3 < 0) or (c1 > 0 and c2 > 0 and c3 > 0):
                return i
        return -1

    def batch_distances_2d(positions_flat: bytes, qx: float, qy: float) -> bytes:  # type: ignore[misc]
        """Pure-Python fallback: compute squared distances."""
        n = len(positions_flat) // 8
        positions = struct.unpack(f"<{n * 2}f", positions_flat)
        result = []
        for i in range(n):
            dx = positions[i * 2] - qx
            dy = positions[i * 2 + 1] - qy
            result.append(dx * dx + dy * dy)
        return struct.pack(f"<{n}f", *result)

    def batch_distances_2d_filtered(
        positions_flat: bytes, qx: float, qy: float, threshold_sq: float
    ) -> list[int]:  # type: ignore[misc]
        """Pure-Python fallback: return indices within threshold."""
        n = len(positions_flat) // 8
        positions = struct.unpack(f"<{n * 2}f", positions_flat)
        hits = []
        for i in range(n):
            dx = positions[i * 2] - qx
            dy = positions[i * 2 + 1] - qy
            if dx * dx + dy * dy <= threshold_sq:
                hits.append(i)
        return hits

    def batch_face_at_direct(vertices_flat_xy: bytes, qx: float, qy: float) -> int:  # type: ignore[misc]
        """Pure-Python fallback: point-in-triangle with inlined vertices."""
        n = len(vertices_flat_xy) // 24  # 6 floats × 4 bytes
        verts = struct.unpack(f"<{n * 6}f", vertices_flat_xy)
        for i in range(n):
            base = i * 6
            v1x, v1y = verts[base], verts[base + 1]
            v2x, v2y = verts[base + 2], verts[base + 3]
            v3x, v3y = verts[base + 4], verts[base + 5]
            c1 = (v2x - v1x) * (qy - v1y) - (v2y - v1y) * (qx - v1x)
            c2 = (v3x - v2x) * (qy - v2y) - (v3y - v2y) * (qx - v2x)
            c3 = (v1x - v3x) * (qy - v3y) - (v1y - v3y) * (qx - v3x)
            if (c1 < 0 and c2 < 0 and c3 < 0) or (c1 > 0 and c2 > 0 and c3 > 0):
                return i
        return -1

    def batch_group_faces_by_material(materials_flat: bytes) -> dict[int, list[int]]:  # type: ignore[misc]
        """Pure-Python fallback: group faces by material."""
        n = len(materials_flat) // 4
        materials = struct.unpack(f"<{n}i", materials_flat)
        groups: dict[int, list[int]] = {}
        for i, mat in enumerate(materials):
            if mat not in groups:
                groups[mat] = []
            groups[mat].append(i)
        return groups

    def batch_compute_aabb_2d(vertices_flat: bytes) -> tuple[float, float, float, float]:  # type: ignore[misc]
        """Pure-Python fallback: compute 2D AABB."""
        n = len(vertices_flat) // 8
        if n == 0:
            return (0.0, 0.0, 0.0, 0.0)
        verts = struct.unpack(f"<{n * 2}f", vertices_flat)
        minx = maxx = verts[0]
        miny = maxy = verts[1]
        for i in range(1, n):
            x, y = verts[i * 2], verts[i * 2 + 1]
            if x < minx:
                minx = x
            if x > maxx:
                maxx = x
            if y < miny:
                miny = y
            if y > maxy:
                maxy = y
        return (minx, miny, maxx, maxy)


def is_available() -> bool:
    """Return True if the C extension is loaded."""
    return _C_AVAILABLE


def build_face_vertex_flat_array(bwm: BWM) -> bytes:
    """Build a flat float array of face vertices for batch_face_at_direct.

    Returns bytes of N×6 floats: (v1x, v1y, v2x, v2y, v3x, v3y) per face.
    """
    faces = bwm.faces
    arr = array.array("f")
    for face in faces:
        arr.append(face.v1.x)
        arr.append(face.v1.y)
        arr.append(face.v2.x)
        arr.append(face.v2.y)
        arr.append(face.v3.x)
        arr.append(face.v3.y)
    return arr.tobytes()


def build_instance_position_flat_array(positions: list[tuple[float, float]]) -> bytes:
    """Build a flat float array from (x, y) position tuples.

    Returns bytes of N×2 floats.
    """
    arr = array.array("f")
    for x, y in positions:
        arr.append(x)
        arr.append(y)
    return arr.tobytes()


def build_material_flat_array(bwm: BWM) -> bytes:
    """Build a flat int array of face materials.

    Returns bytes of N int32.
    """
    arr = array.array("i")
    for face in bwm.faces:
        arr.append(int(face.material))
    return arr.tobytes()


__all__ = [
    "batch_compute_aabb_2d",
    "batch_distances_2d",
    "batch_distances_2d_filtered",
    "batch_face_at_direct",
    "batch_group_faces_by_material",
    "batch_point_in_triangles",
    "build_face_vertex_flat_array",
    "build_instance_position_flat_array",
    "build_material_flat_array",
    "is_available",
]
