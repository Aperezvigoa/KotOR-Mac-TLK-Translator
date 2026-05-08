"""Find command: source-aware resource search with strict resolution order."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykotor.extract.file import ResourceIdentifier
from pykotor.extract.installation import SearchLocation
from pykotor.extract.path_source import resolve_resource_source, resolve_source_path_from_args
from pykotor.resource.type import ResourceType
from pykotor.tools.finder import FindResult, canonical_search_order

if TYPE_CHECKING:
    from argparse import Namespace

    from loggerplus import RobustLogger as Logger


def _parse_order_arg(order_str: str | None) -> list[SearchLocation] | None:
    """Parse --order LOC1,LOC2,... into list of SearchLocation."""
    if not order_str or not order_str.strip():
        return None
    name_to_loc = {e.name: e for e in SearchLocation}
    order = []
    for part in order_str.strip().upper().split(","):
        part = part.strip()
        if part in name_to_loc:
            order.append(name_to_loc[part])
    return order if order else None


def cmd_find(args: Namespace, logger: Logger) -> int:
    """Find resource(s) in a KOTOR installation using engine resolution order.

    Usage:
        pykotor find 203tell.wok --path "G:/SteamLibrary/.../KOTOR2"
        pykotor find 203tell.wok --path "G:/..." --all-locations
        pykotor find 203tel* --path "G:/..."  (glob: override folder only)
    """
    path = resolve_source_path_from_args(args, logger)
    if path is None:
        return 1

    resolved_source = resolve_resource_source(path)

    resref = getattr(args, "resref", None) or getattr(args, "query", None)
    if not resref or not str(resref).strip():
        logger.error("No resource specified. Use: pykotor find <resref[.ext]> [--path PATH]")
        return 1

    resref_str = str(resref).strip()
    glob_pattern = None
    if "*" in resref_str or "?" in resref_str:
        glob_pattern = resref_str
        resref_str = resref_str.split(".")[0] if "." in resref_str else resref_str

    type_arg = getattr(args, "resource_type", None) or getattr(args, "type", None)
    restype: ResourceType | None = None
    if type_arg:
        ext = str(type_arg).strip().lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        restype = ResourceType.from_extension(ext) if ext != "." else None
    order = _parse_order_arg(getattr(args, "order", None))
    all_locations = getattr(args, "all_locations", False)

    if order is None:
        order = canonical_search_order()

    if glob_pattern:
        identifiers = resolved_source.matching_identifiers(glob_pattern=glob_pattern, restype=restype)
    else:
        identifier = ResourceIdentifier.from_path(resref_str)
        if restype is not None:
            identifier = ResourceIdentifier(identifier.resname, restype)
        if identifier.restype == ResourceType.INVALID:
            logger.error("Could not determine resource type from '%s'. Include an extension or pass --type.", resref_str)
            return 1
        identifiers = [identifier]

    results: list[FindResult] = []
    locations_map = resolved_source.locations(identifiers, order=order if resolved_source.installation is not None else None)
    for query in identifiers:
        query_locations = locations_map.get(query, [])
        if not query_locations:
            continue
        for idx, location in enumerate(query_locations):
            file_resource = location.as_file_resource()
            if resolved_source.installation is not None and idx < len(order):
                source_location = order[idx]
            elif resolved_source.kind in {"capsule", "module"}:
                source_location = SearchLocation.CUSTOM_MODULES
            else:
                source_location = SearchLocation.CUSTOM_FOLDERS
            location_type = {
                "folder": "Folder",
                "capsule": "Archive",
                "module": "Module",
                "file": "File",
                "game_root": source_location.name.title(),
            }.get(resolved_source.kind, source_location.name.title())
            results.append(
                FindResult(
                    resref=query.resname,
                    restype=query.restype,
                    size=file_resource.size(),
                    source=source_location,
                    filepath=location.filepath,
                    archive_path=str(file_resource.filepath()) if file_resource.inside_capsule else None,
                    archive_index=0,
                    priority_index=idx + 1,
                    is_selected=(idx == 0),
                    location_type=location_type,
                )
            )
            if not all_locations:
                break

    if not results:
        logger.warning(
            "Resource not found. Searched in resolution order: %s. Try a glob pattern (e.g. 203tel*) or list modules.",
            ", ".join(s.name for s in order),
        )
        return 1

    for r in results:
        sel = " selected" if r.is_selected else ""
        arch = f" ({r.archive_path}, idx {r.archive_index})" if r.archive_path else ""
        logger.info(
            "%s.%s  %s  %s bytes  %s%s%s",
            r.resref,
            r.restype.extension,
            r.restype.name,
            r.size,
            r.location_type,
            arch,
            sel,
        )
    return 0
