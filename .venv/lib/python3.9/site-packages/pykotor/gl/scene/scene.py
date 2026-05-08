"""OpenGL scene: models, camera, picking, and render loop for module designer."""

from __future__ import annotations

import os
import time

from typing import TYPE_CHECKING, ClassVar, TypeVar

from pykotor.extract.installation import SearchLocation
from pykotor.gl import mat4, unProject, vec3, vec4
from pykotor.gl.compat import (
    GL_BGRA,
    GL_BLEND,
    GL_COLOR_BUFFER_BIT,
    GL_CULL_FACE,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_COMPONENT,
    GL_DEPTH_TEST,
    GL_FALSE,
    GL_FILL,
    GL_FLOAT,
    GL_FRONT_AND_BACK,
    GL_LEQUAL,
    GL_LINE,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_SRC_ALPHA,
    GL_TRUE,
    GL_UNSIGNED_INT_8_8_8_8,
    HAS_PYOPENGL,
    glBlendFunc,
    glClear,
    glClearColor,
    glDepthFunc,
    glDepthMask,
    glDisable,
    glEnable,
    glPolygonMode,
    glReadPixels,
)
from pykotor.gl.models.axis_gizmo import AxisGizmo
from pykotor.gl.models.mdl import Mesh as _Mesh
from pykotor.gl.native.gl_accel import (
    frustum_cull_objects as _batch_frustum_cull,
)
from pykotor.gl.scene.frustum import CullingStats, Frustum
from pykotor.gl.scene.render_object import RenderObject
from pykotor.gl.scene.scene_base import SceneBase
from pykotor.gl.scene.scene_cache import SceneCache
from pykotor.gl.shader import (
    KOTOR_FSHADER,
    KOTOR_VSHADER,
    PICKER_FSHADER,
    PICKER_VSHADER,
    PLAIN_FSHADER,
    PLAIN_VSHADER,
    Shader,
)
from pykotor.resource.formats.lyt.lyt_data import LYTRoom
from pykotor.resource.generics.git import (
    GITCamera,
    GITCreature,
    GITDoor,
    GITEncounter,
    GITObject,
    GITPlaceable,
    GITSound,
    GITStore,
    GITTrigger,
    GITWaypoint,
)
from utility.common.geometry import Vector3 as GeomVector3

if TYPE_CHECKING:
    from pykotor.common.module import Module
    from pykotor.extract.installation import Installation
    from pykotor.gl.models.mdl import Model

T = TypeVar("T")
SEARCH_ORDER_2DA: list[SearchLocation] = [SearchLocation.OVERRIDE, SearchLocation.CHITIN]
SEARCH_ORDER: list[SearchLocation] = [SearchLocation.OVERRIDE, SearchLocation.CHITIN]


class Scene(SceneBase):
    """Optimized scene renderer with caching and batched operations.

    Performance optimizations:
    - Cached object categorization (avoids list comprehensions every frame)
    - Cached view/projection matrices (set once per frame, not per object)
    - Cached bounding spheres for frustum culling
    - Incremental cache building (only rebuilds when dirty)
    - Cached camera focus gizmo placement

    Prior third-party source paths for the render loop were listed here; see
    ``wiki/reverse_engineering_findings.md`` (*PyKotor GL — reference implementation paths*).
    """

    def __init__(
        self,
        *args,
        installation: Installation | None = None,
        module: Module | None = None,
        **kwargs,
    ):
        # Backwards-compat for older callers that still pass renderer-selection kwargs.
        # These are ignored; PyKotor now uses PyOpenGL for rendering.
        kwargs.pop("moderngl_context", None)
        kwargs.pop("use_legacy_gl", None)

        super().__init__(installation=installation, module=module, **kwargs)

        # Canonical backend selection log (one line, high signal).
        from loggerplus import RobustLogger

        RobustLogger().debug(
            "Scene backend selection: pyopengl=%s",
            HAS_PYOPENGL,
        )

        # Initialize PyOpenGL shaders if available.
        if HAS_PYOPENGL:
            self.picker_shader: Shader = Shader(PICKER_VSHADER, PICKER_FSHADER)
            self.plain_shader: Shader = Shader(PLAIN_VSHADER, PLAIN_FSHADER)
            self.shader: Shader = Shader(KOTOR_VSHADER, KOTOR_FSHADER)
            self._axis_gizmo: AxisGizmo = AxisGizmo()
        else:
            self.picker_shader = None  # type: ignore[assignment]
            self.plain_shader = None  # type: ignore[assignment]
            self.shader = None  # type: ignore[assignment]
            self._axis_gizmo = None  # type: ignore[assignment]

        # Frustum culling
        self.frustum: Frustum = Frustum()
        self.culling_stats: CullingStats = CullingStats()
        self.enable_frustum_culling: bool = True
        # Default bounding sphere radius for objects without computed bounds
        self.default_cull_radius: float = 5.0

        # Cached object lists for render batching (rebuilt when objects change)
        self._cached_regular_objects: list[RenderObject] | None = None
        self._cached_special_objects: list[RenderObject] | None = None
        self._cached_sound_objects: list[RenderObject] | None = None
        self._cached_encounter_objects: list[RenderObject] | None = None
        self._cached_trigger_objects: list[RenderObject] | None = None
        self._objects_dirty: bool = True
        self._last_objects_count: int = 0

        # Cached camera matrices (set once per frame, used by multiple shaders)
        self._cached_view: mat4 | None = None
        self._cached_projection: mat4 | None = None

        # Per-frame profile timings (TOOLSET_MODULE_DESIGNER_PROFILE): (cache_ms, draw_ms) per frame
        self._profile_frame_times: list[tuple[float, float]] = []

    def _invalidate_object_cache(self):
        """Mark object caches as dirty. Call when objects are added/removed."""
        self._objects_dirty = True
        self._cached_regular_objects = None
        self._cached_special_objects = None
        self._cached_sound_objects = None
        self._cached_encounter_objects = None
        self._cached_trigger_objects = None

    def _rebuild_object_caches(self):
        """Rebuild cached object lists for efficient iteration.

        Also precomputes _hide_attr on each RenderObject so that
        should_hide_obj() becomes O(1) instead of O(9 isinstance).
        """
        if not self._objects_dirty and len(self.objects) == self._last_objects_count:
            return

        special_models: frozenset[str] = frozenset(self.SPECIAL_MODELS)

        # Build type->hide_attr mapping for precomputation
        hide_attr_map: dict[type, str] = {t: a for t, a in self._HIDE_TYPE_MAP}

        regular: list[RenderObject] = []
        special: list[RenderObject] = []
        sounds: list[RenderObject] = []
        encounters: list[RenderObject] = []
        triggers: list[RenderObject] = []

        for obj in self.objects.values():
            # Precompute hide_attr (avoids 9 isinstance checks per frame per object)
            data = obj.data
            hide_attr = ""
            if data is not None:
                data_type = type(data)
                hide_attr = hide_attr_map.get(data_type, "")
            obj._hide_attr = hide_attr

            model = obj.model
            if model in special_models:
                special.append(obj)
                if model == "sound":
                    sounds.append(obj)
                elif model == "encounter":
                    encounters.append(obj)
                elif model == "trigger":
                    triggers.append(obj)
            else:
                regular.append(obj)

        self._cached_regular_objects = regular
        self._cached_special_objects = special
        self._cached_sound_objects = sounds
        self._cached_encounter_objects = encounters
        self._cached_trigger_objects = triggers
        self._objects_dirty = False
        self._last_objects_count = len(self.objects)

    def _update_camera_matrices(self):
        """Update cached camera matrices.

        Camera.view() and Camera.projection() already have internal caching
        that only recomputes when dirty. We just store the results for use
        in multiple shaders per frame.
        """
        # Camera has internal dirty tracking, so these calls are cheap when unchanged
        self._cached_view = self.camera.view()
        self._cached_projection = self.camera.projection()

    def render(self):
        if not HAS_PYOPENGL:
            from pykotor.gl.compat import MissingPyOpenGLError

            raise MissingPyOpenGLError("PyOpenGL is required for rendering.")

        # Qt can still call paintGL during teardown after makeCurrent() has failed.
        # In that case, any GL call may raise GLError (e.g. glUniformMatrix4fv -> GL_INVALID_OPERATION).
        if self.is_shutdown:
            return

        _profile = os.environ.get("TOOLSET_MODULE_DESIGNER_PROFILE", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        _t0 = time.perf_counter() if _profile else None

        try:
            # Poll for completed async resources (non-blocking) - MAIN PROCESS ONLY
            self.poll_async_resources()

            # Build/sync scene cache.
            # Fast path: when all objects exist and no invalidations, only syncs
            # positions (set_position/set_rotation have identity-check early returns).
            # Full rebuild only runs when object counts differ or caches are cleared.
            SceneCache.build_cache(self)

            if _profile and _t0 is not None:
                _t1 = time.perf_counter()
                _cache_ms = (_t1 - _t0) * 1000

            # Rebuild object lists if objects changed (cheap check)
            if self._objects_dirty or len(self.objects) != self._last_objects_count:
                self._rebuild_object_caches()

            # Update camera matrices once per frame
            self._update_camera_matrices()

            # Update frustum for culling
            if self.enable_frustum_culling:
                self.frustum.update_from_camera(self.camera)

            if self.enable_frustum_culling:
                self.culling_stats.reset()

            # Prepare GL state and main shader
            self._prepare_gl_and_shader_optimized()
            self.shader.set_bool("enableLightmap", self.use_lightmap)

            # Reset per-frame state tracking for optimized draw calls
            _Mesh.reset_draw_state(getattr(self.textures, "_generation", -1))
            Shader._active_id = -1

            # Render regular objects (models)
            assert self._cached_regular_objects is not None
            identity = mat4()  # Create once, reuse
            if self.use_wireframe:
                glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            try:
                if self.enable_frustum_culling:
                    # Batch frustum cull: test all objects at once (C extension when available)
                    visibility = _batch_frustum_cull(
                        self.frustum,
                        self._cached_regular_objects,
                        self,
                        self.default_cull_radius,
                    )
                    for i, obj in enumerate(self._cached_regular_objects):
                        if not visibility[i]:
                            self.culling_stats.record_object(visible=False)
                            continue
                        self.culling_stats.record_object(visible=True)
                        self._render_object(self.shader, obj, identity)
                else:
                    for obj in self._cached_regular_objects:
                        self._render_object(self.shader, obj, identity)
            finally:
                if self.use_wireframe:
                    glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

            # Setup plain shader for special objects (once)
            glEnable(GL_BLEND)
            self.plain_shader.use()
            assert self._cached_view is not None and self._cached_projection is not None
            self.plain_shader.set_matrix4("view", self._cached_view)
            self.plain_shader.set_matrix4("projection", self._cached_projection)
            self.plain_shader.set_vector4("color", vec4(0.0, 0.0, 1.0, 0.4))

            # Render special objects (icons)
            assert self._cached_special_objects is not None
            if self.enable_frustum_culling:
                special_visibility = _batch_frustum_cull(
                    self.frustum,
                    self._cached_special_objects,
                    self,
                    self.default_cull_radius,
                )
                for i, obj in enumerate(self._cached_special_objects):
                    if not special_visibility[i]:
                        self.culling_stats.record_object(visible=False)
                        continue
                    self.culling_stats.record_object(visible=True)
                    self._render_object(self.plain_shader, obj, identity)
            else:
                for obj in self._cached_special_objects:
                    self._render_object(self.plain_shader, obj, identity)

            # Draw bounding box for selected objects (only RenderObjects have cube/boundary)
            # The model surfaces are already in the depth buffer, so the cube faces fail the
            # depth test at pixels occupied by the model (nearly all of them).  Disable depth
            # test so the selection indicator always renders visibly on top.
            glDisable(GL_DEPTH_TEST)
            glDepthMask(GL_FALSE)  # type: ignore[arg-type]
            glDisable(GL_CULL_FACE)  # Draw both inner and outer faces for a solid-filled look
            self.plain_shader.set_vector4("color", vec4(1.0, 0.0, 0.0, 0.4))
            for obj in self.selection:
                if isinstance(obj, RenderObject):
                    obj.cube(self).draw(self.plain_shader, obj.transform())
            glEnable(GL_DEPTH_TEST)
            glDepthMask(GL_TRUE)  # type: ignore[arg-type]

            # Draw boundary for selected objects
            glDisable(GL_CULL_FACE)
            self.plain_shader.set_vector4("color", vec4(0.0, 1.0, 0.0, 0.8))
            for obj in self.selection:
                if isinstance(obj, RenderObject):
                    obj.boundary(self).draw(self.plain_shader, obj.transform())

            # Draw non-selected boundaries (only if visible and enabled)
            if not self.hide_sound_boundaries:
                assert self._cached_sound_objects is not None
                for obj in self._cached_sound_objects:
                    if not self.enable_frustum_culling or self._is_object_visible(obj):
                        obj.boundary(self).draw(self.plain_shader, obj.transform())

            if not self.hide_encounter_boundaries:
                assert self._cached_encounter_objects is not None
                for obj in self._cached_encounter_objects:
                    if not self.enable_frustum_culling or self._is_object_visible(obj):
                        obj.boundary(self).draw(self.plain_shader, obj.transform())

            if not self.hide_trigger_boundaries:
                assert self._cached_trigger_objects is not None
                for obj in self._cached_trigger_objects:
                    if not self.enable_frustum_culling or self._is_object_visible(obj):
                        obj.boundary(self).draw(self.plain_shader, obj.transform())

            # Draw the axis gizmo at the camera focal point (view focus), not at
            # the mouse-world anchor (`scene.cursor`), which may change every frame.
            if self.show_focus_point_gizmo and self._axis_gizmo is not None:
                focus_point = self.camera_focal_point()
                self._axis_gizmo.draw(
                    self.plain_shader,
                    vec3(focus_point.x, focus_point.y, focus_point.z),
                    self.camera.distance,
                )

            if _profile and _t0 is not None:
                _t2 = time.perf_counter()
                _draw_ms = (_t2 - _t1) * 1000  # noqa: F821
                self._profile_frame_times.append((_cache_ms, _draw_ms))  # noqa: F821
                if len(self._profile_frame_times) >= 200:
                    n = len(self._profile_frame_times)
                    mean_cache = sum(p[0] for p in self._profile_frame_times) / n
                    mean_draw = sum(p[1] for p in self._profile_frame_times) / n
                    from loggerplus import RobustLogger

                    RobustLogger().info(
                        "[MODULE_DESIGNER_PROFILE] per-frame (n=%d): mean cache=%.2f ms, mean draw=%.2f ms, mean total=%.2f ms",
                        n,
                        mean_cache,
                        mean_draw,
                        mean_cache + mean_draw,
                    )
                    self._profile_frame_times.clear()

            # End frame statistics
            if self.enable_frustum_culling:
                self.culling_stats.end_frame()
        except Exception as exc:  # noqa: BLE001
            # Lost/invalid context during widget teardown often manifests as GLError(1282).
            try:
                from OpenGL.error import GLError  # type: ignore[import-not-found]

                if isinstance(exc, GLError):
                    from loggerplus import RobustLogger

                    RobustLogger().debug(
                        "Scene.render: OpenGL error during render; skipping frame", exc_info=True
                    )
                    return
            except Exception:  # noqa: BLE001
                # If OpenGL isn't importable for some reason, just re-raise the original error.
                pass
            raise

    # Depth value at or above this threshold is treated as "sky" (no geometry hit).
    _FAR_PLANE_DEPTH_THRESHOLD: float = 0.9999

    def screen_to_world_from_depth_buffer(self, x: int, y: int) -> GeomVector3:
        """Convert screen coordinates to world coordinates using the *current* depth buffer.

        This is a fast-path for interactive tools (e.g. the Module Designer) that already
        rendered the scene this frame and just need to unproject the mouse position.

        Unlike `screen_to_world()`, this does **not** clear the framebuffer or perform an
        extra depth-only render pass. It simply reads a single depth pixel and unprojects.

        When the depth value is at the far plane (no geometry under the cursor), the
        camera's focal point is returned instead of a position at near-infinity. This
        keeps mouse-projected placement coordinates finite and stable over empty sky.

        Preconditions:
        - A valid GL context is current.
        - The scene has been rendered at least once with the current camera configuration
          (so the depth buffer and cached matrices are up-to-date).
        """
        if self.is_shutdown:
            return GeomVector3(0.0, 0.0, 0.0)

        # Use cached matrices if available (these are refreshed once per render()).
        if self._cached_view is not None and self._cached_projection is not None:
            view = self._cached_view
            projection = self._cached_projection
        else:
            view = self.camera.view()
            projection = self.camera.projection()

        zpos = glReadPixels(
            x,
            self.camera.height - y,
            1,
            1,
            GL_DEPTH_COMPONENT,
            GL_FLOAT,
        )[0][0]  # type: ignore[]

        # If the depth sample is at the far plane (sky / no geometry), fall back to the
        # camera focal point. Unprojecting z=1.0 places the point thousands of units
        # away, which is not useful for placement/manipulation workflows.
        if float(zpos) >= self._FAR_PLANE_DEPTH_THRESHOLD:
            return self.camera_focal_point()

        cursor_glm: vec3 = unProject(
            vec3(float(x), float(self.camera.height - y), float(zpos)),
            view,
            projection,
            vec4(0, 0, self.camera.width, self.camera.height),
        )
        return GeomVector3(cursor_glm.x, cursor_glm.y, cursor_glm.z)

    def _prepare_gl_and_shader_optimized(self):
        """Optimized GL state preparation using cached matrices."""
        glClearColor(0.5, 0.5, 1, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)  # type: ignore[]

        # Correct depth ordering is essential for layered meshes (e.g., hair planes over a head).
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)

        # Configure standard alpha blending. The main fragment shader also applies an alpha cutoff
        # for masked textures (see `KOTOR_FSHADER`).
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        if self.backface_culling:
            glEnable(GL_CULL_FACE)
        else:
            glDisable(GL_CULL_FACE)
        self.shader.use()

        # Use cached matrices instead of recalculating
        assert self._cached_view is not None and self._cached_projection is not None
        self.shader.set_matrix4("view", self._cached_view)
        self.shader.set_matrix4("projection", self._cached_projection)

    def _is_object_visible(self, obj: RenderObject) -> bool:
        """Check if an object is visible within the frustum.

        Uses cached bounding sphere from RenderObject for efficiency.

        Args:
            obj: The render object to test.

        Returns:
            True if the object should be rendered.
        """
        # Use cached bounding sphere from RenderObject
        center, radius = obj.bounding_sphere(self, self.default_cull_radius)
        return self.frustum.sphere_in_frustum(center, radius)

    # Class-level type map for should_hide_obj (avoids dict creation per call)
    _HIDE_TYPE_MAP: ClassVar[tuple[tuple[type, str], ...]] = (
        (GITCreature, "hide_creatures"),
        (GITPlaceable, "hide_placeables"),
        (GITDoor, "hide_doors"),
        (GITTrigger, "hide_triggers"),
        (GITEncounter, "hide_encounters"),
        (GITWaypoint, "hide_waypoints"),
        (GITSound, "hide_sounds"),
        (GITStore, "hide_sounds"),
        (GITCamera, "hide_cameras"),
    )

    def should_hide_obj(
        self,
        obj: RenderObject,
    ) -> bool:
        hide_attr = obj._hide_attr
        return bool(hide_attr and getattr(self, hide_attr, False))

    def _object_list_snapshot(self) -> list[RenderObject]:
        """Return a stable snapshot of objects for index-based rendering workflows."""
        return list(self.objects.values())

    def _render_object(
        self,
        shader: Shader,
        obj: RenderObject,
        transform: mat4,
    ):
        # Inline hide check to avoid method call overhead on hot path.
        _hide = obj._hide_attr  # noqa: SLF001
        if _hide and getattr(self, _hide, False):
            return

        model: Model = obj.resolve_model(self)
        # Avoid cast() call — pure overhead at runtime (typing.cast is a no-op).
        # Access _transform directly to skip method call overhead.
        next_transform: mat4 = transform * obj._transform  # type: ignore[assignment]  # noqa: SLF001
        model.draw(shader, next_transform, override_texture=obj.override_texture)

        for child in obj.children:
            self._render_object(shader, child, next_transform)

    def picker_render(self):
        """Render scene for object picking with unique colors per object.

        Optimized to use cached matrices and enumerate for O(1) index access.
        """
        if self.is_shutdown:
            return

        glClearColor(1.0, 1.0, 1.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)  # pyright: ignore[reportOperatorIssue]

        if self.backface_culling:
            glEnable(GL_CULL_FACE)
        else:
            glDisable(GL_CULL_FACE)

        self.picker_shader.use()

        # Use cached matrices if available, otherwise compute
        if self._cached_view is not None and self._cached_projection is not None:
            self.picker_shader.set_matrix4("view", self._cached_view)
            self.picker_shader.set_matrix4("projection", self._cached_projection)
        else:
            self.picker_shader.set_matrix4("view", self.camera.view())
            self.picker_shader.set_matrix4("projection", self.camera.projection())

        # Use enumerate instead of list.index() which is O(n) per call
        identity = mat4()
        instances: list[RenderObject] = self._object_list_snapshot()
        for idx, obj in enumerate(instances):
            r: int = idx & 0xFF
            g: int = (idx >> 8) & 0xFF
            b: int = (idx >> 16) & 0xFF
            color = vec3(r / 0xFF, g / 0xFF, b / 0xFF)
            self.picker_shader.set_vector3("colorId", color)
            self._picker_render_object(obj, identity)

    def _picker_render_object(self, obj: RenderObject, transform: mat4):
        if self.should_hide_obj(obj) and not self.pick_include_hidden:
            return

        world_transform = transform * obj._transform  # noqa: SLF001
        model: Model = obj.resolve_model(self)
        model.draw(self.picker_shader, world_transform)  # type: ignore[arg-type]
        for child in obj.children:
            self._picker_render_object(child, world_transform)  # noqa: SLF001

    def pick(
        self,
        x: float,
        y: float,
    ) -> RenderObject | None:
        self.picker_render()
        pixel: int = glReadPixels(x, y, 1, 1, GL_BGRA, GL_UNSIGNED_INT_8_8_8_8)[0][0] >> 8  # type: ignore[]
        instances: list[RenderObject] = self._object_list_snapshot()
        return instances[pixel] if pixel != 0xFFFFFF else None  # noqa: PLR2004

    def select(
        self,
        target: RenderObject | GITObject,
        *,
        clear_existing: bool = True,
    ):
        if clear_existing:
            self.selection.clear()

        SceneCache.build_cache(self)
        actual_target: RenderObject | None = None
        if isinstance(target, GITObject):
            for obj in self.objects.values():
                if obj.data is target:
                    actual_target = obj
                    break
        else:
            actual_target = target

        if actual_target is not None:
            self.selection.append(actual_target)

    def screen_to_world(
        self,
        x: int,
        y: int,
    ) -> GeomVector3:
        """Convert screen coordinates to world coordinates.

        Optimized to:
        - Use cached room objects list
        - Use cached view/projection matrices
        - Minimize GL state changes
        """
        if self.is_shutdown:
            return GeomVector3(0.0, 0.0, 0.0)

        # Prepare GL state efficiently
        glClearColor(0.5, 0.5, 1, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)  # type: ignore[]
        if self.backface_culling:
            glEnable(GL_CULL_FACE)
        else:
            glDisable(GL_CULL_FACE)
        glDisable(GL_BLEND)
        self.shader.use()

        # Use cached matrices if available
        if self._cached_view is not None and self._cached_projection is not None:
            view = self._cached_view
            projection = self._cached_projection
        else:
            view = self.camera.view()
            projection = self.camera.projection()

        self.shader.set_matrix4("view", view)
        self.shader.set_matrix4("projection", projection)

        # Only render room geometry for depth calculation
        identity = mat4()
        for obj in self.objects.values():
            if isinstance(obj.data, LYTRoom):
                self._render_object(self.shader, obj, identity)

        zpos = glReadPixels(
            x,
            self.camera.height - y,
            1,
            1,
            GL_DEPTH_COMPONENT,
            GL_FLOAT,
        )[0][0]  # type: ignore[]

        cursor_glm: vec3 = unProject(
            vec3(float(x), float(self.camera.height - y), float(zpos)),
            view,
            projection,
            vec4(0, 0, self.camera.width, self.camera.height),
        )
        return GeomVector3(cursor_glm.x, cursor_glm.y, cursor_glm.z)

    def _prepare_gl_and_shader(self):
        """Legacy method for backward compatibility."""
        glClearColor(0.5, 0.5, 1, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)  # type: ignore[]
        if self.backface_culling:
            glEnable(GL_CULL_FACE)
        else:
            glDisable(GL_CULL_FACE)
        glDisable(GL_BLEND)
        self.shader.use()
        self.shader.set_matrix4("view", self.camera.view())
        self.shader.set_matrix4("projection", self.camera.projection())
