"""Shared dispatch helpers for GFF-backed resource models.

This module centralizes the per-ResourceType read/write/bytes/construct/dismantle
pipeline for GFF-backed resources so callers do not need to maintain local maps.

The registry is exhaustive against ``ResourceType``: every GFF-backed resource type is
either mapped to a pipeline or listed explicitly as unsupported because no typed model
exists for it yet.
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any, Callable, NamedTuple, cast

from pykotor.resource.formats.gff import GFF, bytes_gff, read_gff, write_gff
from pykotor.resource.generics.are import (
    bytes_are,
    construct_are,
    dismantle_are,
    read_are,
    write_are,
)
from pykotor.resource.generics.dlg import (
    bytes_dlg,
    construct_dlg,
    dismantle_dlg,
    read_dlg,
    write_dlg,
)
from pykotor.resource.generics.fac import (
    bytes_fac,
    construct_fac,
    dismantle_fac,
    read_fac,
    write_fac,
)
from pykotor.resource.generics.git import (
    bytes_git,
    construct_git,
    dismantle_git,
    read_git,
    write_git,
)
from pykotor.resource.generics.gui import (
    bytes_gui,
    construct_gui,
    dismantle_gui,
    read_gui,
    write_gui,
)
from pykotor.resource.generics.ifo import (
    bytes_ifo,
    construct_ifo,
    dismantle_ifo,
    read_ifo,
    write_ifo,
)
from pykotor.resource.generics.jrl import (
    bytes_jrl,
    construct_jrl,
    dismantle_jrl,
    read_jrl,
    write_jrl,
)
from pykotor.resource.generics.pth import (
    bytes_pth,
    construct_pth,
    dismantle_pth,
    read_pth,
    write_pth,
)
from pykotor.resource.generics.utc import (
    bytes_utc,
    construct_utc,
    dismantle_utc,
    read_utc,
    write_utc,
)
from pykotor.resource.generics.utd import (
    bytes_utd,
    construct_utd,
    dismantle_utd,
    read_utd,
    write_utd,
)
from pykotor.resource.generics.ute import (
    bytes_ute,
    construct_ute,
    dismantle_ute,
    read_ute,
    write_ute,
)
from pykotor.resource.generics.uti import (
    bytes_uti,
    construct_uti,
    dismantle_uti,
    read_uti,
    write_uti,
)
from pykotor.resource.generics.utm import (
    bytes_utm,
    construct_utm,
    dismantle_utm,
    read_utm,
    write_utm,
)
from pykotor.resource.generics.utp import (
    bytes_utp,
    construct_utp,
    dismantle_utp,
    read_utp,
    write_utp,
)
from pykotor.resource.generics.uts import (
    bytes_uts,
    construct_uts,
    dismantle_uts,
    read_uts,
    write_uts,
)
from pykotor.resource.generics.utt import (
    bytes_utt,
    construct_utt,
    dismantle_utt,
    read_utt,
    write_utt,
)
from pykotor.resource.generics.utw import (
    bytes_utw,
    construct_utw,
    dismantle_utw,
    read_utw,
    write_utw,
)
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from pykotor.common.misc import Game
    from pykotor.resource.type import SOURCE_TYPES


class GFFResourcePipeline(NamedTuple):
    read: Callable[..., Any]
    write: Callable[..., Any]
    to_bytes: Callable[..., bytes]
    construct: Callable[[GFF], Any]
    dismantle: Callable[..., GFF]


def _construct_gff(gff: GFF) -> GFF:
    return gff


def _dismantle_gff(gff: GFF, *_args: Any, **_kwargs: Any) -> GFF:
    return gff


def _write_raw_gff(
    gff: GFF,
    target: Any,
    _game: Game | None = None,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
) -> None:
    del use_deprecated
    write_gff(gff, target, file_format=file_format)


def _bytes_raw_gff(
    gff: GFF,
    _game: Game | None = None,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
) -> bytes:
    del use_deprecated
    return cast(bytes, bytes_gff(gff, file_format=file_format))


def _write_fac_with_optional_game(
    fac: Any,
    target: Any,
    _game: Game | None = None,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
) -> None:
    del use_deprecated
    write_fac(fac, target, file_format=file_format)


def _bytes_fac_with_optional_game(
    fac: Any,
    _game: Game | None = None,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
) -> bytes:
    del use_deprecated
    return cast(bytes, bytes_fac(fac, file_format=file_format))


_BASE_GFF_RESOURCE_PIPELINES: dict[ResourceType, GFFResourcePipeline] = {
    ResourceType.GFF: GFFResourcePipeline(
        read_gff, _write_raw_gff, _bytes_raw_gff, _construct_gff, _dismantle_gff
    ),
    ResourceType.RES: GFFResourcePipeline(
        read_gff, _write_raw_gff, _bytes_raw_gff, _construct_gff, _dismantle_gff
    ),
    ResourceType.ARE: GFFResourcePipeline(
        read_are, write_are, bytes_are, construct_are, dismantle_are
    ),
    ResourceType.DLG: GFFResourcePipeline(
        read_dlg, write_dlg, bytes_dlg, construct_dlg, dismantle_dlg
    ),
    ResourceType.FAC: GFFResourcePipeline(
        read_fac,
        _write_fac_with_optional_game,
        _bytes_fac_with_optional_game,
        construct_fac,
        dismantle_fac,
    ),
    ResourceType.GIT: GFFResourcePipeline(
        read_git, write_git, bytes_git, construct_git, dismantle_git
    ),
    ResourceType.GUI: GFFResourcePipeline(
        read_gui, write_gui, bytes_gui, construct_gui, dismantle_gui
    ),
    ResourceType.IFO: GFFResourcePipeline(
        read_ifo, write_ifo, bytes_ifo, construct_ifo, dismantle_ifo
    ),
    ResourceType.JRL: GFFResourcePipeline(
        read_jrl, write_jrl, bytes_jrl, construct_jrl, dismantle_jrl
    ),
    ResourceType.PTH: GFFResourcePipeline(
        read_pth, write_pth, bytes_pth, construct_pth, dismantle_pth
    ),
    ResourceType.UTC: GFFResourcePipeline(
        read_utc, write_utc, bytes_utc, construct_utc, dismantle_utc
    ),
    ResourceType.UTD: GFFResourcePipeline(
        read_utd, write_utd, bytes_utd, construct_utd, dismantle_utd
    ),
    ResourceType.UTE: GFFResourcePipeline(
        read_ute, write_ute, bytes_ute, construct_ute, dismantle_ute
    ),
    ResourceType.UTI: GFFResourcePipeline(
        read_uti, write_uti, bytes_uti, construct_uti, dismantle_uti
    ),
    ResourceType.UTM: GFFResourcePipeline(
        read_utm, write_utm, bytes_utm, construct_utm, dismantle_utm
    ),
    ResourceType.UTP: GFFResourcePipeline(
        read_utp, write_utp, bytes_utp, construct_utp, dismantle_utp
    ),
    ResourceType.UTS: GFFResourcePipeline(
        read_uts, write_uts, bytes_uts, construct_uts, dismantle_uts
    ),
    ResourceType.UTT: GFFResourcePipeline(
        read_utt, write_utt, bytes_utt, construct_utt, dismantle_utt
    ),
    ResourceType.UTW: GFFResourcePipeline(
        read_utw, write_utw, bytes_utw, construct_utw, dismantle_utw
    ),
}


_BIOWARE_TEMPLATE_TARGETS: dict[ResourceType, ResourceType] = {
    ResourceType.BTI: ResourceType.UTI,
    ResourceType.BTC: ResourceType.UTC,
    ResourceType.BTT: ResourceType.UTT,
    ResourceType.BTS: ResourceType.UTS,
    ResourceType.BTE: ResourceType.UTE,
    ResourceType.BTD: ResourceType.UTD,
    ResourceType.BTP: ResourceType.UTP,
    ResourceType.BTM: ResourceType.UTM,
}


def _safe_target_type(restype: ResourceType) -> ResourceType:
    if restype.target_member is None:
        return restype
    with suppress(KeyError):
        return ResourceType.__members__[restype.target_member]
    return restype


def is_gff_resource_type(restype: ResourceType) -> bool:
    return bool(restype.is_gff() or _safe_target_type(restype).is_gff())


def _resolve_gff_pipeline_type(restype: ResourceType) -> ResourceType:
    canonical_type = _safe_target_type(restype)
    return _BIOWARE_TEMPLATE_TARGETS.get(canonical_type, canonical_type)


_GFF_RESOURCE_PIPELINES: dict[ResourceType, GFFResourcePipeline] = {
    restype: pipeline
    for restype in ResourceType
    if is_gff_resource_type(restype)
    for pipeline in [_BASE_GFF_RESOURCE_PIPELINES.get(_resolve_gff_pipeline_type(restype))]
    if pipeline is not None
}


SUPPORTED_GFF_RESOURCE_TYPES: frozenset[ResourceType] = frozenset(_GFF_RESOURCE_PIPELINES)
UNSUPPORTED_GFF_RESOURCE_TYPES: frozenset[ResourceType] = frozenset(
    restype
    for restype in ResourceType
    if is_gff_resource_type(restype) and restype not in _GFF_RESOURCE_PIPELINES
)


def get_gff_resource_pipeline(restype: ResourceType) -> GFFResourcePipeline | None:
    """Return the GFF-backed resource pipeline for a resource type, if supported."""
    return _GFF_RESOURCE_PIPELINES.get(restype)


def get_gff_read_converter(
    restype: ResourceType,
) -> Callable[[SOURCE_TYPES, int, int | None], Any] | None:
    """Return the shared GFF reader for a resource type, if supported."""
    pipeline = get_gff_resource_pipeline(restype)
    if pipeline is None:
        return None
    return pipeline.read


def reconstruct_gff_as_bytes(gff: GFF, restype: ResourceType) -> bytes | None:
    """Construct and serialize a typed GFF-backed resource when the type is supported."""
    pipeline = get_gff_resource_pipeline(restype)
    if pipeline is None:
        return None
    return pipeline.to_bytes(pipeline.construct(gff))


__all__ = [
    "GFFResourcePipeline",
    "get_gff_read_converter",
    "get_gff_resource_pipeline",
    "reconstruct_gff_as_bytes",
    "SUPPORTED_GFF_RESOURCE_TYPES",
    "UNSUPPORTED_GFF_RESOURCE_TYPES",
    "is_gff_resource_type",
]
