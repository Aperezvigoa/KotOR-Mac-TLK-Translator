"""Central restype -> decoder registry for resource bytes -> domain objects.

Reused by Installation, ModuleResource, and InstallationWorkspace so decode
logic lives in one place. Decoders accept bytes and return the typed domain object
(e.g. read_utc(data) -> UTC).
"""

from __future__ import annotations

from typing import Any, Callable

from pykotor.resource.formats.bwm import read_bwm
from pykotor.resource.formats.gff import read_gff
from pykotor.resource.formats.lyt import read_lyt
from pykotor.resource.formats.tpc import read_tpc
from pykotor.resource.formats.vis import read_vis
from pykotor.resource.gff_dispatch import get_gff_read_converter
from pykotor.resource.type import ResourceType

# Decoder: bytes -> domain object (GFF, UTC, LYT, etc.)
_DECODER_REGISTRY: dict[ResourceType, Callable[[bytes], Any]] = {
    ResourceType.LYT: read_lyt,
    ResourceType.NCS: lambda data: data,
    ResourceType.TPC: read_tpc,
    ResourceType.TGA: read_tpc,
    ResourceType.VIS: read_vis,
    ResourceType.WOK: read_bwm,
    ResourceType.GFF: read_gff,
}


def get_decoder(restype: ResourceType) -> Callable[[bytes], Any] | None:
    """Return the decoder for the given ResourceType, or None if none is registered."""
    gff_reader = get_gff_read_converter(restype)
    if gff_reader is not None:
        return lambda data: gff_reader(data, 0, None)
    return _DECODER_REGISTRY.get(restype)
