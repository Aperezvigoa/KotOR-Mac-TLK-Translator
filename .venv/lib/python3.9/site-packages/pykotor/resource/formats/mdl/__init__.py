"""MDL (Model) format for KotOR.

This module provides support for reading, writing, and manipulating MDL/MDX model files
used in Knights of the Old Republic (K1) and The Sith Lords (TSL).

MDL Format Overview:
-------------------
MDL files store 3D model geometry, animations, materials, and node hierarchies for
characters, creatures, placeables, and area geometry. MDL files contain hierarchical
node structures with:

- Geometry nodes (Trimesh, Skin, Danglymesh)
- Animation nodes (controllers for position, orientation, scale)
- Light nodes (point lights, spot lights, ambient)
- Emitter nodes (particle effects)
- Reference nodes (model references, placeables)
- Camera nodes (viewpoint definitions)

Each node can have:
- Position, orientation (quaternion), scale
- Controllers (keyframe animations)
- Children nodes (hierarchical structure)
- Node-specific data (geometry, lights, etc.)

The MDL file contains node hierarchy, animations, and metadata, while the MDX file
contains vertex data, faces, and geometry payload.

Observed behavior (retail KotOR I / TSL):
----------------------------------------
- GFF templates and area-related resources use predictable field labels for model ResRefs
  and variants, including ``ModelName``, ``ModelPart``, ``MODELTYPE``, ``refModel``,
  ``ModelVariation``, ``ModelPart1``, ``VisibleModel``, and ``Model``.
- It has been observed that the games also use related literal keys for hooks, weapons,
  and tooling (e.g. ``modelhook``, ``Bullet_Model``, ``Gun_Model``, ``RotatingModel``,
  ``Models``, ``Model%d``, ``c_FocusGobDummyModel%d``).
- TSL adds a supermodel resource scheme using ``SUPERMODELS`` and paths such as
  ``.\\supermodels`` / ``d:\\supermodels`` plus ``SUPERMODELS:smset*`` ResRef-style tokens;
  K1 does not use that scheme in the same way.
- Dummy and hit-detection names such as ``headconjure`` and the ``_head_hit`` suffix appear
  in creature/placeable visual setup.
- Some log lines mention failing creature model loads or missing default models; those
  strings match what players and modders see when a model ResRef cannot be resolved.

Deeper notes tying these literals to engine loaders and GFF usage live in the project wiki
(``wiki/reverse_engineering_findings.md``); this package sticks to on-disk patterns and
observed in-game behavior.
"""

from __future__ import annotations

from pykotor.resource.formats.mdl._install_mdl_io_aabb import ensure_io_mdl_aabb_patched_on_disk

ensure_io_mdl_aabb_patched_on_disk()

from pykotor.resource.formats.mdl.mdl_data import (
    MDL,
    MDLNode,
    MDLMesh,
    MDLSkin,
    MDLConstraint,
    MDLDangly,
    MDLAnimation,
    MDLController,
    MDLControllerRow,
    MDLBoneVertex,
    MDLEmitter,
    MDLEvent,
    MDLLight,
    MDLFace,
    MDLReference,
    MDLSaber,
    MDLWalkmesh,
)
from pykotor.resource.formats.mdl.mdl_types import (
    MDLClassification,
    MDLControllerType,
    MDLNodeFlags,
    MDLNodeType,
    MDLGeometryType,
)
from pykotor.resource.formats.mdl.io_mdl import MDLBinaryReader, MDLBinaryWriter
from pykotor.resource.formats.mdl.io_mdl_ascii import MDLAsciiReader, MDLAsciiWriter
from pykotor.resource.formats.mdl.mdl_auto import (
    bytes_mdl,
    write_mdl,
    read_mdl,
    read_mdl_fast,
    detect_mdl,
)

__all__ = [
    "MDL",
    "MDLAnimation",
    "MDLAsciiReader",
    "MDLAsciiWriter",
    "MDLBinaryReader",
    "MDLBinaryWriter",
    "MDLBoneVertex",
    "MDLClassification",
    "MDLConstraint",
    "MDLController",
    "MDLControllerRow",
    "MDLControllerType",
    "MDLDangly",
    "MDLEmitter",
    "MDLEvent",
    "MDLFace",
    "MDLLight",
    "MDLMesh",
    "MDLNode",
    "MDLNodeFlags",
    "MDLReference",
    "MDLSaber",
    "MDLSkin",
    "MDLWalkmesh",
    "bytes_mdl",
    "detect_mdl",
    "read_mdl",
    "read_mdl_fast",
    "write_mdl",
]
