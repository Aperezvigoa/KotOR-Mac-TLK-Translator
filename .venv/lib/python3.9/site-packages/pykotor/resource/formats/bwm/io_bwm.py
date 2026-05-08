"""Binary reader/writer for KotOR walkmeshes (BWM/WOK).

KotOR.js walkmesh port: see .cursor/plans/kotorjs_walkmesh_port_plan.md

This module translates between on-disk WOK/BWM files and the in-memory BWM model
defined in `bwm_data.py`. The binary layout mirrors the game's expectations:

- Header:  "BWM " + "V1.0" + walkMeshType (4) + four hook float3 (48) + position (12) + 16x uint32
- Vertex array (float32 triplets)
- Face indices (uint32 triplets into the vertex array)
- Materials per face (uint32 SurfaceMaterial id)
- Face normals (float32 triplets)
- Planar distances (float32 per face)
- *AABB* nodes (bounds, face index or 0xFFFFFFFF, split plane, children)
- Walkable adjacencies (3 ints per walkable face; -1 for no neighbor)
- Edges (pairs of (edge_index, transition) where edge_index = face*3 + edge)
- Perimeters (1-based indices into the edge array for edges with final=True)

Important:
---------
Where faces or vertices must be converted to indices, we find indices by object
identity (the `is` operator), not value equality, to avoid collisions when value
equality is true for different objects. This complements the value-based
`__eq__`/`__hash__` used for comparisons on faces/vertices.
"""

from __future__ import annotations

import struct

from logging import Logger
from typing import TYPE_CHECKING

import kaitaistruct

from bioware_kaitai_formats.bwm import Bwm

from pykotor.common.stream import BinaryReader
from pykotor.resource.formats.bwm.bwm_data import (  # noqa: E402
    BWM,
    BWMFace,
    BWMType,
)
from pykotor.resource.type import ResourceReader, ResourceWriter, autoclose  # noqa: E402
from utility.common.geometry import SurfaceMaterial, Vector3  # noqa: E402

if TYPE_CHECKING:
    from pykotor.resource.formats.bwm.bwm_data import (
        BWMAdjacency,
        BWMEdge,
        BWMNodeAABB,
    )
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


def _load_bwm_from_kaitai(data: bytes) -> BWM:
    """Load walkmesh via Kaitai (geometry + materials); edges read with legacy uint32 rules."""
    parsed = Bwm.from_bytes(data)
    wok = BWM()
    wp = parsed.walkmesh_properties
    wok.walkmesh_type = BWMType(wp.walkmesh_type)
    r1, r2, a1, a2, pos = (
        wp.relative_use_position_1,
        wp.relative_use_position_2,
        wp.absolute_use_position_1,
        wp.absolute_use_position_2,
        wp.position,
    )
    wok.relative_hook1 = Vector3(r1.x, r1.y, r1.z)
    wok.relative_hook2 = Vector3(r2.x, r2.y, r2.z)
    wok.absolute_hook1 = Vector3(a1.x, a1.y, a1.z)
    wok.absolute_hook2 = Vector3(a2.x, a2.y, a2.z)
    wok.position = Vector3(pos.x, pos.y, pos.z)

    va = parsed.vertices
    vertices: list[Vector3] = (
        [Vector3(v.x, v.y, v.z) for v in va.vertices] if va is not None else []
    )

    faces: list[BWMFace] = []
    fi = parsed.face_indices
    if fi is not None:
        for tri in fi.faces:
            v1, v2, v3 = vertices[tri.v1_index], vertices[tri.v2_index], vertices[tri.v3_index]
            faces.append(BWMFace(v1, v2, v3))

    ma = parsed.materials
    if ma is not None:
        for face, material_id in zip(faces, ma.materials):
            face.material = SurfaceMaterial(material_id)

    dto = parsed.data_table_offsets
    br = BinaryReader.from_bytes(data, 0)
    if dto.edge_count > 0:
        br.seek(dto.edge_offset)
        for _ in range(dto.edge_count):
            edge_index = br.read_uint32()
            transition = br.read_uint32()
            if transition != 0xFFFFFFFF:
                face_index = edge_index // 3
                trans_index = edge_index % 3
                if trans_index == 0:
                    faces[face_index].trans1 = transition
                elif trans_index == 1:
                    faces[face_index].trans2 = transition
                elif trans_index == 2:
                    faces[face_index].trans3 = transition

    wok.faces = faces
    return wok


def _load_bwm_legacy(reader: BinaryReader) -> BWM:
    """Original BWM reader (Kaitai fallback)."""
    wok = BWM()

    file_type = reader.read_string(4)
    file_version = reader.read_string(4)

    if file_type != "BWM ":
        msg = f"Not a valid binary BWM file. Expected 'BWM ', got '{file_type}' (hex: {file_type.encode('latin1').hex()})"
        raise ValueError(msg)

    if file_version != "V1.0":
        msg = f"Unsupported BWM version: got '{file_version}', expected 'V1.0'"
        raise ValueError(msg)

    wok.walkmesh_type = BWMType(reader.read_uint32())
    wok.relative_hook1 = reader.read_vector3()
    wok.relative_hook2 = reader.read_vector3()
    wok.absolute_hook1 = reader.read_vector3()
    wok.absolute_hook2 = reader.read_vector3()
    wok.position = reader.read_vector3()

    vertices_count = reader.read_uint32()
    vertices_offset = reader.read_uint32()
    face_count = reader.read_uint32()
    indices_offset = reader.read_uint32()
    materials_offset = reader.read_uint32()
    _ = reader.read_uint32()
    _ = reader.read_uint32()
    _ = reader.read_uint32()
    _ = reader.read_uint32()
    _ = reader.read_uint32()
    _ = reader.read_uint32()
    _ = reader.read_uint32()
    edges_count = reader.read_uint32()
    edges_offset = reader.read_uint32()
    _ = reader.read_uint32()
    _ = reader.read_uint32()

    reader.seek(vertices_offset)
    vertices: list[Vector3] = [reader.read_vector3() for _ in range(vertices_count)]
    faces: list[BWMFace] = []
    reader.seek(indices_offset)
    for _ in range(face_count):
        i1, i2, i3 = (
            reader.read_uint32(),
            reader.read_uint32(),
            reader.read_uint32(),
        )
        faces.append(BWMFace(vertices[i1], vertices[i2], vertices[i3]))

    reader.seek(materials_offset)
    for face in faces:
        material_id = reader.read_uint32()
        face.material = SurfaceMaterial(material_id)

    reader.seek(edges_offset)
    for _ in range(edges_count):
        edge_index = reader.read_uint32()
        transition = reader.read_uint32()
        if transition != 0xFFFFFFFF:
            face_index = edge_index // 3
            trans_index = edge_index % 3
            if trans_index == 0:
                faces[face_index].trans1 = transition
            elif trans_index == 1:
                faces[face_index].trans2 = transition
            elif trans_index == 2:
                faces[face_index].trans3 = transition

    wok.faces = faces
    return wok


class BWMBinaryReader(ResourceReader):
    """Reads BWM/WOK (Walkmesh) files.

    Walkmesh files define collision geometry for areas, including walkable surfaces,
    adjacencies, AABB trees for spatial queries, and edge transitions.

    """

    def __init__(
        self,
        source: SOURCE_TYPES,
        offset: int = 0,
        size: int = 0,
    ):
        """Initializes a walkmesh reader (WOK/BWM).

        Args:
        ----
            source: {The source object to initialize from}
            offset: {The offset into the source}
            size: {The number of bytes to read from the source}.

        Returns:
        -------
            self: {The initialized Wok object}

        Processing Logic:
        ----------------
            - Initializes the superclass with the given source, offset and size
            - Sets the wok attribute to None
            - Initializes the position, relative and absolute hook vectors to null vectors
            - Sets up the instance attributes.
        """
        super().__init__(source, offset, size)
        self._wok: BWM | None = None
        self.position: Vector3 = Vector3.from_null()
        self.relative_hook1: Vector3 = Vector3.from_null()
        self.relative_hook2: Vector3 = Vector3.from_null()
        self.absolute_hook1: Vector3 = Vector3.from_null()
        self.absolute_hook2: Vector3 = Vector3.from_null()

    @autoclose
    def load(self, *, auto_close: bool = True) -> BWM:  # noqa: FBT001, FBT002, ARG002
        """Loads a WOK/BWM binary file into a BWM instance.

        Args:
        ----
            self: The BWMReader object
            auto_close: Whether to automatically close the file after loading

        Returns:
        -------
            BWM: The loaded BWM object

        Processing Logic:
        ----------------
            - Validates header and version
            - Reads properties, vertices, face indices, materials
            - Applies per-edge transitions to faces
            - Populates BWM.faces
        """
        data = self._reader.read_all()
        try:
            self._wok = _load_bwm_from_kaitai(data)
        except kaitaistruct.KaitaiStructError:
            self._wok = _load_bwm_legacy(BinaryReader.from_bytes(data, 0))
        return self._wok


class BWMBinaryWriter(ResourceWriter):
    HEADER_SIZE = 136

    def __init__(
        self,
        wok: BWM,
        target: TARGET_TYPES,
        *,
        regenerate_derived: bool = True,
        logger: Logger | None = None,
    ):
        super().__init__(target)
        self._wok: BWM = wok
        self._regenerate_derived: bool = regenerate_derived
        self._logger: Logger | None = logger

    @autoclose
    def write(self, *, auto_close: bool = True):  # noqa: FBT001, FBT002, ARG002  # pyright: ignore[reportUnusedParameters]
        """Writes a BWM instance to WOK/BWM binary format.

        Args:
        ----
            self: The walkmesh object
            auto_close: Whether to close the file after writing (default: True).

        Processing Logic:
        ----------------
            1. Extracts vertex, face, edge and metadata from the walkmesh
            2. Packs sections and computes offsets
            3. Writes header, counts and offsets, followed by section data
        """

        def _log(msg: str) -> None:
            if self._logger is not None:
                self._logger.debug(msg)  # noqa: G004

        # Reference: KotOR.js src/odyssey/OdysseyWalkMesh.ts:834-1019 (toExportBuffer)
        if self._regenerate_derived:
            _log("write: enforcing transition invariant")
            self._wok.enforce_transition_invariant()
            _log("write: asserting transition arrows invariant")
            self._wok.assert_transition_arrows_invariant()
        _log("write: collecting vertices")
        vertices: list[Vector3] = self._wok.vertices()
        _log(f"write: vertices count={len(vertices)}")

        # Reference: KotOR.js src/odyssey/OdysseyWalkMesh.ts:834-836 (toExportBuffer calls buildPerimeters).
        # Emit the canonical ordering (walkable faces first) to match engine/tooling expectations.
        # Reference: KotOR.js src/odyssey/OdysseyWalkMesh.ts:729-731 (rebuild: sort walkable first).
        _log("write: ordering faces (walkable first)")
        walkable: list[BWMFace] = [face for face in self._wok.faces if face.material.walkable()]
        unwalkable: list[BWMFace] = [
            face for face in self._wok.faces if not face.material.walkable()
        ]
        faces: list[BWMFace] = walkable + unwalkable
        _log(
            f"write: faces count={len(faces)} (walkable={len(walkable)}, unwalkable={len(unwalkable)})"
        )

        walkable = [face for face in faces if face.material.walkable()]
        _log("write: building AABB tree")
        aabbs: list[BWMNodeAABB] = self._wok.aabbs()
        _log(f"write: AABB nodes count={len(aabbs)}")

        vertex_offset = 136
        _log("write: packing vertex data")
        vertex_data: bytearray = bytearray()
        for vertex in vertices:
            vertex_data += struct.pack("fff", vertex.x, vertex.y, vertex.z)

        _log(f"write: vertex_data size={len(vertex_data)} bytes")
        indices_offset: int = vertex_offset + len(vertex_data)
        _log("write: packing face indices")
        indices_data: bytearray = bytearray()
        for face in faces:
            # Find vertex indices by object identity
            i1 = next(i for i, v in enumerate(vertices) if v is face.v1)
            i2 = next(i for i, v in enumerate(vertices) if v is face.v2)
            i3 = next(i for i, v in enumerate(vertices) if v is face.v3)
            indices_data += struct.pack("III", i1, i2, i3)

        _log(f"write: indices_data size={len(indices_data)} bytes")
        material_offset: int = indices_offset + len(indices_data)
        _log("write: packing materials")
        material_data: bytearray = bytearray()
        for face in faces:
            material_data += struct.pack("I", face.material.value)

        _log(f"write: material_data size={len(material_data)} bytes")
        # Reference: KotOR.js src/odyssey/OdysseyWalkMesh.ts:735-750 (rebuild: normal and coeff from vertices).
        normal_offset = material_offset + len(material_data)
        _log("write: packing face normals")
        normal_data = bytearray()
        for face in faces:
            normal = face.normal()
            normal_data += struct.pack("fff", normal.x, normal.y, normal.z)

        _log(f"write: normal_data size={len(normal_data)} bytes")
        coefficient_offset = normal_offset + len(normal_data)
        _log("write: packing planar coefficients")
        coeffeicent_data = bytearray()
        for face in faces:
            coeffeicent_data += struct.pack("f", face.planar_distance())

        # Reference: KotOR.js src/odyssey/OdysseyWalkMesh.ts:958-962 (toExportBuffer AABB write: min.z+10, max.z-10).
        aabb_offset = coefficient_offset + len(coeffeicent_data)
        aabb_data = bytearray()
        for aabb in aabbs:
            aabb_data += struct.pack("fff", aabb.bb_min.x, aabb.bb_min.y, aabb.bb_min.z + 10.0)
            aabb_data += struct.pack("fff", aabb.bb_max.x, aabb.bb_max.y, aabb.bb_max.z - 10.0)
            # Find face index by object identity
            face_idx = (
                0xFFFFFFFF
                if aabb.face is None
                else next(i for i, f in enumerate(faces) if f is aabb.face)
            )
            aabb_data += struct.pack("I", face_idx)
            aabb_data += struct.pack("I", 4)
            aabb_data += struct.pack("I", aabb.sigplane.value)
            # Find AABB indices by object identity
            # CRITICAL FIX: Use 0-based indices (not 1-based) for AABB children
            # Retail parsers treat these as zero-based array indices into the AABB table.
            #
            # Reference: wiki/BWM-File-Format.md (AABB tree; zero-based child indices).
            left_idx = (
                0xFFFFFFFF
                if aabb.left is None
                else next(i for i, a in enumerate(aabbs) if a is aabb.left)
            )
            right_idx = (
                0xFFFFFFFF
                if aabb.right is None
                else next(i for i, a in enumerate(aabbs) if a is aabb.right)
            )
            aabb_data += struct.pack("I", left_idx)
            aabb_data += struct.pack("I", right_idx)

        _log(f"write: aabb_data size={len(aabb_data)} bytes")
        # Adjacency matrix layout: see wiki reverse_engineering_findings (*io_bwm.py — adjacency note*).
        adjacency_offset = aabb_offset + len(aabb_data)
        _log("write: packing adjacency (walkable faces)")
        adjacency_data = bytearray()
        _adjacency_batch: list[
            tuple[BWMAdjacency | None, BWMAdjacency | None, BWMAdjacency | None]
        ] = self._wok.walkable_adjacency_tuples(walkable)
        for face_idx, face in enumerate(walkable):
            adjancencies: tuple[BWMAdjacency | None, BWMAdjacency | None, BWMAdjacency | None] = (
                _adjacency_batch[face_idx]
            )
            indexes: list[int] = []
            for adjacency in adjancencies:
                if adjacency is None:
                    indexes.append(-1)
                else:
                    # Find face index by object identity
                    idx = next(i for i, f in enumerate(faces) if f is adjacency.face)
                    indexes.append(idx * 3 + adjacency.edge)
            adjacency_data += struct.pack("iii", *indexes)

        _log(f"write: adjacency_data size={len(adjacency_data)} bytes")
        # Reference: KotOR.js src/odyssey/OdysseyWalkMesh.ts:838 (edge_size from perimeters), 993-1001 (edges from perimeter loops).
        edge_offset = adjacency_offset + len(adjacency_data)
        _log("write: collecting perimeter edges")
        # Get perimeter edges from the walkmesh
        # NOTE: edges() returns perimeter edges based on walkable face indices
        # We need to map these to the reordered face list (walkable + unwalkable)
        perimeter_edges: list[BWMEdge] = self._wok.edges()
        _log(f"write: perimeter_edges count={len(perimeter_edges)}")

        # Convert perimeter edges to use reordered face indices
        # IMPORTANT: We must use identity-based lookup (the `is` operator), NOT value-based
        # equality. BWMFace has custom __eq__/__hash__ that uses vertex coordinates and
        # transitions for equality. If two faces have the same coordinates and transitions
        # (e.g., a walkable and unwalkable face sharing geometry), using a dict would cause
        # key collisions and return the wrong face index. This would cause transitions to
        # be assigned to the wrong faces (e.g., unwalkable instead of walkable), breaking
        # pathfinding in the game.
        # Reference: wiki/BWM-File-Format.md - Edges section
        edges: list[BWMEdge] = []
        edge_index_map: dict[int, BWMEdge] = {}
        face_index_map: dict[int, int] = {id(face): idx for idx, face in enumerate(faces)}
        for edge in perimeter_edges:
            # Find the face index in the reordered list BY IDENTITY (not value equality)
            # This is critical: we need the exact object reference, not just an equal face
            face_idx = face_index_map.get(id(edge.face))
            if face_idx is None:
                # Face not found in reordered list (shouldn't happen, but handle gracefully)
                continue
            # Create new BWMEdge with correct face reference and transition
            # The edge.index is the local edge index (0, 1, or 2) within the face
            from pykotor.resource.formats.bwm.bwm_data import BWMEdge

            new_edge = BWMEdge(faces[face_idx], edge.index, edge.transition)
            edge_index = face_idx * 3 + edge.index
            edge_index_map[edge_index] = new_edge
            edges.append(new_edge)

        # Reference: KotOR.js src/odyssey/OdysseyWalkMesh.ts:838, 998-1006 (edges only from buildPerimeters).
        # When regenerating, emit perimeter-only edges (no non-perimeter roundtrip).
        if not self._regenerate_derived:
            for face in faces:
                face_idx = face_index_map[id(face)]
                transitions = (face.trans1, face.trans2, face.trans3)
                for edge_idx, transition in enumerate(transitions):
                    if transition is None:
                        continue
                    edge_index = face_idx * 3 + edge_idx
                    if edge_index in edge_index_map:
                        existing = edge_index_map[edge_index]
                        if existing.transition == -1:
                            existing.transition = transition
                        continue
                    from pykotor.resource.formats.bwm.bwm_data import BWMEdge

                    new_edge = BWMEdge(face, edge_idx, transition)
                    edge_index_map[edge_index] = new_edge
                    edges.append(new_edge)

        _log(f"write: edges list count={len(edges)}")
        _log("write: packing edge data")
        edge_data = bytearray()
        for edge in edges:
            # Find face index by object identity using the map
            face_idx = face_index_map[id(edge.face)]
            edge_index = face_idx * 3 + edge.index
            edge_data += struct.pack("ii", edge_index, edge.transition)

        _log(f"write: edge_data size={len(edge_data)} bytes")
        # Reference: KotOR.js src/odyssey/OdysseyWalkMesh.ts:1004-1009 (offset += perimeter.edges.length; write offset).
        # Find edge indices by object identity for perimeters (1-based index of last edge of each loop).
        _log("write: building perimeter indices")
        edge_identity_map: dict[int, int] = {id(edge): idx for idx, edge in enumerate(edges)}
        perimeters: list[int] = [edge_identity_map[id(edge)] + 1 for edge in edges if edge.final]
        _log(f"write: perimeters count={len(perimeters)}")
        perimeter_offset = edge_offset + len(edge_data)
        _log("write: packing perimeter data")
        perimeter_data = bytearray()
        for perimeter in perimeters:
            perimeter_data += struct.pack("I", perimeter)
        edges_count_out = len(edges)
        perimeters_count_out = len(perimeters)
        _log(f"write: perimeter_data size={len(perimeter_data)} bytes")

        # Reference: wiki/BWM-File-Format.md — walkMeshType, four hook float3s, position (64 bytes).
        _log("write: writing header (magic, type, hooks, position, counts, offsets)")
        self._writer.write_string("BWM V1.0")
        self._writer.write_uint32(self._wok.walkmesh_type.value)
        self._writer.write_vector3(self._wok.relative_hook1)
        self._writer.write_vector3(self._wok.relative_hook2)
        self._writer.write_vector3(self._wok.absolute_hook1)
        self._writer.write_vector3(self._wok.absolute_hook2)
        self._writer.write_vector3(self._wok.position)

        self._writer.write_uint32(len(vertices))
        self._writer.write_uint32(vertex_offset)
        self._writer.write_uint32(len(faces))
        self._writer.write_uint32(indices_offset)
        self._writer.write_uint32(material_offset)
        self._writer.write_uint32(normal_offset)
        self._writer.write_uint32(coefficient_offset)
        self._writer.write_uint32(len(aabbs))
        self._writer.write_uint32(aabb_offset)
        self._writer.write_uint32(0)
        self._writer.write_uint32(len(self._wok.walkable_faces()))
        self._writer.write_uint32(adjacency_offset)
        self._writer.write_uint32(edges_count_out)
        self._writer.write_uint32(edge_offset)
        self._writer.write_uint32(perimeters_count_out)
        self._writer.write_uint32(perimeter_offset)

        _log("write: writing vertex_data to stream")
        self._writer.write_bytes(vertex_data)
        _log("write: writing indices_data to stream")
        self._writer.write_bytes(indices_data)
        _log("write: writing material_data to stream")
        self._writer.write_bytes(material_data)
        _log("write: writing normal_data to stream")
        self._writer.write_bytes(normal_data)
        _log("write: writing coeffeicent_data to stream")
        self._writer.write_bytes(coeffeicent_data)
        _log("write: writing aabb_data to stream")
        self._writer.write_bytes(aabb_data)
        _log("write: writing adjacency_data to stream")
        self._writer.write_bytes(adjacency_data)
        _log("write: writing edge_data to stream")
        self._writer.write_bytes(edge_data)
        _log("write: writing perimeter_data to stream")
        self._writer.write_bytes(perimeter_data)
        _log("write: done")
