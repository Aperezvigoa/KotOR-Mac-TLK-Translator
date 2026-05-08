"""Python wrapper for _gl_accel C extension.

Provides batch frustum culling, plane extraction, transform bounds,
and matrix operations. Falls back gracefully when the C extension is
unavailable (pure-Python fallback for frustum_cull_objects).
"""

from __future__ import annotations

import array

from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from pykotor.gl.scene.render_object import RenderObject

# Try importing the C extension.
try:
    from pykotor.gl.native._gl_accel import (
        aabb_in_frustum_batch,
        batch_frustum_cull,
        batch_hook_snap_distances,
        batch_sphere_distances,
        batch_transform_vertices_2d,
        batch_vertices_in_rect,
        compute_node_world_transforms,
        extract_frustum_planes,
        mat4_multiply_batch,
        transform_bounds,
    )

    _C_AVAILABLE = True
except ImportError:
    _C_AVAILABLE = False

    def batch_frustum_cull(planes: bytes, spheres: bytes) -> bytearray:  # type: ignore[misc]
        raise RuntimeError("_gl_accel C extension not available")

    def extract_frustum_planes(vp_matrix: bytes) -> bytes:  # type: ignore[misc]
        raise RuntimeError("_gl_accel C extension not available")

    def transform_bounds(
        vertex_data: bytes, vertex_count: int, stride: int, pos_offset: int, matrix: bytes
    ) -> tuple:  # type: ignore[misc]
        raise RuntimeError("_gl_accel C extension not available")

    def batch_sphere_distances(planes: bytes, spheres: bytes) -> bytes:  # type: ignore[misc]
        raise RuntimeError("_gl_accel C extension not available")

    def mat4_multiply_batch(transforms: bytes, parent_matrix: bytes) -> bytes:  # type: ignore[misc]
        raise RuntimeError("_gl_accel C extension not available")

    def aabb_in_frustum_batch(planes: bytes, aabbs: bytes) -> bytearray:  # type: ignore[misc]
        raise RuntimeError("_gl_accel C extension not available")

    def compute_node_world_transforms(
        local_transforms: bytes, parent_indices: bytes, root_transform: bytes
    ) -> bytes:  # type: ignore[misc]
        raise RuntimeError("_gl_accel C extension not available")

    def batch_transform_vertices_2d(
        vertices: bytes,
        cos_r: float,
        sin_r: float,
        flip_x: bool,
        flip_y: bool,
        tx: float,
        ty: float,
    ) -> tuple:  # type: ignore[misc]
        raise RuntimeError("_gl_accel C extension not available")

    def batch_hook_snap_distances(
        existing_hooks: bytes, test_local: bytes, pos_x: float, pos_y: float, snap_threshold: float
    ) -> tuple | None:  # type: ignore[misc]
        raise RuntimeError("_gl_accel C extension not available")

    def batch_vertices_in_rect(
        vertices: bytes,
        cos_r: float,
        sin_r: float,
        flip_x: bool,
        flip_y: bool,
        tx: float,
        ty: float,
        rmin_x: float,
        rmin_y: float,
        rmax_x: float,
        rmax_y: float,
    ) -> int:  # type: ignore[misc]
        raise RuntimeError("_gl_accel C extension not available")


def c_available() -> bool:
    """Return True if the compiled C acceleration module is loaded."""
    return _C_AVAILABLE


def pack_planes_from_frustum(frustum) -> bytes:
    """Pack a Frustum object's 6 planes into 24 floats (bytes).

    Args:
        frustum: A Frustum instance with .planes list of Vector4.

    Returns:
        bytes of 24 floats suitable for C extension calls.
    """
    buf = array.array("f")
    for plane in frustum.planes:
        buf.append(plane.x)
        buf.append(plane.y)
        buf.append(plane.z)
        buf.append(plane.w)
    return buf.tobytes()


def pack_spheres(objects: Sequence[RenderObject], scene, default_radius: float) -> bytes:
    """Pack bounding spheres for a list of RenderObjects into N×4 floats.

    Args:
        objects: Sequence of RenderObject instances.
        scene: The Scene instance (needed for bounding_sphere()).
        default_radius: Default culling radius for objects without computed bounds.

    Returns:
        bytes of N×4 floats (cx, cy, cz, radius).
    """
    buf = array.array("f")
    for obj in objects:
        center, radius = obj.bounding_sphere(scene, default_radius)
        buf.append(center.x)
        buf.append(center.y)
        buf.append(center.z)
        buf.append(radius)
    return buf.tobytes()


def frustum_cull_objects(
    frustum,
    objects: Sequence[RenderObject],
    scene,
    default_radius: float,
) -> list[bool]:
    """Batch frustum cull a list of RenderObjects.

    If the C extension is available, packs data and calls the batch C function.
    Otherwise, falls back to per-object Python checks.

    Args:
        frustum: Frustum instance with .planes.
        objects: Sequence of RenderObjects to test.
        scene: Scene instance.
        default_radius: Default bounding sphere radius.

    Returns:
        list of bools, True = visible. Same length as objects.
    """
    if not objects:
        return []

    if _C_AVAILABLE:
        planes_bytes = pack_planes_from_frustum(frustum)
        spheres_bytes = pack_spheres(objects, scene, default_radius)
        vis = batch_frustum_cull(planes_bytes, spheres_bytes)
        return [bool(v) for v in vis]

    # Pure-Python fallback
    result: list[bool] = []
    for obj in objects:
        center, radius = obj.bounding_sphere(scene, default_radius)
        visible = True
        for plane in frustum.planes:
            dist = plane.x * center.x + plane.y * center.y + plane.z * center.z + plane.w
            if dist < -radius:
                visible = False
                break
        result.append(visible)
    return result
