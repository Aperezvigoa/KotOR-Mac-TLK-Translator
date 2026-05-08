"""Camera: view/projection matrices with invalidation cache for GL rendering."""

from __future__ import annotations

import math

from typing import TYPE_CHECKING, Literal, Union

from pykotor.gl import (
    cross,
    inverse,
    mat4,
    normalize,
    ortho,
    perspective,
    rotate,
    translate,
    vec3,
)

if TYPE_CHECKING:
    from utility.common.geometry import Vector3


def _wrap_angle_pi(angle: float) -> float:
    """Normalize an angle to the [-pi, pi] range."""
    return (angle + math.pi) % (2 * math.pi) - math.pi


class Camera:
    """Camera with cached view/projection matrices.

    Performance optimization: view() and projection() matrix calculations are
    cached and only recomputed when camera parameters change. This provides
    significant speedup when matrices are accessed multiple times per frame.

    All position/orientation attributes (x, y, z, pitch, yaw, distance) use
    properties that automatically invalidate the view cache when modified.
    Similarly, width/height/fov invalidate the projection cache.

    Reference: Standard game engine practice (Unity, Unreal use similar caching)
    """

    __slots__ = (
        "_cached_projection",
        "_cached_view",
        "_distance",
        "_fov",
        "_height",
        "_orthographic",
        "_pitch",
        "_projection_dirty",
        "_view_dirty",
        "_width",
        "_x",
        "_y",
        "_yaw",
        "_z",
    )

    def __init__(
        self,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
        width: int | None = None,
        height: int | None = None,
        pitch: float | None = None,
        yaw: float | None = None,
        distance: float | None = None,
        fov: float | None = None,
        orthographic: bool = False,
        cached_view: mat4 | None = None,
        cached_projection: mat4 | None = None,
        view_dirty: bool | None = None,
        projection_dirty: bool | None = None,
    ):
        # Initialize internal attributes directly to avoid property setters
        # triggering invalidation during construction
        self._x: float = 40.0 if x is None else x
        self._y: float = 130.0 if y is None else y
        self._z: float = 0.5 if z is None else z
        self._width: int = 1920 if width is None else width
        self._height: int = 1080 if height is None else height
        self._pitch: float = math.pi / 2 if pitch is None else pitch
        self._yaw: float = 0.0 if yaw is None else yaw
        self._distance: float = 10.0 if distance is None else distance
        self._fov: float = 90.0 if fov is None else fov
        self._orthographic: bool = (
            False if orthographic is None else orthographic
        )  # When True, use orthographic projection

        # Cached matrices
        self._cached_view: mat4 | None = None if cached_view is None else cached_view
        self._cached_projection: mat4 | None = (
            None if cached_projection is None else cached_projection
        )
        self._view_dirty: bool = True if view_dirty is None else view_dirty
        self._projection_dirty: bool = True if projection_dirty is None else projection_dirty

    # Position properties - invalidate view cache on change
    @property
    def x(self) -> float:
        return self._x

    @x.setter
    def x(self, value: float) -> None:
        if self._x != value:
            self._x = value
            self._view_dirty = True

    @property
    def y(self) -> float:
        return self._y

    @y.setter
    def y(self, value: float) -> None:
        if self._y != value:
            self._y = value
            self._view_dirty = True

    @property
    def z(self) -> float:
        return self._z

    @z.setter
    def z(self, value: float) -> None:
        if self._z != value:
            self._z = value
            self._view_dirty = True

    # Orientation properties - invalidate view cache on change
    @property
    def pitch(self) -> float:
        return self._pitch

    @pitch.setter
    def pitch(self, value: float) -> None:
        if self._pitch != value:
            self._pitch = value
            self._view_dirty = True

    @property
    def yaw(self) -> float:
        return self._yaw

    @yaw.setter
    def yaw(self, value: float) -> None:
        if self._yaw != value:
            self._yaw = value
            self._view_dirty = True

    @property
    def distance(self) -> float:
        return self._distance

    @distance.setter
    def distance(self, value: float) -> None:
        if self._distance != value:
            self._distance = value
            self._view_dirty = True

    # Viewport/projection properties - invalidate projection cache on change
    @property
    def width(self) -> int:
        return self._width

    @width.setter
    def width(self, value: int) -> None:
        if self._width != value:
            self._width = value
            self._projection_dirty = True

    @property
    def height(self) -> int:
        return self._height

    @height.setter
    def height(self, value: int) -> None:
        if self._height != value:
            self._height = value
            self._projection_dirty = True

    @property
    def fov(self) -> float:
        return self._fov

    @fov.setter
    def fov(self, value: float) -> None:
        if self._fov != value:
            self._fov = value
            self._projection_dirty = True

    @property
    def orthographic(self) -> bool:
        """When True the camera uses orthographic (parallel) projection."""
        return self._orthographic

    @orthographic.setter
    def orthographic(self, value: bool) -> None:
        if self._orthographic != value:
            self._orthographic = value
            self._projection_dirty = True

    def _invalidate_view(self):
        """Mark view matrix as needing recalculation.

        Note: This is now called automatically by property setters for
        x, y, z, pitch, yaw, and distance. Manual calls are only needed
        for bulk updates or special cases.
        """
        self._view_dirty = True

    def _invalidate_projection(self):
        """Mark projection matrix as needing recalculation.

        Note: This is now called automatically by property setters for
        width, height, and fov. Manual calls are only needed for bulk
        updates or special cases.
        """
        self._projection_dirty = True

    def set_resolution(
        self,
        width: int,
        height: int,
    ):
        # Properties handle cache invalidation automatically
        self.width = width
        self.height = height

    def set_position(
        self,
        position: Union[Vector3, vec3],
    ):
        # Properties handle cache invalidation automatically
        self.x = position.x
        self.y = position.y
        self.z = position.z

    def view(self) -> mat4:
        """Get view matrix with caching.

        Matrix is recalculated only when camera position/orientation changes.
        """
        if not self._view_dirty and self._cached_view is not None:
            return self._cached_view

        up: vec3 = vec3(0, 0, 1)
        pitch_axis: vec3 = vec3(1, 0, 0)

        x, y, z = self.x, self.y, self.z
        cos_yaw = math.cos(self.yaw)
        sin_yaw = math.sin(self.yaw)
        pitch_offset = self.pitch - math.pi / 2
        cos_pitch = math.cos(pitch_offset)
        sin_pitch = math.sin(pitch_offset)

        x += cos_yaw * cos_pitch * self.distance
        y += sin_yaw * cos_pitch * self.distance
        z += sin_pitch * self.distance

        camera: mat4 = mat4() * translate(vec3(x, y, z))
        camera = rotate(camera, self.yaw + math.pi / 2, up)
        camera = rotate(camera, math.pi - self.pitch, pitch_axis)

        self._cached_view = inverse(camera)
        self._view_dirty = False
        return self._cached_view

    def projection(self) -> mat4:
        """Get projection matrix with caching.

        Matrix is recalculated only when FOV or aspect ratio changes.
        Returns perspective or orthographic matrix depending on self.orthographic.
        """
        if not self._projection_dirty and self._cached_projection is not None:
            return self._cached_projection

        # Prevent division by zero - use 1.0 aspect ratio if height is 0
        aspect_ratio: float = self.width / self.height if self.height > 0 else 1.0

        if self._orthographic:
            # Scale orthographic extents to match the visible area at the focal distance in
            # perspective mode so switching is seamless.  half_h = distance * tan(fov/2).
            half_h = self.distance * math.tan(math.radians(self.fov) / 2.0)
            half_w = half_h * aspect_ratio
            self._cached_projection = ortho(-half_w, half_w, -half_h, half_h, 0.1, 5000)
        else:
            self._cached_projection = perspective(
                self.fov,
                aspect_ratio,
                0.1,
                5000,
            )
        self._projection_dirty = False
        return self._cached_projection

    def translate(
        self,
        translation: vec3,
    ):
        # Properties handle cache invalidation automatically
        self.x += translation.x
        self.y += translation.y
        self.z += translation.z

    def rotate(
        self,
        yaw: float,
        pitch: float,
        *,
        clamp: bool = False,
        lower_limit: float = 0,
        upper_limit: float = math.pi,
    ):
        new_yaw = _wrap_angle_pi(self.yaw + yaw)
        new_pitch = self.pitch + pitch

        if clamp:
            orbit_epsilon = 0.01
            min_pitch = lower_limit + orbit_epsilon
            max_pitch = upper_limit - orbit_epsilon
            if min_pitch > max_pitch:
                midpoint = (lower_limit + upper_limit) * 0.5
                min_pitch = midpoint
                max_pitch = midpoint
            new_pitch = max(min_pitch, min(max_pitch, new_pitch))
        else:
            new_pitch = _wrap_angle_pi(new_pitch)

        self.yaw = new_yaw
        self.pitch = new_pitch

    def forward(
        self,
        *,
        ignore_z: bool = True,
    ) -> vec3:
        eye_x: float = math.cos(self.yaw) * math.cos(self.pitch - math.pi / 2)
        eye_y: float = math.sin(self.yaw) * math.cos(self.pitch - math.pi / 2)
        eye_z: Union[float, Literal[0]] = 0 if ignore_z else math.sin(self.pitch - math.pi / 2)
        return normalize(-vec3(eye_x, eye_y, eye_z))

    def sideward(
        self,
        *,
        ignore_z: bool = True,
    ) -> vec3:
        return normalize(cross(self.forward(ignore_z=ignore_z), vec3(0.0, 0.0, 1.0)))

    def upward(
        self,
        *,
        ignore_xy: bool = True,
    ) -> vec3:
        if ignore_xy:
            return normalize(vec3(0, 0, 1))
        forward: vec3 = self.forward(ignore_z=False)
        sideward: vec3 = self.sideward(ignore_z=False)
        cross_product: vec3 = cross(forward, sideward)
        return normalize(cross_product)

    def true_position(self) -> vec3:
        cos_yaw: float = math.cos(self.yaw)
        cos_pitch: float = math.cos(self.pitch - math.pi / 2)
        sin_yaw: float = math.sin(self.yaw)
        sin_pitch: float = math.sin(self.pitch - math.pi / 2)
        return vec3(
            self.x + cos_yaw * cos_pitch * self.distance,
            self.y + sin_yaw * cos_pitch * self.distance,
            self.z + sin_pitch * self.distance,
        )
