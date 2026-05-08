"""MDL (model) GL representation: load binary MDL, build node hierarchy, and render with OpenGL."""

from __future__ import annotations

import ctypes
import logging
import math
import struct

from copy import copy
from typing import TYPE_CHECKING, Any

import numpy as np

from pykotor.gl import (
    glm,
    mat4,
    quat,
    value_ptr,
    vec3,
    vec4,
)
from pykotor.gl.compat import has_pyopengl, missing_constant, missing_gl_func, safe_gl_error_module
from utility.common.geometry import Vector3

if TYPE_CHECKING:
    from pykotor.gl.scene import Scene
    from pykotor.gl.shader import Shader

HAS_PYOPENGL = has_pyopengl()
gl_error = safe_gl_error_module()


if HAS_PYOPENGL:
    from OpenGL import (
        error as gl_error,  # type: ignore[no-redef]  # pyright: ignore[reportMissingImports]
    )
    from OpenGL.GL import glGenBuffers, glGenVertexArrays, glUniformMatrix4fv, glVertexAttribPointer
    from OpenGL.GL.shaders import GL_FALSE  # pyright: ignore[reportMissingImports]
    from OpenGL.raw.GL.ARB.tessellation_shader import (
        GL_TRIANGLES,  # pyright: ignore[reportMissingImports]
    )
    from OpenGL.raw.GL.ARB.vertex_shader import (
        GL_FLOAT,  # pyright: ignore[reportMissingImports]
    )
    from OpenGL.raw.GL.VERSION.GL_1_0 import (
        GL_UNSIGNED_SHORT,  # pyright: ignore[reportMissingImports]
    )
    from OpenGL.raw.GL.VERSION.GL_1_1 import (  # pyright: ignore[reportMissingImports]
        GL_TEXTURE_2D,
        glBindTexture,
        glDrawElements,
    )
    from OpenGL.raw.GL.VERSION.GL_1_3 import (  # pyright: ignore[reportMissingImports]
        GL_TEXTURE0,
        GL_TEXTURE1,
        glActiveTexture,
    )
    from OpenGL.raw.GL.VERSION.GL_1_5 import (  # pyright: ignore[reportMissingImports]
        GL_ARRAY_BUFFER,
        GL_ELEMENT_ARRAY_BUFFER,
        GL_STATIC_DRAW,
        glBindBuffer,
        glBufferData,
    )
    from OpenGL.raw.GL.VERSION.GL_2_0 import (
        glEnableVertexAttribArray,  # pyright: ignore[reportMissingImports]
    )
    from OpenGL.raw.GL.VERSION.GL_3_0 import (
        glBindVertexArray,  # pyright: ignore[reportMissingImports]
    )

    from pykotor.gl.compat import (  # noqa: E501
        GL_BLEND,
        GL_ONE,
        GL_ONE_MINUS_SRC_ALPHA,
        GL_SRC_ALPHA,
        GL_SRC_COLOR,
        glBlendFunc,
        glDepthMask,
        glDisable,
        glEnable,
    )
else:
    glGenBuffers = missing_gl_func("glGenBuffers")
    glGenVertexArrays = missing_gl_func("glGenVertexArrays")
    glUniformMatrix4fv = missing_gl_func("glUniformMatrix4fv")
    glVertexAttribPointer = missing_gl_func("glVertexAttribPointer")
    glBindTexture = missing_gl_func("glBindTexture")
    glDrawElements = missing_gl_func("glDrawElements")
    GL_TEXTURE_2D = missing_constant("GL_TEXTURE_2D")
    glActiveTexture = missing_gl_func("glActiveTexture")
    glBindBuffer = missing_gl_func("glBindBuffer")
    glBufferData = missing_gl_func("glBufferData")
    glEnableVertexAttribArray = missing_gl_func("glEnableVertexAttribArray")
    glBindVertexArray = missing_gl_func("glBindVertexArray")
    GL_FALSE = missing_constant("GL_FALSE")
    GL_TRIANGLES = missing_constant("GL_TRIANGLES")
    GL_FLOAT = missing_constant("GL_FLOAT")
    GL_UNSIGNED_SHORT = missing_constant("GL_UNSIGNED_SHORT")
    GL_TEXTURE0 = missing_constant("GL_TEXTURE0")
    GL_TEXTURE1 = missing_constant("GL_TEXTURE1")
    GL_ARRAY_BUFFER = missing_constant("GL_ARRAY_BUFFER")
    GL_ELEMENT_ARRAY_BUFFER = missing_constant("GL_ELEMENT_ARRAY_BUFFER")
    GL_STATIC_DRAW = missing_constant("GL_STATIC_DRAW")
    GL_BLEND = missing_constant("GL_BLEND")
    GL_ONE = missing_constant("GL_ONE")
    GL_ONE_MINUS_SRC_ALPHA = missing_constant("GL_ONE_MINUS_SRC_ALPHA")
    GL_SRC_ALPHA = missing_constant("GL_SRC_ALPHA")
    GL_SRC_COLOR = missing_constant("GL_SRC_COLOR")
    glBlendFunc = missing_gl_func("glBlendFunc")
    glDepthMask = missing_gl_func("glDepthMask")
    glDisable = missing_gl_func("glDisable")
    glEnable = missing_gl_func("glEnable")


from pykotor.gl.native.gl_accel import (
    c_available as _gl_accel_c_available,
    compute_node_world_transforms as _c_compute_node_transforms,
)

logger = logging.getLogger(__name__)


def _pack_mat4(m: mat4) -> bytes:
    """Pack a glm.mat4 into 16 column-major floats as bytes."""
    vp = value_ptr(m)
    return struct.pack(
        "16f",
        vp[0],
        vp[1],
        vp[2],
        vp[3],
        vp[4],
        vp[5],
        vp[6],
        vp[7],
        vp[8],
        vp[9],
        vp[10],
        vp[11],
        vp[12],
        vp[13],
        vp[14],
        vp[15],
    )


def _unpack_mat4(data: bytes, offset: int = 0) -> mat4:
    """Unpack 16 column-major floats from bytes into a glm.mat4.

    Uses PyGLM's native from_bytes() (~6x faster than struct.unpack_from).
    """
    return mat4.from_bytes(data[offset : offset + 64])


class Model:
    def __init__(self, scene: Scene, root: Node):
        self._scene: Scene = scene
        self.root: Node = root
        # Flattened node hierarchy for batch C transform computation
        self._flat_local_transforms: bytes | None = None
        self._flat_parent_indices: bytes | None = None
        self._flat_mesh_indices: list[tuple[int, Any, bool]] | None = (
            None  # (flat_idx, mesh, render_flag)
        )
        self._flat_node_count: int = 0
        self._flat_built: bool = False

    def _build_flat_hierarchy(self):
        """Pre-flatten the node tree into arrays for batch C transform computation.

        Nodes are stored in BFS (topological) order so parent indices are always
        less than child indices, which the C function requires.
        """
        if self._flat_built:
            return

        nodes: list[Node] = []
        parent_map: list[int] = []

        # BFS traversal ensures topological order
        queue: list[tuple[Node, int]] = [(self.root, -1)]
        while queue:
            node, parent_idx = queue.pop(0)
            my_idx = len(nodes)
            nodes.append(node)
            parent_map.append(parent_idx)
            for child in node.children:
                queue.append((child, my_idx))

        n = len(nodes)
        self._flat_node_count = n

        # Pack local transforms
        local_parts: list[bytes] = []
        for node in nodes:
            local_parts.append(_pack_mat4(node._transform))  # noqa: SLF001
        self._flat_local_transforms = b"".join(local_parts)

        # Pack parent indices as int32
        self._flat_parent_indices = struct.pack(f"{n}i", *parent_map)

        # Record which flat indices have drawable meshes
        mesh_list: list[tuple[int, Any, bool]] = []
        for i, node in enumerate(nodes):
            if node.mesh is not None and node.render:
                mesh_list.append((i, node.mesh, True))
        self._flat_mesh_indices = mesh_list
        self._flat_built = True

    def draw(
        self,
        shader: Shader,
        transform: mat4,
        *,
        override_texture: str | None = None,
    ):
        # Use flattened C path if available
        if _gl_accel_c_available():
            self._draw_flat(shader, transform, override_texture)
        else:
            self.root.draw(shader, transform, override_texture)

    def _draw_flat(
        self,
        shader: Shader,
        transform: mat4,
        override_texture: str | None = None,
    ):
        """Draw using flattened node hierarchy + batch C transform computation.

        Instead of recursive Python calls through the node tree, this:
        1. Pre-flattens the tree once (BFS order)
        2. Computes ALL world transforms in a single C call
        3. Only iterates nodes that have meshes for GL draw calls
        """
        if not self._flat_built:
            self._build_flat_hierarchy()

        assert self._flat_local_transforms is not None
        assert self._flat_parent_indices is not None
        assert self._flat_mesh_indices is not None

        # One C call computes all N world transforms
        root_bytes = _pack_mat4(transform)
        world_bytes = _c_compute_node_transforms(
            self._flat_local_transforms,
            self._flat_parent_indices,
            root_bytes,
        )

        # Only iterate nodes with meshes (typically ~50-100 out of thousands)
        for flat_idx, mesh, _render in self._flat_mesh_indices:
            world_transform = _unpack_mat4(world_bytes, flat_idx * 64)  # 16 floats × 4 bytes
            mesh.draw(shader, world_transform, override_texture)

    def find(self, name: str) -> Node | None:
        nodes: list[Node] = [self.root]
        while nodes:
            node: Node = nodes.pop()
            if node.name.lower() == name.lower():
                return node
            nodes.extend(node.children)
        return None

    def all(self) -> list[Node]:
        all_nodes: list[Node] = []
        search: list[Node] = [self.root]
        while search:
            node: Node = search.pop()
            search.extend(node.children)
            all_nodes.append(node)
        return all_nodes

    def box(self) -> tuple[Vector3, Vector3]:
        return self.bounds(mat4())

    def bounds(self, transform: mat4) -> tuple[Vector3, Vector3]:
        """Calculate the bounding box of the model with the given transform."""
        min_point = Vector3(100000, 100000, 100000)
        max_point = Vector3(-100000, -100000, -100000)
        self._box_rec(self.root, transform, min_point, max_point)

        min_point.x -= 0.1
        min_point.y -= 0.1
        min_point.z -= 0.1
        max_point.x += 0.1
        max_point.y += 0.1
        max_point.z += 0.1

        return min_point, max_point

    def _box_rec(
        self,
        node: Node,
        transform: mat4,
        min_point: Vector3,
        max_point: Vector3,
    ):
        """Calculates bounding box of node and its children recursively.

        Call the 'box' function to get started here, don't call this directly.

        Args:
        ----
            node: {Node object whose bounding box is calculated}
            transform: {Transformation matrix to apply on node}
            min_point: {Vector3 to store minimum point of bounding box}
            max_point: {Vector3 to store maximum point of bounding box}.

        Processing Logic:
        ----------------
            - Apply transformation on node position and rotation
            - Iterate through vertices of node mesh if present
            - Transform vertices and update bounding box points
            - Recursively call function for each child node.
        """
        transform = transform * glm.translate(node._position)  # noqa: SLF001
        transform = transform * glm.mat4_cast(node._rotation)  # noqa: SLF001

        if node.mesh and node.render:
            vertex_count = len(node.mesh.vertex_data) // node.mesh.mdx_size
            for i in range(vertex_count):
                index = i * node.mesh.mdx_size + node.mesh.mdx_vertex
                data = node.mesh.vertex_data[index : index + 12]
                x, y, z = struct.unpack("fff", data)
                position = transform * Vector3(x, y, z)
                min_point.x = min(min_point.x, position.x)
                min_point.y = min(min_point.y, position.y)
                min_point.z = min(min_point.z, position.z)
                max_point.x = max(max_point.x, position.x)
                max_point.y = max(max_point.y, position.y)
                max_point.z = max(max_point.z, position.z)

        for child in node.children:
            self._box_rec(child, transform, min_point, max_point)


class Node:
    def __init__(
        self,
        scene: Scene,
        parent: Node | None,
        name: str,
    ):
        self._scene: Scene = scene
        self._parent: Node | None = parent
        self.name: str = name
        self._transform: mat4 = mat4()
        self._position: Vector3 = Vector3()
        self._rotation: quat = glm.quat()
        self.children: list[Node] = []
        self.render: bool = True
        self.mesh: Mesh | None = None

        self._recalc_transform()

    def root(self) -> Node | None:
        ancestor: Node | None = self._parent
        while ancestor:
            ancestor = ancestor._parent  # noqa: SLF001
        return ancestor

    def ancestors(self) -> list[Node]:
        ancestors: list[Node] = []
        ancestor: Node | None = self._parent
        while ancestor:
            ancestors.append(ancestor)
            ancestor = ancestor._parent  # noqa: SLF001
        return list(reversed(ancestors))

    def global_position(self) -> Vector3:
        ancestors: list[Node] = [*self.ancestors(), self]
        transform = mat4()
        for ancestor in ancestors:
            transform = transform * glm.translate(ancestor._position)  # noqa: SLF001
            transform = transform * glm.mat4_cast(ancestor._rotation)  # noqa: SLF001
        pos = vec3()
        glm.decompose(transform, vec3(), quat(), pos, vec3(), vec4())
        return Vector3(pos.x, pos.y, pos.z)

    def global_rotation(self) -> quat:
        ancestors: list[Node] = [*self.ancestors(), self]
        transform = mat4()
        for ancestor in ancestors:
            transform = transform * glm.translate(ancestor._position)  # noqa: SLF001
            transform = transform * glm.mat4_cast(ancestor._rotation)  # noqa: SLF001
        rotation = quat()
        glm.decompose(transform, vec3(), rotation, vec3(), vec3(), vec4())
        return rotation

    def global_transform(self) -> mat4:
        ancestors: list[Node] = [*self.ancestors(), self]
        transform = mat4()
        for ancestor in ancestors:
            transform = transform * glm.translate(ancestor._position)  # noqa: SLF001
            transform = transform * glm.mat4_cast(ancestor._rotation)  # noqa: SLF001
        return transform

    def transform(self) -> mat4:
        return copy(self._transform)

    def _recalc_transform(self):
        self._transform = glm.translate(self._position) * glm.mat4_cast(self._rotation)

    def position(self) -> Vector3:
        return copy(self._position)

    def set_position(self, x: float, y: float, z: float):
        self._position = Vector3(x, y, z)
        self._recalc_transform()

    def rotation(self) -> quat:
        return copy(self._rotation)

    def set_rotation(
        self,
        pitch: float,
        yaw: float,
        roll: float,
    ):
        self._rotation = quat(Vector3(pitch, yaw, roll))
        self._recalc_transform()

    def draw(
        self,
        shader: Shader,
        transform: mat4,
        override_texture: str | None = None,
    ):
        transform = transform * self._transform

        if self.mesh and self.render:
            self.mesh.draw(shader, transform, override_texture)

        for child in self.children:
            child.draw(shader, transform, override_texture=override_texture)


class Mesh:
    _blend_state: int = (
        -1
    )  # -1=unknown, 0=disabled, 1=enabled — tracks glEnable/glDisable(GL_BLEND)
    _last_alpha_cutoff: float = -1.0  # Tracks last alphaCutoff uniform to skip redundant sets
    _frame_tex_gen: int = (
        -1
    )  # Cached per-frame texture generation counter (set in reset_draw_state)
    # Per-frame GL state tracking to skip redundant calls
    _last_diffuse_tex_id: int = -1  # Last bound diffuse texture GL id
    _last_lightmap_tex_id: int = -1  # Last bound lightmap texture GL id
    _last_vao: int = -1  # Last bound VAO
    _last_active_texture: int = -1  # Last glActiveTexture unit
    _model_uniform_loc: int = -1  # Cached "model" uniform location for current shader

    def __init__(
        self,
        scene: Scene,
        node: Node,
        texture: str,
        lightmap: str,
        vertex_data: bytearray,
        element_data: bytearray,
        block_size: int,
        data_bitflags: int,
        vertex_offset: int,
        normal_offset: int,
        texture_offset: int,
        lightmap_offset: int,
    ):
        self.scene: Scene = scene
        self._node: Node = node

        self.texture: str = "NULL"
        self.lightmap: str = "NULL"

        self.vertex_data: bytearray = vertex_data
        self.mdx_size: int = block_size
        self.mdx_vertex: int = vertex_offset
        self.mdx_texture: int = texture_offset
        self.mdx_lightmap: int = lightmap_offset
        self._index_data: bytes = bytes(element_data)
        self._vertex_blob_cache: bytes | None = None

        # Cached texture references (avoids CaseInsensitiveDict lookup per frame)
        self._cached_diffuse_tex: Any = None
        self._cached_diffuse_name: str = ""
        self._cached_lightmap_tex: Any = None
        self._cached_lightmap_name: str = ""
        self._cached_tex_gen: int = -1

        if HAS_PYOPENGL:
            self._vao = glGenVertexArrays(1)
            self._vbo = glGenBuffers(1)
            self._ebo = glGenBuffers(1)
            glBindVertexArray(self._vao)

            glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
            # Convert vertex_data bytearray to MemoryView
            vertex_data_mv = memoryview(vertex_data)
            glBufferData(GL_ARRAY_BUFFER, len(vertex_data), vertex_data_mv, GL_STATIC_DRAW)

            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ebo)
            # Convert element_data bytearray to MemoryView
            element_data_mv = memoryview(element_data)
            glBufferData(
                GL_ELEMENT_ARRAY_BUFFER, len(element_data), element_data_mv, GL_STATIC_DRAW
            )

            if data_bitflags & 0x0001:
                glEnableVertexAttribArray(1)
                glVertexAttribPointer(
                    1, 3, GL_FLOAT, GL_FALSE, block_size, ctypes.c_void_p(vertex_offset)
                )

            if data_bitflags & 0x0020 and texture and texture != "NULL":
                glEnableVertexAttribArray(3)
                glVertexAttribPointer(
                    3, 2, GL_FLOAT, GL_FALSE, block_size, ctypes.c_void_p(texture_offset)
                )
                self.texture = texture

            if data_bitflags & 0x0004 and lightmap and lightmap != "NULL":
                glEnableVertexAttribArray(4)
                glVertexAttribPointer(
                    4, 2, GL_FLOAT, GL_FALSE, block_size, ctypes.c_void_p(lightmap_offset)
                )
                self.lightmap = lightmap

            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindVertexArray(0)
        else:
            self._vao: int = 0
            self._vbo: int = 0
            self._ebo: int = 0

        self._face_count: int = len(element_data) // 2

    def _resolve_texture(self, name: str, *, lightmap: bool = False):
        """Resolve texture with per-mesh cache; uses frame-level generation counter."""
        tex_gen = Mesh._frame_tex_gen
        if lightmap:
            if (
                self._cached_lightmap_tex is not None
                and self._cached_lightmap_name == name
                and self._cached_tex_gen == tex_gen
            ):
                return self._cached_lightmap_tex
            resolved = self.scene.texture(name, lightmap=True)
            self._cached_lightmap_tex = resolved
            self._cached_lightmap_name = name
            self._cached_tex_gen = tex_gen
            return resolved
        else:
            if (
                self._cached_diffuse_tex is not None
                and self._cached_diffuse_name == name
                and self._cached_tex_gen == tex_gen
            ):
                return self._cached_diffuse_tex
            resolved = self.scene.texture(name)
            self._cached_diffuse_tex = resolved
            self._cached_diffuse_name = name
            self._cached_tex_gen = tex_gen
            return resolved

    def draw(
        self,
        shader: Shader,
        transform: mat4,
        override_texture: str | None = None,
    ):
        # Ensure shader is bound (usually a no-op due to active-ID tracking).
        shader.use()

        # Upload model matrix directly — bypass shader.set_matrix4 dict lookup.
        loc = Mesh._model_uniform_loc
        if loc < 0:
            loc = shader.uniform("model")
            Mesh._model_uniform_loc = loc
        glUniformMatrix4fv(loc, 1, GL_FALSE, value_ptr(transform))

        # Resolve diffuse texture (cached per-frame via generation counter).
        tex_name = override_texture or self.texture
        diffuse_tex = self._resolve_texture(tex_name)
        diffuse_id: int = diffuse_tex._id  # noqa: SLF001

        # Bind diffuse on TEXTURE0 — skip if already bound.
        if Mesh._last_diffuse_tex_id != diffuse_id:
            if Mesh._last_active_texture != GL_TEXTURE0:
                glActiveTexture(GL_TEXTURE0)
                Mesh._last_active_texture = GL_TEXTURE0
            glBindTexture(GL_TEXTURE_2D, diffuse_id)
            Mesh._last_diffuse_tex_id = diffuse_id

        # Material hints (TXI blending) for effect meshes (light shafts, etc.).
        blend_mode = int(getattr(diffuse_tex, "blend_mode", 0))

        # Fast path: ~99% of meshes are opaque (blend_mode == 0, no alpha cutoff).
        if blend_mode == 0:
            alpha_cutoff = float(getattr(diffuse_tex, "alpha_cutoff", 0.0))
            if alpha_cutoff > 0.0:
                # Punchthrough / implicit cutout
                if Mesh._blend_state != 0:
                    glDisable(GL_BLEND)
                    Mesh._blend_state = 0
                glDepthMask(True)
                if Mesh._last_alpha_cutoff != alpha_cutoff:
                    shader.set_float("alphaCutoff", alpha_cutoff)
                    Mesh._last_alpha_cutoff = alpha_cutoff
            else:
                # Default opaque — most common
                if Mesh._blend_state != 0:
                    glDisable(GL_BLEND)
                    Mesh._blend_state = 0
                glDepthMask(True)
                if Mesh._last_alpha_cutoff != 0.0:
                    shader.set_float("alphaCutoff", 0.0)
                    Mesh._last_alpha_cutoff = 0.0
        elif blend_mode == 1:  # Additive
            has_alpha = bool(getattr(diffuse_tex, "has_alpha", True))
            if Mesh._blend_state != 1:
                glEnable(GL_BLEND)
                Mesh._blend_state = 1
            glDepthMask(False)
            glBlendFunc(GL_SRC_ALPHA if has_alpha else GL_SRC_COLOR, GL_ONE)
            if Mesh._last_alpha_cutoff != 0.0:
                shader.set_float("alphaCutoff", 0.0)
                Mesh._last_alpha_cutoff = 0.0
        else:  # blend_mode == 2: Punchthrough
            alpha_cutoff = float(getattr(diffuse_tex, "alpha_cutoff", 0.0))
            if Mesh._blend_state != 0:
                glDisable(GL_BLEND)
                Mesh._blend_state = 0
            glDepthMask(True)
            if Mesh._last_alpha_cutoff != alpha_cutoff:
                shader.set_float("alphaCutoff", alpha_cutoff)
                Mesh._last_alpha_cutoff = alpha_cutoff

        # Bind lightmap on TEXTURE1 — skip if already bound.
        lightmap_tex = self._resolve_texture(self.lightmap, lightmap=True)
        lightmap_id: int = lightmap_tex._id  # noqa: SLF001
        if Mesh._last_lightmap_tex_id != lightmap_id:
            if Mesh._last_active_texture != GL_TEXTURE1:
                glActiveTexture(GL_TEXTURE1)
                Mesh._last_active_texture = GL_TEXTURE1
            glBindTexture(GL_TEXTURE_2D, lightmap_id)
            Mesh._last_lightmap_tex_id = lightmap_id

        # Bind VAO and draw — skip VAO bind if already active.
        vao = self._vao
        if Mesh._last_vao != vao:
            glBindVertexArray(vao)
            Mesh._last_vao = vao
        glDrawElements(GL_TRIANGLES, self._face_count, GL_UNSIGNED_SHORT, None)

    @staticmethod
    def reset_draw_state(tex_gen: int = -1):
        """Reset tracked GL blend/alpha state at the start of each render pass."""
        Mesh._blend_state = -1
        Mesh._last_alpha_cutoff = -1.0
        Mesh._frame_tex_gen = tex_gen
        Mesh._last_diffuse_tex_id = -1
        Mesh._last_lightmap_tex_id = -1
        Mesh._last_vao = -1
        Mesh._last_active_texture = -1
        Mesh._model_uniform_loc = -1

    def vertex_blob(self) -> bytes:
        """Generate an interleaved vertex blob for rendering.

        Returns a bytes object containing interleaved vertex data:
        - 3 floats for position (x, y, z)
        - 2 floats for diffuse UV (u, v)
        - 2 floats for lightmap UV (u, v)
        """
        if self._vertex_blob_cache is not None:
            return self._vertex_blob_cache

        import numpy as np

        vertex_count = len(self.vertex_data) // self.mdx_size
        if vertex_count == 0:
            self._vertex_blob_cache = np.zeros((1, 7), dtype=np.float32).tobytes()
            return self._vertex_blob_cache

        blob = np.zeros((vertex_count, 7), dtype=np.float32)
        positions = np.frombuffer(
            self.vertex_data,
            dtype="<f4",
            count=vertex_count * 3,
            offset=self.mdx_vertex,
        ).reshape(vertex_count, 3)
        blob[:, 0:3] = positions

        if self.mdx_texture >= 0:
            diffuse = np.frombuffer(
                self.vertex_data,
                dtype="<f4",
                count=vertex_count * 2,
                offset=self.mdx_texture,
            ).reshape(vertex_count, 2)
            blob[:, 3:5] = diffuse

        if self.mdx_lightmap >= 0:
            lightmap = np.frombuffer(
                self.vertex_data,
                dtype="<f4",
                count=vertex_count * 2,
                offset=self.mdx_lightmap,
            ).reshape(vertex_count, 2)
            blob[:, 5:7] = lightmap

        self._vertex_blob_cache = blob.tobytes()
        return self._vertex_blob_cache

    @property
    def index_data(self) -> bytes:
        """Return the index data for the mesh."""
        return self._index_data


class Cube:
    def __init__(
        self,
        scene: Scene,
        min_point: Vector3 | None = None,
        max_point: Vector3 | None = None,
    ):
        self._scene = scene

        min_point = Vector3(-1.0, -1.0, -1.0) if min_point is None else min_point
        max_point = Vector3(1.0, 1.0, 1.0) if max_point is None else max_point

        vertices = np.array(
            [
                min_point.x,
                min_point.y,
                max_point.z,
                max_point.x,
                min_point.y,
                max_point.z,
                max_point.x,
                max_point.y,
                max_point.z,
                min_point.x,
                max_point.y,
                max_point.z,
                min_point.x,
                min_point.y,
                min_point.z,
                max_point.x,
                min_point.y,
                min_point.z,
                max_point.x,
                max_point.y,
                min_point.z,
                min_point.x,
                max_point.y,
                min_point.z,
            ],
            dtype="float32",
        )

        elements = np.array(
            [
                0,
                1,
                2,
                2,
                3,
                0,
                1,
                5,
                6,
                6,
                2,
                1,
                7,
                6,
                5,
                5,
                4,
                7,
                4,
                0,
                3,
                3,
                7,
                4,
                4,
                5,
                1,
                1,
                0,
                4,
                3,
                2,
                6,
                6,
                7,
                3,
            ],
            dtype="int16",
        )

        self.min_point: Vector3 = min_point
        self.max_point: Vector3 = max_point
        self._vertex_data = vertices
        self._index_data = elements
        self._face_count: int = len(elements)
        self._buffers_supported = False

        if HAS_PYOPENGL:
            try:
                self._vao = glGenVertexArrays(1)
                self._vbo = glGenBuffers(1)
                self._ebo = glGenBuffers(1)
                glBindVertexArray(self._vao)

                glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
                glBufferData(GL_ARRAY_BUFFER, len(vertices) * 4, vertices, GL_STATIC_DRAW)

                glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ebo)
                glBufferData(GL_ELEMENT_ARRAY_BUFFER, elements.nbytes, elements, GL_STATIC_DRAW)

                glEnableVertexAttribArray(1)
                glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))

                glBindBuffer(GL_ARRAY_BUFFER, 0)
                glBindVertexArray(0)
                self._buffers_supported = True
            except gl_error.NullFunctionError:
                logger.warning(
                    "OpenGL buffer objects are unavailable; falling back to CPU-only cube bounds."
                )
                self._face_count = 0
                self._vao = 0
                self._vbo = 0
                self._ebo = 0
        else:
            self._vao = 0
            self._vbo = 0
            self._ebo = 0

    def draw(self, shader: Shader, transform: mat4):
        if not self._buffers_supported:
            return
        if not HAS_PYOPENGL:
            raise gl_error.NullFunctionError("PyOpenGL is unavailable.")

        shader.set_matrix4("model", transform)
        glBindVertexArray(self._vao)
        glDrawElements(GL_TRIANGLES, self._face_count, GL_UNSIGNED_SHORT, None)

    def vertex_blob(self) -> bytes:
        """Interleaved vertex data (position only)."""
        vertex_count = len(self._vertex_data) // 3
        blob = np.zeros((vertex_count, 7), dtype=np.float32)
        blob[:, 0:3] = self._vertex_data.reshape(vertex_count, 3)
        return blob.tobytes()

    @property
    def index_data(self) -> bytes:
        return self._index_data.tobytes()


class Boundary:
    def __init__(
        self,
        scene: Scene,
        vertices: list[Vector3],
    ):
        self._scene: Scene = scene

        vertices_np, elements_np = self._build_nd(vertices)
        self._vertex_data: np.ndarray = vertices_np
        self._index_data: np.ndarray = elements_np
        self._face_count: int = len(elements_np)
        self._buffers_supported = False

        if HAS_PYOPENGL:
            try:
                self._vao = glGenVertexArrays(1)
                self._vbo = glGenBuffers(1)
                self._ebo = glGenBuffers(1)
                glBindVertexArray(self._vao)

                glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
                glBufferData(GL_ARRAY_BUFFER, len(vertices_np) * 4, vertices_np, GL_STATIC_DRAW)

                glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ebo)
                glBufferData(
                    GL_ELEMENT_ARRAY_BUFFER, elements_np.nbytes, elements_np, GL_STATIC_DRAW
                )

                glEnableVertexAttribArray(1)
                glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))

                glBindBuffer(GL_ARRAY_BUFFER, 0)
                glBindVertexArray(0)
                self._buffers_supported = True
            except gl_error.NullFunctionError:
                logger.warning(
                    "OpenGL buffer objects are unavailable; boundary rendering disabled."
                )
                self._face_count = 0
                self._vao = 0
                self._vbo = 0
                self._ebo = 0
        else:
            self._vao = 0
            self._vbo = 0
            self._ebo = 0

    @classmethod
    def from_circle(
        cls,
        scene: Scene,
        radius: float,
        smoothness: int = 10,
    ) -> Boundary:
        vertices: list[Vector3] = []
        for i in range(smoothness):
            x = math.cos(i / smoothness * math.pi / 2)
            y = math.sin(i / smoothness * math.pi / 2)
            vertices.append(Vector3(x, y, 0) * radius)
        for i in range(smoothness):
            x = math.cos(i / smoothness * math.pi / 2 + math.pi / 2)
            y = math.sin(i / smoothness * math.pi / 2 + math.pi / 2)
            vertices.append(Vector3(x, y, 0) * radius)
        for i in range(smoothness):
            x = math.cos(i / smoothness * math.pi / 2 + math.pi / 2 * 2)
            y = math.sin(i / smoothness * math.pi / 2 + math.pi / 2 * 2)
            vertices.append(Vector3(x, y, 0) * radius)
        for i in range(smoothness):
            x = math.cos(i / smoothness * math.pi / 2 + math.pi / 2 * 3)
            y = math.sin(i / smoothness * math.pi / 2 + math.pi / 2 * 3)
            vertices.append(Vector3(x, y, 0) * radius)
        return Boundary(scene, vertices)

    def draw(self, shader: Shader, transform: mat4):
        if not self._buffers_supported:
            return
        if not HAS_PYOPENGL:
            raise gl_error.NullFunctionError("PyOpenGL is unavailable.")

        shader.set_matrix4("model", transform)
        glBindVertexArray(self._vao)
        glDrawElements(GL_TRIANGLES, self._face_count, GL_UNSIGNED_SHORT, None)

    def vertex_blob(self) -> bytes:
        """Interleaved vertex data (position only)."""
        vertex_count = len(self._vertex_data) // 3
        blob = np.zeros((vertex_count, 7), dtype=np.float32)
        blob[:, 0:3] = self._vertex_data.reshape(vertex_count, 3)
        return blob.tobytes()

    @property
    def index_data(self) -> bytes:
        return self._index_data.tobytes()

    def _build_nd(self, vertices: list[Vector3]) -> tuple[np.ndarray, np.ndarray]:
        vertices_np: list[float] = []
        for vertex in vertices:
            vertices_np.extend([*vertex, *Vector3(vertex.x, vertex.y, vertex.z + 2)])

        faces_np: list[int] = []
        count = len(vertices) * 2
        for i, _vertex in enumerate(vertices):
            index1 = i * 2
            index2 = i * 2 + 2 if i * 2 + 2 < count else 0
            index3 = i * 2 + 1
            index4 = (i * 2 + 2) + 1 if (i * 2 + 2) + 1 < count else 1
            faces_np.extend([index1, index2, index3, index2, index4, index3])
        return np.array(vertices_np, dtype="float32"), np.array(faces_np, dtype="int16")


class Empty:
    def __init__(self, scene: Scene):
        self._scene: Scene = scene

    def draw(self, shader: Shader, transform: mat4): ...
