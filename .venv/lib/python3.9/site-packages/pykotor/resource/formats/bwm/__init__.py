"""BWM (walkmesh) package: faces, edges, adjacency and binary I/O for module geometry."""

from __future__ import annotations

from pykotor.resource.formats.bwm.bwm_auto import (
    BWM_VALIDATION_DIAGRAM_MAGIC,
    bytes_bwm,
    read_bwm,
    write_bwm,
    write_bwm_ascii,
    write_bwm_validation_diagram,
)
from pykotor.resource.formats.bwm.bwm_data import (
    BWM,
    BWMAdjacency,
    BWMEdge,
    BWMFace,
    BWMType,
)
from pykotor.resource.formats.bwm.io_bwm import (
    BWMBinaryReader,
    BWMBinaryWriter,
)

__all__ = [
    "BWM",
    "BWM_VALIDATION_DIAGRAM_MAGIC",
    "BWMAdjacency",
    "BWMBinaryReader",
    "BWMBinaryWriter",
    "BWMEdge",
    "BWMFace",
    "BWMType",
    "bytes_bwm",
    "read_bwm",
    "write_bwm",
    "write_bwm_ascii",
    "write_bwm_validation_diagram",
]
