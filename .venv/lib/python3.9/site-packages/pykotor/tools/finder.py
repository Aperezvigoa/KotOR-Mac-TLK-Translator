"""Installation-aware resource finder with strict resolution order.

Single source of truth for canonical search order and find results used by
CLI find/get and MCP find/extract. Per KotorMCP redesign plan Phase 1.1.
"""

from __future__ import annotations

import fnmatch

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pykotor.extract.file import LocationResult, ResourceIdentifier
from pykotor.extract.installation import Installation, SearchLocation
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from collections.abc import Sequence


# Human-readable names for SearchLocation (for display and location_type)
SEARCH_LOCATION_NAMES: dict[SearchLocation, str] = {
    SearchLocation.CUSTOM_FOLDERS: "Custom folders",
    SearchLocation.OVERRIDE: "Override",
    SearchLocation.CUSTOM_MODULES: "Custom modules",
    SearchLocation.MODULES: "Modules",
    SearchLocation.CHITIN: "Chitin",
    SearchLocation.TEXTURES_TPA: "Texture pack TPA",
    SearchLocation.TEXTURES_TPB: "Texture pack TPB",
    SearchLocation.TEXTURES_TPC: "Texture pack TPC",
    SearchLocation.TEXTURES_GUI: "Texture pack GUI",
    SearchLocation.RIMS: "RIM files",
    SearchLocation.LIPS: "LIP files",
    SearchLocation.MUSIC: "StreamMusic",
    SearchLocation.SOUND: "StreamSounds",
    SearchLocation.VOICE: "StreamWaves/StreamVoice",
}


def canonical_search_order() -> list[SearchLocation]:
    """Return the canonical resource resolution order (engine order).

    Same as Installation.locations() default and KEY-File-Format: higher
    priority locations first. Used by CLI find/get and MCP find/extract.
    """
    return [
        SearchLocation.CUSTOM_FOLDERS,
        SearchLocation.OVERRIDE,
        SearchLocation.CUSTOM_MODULES,
        SearchLocation.MODULES,
        SearchLocation.CHITIN,
    ]


@dataclass
class FindResult:
    """Result of finding a resource in an installation (one location)."""

    resref: str
    restype: ResourceType
    size: int
    source: SearchLocation
    filepath: Path
    archive_path: str | None  # path to capsule (e.g. data/models.bif) or None for override files
    archive_index: int  # index within archive if applicable, else 0
    priority_index: int  # 1-based position in search order
    is_selected: bool  # True if this is the first in order (engine would load this)
    location_type: str  # human-readable source, e.g. "Override", "Modules", "Chitin"

    @property
    def identifier(self) -> ResourceIdentifier:
        return ResourceIdentifier(self.resref, self.restype)


def _location_result_to_find_result(
    identifier: ResourceIdentifier,
    location: LocationResult,
    source: SearchLocation,
    priority_index: int,
    is_selected: bool,
) -> FindResult:
    """Build a FindResult from a LocationResult and context."""
    filepath = (
        Path(location.filepath) if hasattr(location.filepath, "__fspath__") else location.filepath
    )
    archive_path: str | None = None
    archive_index = 0
    path_str = str(filepath).lower()
    if path_str.endswith((".bif", ".rim", ".erf", ".mod", ".sav", ".hak")):
        archive_path = str(filepath)
    location_type = SEARCH_LOCATION_NAMES.get(
        source, source.name if hasattr(source, "name") else str(source)
    )
    return FindResult(
        resref=identifier.resname,
        restype=identifier.restype,
        size=location.size,
        source=source,
        filepath=filepath,
        archive_path=archive_path,
        archive_index=archive_index,
        priority_index=priority_index,
        is_selected=is_selected,
        location_type=location_type,
    )


def find_resource(
    installation: Installation,
    resref: str | None = None,
    restype: ResourceType | None = None,
    glob_pattern: str | None = None,
    order: Sequence[SearchLocation] | None = None,
    all_locations: bool = True,
    *,
    queries: list[ResourceIdentifier] | None = None,
) -> list[FindResult]:
    """Find resource(s) in an installation using strict resolution order.

    Args:
        installation: The game installation to search.
        resref: Resource name (use with restype, or with glob_pattern for single resref).
        restype: Resource type (inferred from extension if resref has one and restype omitted).
        glob_pattern: If set, match resrefs with fnmatch (e.g. "203tel*"); resref then used as pattern.
        order: Search location order; None uses canonical_search_order().
        all_locations: If True, return all locations with priority_index and is_selected; if False, return only the selected (first) per query.
        queries: Explicit list of ResourceIdentifiers to look up; when set, resref/restype/glob_pattern are ignored.

    Returns:
        List of FindResult, ordered by query then by search order. First result per query has is_selected=True.
    """
    if order is None:
        order = canonical_search_order()
    order_list = list(order)

    if queries is not None:
        pass
    elif glob_pattern is not None:
        # Resolve matching identifiers from override (and optionally modules/chitin via installation)
        queries = _identifiers_matching_glob(installation, glob_pattern)
        if not queries:
            return []
    elif resref:
        if restype is None:
            # Try to infer from resref (e.g. "203tell.wok" -> WOK)
            if "." in resref:
                ident = ResourceIdentifier.from_path(resref)
                if ident.restype != ResourceType.INVALID:
                    resref = ident.resname
                    restype = ident.restype
                else:
                    restype = ResourceType.INVALID
            else:
                restype = ResourceType.INVALID
        if restype == ResourceType.INVALID:
            # No extension and no type: try common types or return empty
            return []
        queries = [ResourceIdentifier(resref, restype)]
    else:
        return []

    locs_map = installation.locations(queries, order=order_list)
    results: list[FindResult] = []
    for q in queries:
        locations_list = locs_map.get(q, [])
        if not locations_list:
            continue
        # locations() returns results in order of SearchLocation (order_list); each index
        # corresponds to the location that produced that result.
        for idx, loc in enumerate(locations_list):
            src = order_list[idx] if idx < len(order_list) else order_list[-1]
            find_result = _location_result_to_find_result(
                q,
                loc,
                src,
                priority_index=idx + 1,
                is_selected=(idx == 0),
            )
            if all_locations:
                results.append(find_result)
            elif idx == 0:
                results.append(find_result)
                break
    return results


def _identifiers_matching_glob(
    installation: Installation, pattern: str
) -> list[ResourceIdentifier]:
    """Collect ResourceIdentifiers from installation that match the glob pattern (resref only).

    Pattern is fnmatch applied to resref (e.g. "203tel*" matches 203tell, 203tel, etc.).
    Scans override directory only (modules/chitin would require loading all resources).
    """
    seen: set[str] = set()
    out: list[ResourceIdentifier] = []

    # Override: walk override path
    override_path = installation.override_path()
    if override_path.exists():
        for f in override_path.rglob("*"):
            if not f.is_file():
                continue
            ident = ResourceIdentifier.from_path(f)
            if ident.restype == ResourceType.INVALID:
                continue
            key = ident.resname.lower()
            if key in seen:
                continue
            if fnmatch.fnmatch(ident.resname.lower(), pattern.lower()):
                seen.add(key)
                out.append(ident)

    # Modules and chitin: use internal lists (Installation doesn't expose iter_identifiers)
    # We need to load and iterate - use locations with a single "probe" then rely on override for glob
    # For full glob we'd need to iterate _modules and _chitin; that's expensive.
    # So we only add override matches for glob; user can run find without glob for specific resref.
    return out
