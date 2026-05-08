"""Get command: extract a single resource from a resolved source path."""

from __future__ import annotations

import pathlib

from typing import TYPE_CHECKING

from pykotor.extract.file import ResourceIdentifier
from pykotor.extract.installation import SearchLocation
from pykotor.extract.path_source import resolve_resource_source, resolve_source_path_from_args
from pykotor.tools.finder import canonical_search_order
from pykotor.tools.path_safety import resolve_and_validate_under_base

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


def cmd_get(args: Namespace, logger: Logger) -> int:
    """Extract the resource the engine would load (first in resolution order) to disk.

    Usage:
        pykotor get 203tell.wok --path "G:/.../KOTOR2" --output .
        pykotor get 203tel.lyt --path "G:/..." --order OVERRIDE,CHITIN
    """
    path = resolve_source_path_from_args(args, logger)
    if path is None:
        return 1

    resref_str = getattr(args, "resref", None) or getattr(args, "query", None)
    if not resref_str or not str(resref_str).strip():
        logger.error(
            "No resource specified. Use: pykotor get <resref[.ext]> [--path PATH] [--output DIR]"
        )
        return 1

    resolved_source = resolve_resource_source(path)

    ident = ResourceIdentifier.from_path(str(resref_str).strip())
    resname = ident.resname
    restype = ident.restype
    if restype.is_invalid or not restype.extension:
        logger.error(
            "Could not determine resource type from '%s'. Include extension (e.g. 203tell.wok).",
            resref_str,
        )
        return 1

    source = getattr(args, "source", None)
    if source and str(source).strip():
        name_to_loc = {e.name: e for e in SearchLocation}
        loc = name_to_loc.get(str(source).strip().upper())
        if loc is not None:
            order = [loc]
        else:
            logger.warning(
                "Unknown --source '%s'; using default order. Valid: %s",
                source,
                ", ".join(name_to_loc),
            )
            order = canonical_search_order()
    else:
        order = _parse_order_arg(getattr(args, "order", None))
        if order is None:
            order = canonical_search_order()

    if resolved_source.installation is None and getattr(args, "source", None):
        logger.warning("--source only applies to game-root lookups; ignoring it for %s.", path)

    result = resolved_source.resource(resname, restype, order=order)
    if result is None:
        logger.warning(
            "Resource '%s.%s' not found. Searched in order: %s. Try: pykotor find %s --path %s (or use a glob, e.g. *.dlg)",
            resname,
            restype.extension,
            ", ".join(s.name for s in order),
            resref_str,
            path,
        )
        return 1

    output = getattr(args, "output", None) or "."
    export_format = getattr(args, "format", "binary")
    output_path = pathlib.Path(output).resolve()
    default_name = (
        f"{resname}.{restype.extension}.json"
        if export_format == "json"
        else f"{resname}.{restype.extension}"
    )
    if output_path.is_dir() or (not output_path.exists() and not output_path.suffix):
        output_path = output_path / default_name
    elif export_format == "json":
        if output_path.suffix.lower() != ".json":
            output_path = (
                output_path.with_suffix(f"{output_path.suffix}.json")
                if output_path.suffix
                else output_path.with_suffix(".json")
            )
    elif output_path.suffix.lower() != f".{restype.extension}":
        output_path = output_path.parent / f"{output_path.stem}.{restype.extension}"

    try:
        output_path = resolve_and_validate_under_base(
            output_path, pathlib.Path.cwd(), allow_nonexistent=True
        )
    except ValueError as e:
        logger.error("Output path rejected: %s", e)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_data = result.data
    if export_format == "json":
        from pykotor.cli.commands.format_convert import resource_data_to_json_bytes

        try:
            output_data = resource_data_to_json_bytes(result.data, restype)
        except ValueError as e:
            logger.error(str(e))
            return 1

    output_path.write_bytes(output_data)
    logger.info(
        "Extracted %s.%s (%s bytes) to %s",
        resname,
        restype.extension,
        len(output_data),
        output_path,
    )
    return 0
