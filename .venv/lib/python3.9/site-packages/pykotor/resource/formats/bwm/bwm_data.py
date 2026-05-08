"""Binary WalkMesh (BWM/WOK) runtime model for KotOR (Aurora/NWN engine lineage).

KotOR areas use a walkmesh (stored on disk in WOK/BWM form) to describe the set of
triangles the player and AI can stand on, plus edge metadata for transitions
(e.g., doors, area hooks) and an acceleration structure (AABB tree) for queries.

This module contains a high-level, in-memory representation of that data:
 - BWM:     The entire walkmesh object (faces, transforms/hooks, helpers)
 - BWMFace: A single triangle with a material and up to 3 per-edge transition ids
 - BWMEdge: A boundary edge for perimeters (computed from geometry, not stored)
 - BWMAdjacency: Logical adjacency of one face/edge to a neighboring face/edge
 - BWMNodeAABB: AABB tree node for broad-phase intersection

KotOR.js walkmesh port: see .cursor/plans/kotorjs_walkmesh_port_plan.md

Observed retail behavior:
----------
    KotOR I and TSL resolve room walkmesh data by preferring the binary ``BWM V1.0`` resource
    and only then falling back to the ASCII walkmesh text path. The header ``walkmesh_type``
    field (file offset ``0x08``) distinguishes placeable/door meshes (``0``) from full area
    walkmeshes (``1``) that carry AABB trees, adjacency, edges, and perimeters.

    Maintainers: superseded walkmesh loader cross-references are **migrated** to the wiki
    engine-findings article (*PyKotor package: migrated library notes* and its BWM / walkmesh
    subsection).

    Third-party GitHub URL lines removed from this module are archived at
    ``wiki/reverse_engineering_findings_bwm_data_github_urls_pre_scrub.md``.

    Binary Format:
    ------------
    Header (8 bytes):
    Offset | Size | Type   | Description
    -------|------|--------|-------------
    0x00   | 4    | char[] | File Type ("BWM ")
    0x04   | 4    | char[] | File Version ("V1.0")
    Walkmesh Properties (52 bytes):
    Offset | Size | Type   | Description
    -------|------|--------|-------------
    0x08   | 4    | uint32 | Walkmesh Type (0=PWK/DWK, 1=WOK/Area)
    0x0C   | 12   | float3 | Relative Use Position 1 (x, y, z)
    0x18   | 12   | float3 | Relative Use Position 2 (x, y, z)
    0x24   | 12   | float3 | Absolute Use Position 1 (x, y, z)
    0x30   | 12   | float3 | Absolute Use Position 2 (x, y, z)
    0x3C   | 12   | float3 | Position (x, y, z)
    Data Tables (offsets stored in header):
    - Vertices: Array of float3 (x, y, z) per vertex
    - Face Indices: Array of uint32 triplets (vertex indices per face)
    - Materials: Array of uint32 (SurfaceMaterial ID per face)
    - Normals: Array of float3 (face normal per face)
    - Planar Distances: Array of float32 (per face)
    - AABB Nodes: Array of AABB structures (WOK only)
    - Adjacencies: Array of int32 triplets (WOK only, -1 for no neighbor)
    - Edges: Array of (edge_index, transition) pairs (WOK only)
    - Perimeters: Array of edge indices (WOK only)

Identity vs Equality
--------------------
Faces and vertices implement value-based equality to support comparisons, hashing
and tests. However, certain algorithms must map a specific face OBJECT back to its
index in the `BWM.faces` sequence to produce edge indices of the form:

    edge_index = face_index * 3 + local_edge_index

Value-based equality makes Python's list.index() unsuitable here because it may
return the index of a different but equal face. To avoid this, code in this module
uses identity-based selection (the `is` operator) when computing indices.
See `_index_by_identity()` and the writer logic in `io_bwm.py`.

Transitions vs Adjacency
------------------------
The `trans1`, `trans2`, and `trans3` fields on `BWMFace` are optional per-edge
transition indices into other area data (e.g., LYT/door references). They are NOT
unique identifiers and do not encode geometric adjacency. Adjacency is derived
purely from geometry (shared vertices on walkable faces).
"""

from __future__ import annotations

import itertools
import math

from copy import copy
from enum import IntEnum
from typing import TYPE_CHECKING, Any

from pykotor.resource.formats._base import BiowareResource, ComparableMixin
from utility.common.geometry import Face, SurfaceMaterial, Vector3

if TYPE_CHECKING:
    from typing_extensions import Literal  # pyright: ignore[reportMissingModuleSource]

# A lot of the code in this module was adapted from the KotorBlender fork by seedhartha:


class BWMType(IntEnum):
    """Walkmesh type enumeration.

    Determines whether walkmesh is for area geometry (WOK) or placeable/door objects (PWK/DWK).
    Area walkmeshes include AABB trees and adjacency data, while placeable walkmeshes are simpler.

    The on-disk header uses ``walkmesh_type`` at offset ``0x08``: ``0`` = placeable/door
    (PWK/DWK), ``1`` = area (WOK) with the heavier tables.

    Values:
    ------
        PlaceableOrDoor = 0: Walkmesh for placeable objects or doors (PWK/DWK)
            Simpler format without AABB trees or adjacency data
            Used for interactive objects that can be placed in areas

        AreaModel = 1: Walkmesh for area geometry (WOK)
            Full format with AABB trees, adjacencies, edges, and perimeters
            Used for area room geometry and pathfinding
    """

    PlaceableOrDoor = 0
    AreaModel = 1


class BWM(BiowareResource):
    """In-memory walkmesh model (faces, hooks, helpers).

    Walkmeshes define collision geometry for areas and objects. They consist of triangular
    faces with materials (determining walkability, line-of-sight blocking, etc.), optional
    edge transitions for area connections, and spatial acceleration structures (AABB trees)
    for efficient queries.

    Runtime layout mirrors what retail games stream from module archives.

    Attributes:
    ----------
        walkmesh_type: Type of walkmesh (AreaModel or PlaceableOrDoor)
            Determines which data structures are present (AABB trees, adjacencies, etc.)
            AreaModel (WOK) includes full spatial acceleration and adjacency data

        faces: List of triangular faces making up the walkmesh
            Each face has 3 vertices, a material (SurfaceMaterial), and optional transitions
            Faces define walkable surfaces, collision boundaries, and line-of-sight blockers

        position: 3D position offset for the walkmesh (x, y, z)
            Used to position walkmesh relative to area origin
            Typically (0, 0, 0) for area walkmeshes

        relative_hook1: First relative hook position (x, y, z)
            Reference: PyKotor io_bwm.py:119 (relative_hook1 reading)
            Hook point relative to walkmesh origin
            Used for door/transition placement (relative to walkmesh)

        relative_hook2: Second relative hook position (x, y, z)
            Reference: PyKotor io_bwm.py:120 (relative_hook2 reading)
            Hook point relative to walkmesh origin
            Used for door/transition placement (relative to walkmesh)

        absolute_hook1: First absolute hook position (x, y, z)
            Reference: PyKotor io_bwm.py:121 (absolute_hook1 reading)
            Hook point in world space (absolute coordinates)
            Used for door/transition placement (absolute world position)

        absolute_hook2: Second absolute hook position (x, y, z)
            Reference: PyKotor io_bwm.py:122 (absolute_hook2 reading)
            Hook point in world space (absolute coordinates)
            Used for door/transition placement (absolute world position)
    """

    COMPARABLE_FIELDS = (
        "walkmesh_type",
        "position",
        "relative_hook1",
        "relative_hook2",
        "absolute_hook1",
        "absolute_hook2",
    )
    COMPARABLE_SEQUENCE_FIELDS = ("faces",)

    def __init__(self):
        # Walkmesh type (AreaModel=WOK or PlaceableOrDoor=PWK/DWK)
        self.walkmesh_type: BWMType = BWMType.AreaModel

        # List of triangular faces (vertices, material, transitions)
        self.faces: list[BWMFace] = []

        # 3D position offset for walkmesh (typically 0,0,0 for areas)
        self.position: Vector3 = Vector3.from_null()

        # First relative hook position (door/transition placement, relative to walkmesh)
        self.relative_hook1: Vector3 = Vector3.from_null()

        # Second relative hook position (door/transition placement, relative to walkmesh)
        self.relative_hook2: Vector3 = Vector3.from_null()

        # First absolute hook position (door/transition placement, world space)
        self.absolute_hook1: Vector3 = Vector3.from_null()

        # Second absolute hook position (door/transition placement, world space)
        self.absolute_hook2: Vector3 = Vector3.from_null()

    def __eq__(self, other):
        if not isinstance(other, BWM):
            return NotImplemented  # type: ignore[no-any-return]
        return (
            self.walkmesh_type == other.walkmesh_type
            and self.faces == other.faces
            and self.position == other.position
            and self.relative_hook1 == other.relative_hook1
            and self.relative_hook2 == other.relative_hook2
            and self.absolute_hook1 == other.absolute_hook1
            and self.absolute_hook2 == other.absolute_hook2
        )

    def __hash__(self):
        return hash(
            (
                self.walkmesh_type,
                tuple(self.faces),
                self.position,
                self.relative_hook1,
                self.relative_hook2,
                self.absolute_hook1,
                self.absolute_hook2,
            ),
        )

    def walkable_faces(self) -> list[BWMFace]:
        """Get a list of walkable faces'.

        Args:
        ----
            self: Object containing faces

        Returns:
        -------
            list[BWMFace]: List of faces that are walkable

        Processing Logic:
        ----------------
            - Iterate through all faces in self.faces
            - Check if each face's material is walkable using face.material.walkable()
            - Add face to return list if walkable.
        """
        return [face for face in self.faces if face.material.walkable()]

    def unwalkable_faces(self) -> list[BWMFace]:
        """Return unwalkable faces in the mesh.

        Returns:
        -------
            list[BWMFace]: List of unwalkable faces in the mesh

        Processing Logic:
        ----------------
            - Iterate through all faces in the mesh
            - Check if the material of the face is not walkable
            - Add the face to the return list if material is not walkable
            - Return the list of unwalkable faces.
        """
        return [face for face in self.faces if not face.material.walkable()]

    def vertices(self) -> list[Vector3]:
        """Returns unique vertex objects referenced by faces in the walkmesh.

        Returns:
        -------
            A list of Vector3 objects. Uniqueness is identity-based; the order
            is first-seen while iterating faces.
        """
        seen: set[int] = set()
        vertices: list[Vector3] = []
        for face in self.faces:
            for v in (face.v1, face.v2, face.v3):
                vid = id(v)
                if vid not in seen:
                    seen.add(vid)
                    vertices.append(v)
        return vertices

    def aabbs(self) -> list[BWMNodeAABB]:
        """Returns a list of AABBs for all faces in the node.

        Args:
        ----
            self: The node object

        Returns:
        -------
            list[BWMNodeAABB]: List of AABB objects for each face

        Processing Logic:
        ----------------
            - Check walkmesh type - PWK/DWK (PlaceableOrDoor) don't have AABB trees
            - Recursively traverse the faces tree to collect all leaf faces
            - Calculate AABB for each leaf face
            - Add AABB to return list
            - Return list of all AABBs.
        """
        # PWK/DWK files don't have AABB trees (only WOK/AreaModel do)
        #
        # Reference: wiki/BWM-File-Format.md - AABB trees are WOK-only
        if self.walkmesh_type == BWMType.PlaceableOrDoor:
            return []

        # Empty walkmeshes cannot generate AABB trees
        if not self.faces:
            return []

        aabbs: list[BWMNodeAABB] = []
        self._aabbs_rec(aabbs, copy(self.faces))
        return aabbs

    def _aabbs_rec(
        self,
        aabbs: list[BWMNodeAABB],
        faces: list[BWMFace],
        rlevel: int = 0,
    ) -> BWMNodeAABB:
        """Recursively build an axis aligned bounding box tree from a list of faces.

        Args:
        ----
            aabbs: list[BWMNodeAABB]: Accumulator for AABBs
            faces: list[BWMFace]: List of faces to build tree from
            rlevel: int: Recursion level

        Returns:
        -------
            None: Tree is built by side effect of modifying aabbs

        Processing Logic:
        ----------------
            - Calculate bounding box of all faces
            - Split faces into left and right based on longest axis
            - Recursively build left and right trees
            - Stop when single face remains or axes exhausted
        """
        max_level: int = 128
        if rlevel > max_level:
            msg = f"recursion level must not exceed {max_level}, but is currently at level {rlevel}"
            raise ValueError(msg)

        if not faces:
            msg = "face_list must not be empty"
            raise ValueError(msg)

        # Calculate bounding box
        bbmin = Vector3(100000.0, 100000.0, 100000.0)
        bbmax = Vector3(-100000.0, -100000.0, -100000.0)
        bbcentre: Vector3 = Vector3.from_null()
        for face in faces:
            for vertex in (face.v1, face.v2, face.v3):
                for axis in range(3):
                    bbmin[axis] = min(bbmin[axis], vertex[axis])
                    bbmax[axis] = max(bbmax[axis], vertex[axis])
            bbcentre += face.centre()
        bbcentre = bbcentre / len(faces)

        # Only one face left - this node is a leaf
        if len(faces) == 1:
            leaf = BWMNodeAABB(bbmin, bbmax, faces[0], 0, None, None)
            aabbs.append(leaf)
            return leaf

        # Find longest axis
        split_axis: int = 0
        bb_size: Vector3 = bbmax - bbmin
        if bb_size.y > bb_size.x:
            split_axis = 1
        if bb_size.z > bb_size.y:
            split_axis = 2

        # Change axis in case points are coplanar with the split plane
        change_axis: bool = True
        for face in faces:
            change_axis = change_axis and face.centre()[split_axis] == bbcentre[split_axis]
        if change_axis:
            split_axis = 0 if split_axis == 2 else split_axis + 1

        # Put faces on the left and right side of the split plane into separate
        # lists. Try all axises to prevent tree degeneration.
        faces_left: list[BWMFace] = []
        faces_right: list[BWMFace] = []
        tested_axes = 1
        while True:
            faces_left = []
            faces_right = []
            for face in faces:
                centre: Vector3 = face.centre()
                if centre[split_axis] < bbcentre[split_axis]:
                    faces_left.append(face)
                else:
                    faces_right.append(face)

            if faces_left and faces_right:
                break

            split_axis = 0 if split_axis == 2 else split_axis + 1
            tested_axes += 1
            if tested_axes == 3:
                # All faces have the same center - create a single leaf node with all faces
                # This handles degenerate cases where faces cannot be split
                #
                # In degenerate cases, we create a single leaf containing all faces
                # The game engine can still use this for spatial queries, just less efficiently
                if len(faces) == 1:
                    leaf = BWMNodeAABB(bbmin, bbmax, faces[0], 0, None, None)
                    aabbs.append(leaf)
                    return leaf
                # Multiple faces with same center - create a single leaf with first face
                # This is a fallback for truly degenerate cases
                # NOTE: This may not match original file structure, but allows roundtrip
                leaf = BWMNodeAABB(bbmin, bbmax, faces[0], 0, None, None)
                aabbs.append(leaf)
                return leaf

        aabb = BWMNodeAABB(bbmin, bbmax, None, split_axis + 1, None, None)
        aabbs.append(aabb)

        # Recursively build left and right subtrees
        # Both lists are guaranteed to be non-empty due to the check above
        if faces_left:
            left_child = self._aabbs_rec(aabbs, faces_left, rlevel + 1)
            aabb.left = left_child
        # This should never happen due to the check above, but handle gracefully
        # Create a leaf node with the first face from faces_right as fallback
        elif faces_right:
            leaf = BWMNodeAABB(bbmin, bbmax, faces_right[0], 0, None, None)
            aabbs.append(leaf)
            aabb.left = leaf

        if faces_right:
            right_child = self._aabbs_rec(aabbs, faces_right, rlevel + 1)
            aabb.right = right_child
        # This should never happen due to the check above, but handle gracefully
        # Create a leaf node with the first face from faces_left as fallback
        elif faces_left:
            leaf = BWMNodeAABB(bbmin, bbmax, faces_left[0], 0, None, None)
            aabbs.append(leaf)
            aabb.right = leaf

        return aabb

    def _edge_endpoints(self, face: BWMFace, edge_id: int) -> tuple[Vector3, Vector3]:
        """Start and end vertex (by reference) for face edge. Edge 0=v1->v2, 1=v2->v3, 2=v3->v1.
        Used for KotOR.js-style perimeter chaining (vertIdx1/vertIdx2).
        """
        if edge_id == 0:
            return (face.v1, face.v2)
        if edge_id == 1:
            return (face.v2, face.v3)
        return (face.v3, face.v1)

    def edges(self) -> list[BWMEdge]:
        """Returns perimeter edges (edges with no walkable neighbor), chained by vertex continuity.

        Logic from KotOR.js src/odyssey/OdysseyWalkMesh.ts:756-814 (buildPerimeters):
        collect perimeter edges from walkable faces, then chain by matching edge end vertex to
        next edge start vertex (vertIdx2 == next.vertIdx1); close loop when next == start.
        PyKotor-unique: we derive perimeter from adjacency (no adjacent walkable = perimeter edge).
        """
        walkable: list[BWMFace] = [face for face in self.faces if face.material.walkable()]
        # OPTIMIZATION: Compute all adjacencies in batch instead of calling adjacencies() N times
        # This reduces complexity from O(N²) to O(N) by building an edge-to-faces mapping
        adjacencies: list[tuple[BWMAdjacency | None, BWMAdjacency | None, BWMAdjacency | None]] = (
            self._compute_all_adjacencies(walkable)
        )

        # Build mapping from walkable face index to overall face index
        # This is needed because adjacencies use overall face indices, but we iterate over walkable faces
        walkable_to_overall: dict[int, int] = {
            walkable_idx: self._index_by_identity(walkable_face)
            for walkable_idx, walkable_face in enumerate(walkable)
        }

        # Collect all perimeter edges with (face, edge_id, transition, id(v_start), id(v_end)) for chaining.
        # Reference: KotOR.js OdysseyWalkMesh.ts:757-762 (reduce walkableFaces to edges where adjacent is WalkmeshEdge).
        perimeter_candidates: list[tuple[BWMFace, int, int, int, int]] = []
        for i, j in itertools.product(range(len(walkable)), range(3)):
            if adjacencies[i][j] is not None:
                continue
            face: BWMFace = walkable[i]
            overall_face_idx: int = walkable_to_overall[i]
            face_for_trans: BWMFace = self.faces[overall_face_idx]
            trans: int | None = (
                face_for_trans.trans1
                if j == 0
                else (face_for_trans.trans2 if j == 1 else face_for_trans.trans3)
            )
            transition: int = -1 if trans is None else trans
            v_start, v_end = self._edge_endpoints(face, j)
            perimeter_candidates.append((face, j, transition, id(v_start), id(v_end)))

        # Chain perimeters by vertex continuity: next edge starts where current ends.
        # Reference: KotOR.js OdysseyWalkMesh.ts:781-817 (start_perimeter, find next by vertIdx1 == current.next, close when next == start).
        result: list[BWMEdge] = []
        remaining: list[tuple[BWMFace, int, int, int, int]] = list(perimeter_candidates)
        while remaining:
            face, edge_id, transition, start_id, end_id = remaining.pop(0)
            current_end_id: int = end_id
            loop_start_id: int = start_id
            result.append(BWMEdge(face, edge_id, transition, final=False))
            while True:
                if current_end_id == loop_start_id:
                    result[-1].final = True
                    break
                next_idx: int = next(
                    (
                        idx
                        for idx, (_, _, _, s_id, _) in enumerate(remaining)
                        if s_id == current_end_id
                    ),
                    -1,
                )
                if next_idx < 0:
                    result[-1].final = True
                    break
                n_face, n_edge, n_trans, _, n_end_id = remaining.pop(next_idx)
                current_end_id = n_end_id
                result.append(BWMEdge(n_face, n_edge, n_trans, final=False))
        return result

    def perimeter_edge_set(self) -> set[tuple[int, int]]:
        """Set of (face_index, edge_index) for every perimeter edge (identity-based face index).

        Reference: KotOR.js src/odyssey/OdysseyWalkMesh.ts:756-761 (buildPerimeters: collect edges from adjacentWalkableFaces a/b/c that are WalkmeshEdge).

        Only defined for AreaModel (WOK); returns empty set for PlaceableOrDoor (PWK/DWK).
        Used by enforce_transition_invariant and assert_transition_arrows_invariant.
        """
        if self.walkmesh_type != BWMType.AreaModel:
            return set()
        result: set[tuple[int, int]] = set()
        for edge in self.edges():
            face_idx = self._index_by_identity(edge.face)
            result.add((face_idx, edge.index))
        return result

    def enforce_transition_invariant(self) -> int:
        """Clear transitions on non-perimeter edges so only perimeter edges may have transitions.

        PyKotor invariant; KotOR.js only stores perimeter edges in export (no explicit clear step).
        Only runs for AreaModel (WOK); no-op for PlaceableOrDoor. Returns number of transitions cleared.
        """
        if self.walkmesh_type != BWMType.AreaModel:
            return 0
        perimeter: set[tuple[int, int]] = self.perimeter_edge_set()
        cleared: int = 0
        for i, face in enumerate(self.faces):
            if (i, 0) not in perimeter and face.trans1 is not None:
                face.trans1 = None
                cleared += 1
            if (i, 1) not in perimeter and face.trans2 is not None:
                face.trans2 = None
                cleared += 1
            if (i, 2) not in perimeter and face.trans3 is not None:
                face.trans3 = None
                cleared += 1
        return cleared

    def assert_transition_arrows_invariant(self) -> None:
        """Assert every edge with a transition is a perimeter edge (invariant for WOK).

        PyKotor invariant; KotOR.js only stores perimeter edges in export.
        Raises AssertionError with a clear message if any face has a transition on a non-perimeter edge.
        No-op for PlaceableOrDoor (PWK/DWK).
        """
        if self.walkmesh_type != BWMType.AreaModel:
            return
        perimeter: set[tuple[int, int]] = self.perimeter_edge_set()
        for i, face in enumerate(self.faces):
            if face.trans1 is not None and (i, 0) not in perimeter:
                msg = f"Face {i} edge 0 has transition but is not a perimeter edge"
                raise AssertionError(msg)
            if face.trans2 is not None and (i, 1) not in perimeter:
                msg = f"Face {i} edge 1 has transition but is not a perimeter edge"
                raise AssertionError(msg)
            if face.trans3 is not None and (i, 2) not in perimeter:
                msg = f"Face {i} edge 2 has transition but is not a perimeter edge"
                raise AssertionError(msg)

    @staticmethod
    def edge_inward_direction_xy(face: BWMFace, edge_index: int) -> tuple[Vector3, Vector3]:
        """Inward direction for a perimeter edge: from edge midpoint toward face centroid (XY plane).

        Reference: KotOR.js src/odyssey/WalkmeshEdge.ts:84-109 (updateNormal: midpoint, perpendicular XY, flip toward centroid).
        Returns (midpoint, direction) where direction is normalized (or zero if degenerate).
        Edge 0 = v1->v2, Edge 1 = v2->v3, Edge 2 = v3->v1.
        """
        if edge_index == 0:
            a, b = face.v1, face.v2
        elif edge_index == 1:
            a, b = face.v2, face.v3
        else:
            a, b = face.v3, face.v1
        mid: Vector3 = Vector3(
            (a.x + b.x) * 0.5,
            (a.y + b.y) * 0.5,
            (a.z + b.z) * 0.5,
        )
        centroid: Vector3 = Vector3(
            (face.v1.x + face.v2.x + face.v3.x) / 3.0,
            (face.v1.y + face.v2.y + face.v3.y) / 3.0,
            (face.v1.z + face.v2.z + face.v3.z) / 3.0,
        )
        dx: float = centroid.x - mid.x
        dy: float = centroid.y - mid.y
        length: float = math.sqrt(dx * dx + dy * dy)
        if length < 1e-9:
            return (mid, Vector3(0, 0, 0))
        return (mid, Vector3(dx / length, dy / length, 0))

    def raycast(
        self,
        origin: Vector3,
        direction: Vector3,
        max_distance: float = float("inf"),
        materials: set[SurfaceMaterial] | None = None,
    ) -> tuple[BWMFace, float] | None:
        """Raycast against the walkmesh using AABB tree acceleration.

        Finds the closest intersection between a ray and walkable faces in the walkmesh.
        For area walkmeshes (WOK), uses AABB tree for efficient traversal. For placeable
        walkmeshes (PWK/DWK), tests all faces directly.

        Args:
        ----
            origin: Starting point of the ray (Vector3)
            direction: Direction vector of the ray (Vector3, should be normalized)
            max_distance: Maximum distance to search along the ray (default: infinity)
            materials: Set of materials to test against (None = all walkable materials)

        Returns:
        -------
            tuple[BWMFace, float] | None: (face, distance) if intersection found, None otherwise
            - face: The intersected face
            - distance: Distance from origin to intersection point

        References:
        ----------

        Example:
        -------
            >>> bwm = read_bwm(data)
            >>> result = bwm.raycast(Vector3(0, 0, 10), Vector3(0, 0, -1), max_distance=20.0)
            >>> if result:
            ...     face, distance = result
            ...     print(f"Hit face at distance {distance}")
        """
        if not self.faces:
            return None

        # Default to walkable materials if not specified
        if materials is None:
            materials = {mat for mat in SurfaceMaterial if mat.walkable()}

        # For placeable/door walkmeshes, test all faces directly
        if self.walkmesh_type == BWMType.PlaceableOrDoor:
            return self._raycast_brute_force(origin, direction, max_distance, materials)

        # For area walkmeshes, use AABB tree
        aabbs = self.aabbs()
        if not aabbs:
            return self._raycast_brute_force(origin, direction, max_distance, materials)

        # Find root node (first node in list, or node with no parent)
        # Build set of all nodes that are children
        child_nodes = set()
        for aabb in aabbs:
            if aabb.left is not None:
                child_nodes.add(id(aabb.left))
            if aabb.right is not None:
                child_nodes.add(id(aabb.right))

        # Root is a node that is not a child of any other node
        root_nodes = [aabb for aabb in aabbs if id(aabb) not in child_nodes]
        if not root_nodes:
            # Fallback: use first node (tree structure may be flat or unclear)
            root = aabbs[0] if aabbs else None
            if root is None:
                return self._raycast_brute_force(origin, direction, max_distance, materials)
        else:
            root = root_nodes[0]  # Use first root node found

        # Traverse AABB tree
        return self._raycast_aabb(root, origin, direction, max_distance, materials)

    def _raycast_aabb(
        self,
        node: BWMNodeAABB,
        origin: Vector3,
        direction: Vector3,
        max_distance: float,
        materials: set[SurfaceMaterial],
    ) -> tuple[BWMFace, float] | None:
        """Recursively raycast through AABB tree."""
        # Test ray against AABB bounds
        if not self._ray_aabb_intersect(origin, direction, node.bb_min, node.bb_max, max_distance):
            return None

        # If leaf node, test ray against face
        if node.face is not None:
            if node.face.material not in materials:
                return None
            distance = self._ray_triangle_intersect(origin, direction, node.face, max_distance)
            if distance is not None:
                return (node.face, distance)
            return None

        # Internal node: test children
        best_result: tuple[BWMFace, float] | None = None
        best_distance = max_distance

        if node.left is not None:
            result = self._raycast_aabb(node.left, origin, direction, best_distance, materials)
            if result is not None:
                face, dist = result
                if dist < best_distance:
                    best_result = result
                    best_distance = dist

        if node.right is not None:
            result = self._raycast_aabb(node.right, origin, direction, best_distance, materials)
            if result is not None:
                face, dist = result
                if dist < best_distance:
                    best_result = result
                    best_distance = dist

        return best_result

    def _raycast_brute_force(
        self,
        origin: Vector3,
        direction: Vector3,
        max_distance: float,
        materials: set[SurfaceMaterial],
    ) -> tuple[BWMFace, float] | None:
        """Brute force raycast testing all faces."""
        best_result: tuple[BWMFace, float] | None = None
        best_distance = max_distance

        for face in self.faces:
            if face.material not in materials:
                continue
            distance = self._ray_triangle_intersect(origin, direction, face, best_distance)
            if distance is not None and distance < best_distance:
                best_result = (face, distance)
                best_distance = distance

        return best_result

    def _ray_aabb_intersect(
        self,
        origin: Vector3,
        direction: Vector3,
        bb_min: Vector3,
        bb_max: Vector3,
        max_distance: float,
    ) -> bool:
        """Test if ray intersects AABB using slab method.

        Reference: Fast Ray-Box Intersection (Williams et al., 2005)
        """
        # Avoid division by zero
        inv_dir = Vector3(
            1.0 / direction.x if direction.x != 0.0 else float("inf"),
            1.0 / direction.y if direction.y != 0.0 else float("inf"),
            1.0 / direction.z if direction.z != 0.0 else float("inf"),
        )

        tmin = (bb_min.x - origin.x) * inv_dir.x
        tmax = (bb_max.x - origin.x) * inv_dir.x

        if inv_dir.x < 0:
            tmin, tmax = tmax, tmin

        tymin = (bb_min.y - origin.y) * inv_dir.y
        tymax = (bb_max.y - origin.y) * inv_dir.y

        if inv_dir.y < 0:
            tymin, tymax = tymax, tymin

        if (tmin > tymax) or (tymin > tmax):
            return False

        tmin = max(tmin, tymin)
        tmax = min(tmax, tymax)

        tzmin = (bb_min.z - origin.z) * inv_dir.z
        tzmax = (bb_max.z - origin.z) * inv_dir.z

        if inv_dir.z < 0:
            tzmin, tzmax = tzmax, tzmin

        if (tmin > tzmax) or (tzmin > tmax):
            return False

        tmin = max(tmin, tzmin)
        tmax = min(tmax, tzmax)

        # Check if intersection is within max_distance
        if tmin < 0:
            tmin = tmax
        if tmin < 0 or tmin > max_distance:
            return False

        return True

    def _ray_triangle_intersect(
        self,
        origin: Vector3,
        direction: Vector3,
        face: BWMFace,
        max_distance: float,
    ) -> float | None:
        """Test ray-triangle intersection using Möller-Trumbore algorithm.
        Reference: "Fast, Minimum Storage Ray/Triangle Intersection" (Möller & Trumbore, 1997)
        """

        def cross(a: Vector3, b: Vector3) -> Vector3:
            """Compute cross product of two Vector3."""
            return Vector3(
                a.y * b.z - a.z * b.y,
                a.z * b.x - a.x * b.z,
                a.x * b.y - a.y * b.x,
            )

        v0 = face.v1
        v1 = face.v2
        v2 = face.v3

        edge1 = v1 - v0
        edge2 = v2 - v0
        h = cross(direction, edge2)
        a = edge1.dot(h)

        # Ray is parallel to triangle
        if abs(a) < 1e-6:
            return None

        f = 1.0 / a
        s = origin - v0
        u = f * s.dot(h)

        if u < 0.0 or u > 1.0:
            return None

        q = cross(s, edge1)
        v = f * direction.dot(q)

        if v < 0.0 or u + v > 1.0:
            return None

        # Intersection found, compute distance
        t = f * edge2.dot(q)

        if t > 1e-6 and t < max_distance:
            return t

        return None

    def point_in_face_2d(
        self,
        point: Vector3,
        face: BWMFace,
    ) -> bool:
        """Test if a 2D point (X, Y) is inside a face using barycentric coordinates.

        This method projects the face and point to the XY plane and tests containment.
        The Z coordinate is ignored for the containment test.

        Args:
        ----
            point: Point to test (Vector3, Z coordinate ignored)
            face: Face to test against (BWMFace)

        Returns:
        -------
            bool: True if point is inside the face (in XY plane), False otherwise

        References:
        ----------

        Example:
        -------
            >>> bwm = read_bwm(data)
            >>> point = Vector3(5.0, 3.0, 0.0)
            >>> face = bwm.faces[0]
            >>> if bwm.point_in_face_2d(point, face):
            ...     print("Point is inside face")
        """

        # Use sign-based method (same-side test)
        def sign(p1: Vector3, p2: Vector3, p3: Vector3) -> float:
            """Compute signed area of triangle (p1, p2, p3) in XY plane."""
            return (p1.x - p3.x) * (p2.y - p3.y) - (p2.x - p3.x) * (p1.y - p3.y)

        v1 = face.v1
        v2 = face.v2
        v3 = face.v3

        d1 = sign(point, v1, v2)
        d2 = sign(point, v2, v3)
        d3 = sign(point, v3, v1)

        has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
        has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)

        # Point is inside if all signs are same (not both positive and negative)
        return not (has_neg and has_pos)

    def get_height_at(
        self,
        x: float,
        y: float,
        materials: set[SurfaceMaterial] | None = None,
    ) -> float | None:
        """Get the Z-height (elevation) at a given (X, Y) point.

        Finds the walkable face containing the point and returns its Z coordinate at that location.
        Uses AABB tree for efficient spatial queries on area walkmeshes.

        Args:
        ----
            x: X coordinate
            y: Y coordinate
            materials: Set of materials to consider (None = all walkable materials)

        Returns:
        -------
            float | None: Z coordinate if point is on a walkable face, None otherwise

        References:
        ----------
        Libraries/PyKotor/src/utility/common/geometry.py:1270-1292 (Face.determine_z)


        Example:
        -------
            >>> bwm = read_bwm(data)
            >>> height = bwm.get_height_at(10.0, 5.0)
            >>> if height is not None:
            ...     print(f"Height at (10, 5) is {height}")
        """
        # Default to walkable materials if not specified
        if materials is None:
            materials = {mat for mat in SurfaceMaterial if mat.walkable()}

        # Find face containing the point
        face = self.find_face_at(x, y, materials)
        if face is None:
            return None

        # Check if face is flat (all vertices have same Z)
        if abs(face.v1.z - face.v2.z) < 1e-6 and abs(face.v2.z - face.v3.z) < 1e-6:
            # Flat face: return Z coordinate directly
            return face.v1.z

        # Use face's determine_z method to compute Z coordinate
        try:
            return face.determine_z(x, y)
        except ZeroDivisionError:
            # Fallback: if determine_z fails (degenerate case), return average Z
            return (face.v1.z + face.v2.z + face.v3.z) / 3.0

    def find_face_at(
        self,
        x: float,
        y: float,
        materials: set[SurfaceMaterial] | None = None,
    ) -> BWMFace | None:
        """Find the walkable face containing a given (X, Y) point.

        Uses AABB tree for efficient spatial queries on area walkmeshes. For placeable
        walkmeshes, tests all faces directly.

        Args:
        ----
            x: X coordinate
            y: Y coordinate
            materials: Set of materials to consider (None = all walkable materials)

        Returns:
        -------
            BWMFace | None: Face containing the point, or None if not found

        References:
        ----------

        Example:
        -------
            >>> bwm = read_bwm(data)
            >>> face = bwm.find_face_at(10.0, 5.0)
            >>> if face:
            ...     print(f"Found face with material {face.material}")
        """
        point = Vector3(x, y, 0.0)

        # Default to walkable materials if not specified
        if materials is None:
            materials = {mat for mat in SurfaceMaterial if mat.walkable()}

        # For placeable/door walkmeshes, test all faces directly
        if self.walkmesh_type == BWMType.PlaceableOrDoor:
            return self._find_face_brute_force(point, materials)

        # For area walkmeshes, use AABB tree
        aabbs = self.aabbs()
        if not aabbs:
            return self._find_face_brute_force(point, materials)

        # Find root node (node with no parent)
        child_nodes = set()
        for aabb in aabbs:
            if aabb.left is not None:
                child_nodes.add(id(aabb.left))
            if aabb.right is not None:
                child_nodes.add(id(aabb.right))

        root_nodes = [aabb for aabb in aabbs if id(aabb) not in child_nodes]
        if not root_nodes:
            # Fallback: use first node (tree structure may be flat or unclear)
            root = aabbs[0] if aabbs else None
            if root is None:
                return self._find_face_brute_force(point, materials)
        else:
            root = root_nodes[0]

        # Traverse AABB tree
        return self._find_face_aabb(root, point, materials)

    def _find_face_aabb(
        self,
        node: BWMNodeAABB,
        point: Vector3,
        materials: set[SurfaceMaterial],
    ) -> BWMFace | None:
        """Recursively search AABB tree for face containing point."""
        # Test if point is in AABB bounds (only check X and Y for 2D point-in-face)
        if not (
            node.bb_min.x <= point.x <= node.bb_max.x and node.bb_min.y <= point.y <= node.bb_max.y
        ):
            return None

        # If leaf node, test point against face
        if node.face is not None:
            if node.face.material not in materials:
                return None
            if self.point_in_face_2d(point, node.face):
                return node.face
            return None

        # Internal node: test children
        if node.left is not None:
            result = self._find_face_aabb(node.left, point, materials)
            if result is not None:
                return result

        if node.right is not None:
            result = self._find_face_aabb(node.right, point, materials)
            if result is not None:
                return result

        return None

    def _find_face_brute_force(
        self,
        point: Vector3,
        materials: set[SurfaceMaterial],
    ) -> BWMFace | None:
        """Brute force search testing all faces."""
        for face in self.faces:
            if face.material not in materials:
                continue
            if self.point_in_face_2d(point, face):
                return face
        return None

    def _index_by_identity(
        self,
        face: BWMFace,
    ) -> int:
        """Find the index of a face by object identity, not value equality.

        Args:
        ----
            face: The face object to find.

        Returns:
        -------
            The index of the face in self.faces.

        Raises:
        ------
            ValueError: If the face is not found.
        """
        for i, f in enumerate(self.faces):
            if f is face:
                return i
        msg = "Face not found in faces list"
        raise ValueError(msg)

    def walkable_adjacency_tuples(
        self,
        walkable: list[BWMFace],
    ) -> list[tuple[BWMAdjacency | None, BWMAdjacency | None, BWMAdjacency | None]]:
        """Public alias for :meth:`_compute_all_adjacencies` (BWM binary writer hot path)."""
        return self._compute_all_adjacencies(walkable)

    def _compute_all_adjacencies(
        self,
        walkable: list[BWMFace],
    ) -> list[tuple[BWMAdjacency | None, BWMAdjacency | None, BWMAdjacency | None]]:
        """Compute all adjacencies for walkable faces in a single batch operation.

        This optimized method builds an edge-to-faces mapping to reduce complexity
        from O(N²) to O(N) compared to calling adjacencies() individually for each face.

        Args:
        ----
            walkable: List of walkable faces to compute adjacencies for.

        Returns:
        -------
            List of adjacency tuples, one per walkable face.
            Each tuple contains (adj1, adj2, adj3) where each adj is BWMAdjacency | None.
        """
        # Build edge-to-faces mapping: edge (frozenset of 2 vertices) -> list of (face, edge_index) tuples
        # This allows O(1) lookups instead of O(N) searches
        edge_to_faces: dict[frozenset[Vector3], list[tuple[BWMFace, int]]] = {}

        # Define edge vertices for each face edge
        # Edge 0: v1->v2, Edge 1: v2->v3, Edge 2: v3->v1
        for face in walkable:
            # Edge 0: v1->v2
            edge0 = frozenset([face.v1, face.v2])
            if edge0 not in edge_to_faces:
                edge_to_faces[edge0] = []
            edge_to_faces[edge0].append((face, 0))

            # Edge 1: v2->v3
            edge1 = frozenset([face.v2, face.v3])
            if edge1 not in edge_to_faces:
                edge_to_faces[edge1] = []
            edge_to_faces[edge1].append((face, 1))

            # Edge 2: v3->v1
            edge2 = frozenset([face.v3, face.v1])
            if edge2 not in edge_to_faces:
                edge_to_faces[edge2] = []
            edge_to_faces[edge2].append((face, 2))

        # Now compute adjacencies for each face by looking up edges
        result: list[tuple[BWMAdjacency | None, BWMAdjacency | None, BWMAdjacency | None]] = []

        for face in walkable:
            adj1: BWMAdjacency | None = None
            adj2: BWMAdjacency | None = None
            adj3: BWMAdjacency | None = None

            # Check edge 0 (v1->v2): mirror per-face adjacencies() — last matching neighbor wins.
            edge0 = frozenset([face.v1, face.v2])
            if edge0 in edge_to_faces:
                for other_face, other_edge in edge_to_faces[edge0]:
                    if other_face is not face:
                        adj1 = BWMAdjacency(other_face, other_edge)

            # Check edge 1 (v2->v3)
            edge1 = frozenset([face.v2, face.v3])
            if edge1 in edge_to_faces:
                for other_face, other_edge in edge_to_faces[edge1]:
                    if other_face is not face:
                        adj2 = BWMAdjacency(other_face, other_edge)

            # Check edge 2 (v3->v1)
            edge2 = frozenset([face.v3, face.v1])
            if edge2 in edge_to_faces:
                for other_face, other_edge in edge_to_faces[edge2]:
                    if other_face is not face:
                        adj3 = BWMAdjacency(other_face, other_edge)

            result.append((adj1, adj2, adj3))

        return result

    def adjacencies(
        self,
        face: BWMFace,
    ) -> tuple[BWMAdjacency | None, BWMAdjacency | None, BWMAdjacency | None]:
        """Finds adjacencies of a face.

        Args:
        ----
            face: {Face}: Face to find adjacencies for

        Returns:
        -------
            tuple: {Tuple of adjacencies or None}

        Processing Logic:
        ----------------
            1. Get list of walkable faces
            2. Define edge lists for each potential adjacency
            3. Iterate through walkable faces and check if edges match using a bit flag
            4. Return adjacencies or None.
        """
        walkable: list[BWMFace] = self.walkable_faces()
        adj1: list[Vector3] = [face.v1, face.v2]
        adj2: list[Vector3] = [face.v2, face.v3]
        adj3: list[Vector3] = [face.v3, face.v1]

        adj_index1 = None
        adj_index2 = None
        adj_index3 = None

        def matches(
            face_obj: BWMFace,
            edges: list[Vector3],
        ) -> Literal[2, 1, 0, -1]:
            flag = 0x00
            if face_obj.v1 in edges:
                flag += 0x01
            if face_obj.v2 in edges:
                flag += 0x02
            if face_obj.v3 in edges:
                flag += 0x04
            edge: Literal[2, 1, 0, -1] = -1
            if flag == 0x03:
                edge = 0
            if flag == 0x06:
                edge = 1
            if flag == 0x05:
                edge = 2
            return edge

        for other in walkable:
            if other is face:
                continue
            edge_match1 = matches(other, adj1)
            edge_match2 = matches(other, adj2)
            edge_match3 = matches(other, adj3)

            if edge_match1 != -1:
                adj_index1 = BWMAdjacency(other, edge_match1)
            if edge_match2 != -1:
                adj_index2 = BWMAdjacency(other, edge_match2)
            if edge_match3 != -1:
                adj_index3 = BWMAdjacency(other, edge_match3)

        return adj_index1, adj_index2, adj_index3

    def box(self) -> tuple[Vector3, Vector3]:
        """Calculates bounding box of the mesh.

        Args:
        ----
            self: Mesh object

        Returns:
        -------
            tuple[Vector3, Vector3]: Bounding box minimum and maximum points

        Processing Logic:
        ----------------
            - Initialize bounding box minimum and maximum points to extreme values
            - Iterate through all vertices of the mesh
            - Update minimum x, y, z values of bbmin
            - Update maximum x, y, z values of bbmax
            - Return bounding box minimum and maximum points.
        """
        bbmin = Vector3(1000000, 1000000, 1000000)
        bbmax = Vector3(-1000000, -1000000, -1000000)
        for vertex in self.vertices():
            self._handle_vertex(bbmin, vertex, bbmax)
        return bbmin, bbmax

    def _handle_vertex(self, bbmin: Vector3, vertex: Vector3, bbmax: Vector3):
        """Update bounding box with vertex position.

        Args:
        ----
            bbmin: Vector3 - Bounding box minimum point
            vertex: Vector3 - Vertex position
            bbmax: Vector3 - Bounding box maximum point

        Returns:
        -------
            None - Updates bbmin and bbmax in place

        Processing Logic:
        ----------------
            - Compare vertex x, y, z to bbmin x, y, z and update bbmin with minimum
            - Compare vertex x, y, z to bbmax x, y, z and update bbmax with maximum.
        """
        bbmin.x = min(bbmin.x, vertex.x)
        bbmin.y = min(bbmin.y, vertex.y)
        bbmin.z = min(bbmin.z, vertex.z)
        bbmax.x = max(bbmax.x, vertex.x)
        bbmax.y = max(bbmax.y, vertex.y)
        bbmax.z = max(bbmax.z, vertex.z)

    def faceAt(
        self,
        x: float,
        y: float,
    ) -> BWMFace | None:
        """Returns the face at the given 2D coordinates if there is one otherwise returns None.

        Args:
        ----
            x: The x coordinate.
            y: The y coordinate.

        Returns:
        -------
            BWMFace object or None.
        """
        # Try C-accelerated path first
        try:
            from pykotor.gl.native.render2d_accel import batch_face_at_direct, is_available

            if is_available() and self.faces:
                face_verts_flat = self._get_face_verts_flat()
                idx = batch_face_at_direct(face_verts_flat, x, y)
                if idx >= 0 and idx < len(self.faces):
                    return self.faces[idx]
                return None
        except Exception:  # noqa: BLE001
            pass

        # Pure-Python fallback
        for face in self.faces:
            v1 = face.v1
            v2 = face.v2
            v3 = face.v3

            # Point-in-triangle via signed cross-product edge tests (2D, XY plane).
            c1 = (v2.x - v1.x) * (y - v1.y) - (v2.y - v1.y) * (x - v1.x)
            c2 = (v3.x - v2.x) * (y - v2.y) - (v3.y - v2.y) * (x - v2.x)
            c3 = (v1.x - v3.x) * (y - v3.y) - (v1.y - v3.y) * (x - v3.x)

            if (c1 < 0 and c2 < 0 and c3 < 0) or (c1 > 0 and c2 > 0 and c3 > 0):
                return face
        return None

    def _get_face_verts_flat(self) -> bytes:
        """Get or build cached flat vertex array for C-accelerated faceAt.

        Returns bytes of N×6 floats: (v1x, v1y, v2x, v2y, v3x, v3y) per face.
        """
        cached = getattr(self, "_face_verts_flat_cache", None)
        if cached is not None:
            return cached
        import array as _array

        arr = _array.array("f")
        for face in self.faces:
            arr.append(face.v1.x)
            arr.append(face.v1.y)
            arr.append(face.v2.x)
            arr.append(face.v2.y)
            arr.append(face.v3.x)
            arr.append(face.v3.y)
        result = arr.tobytes()
        self._face_verts_flat_cache: bytes | None = result
        return result

    def _invalidate_face_cache(self):
        """Invalidate the cached flat vertex array (call after modifying faces/vertices)."""
        self._face_verts_flat_cache = None

    def translate(
        self,
        x: float,
        y: float,
        z: float,
    ):
        """Shifts the position of the walkmesh.

        Args:
        ----
            x: How many units to shift on the X-axis.
            y: How many units to shift on the Y-axis.
            z: How many units to shift on the Z-axis.
        """
        for vertex in self.vertices():
            vertex.x += x
            vertex.y += y
            vertex.z += z
        self._invalidate_face_cache()

    def rotate(
        self,
        degrees: float,
    ):
        """Rotates the walkmesh around the Z-axis counter-clockwise.

        Args:
        ----
            degrees: The angle to rotate in degrees.
        """
        radians = math.radians(degrees)
        cos = math.cos(radians)
        sin = math.sin(radians)

        for vertex in self.vertices():
            x, y = vertex.x, vertex.y
            vertex.x = x * cos - y * sin
            vertex.y = x * sin + y * cos
        self._invalidate_face_cache()

    def change_lyt_indexes(
        self,
        old: int,
        new: int | None,
    ):
        """Changes layout indexes in faces.

        Args:
        ----
            old: Index to replace
            new: New index to set or None

        Processing Logic:
        ----------------
            - Loops through all faces in the object
            - Checks if face's trans1, trans2, trans3 attributes equal old index
            - If equal, sets the transition to new index.
        """
        for face in self.faces:
            if face.trans1 == old:
                face.trans1 = new
            if face.trans2 == old:
                face.trans2 = new
            if face.trans3 == old:
                face.trans3 = new

    def flip(
        self,
        x: bool,  # noqa: FBT001
        y: bool,  # noqa: FBT001
    ):
        """Flips the walkmesh around the specified axes.

        Args:
        ----
            x: Flip around the X-axis.
            y: Flip around the Y-axis.
        """
        if not x and not y:
            return

        for vertex in self.vertices():
            if x:
                vertex.x = -vertex.x
            if y:
                vertex.y = -vertex.y

        # Fix the face normals
        if x is not y:
            for face in self.faces:
                v1, v2, v3 = face.v1, face.v2, face.v3
                face.v1, face.v2, face.v3 = v3, v2, v1

    def serialize(self) -> dict[str, Any]:
        """Serialize a BWM walkmesh to JSON-compatible dict.

        Returns:
        -------
            Dictionary representation
        """
        vertices = [v.serialize() for v in self.vertices()]

        faces = []
        for face in self.faces:
            faces.append(
                {
                    "v1": face.v1.serialize(),
                    "v2": face.v2.serialize(),
                    "v3": face.v3.serialize(),
                    "material": face.material.value,
                    "trans1": face.trans1,
                    "trans2": face.trans2,
                    "trans3": face.trans3,
                },
            )

        return {
            "walkmesh_type": self.walkmesh_type.value,
            "vertices": vertices,
            "faces": faces,
        }


class BWMFace(Face, ComparableMixin):
    """Triangle face with material and optional per-edge transitions.

    Each face represents a single triangle in the walkmesh with three vertices, a material
    (determining walkability and surface properties), and optional transition indices for
    each edge. Transitions reference LYT door hooks or area connections, not geometric
    adjacency (which is computed from shared vertices).

    References:
    ----------
        Binary Format (per face):
        -----------------------
        Face data is stored in separate arrays:
        - Indices: 3x uint32 (vertex indices into vertex array)
        - Material: 1x uint32 (SurfaceMaterial ID)
        - Normal: 3x float32 (face normal vector)
        - Transitions: Stored in edges table (edge_index -> transition mapping)

    Attributes:
    ----------
        Inherits from Face: v1, v2, v3 (Vector3 vertices)
            Three vertices defining the triangular face
            Vertices are shared between faces (stored in BWM vertex array)

        material: SurfaceMaterial determining face properties
            Reference: PyKotor io_bwm.py:159-160 (material assignment)
            Determines walkability, line-of-sight blocking, grass rendering, etc.
            Stored as uint32 material ID in binary format

        trans1: Optional transition index for edge 0 (v1->v2)
            Reference: PyKotor io_bwm.py:164-179 (transition reading from edges table)
            Edge index calculation: face_index * 3 + 0
            Transition index into LYT door hooks or area connections
            Value None/0xFFFFFFFF indicates no transition for this edge
            NOT a geometric adjacency identifier

        trans2: Optional transition index for edge 1 (v2->v3)
            Reference: PyKotor io_bwm.py:164-179 (transition reading from edges table)
            Edge index calculation: face_index * 3 + 1
            Transition index into LYT door hooks or area connections
            Value None/0xFFFFFFFF indicates no transition for this edge

        trans3: Optional transition index for edge 2 (v3->v1)
            Reference: PyKotor io_bwm.py:164-179 (transition reading from edges table)
            Edge index calculation: face_index * 3 + 2
            Transition index into LYT door hooks or area connections
            Value None/0xFFFFFFFF indicates no transition for this edge

    Notes:
    -----
        - `trans1`, `trans2`, `trans3` are metadata for engine transitions (e.g.,
          LYT/door indices) and are not unique identifiers.
        - They do not encode geometric adjacency; adjacency is derived from shared
          vertex identity on walkable faces.
        - Transitions are stored in a separate edges table in binary format, not only
          inline on face records; PyKotor reads that table.
    """

    def __init__(
        self,
        v1: Vector3,
        v2: Vector3,
        v3: Vector3,
    ):
        # Three vertices defining the triangular face
        super().__init__(v1, v2, v3)

        # Optional transition indices for each edge (stored in edges table in binary)
        # Edge 0 (v1->v2): transition index into LYT door hooks
        self.trans1: int | None = None

        # Edge 1 (v2->v3): transition index into LYT door hooks
        self.trans2: int | None = None

        # Edge 2 (v3->v1): transition index into LYT door hooks
        self.trans3: int | None = None

    def __eq__(self, other):  # type: ignore[override]
        """Value-based equality (geometry + transitions).

        IMPORTANT: some algorithms must map a *specific face object* back to its index when
        emitting edge indices (face_index * 3 + edge). Those algorithms must use identity-based
        lookup (the `is` operator) instead of relying on `__eq__`. See `io_bwm.py`.
        """
        if not isinstance(other, BWMFace):
            return NotImplemented  # type: ignore[no-any-return]
        parent_eq = super().__eq__(other)
        if parent_eq is NotImplemented:
            return NotImplemented  # type: ignore[no-any-return]
        return (
            parent_eq
            and self.trans1 == other.trans1
            and self.trans2 == other.trans2
            and self.trans3 == other.trans3
        )

    def __hash__(self):  # type: ignore[override]
        return hash((super().__hash__(), self.trans1, self.trans2, self.trans3))


class BWMMostSignificantPlane(IntEnum):
    NEGATIVE_Z = -3
    NEGATIVE_Y = -2
    NEGATIVE_X = -1
    NONE = 0
    POSITIVE_X = 1
    POSITIVE_Y = 2
    POSITIVE_Z = 3


class BWMNodeAABB(ComparableMixin):
    """A node in an AABB (Axis-Aligned Bounding Box) tree for spatial queries.

    AABB trees provide efficient spatial acceleration for walkmesh queries (raycasting,
    point containment, etc.). Internal nodes contain bounding boxes and split planes,
    while leaf nodes reference specific faces. The tree is built recursively by splitting
    faces along the longest axis.

    References:
    ----------
        Binary Format (per AABB node, 32 bytes):
        ---------------------------------------
        Offset | Size | Type   | Description
        -------|------|--------|-------------
        0x00   | 24   | float6 | Bounding Box (min x,y,z, max x,y,z)
        0x18   | 4    | int32  | Face Index (-1 for internal nodes, >=0 for leaves)
        0x1C   | 4    | uint32 | Unknown (typically 0)
        0x20   | 4    | uint32 | Most Significant Plane (split axis)
        0x24   | 4    | uint32 | Left Child Index
        0x28   | 4    | uint32 | Right Child Index

    Attributes:
    ----------
        bb_min: Minimum bounds of the axis-aligned bounding box (x, y, z)
            Minimum corner of the bounding box
            Used for spatial culling and intersection tests

        bb_max: Maximum bounds of the axis-aligned bounding box (x, y, z)
            Maximum corner of the bounding box
            Used for spatial culling and intersection tests

        face: Face referenced by this node (None for internal nodes)
            Leaf nodes reference a specific face (faceIdx >= 0)
            Internal nodes have face = None (faceIdx = -1)

        sigplane: Most significant splitting plane (axis index)
            Reference: PyKotor bwm_data.py:240-245 (split_axis calculation)
            Indicates which axis (0=X, 1=Y, 2=Z) was used to split faces
            Used during tree traversal for efficient queries

        left: Left child node in AABB tree (None for leaves)
            Child nodes contain faces on the "left" side of split plane
            None for leaf nodes (face != None)

        right: Right child node in AABB tree (None for leaves)
            Child nodes contain faces on the "right" side of split plane
            None for leaf nodes (face != None)
    """

    COMPARABLE_FIELDS = ("bb_min", "bb_max", "face", "sigplane", "left", "right")

    def __init__(
        self,
        bb_min: Vector3,
        bb_max: Vector3,
        face: BWMFace | None,
        sigplane: int,
        left: BWMNodeAABB | None,
        right: BWMNodeAABB | None,
    ):
        """Initializes a bounding volume node.

        Args:
        ----
            bb_min: Vector3 - Minimum bounds of the bounding box
            bb_max: Vector3 - Maximum bounds of the bounding box
            face: BWMFace | None - Face that splits the node or None
            sigplane: int - Index of most significant splitting plane
            left: BWMNodeAABB | None - Left child node or None
            right: BWMNodeAABB | None - Right child node or None

        Returns:
        -------
            self - The initialized BWMNodeAABB object

        Processing Logic:
        ----------------
            - Sets the bounding box minimum and maximum bounds
            - Sets the splitting face and most significant plane
            - Sets the left and right child nodes.
        """
        # Minimum bounds of axis-aligned bounding box
        self.bb_min: Vector3 = bb_min

        # Maximum bounds of axis-aligned bounding box
        self.bb_max: Vector3 = bb_max

        # Face referenced by this node (None for internal nodes, face for leaves)
        self.face: BWMFace | None = face

        # Most significant splitting plane (axis: 0=X, 1=Y, 2=Z)
        self.sigplane: BWMMostSignificantPlane = BWMMostSignificantPlane(sigplane)

        # Left child node (None for leaf nodes)
        self.left: BWMNodeAABB | None = left

        # Right child node (None for leaf nodes)
        self.right: BWMNodeAABB | None = right

    def __eq__(self, other):
        if not isinstance(other, BWMNodeAABB):
            return NotImplemented  # type: ignore[no-any-return]
        if self is other:
            return True
        return (
            self.bb_min == other.bb_min
            and self.bb_max == other.bb_max
            and self.face == other.face
            and self.sigplane == other.sigplane
            and self.left == other.left
            and self.right == other.right
        )

    def __hash__(self):
        return hash(
            (
                self.bb_min,
                self.bb_max,
                self.face,
                self.sigplane,
                self.left,
                self.right,
            ),
        )


class BWMAdjacency(ComparableMixin):
    """Maps an edge index to a target face from a source face.

    Adjacency represents geometric connectivity between walkable faces. Two faces are
    adjacent if they share an edge (two vertices). Adjacency is computed from geometry,
    not stored in binary format (unlike transitions, which are stored in edges table).

    References:
    ----------

    Attributes:
    ----------
        face: Target face that is adjacent to the source face
            Reference: PyKotor bwm_data.py:434 (BWMAdjacency construction)
            The face that shares an edge with the source face
            Used for pathfinding and navigation mesh traversal

        edge: Edge index of the target face (0, 1, or 2)
            Reference: PyKotor bwm_data.py:434 (edge_match value)
            Indicates which edge of the target face connects to the source face
            Edge 0 = v1->v2, Edge 1 = v2->v3, Edge 2 = v3->v1
            Used to determine edge orientation for navigation
    """

    COMPARABLE_FIELDS = ("face", "edge")

    def __init__(
        self,
        face: BWMFace,
        index: int,
    ):
        # Target face that shares an edge with source face
        self.face: BWMFace = face

        # Edge index of target face (0, 1, or 2)
        self.edge: int = index

    def __eq__(self, other):
        if not isinstance(other, BWMAdjacency):
            return NotImplemented  # type: ignore[no-any-return]
        return self.face == other.face and self.edge == other.edge

    def __hash__(self):
        return hash((self.face, self.edge))


class BWMEdge(ComparableMixin):
    """Represents a perimeter edge (boundary edge with no walkable neighbor).

    Perimeter edges are edges of walkable faces that are not adjacent to any other
    walkable face. These form the boundaries of walkable areas and may have transition
    indices for area connections (doors, area transitions). Perimeter edges are computed
    from geometry, not stored directly in binary format.

    References:
    ----------

    Attributes:
    ----------
        face: The face this edge belongs to
            Reference: PyKotor bwm_data.py:344 (BWMEdge construction)
            The walkable face that contains this perimeter edge
            Used to determine edge geometry and position

        index: Edge index on the face (0, 1, or 2)
            Reference: PyKotor bwm_data.py:330-344 (edge_index calculation)
            Edge 0 = v1->v2, Edge 1 = v2->v3, Edge 2 = v3->v1
            Global edge index = face_index * 3 + local_edge_index
            Used to map back to face transitions (trans1/trans2/trans3)

        transition: Transition index into LYT file (door hook index)
            Reference: PyKotor bwm_data.py:337-343 (transition reading from face)
            Reference: PyKotor io_bwm.py:169 (transition reading from edges table)
            Index into LYT door hooks for area transitions
            Value -1/0xFFFFFFFF indicates no transition
            Used for door placement and area connections

        final: Flag indicating this is the final edge of a perimeter loop
            Reference: PyKotor bwm_data.py:333 (final flag setting)
            Set to True when perimeter edge loop closes
            Used to mark perimeter boundaries for pathfinding
    """

    COMPARABLE_FIELDS = ("face", "index", "transition", "final")

    def __init__(
        self,
        face: BWMFace,
        index: int,
        transition: int,
        *,
        final: bool = False,
    ):
        # Face this perimeter edge belongs to
        self.face: BWMFace = face

        # Edge index on face (0, 1, or 2)
        self.index: int = index

        # Transition index into LYT door hooks (-1 for no transition)
        self.transition: int = transition

        # Flag indicating final edge of perimeter loop
        self.final: bool = final

    def __eq__(self, other):
        if not isinstance(other, BWMEdge):
            return NotImplemented  # type: ignore[no-any-return]
        return (
            self.face == other.face
            and self.index == other.index
            and self.transition == other.transition
            and self.final == other.final
        )

    def __hash__(self):
        return hash((self.face, self.index, self.transition, self.final))
