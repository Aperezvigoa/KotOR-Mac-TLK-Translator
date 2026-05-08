"""Format conversion command implementations for Pykotorcli.

Converts GFF, TLK, SSF, 2DA, and related formats via ``pykotor.tools.conversions``.
Former per-command **References** naming retail executables and engine-side GFF/2DA loaders
are migrated to ``wiki/reverse_engineering_findings.md`` (*cli/commands/format_convert.py*).
"""

from __future__ import annotations

import json
import pathlib
import shutil

from argparse import Namespace
from typing import TYPE_CHECKING, Callable

from pykotor.extract.path_source import resolve_source_path_from_args
from pykotor.resource.type import ResourceType
from pykotor.tools.conversions import (
    convert_2da_to_csv,
    convert_2da_to_json,
    convert_csv_to_2da,
    convert_gff_to_json,
    convert_gff_to_xml,
    convert_json_to_2da,
    convert_json_to_gff,
    convert_json_to_lip,
    convert_json_to_ssf,
    convert_json_to_tlk,
    convert_lip_to_json,
    convert_ssf_to_json,
    convert_ssf_to_xml,
    convert_tlk_to_json,
    convert_tlk_to_xml,
    convert_xml_to_gff,
    convert_xml_to_ssf,
    convert_xml_to_tlk,
)
from pykotor.tools.resource_json import (
    direct_json_document_to_resource_bytes,
    export_path_tree_to_json,
    resource_source_to_json_bytes,
)

if TYPE_CHECKING:
    from loggerplus import RobustLogger as Logger


_ARCHIVE_RESOURCE_TYPES = {
    ResourceType.ERF,
    ResourceType.MOD,
    ResourceType.RIM,
    ResourceType.SAV,
    ResourceType.BIF,
    ResourceType.HAK,
}


def _resource_type_from_path(path: pathlib.Path) -> ResourceType:
    return ResourceType.from_extension(path.suffix)


def _resource_type_from_hint(type_hint: str | None) -> ResourceType:
    if not type_hint:
        return ResourceType.INVALID
    return ResourceType.from_extension(type_hint)


def _default_json_output_path(input_path: pathlib.Path) -> pathlib.Path:
    if input_path.suffix:
        return input_path.with_suffix(f"{input_path.suffix}.json")
    return input_path.with_suffix(".json")


def _default_json_tree_output_path(input_path: pathlib.Path) -> pathlib.Path:
    return input_path.with_name(f"{input_path.name}-json")


def _infer_default_output_type(input_path: pathlib.Path, type_hint: str | None) -> ResourceType:
    explicit_type = _resource_type_from_hint(type_hint)
    if not explicit_type.is_invalid:
        return explicit_type

    if input_path.suffix.lower() == ".json":
        inferred = ResourceType.from_extension(input_path.with_suffix("").suffix)
        if not inferred.is_invalid:
            return inferred

    return ResourceType.INVALID


def _default_binary_output_path(
    input_path: pathlib.Path, target_type: ResourceType
) -> pathlib.Path:
    if input_path.suffix.lower() == ".json":
        base_path = input_path.with_suffix("")
        if base_path.suffix and base_path.suffix.lower() == f".{target_type.extension}":
            return base_path
        return base_path.with_suffix(f".{target_type.extension}")
    return input_path.with_suffix(f".{target_type.extension}")


def resource_data_to_json_bytes(data: bytes, restype: ResourceType) -> bytes:
    """Convert raw resource bytes into their JSON representation."""
    return resource_source_to_json_bytes(data, restype, mode="direct")


def _run_to_json_conversion(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    restype: ResourceType,
    logger: Logger,
    *,
    key_file: str | None = None,
    no_plaintext: bool = False,
) -> int:
    if restype.is_invalid:
        logger.error("Could not determine input type for %s. Use --type to specify it.", input_path)
        return 1

    if restype in _ARCHIVE_RESOURCE_TYPES:
        archive_args = Namespace(
            input=str(input_path),
            output=str(output_path),
            key_file=key_file,
            no_plaintext=no_plaintext,
        )
        return cmd_archive_to_json(archive_args, logger)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(resource_source_to_json_bytes(input_path, restype, mode="direct"))
        logger.info("Converted %s to %s", input_path.name, output_path.name)
    except Exception:
        logger.exception("Failed to convert %s", input_path)  # noqa: G004
        return 1
    return 0


def _run_from_json_conversion(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    restype: ResourceType,
    logger: Logger,
) -> int:
    if restype.is_invalid:
        logger.error(
            "Could not determine output type. Use --type or provide an output filename with a supported extension."
        )
        return 1

    if restype.target_type().is_gff():
        return _run_conversion(input_path, output_path, convert_json_to_gff, logger)
    if restype == ResourceType.TLK:
        return _run_conversion(input_path, output_path, convert_json_to_tlk, logger)
    if restype == ResourceType.TwoDA:
        return _run_conversion(input_path, output_path, convert_json_to_2da, logger)
    if restype == ResourceType.LIP:
        return _run_conversion(input_path, output_path, convert_json_to_lip, logger)
    if restype == ResourceType.SSF:
        return _run_conversion(input_path, output_path, convert_json_to_ssf, logger)
    if restype in _ARCHIVE_RESOURCE_TYPES:
        archive_args = Namespace(input=str(input_path), output=str(output_path))
        return cmd_json_to_archive(archive_args, logger)

    try:
        document = json.loads(input_path.read_text(encoding="utf-8"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(direct_json_document_to_resource_bytes(document, restype))
        logger.info("Converted %s to %s", input_path.name, output_path.name)
        return 0
    except ValueError:
        pass
    except Exception:
        logger.exception("Failed to convert %s", input_path)  # noqa: G004
        return 1

    logger.error("JSON import is not supported for .%s files.", restype.extension)
    return 1


def _run_conversion(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    conversion_func: Callable,
    logger: Logger,
    **kwargs,
) -> int:
    """Execute a format conversion with consistent error handling and logging.

    Args:
    ----
        input_path: Source file path
        output_path: Destination file path
        conversion_func: The conversion function to call
        logger: Logger instance for messages
        **kwargs: Additional arguments to pass to conversion_func

    Returns:
    -------
        0 on success, 1 on failure
    """
    try:
        conversion_func(input_path, output_path, **kwargs)
        logger.info(f"Converted {input_path.name} to {output_path.name}")  # noqa: G004
    except Exception:
        logger.exception(f"Failed to convert {input_path}")  # noqa: G004
        return 1
    return 0


def cmd_gff2xml(args: Namespace, logger: Logger) -> int:
    """Convert GFF file to XML format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".xml")
    return _run_conversion(input_path, output_path, convert_gff_to_xml, logger)


def cmd_xml2gff(args: Namespace, logger: Logger) -> int:
    """Convert XML file to GFF format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".gff")
    kwargs = {"gff_content_type": args.type} if hasattr(args, "type") else {}
    return _run_conversion(input_path, output_path, convert_xml_to_gff, logger, **kwargs)


def cmd_tlk2xml(args: Namespace, logger: Logger) -> int:
    """Convert TLK file to XML format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".xml")
    return _run_conversion(input_path, output_path, convert_tlk_to_xml, logger)


def cmd_xml2tlk(args: Namespace, logger: Logger) -> int:
    """Convert XML file to TLK format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".tlk")
    return _run_conversion(input_path, output_path, convert_xml_to_tlk, logger)


def cmd_ssf2xml(args: Namespace, logger: Logger) -> int:
    """Convert SSF file to XML format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".xml")
    return _run_conversion(input_path, output_path, convert_ssf_to_xml, logger)


def cmd_xml2ssf(args: Namespace, logger: Logger) -> int:
    """Convert XML file to SSF format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".ssf")
    return _run_conversion(input_path, output_path, convert_xml_to_ssf, logger)


def cmd_2da2csv(args: Namespace, logger: Logger) -> int:
    """Convert 2DA file to CSV format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".csv")
    delimiter = args.delimiter if hasattr(args, "delimiter") else ","
    return _run_conversion(input_path, output_path, convert_2da_to_csv, logger, delimiter=delimiter)


def cmd_csv22da(args: Namespace, logger: Logger) -> int:
    """Convert CSV file to 2DA format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".2da")
    delimiter = args.delimiter if hasattr(args, "delimiter") else ","
    return _run_conversion(input_path, output_path, convert_csv_to_2da, logger, delimiter=delimiter)


def cmd_2da2json(args: Namespace, logger: Logger) -> int:
    """Convert 2DA file to JSON format."""
    input_path = pathlib.Path(args.input)
    output_path = (
        pathlib.Path(args.output) if args.output else _default_json_output_path(input_path)
    )
    return _run_conversion(input_path, output_path, convert_2da_to_json, logger)


def cmd_gff2json(args: Namespace, logger: Logger) -> int:
    """Convert GFF file to JSON format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".json")
    return _run_conversion(input_path, output_path, convert_gff_to_json, logger)


def cmd_json2gff(args: Namespace, logger: Logger) -> int:
    """Convert JSON file to GFF format."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".gff")
    kwargs = {"gff_content_type": args.type} if hasattr(args, "type") else {}
    return _run_conversion(input_path, output_path, convert_json_to_gff, logger, **kwargs)


def cmd_tlk2json(args: Namespace, logger: Logger) -> int:
    """Convert TLK file to JSON format."""
    input_path = pathlib.Path(args.input)
    output_path = (
        pathlib.Path(args.output) if args.output else _default_json_output_path(input_path)
    )
    return _run_conversion(input_path, output_path, convert_tlk_to_json, logger)


def cmd_json2tlk(args: Namespace, logger: Logger) -> int:
    """Convert JSON file to TLK format."""
    input_path = pathlib.Path(args.input)
    output_path = (
        pathlib.Path(args.output)
        if args.output
        else _default_binary_output_path(input_path, ResourceType.TLK)
    )
    return _run_conversion(input_path, output_path, convert_json_to_tlk, logger)


def cmd_lip2json(args: Namespace, logger: Logger) -> int:
    """Convert LIP file to JSON format."""
    input_path = pathlib.Path(args.input)
    output_path = (
        pathlib.Path(args.output) if args.output else _default_json_output_path(input_path)
    )
    return _run_conversion(input_path, output_path, convert_lip_to_json, logger)


def cmd_json2lip(args: Namespace, logger: Logger) -> int:
    """Convert JSON file to LIP format."""
    input_path = pathlib.Path(args.input)
    output_path = (
        pathlib.Path(args.output)
        if args.output
        else _default_binary_output_path(input_path, ResourceType.LIP)
    )
    return _run_conversion(input_path, output_path, convert_json_to_lip, logger)


def cmd_ssf2json(args: Namespace, logger: Logger) -> int:
    """Convert SSF file to JSON format."""
    input_path = pathlib.Path(args.input)
    output_path = (
        pathlib.Path(args.output) if args.output else _default_json_output_path(input_path)
    )
    return _run_conversion(input_path, output_path, convert_ssf_to_json, logger)


def cmd_json2ssf(args: Namespace, logger: Logger) -> int:
    """Convert JSON file to SSF format."""
    input_path = pathlib.Path(args.input)
    output_path = (
        pathlib.Path(args.output)
        if args.output
        else _default_binary_output_path(input_path, ResourceType.SSF)
    )
    return _run_conversion(input_path, output_path, convert_json_to_ssf, logger)


def cmd_json22da(args: Namespace, logger: Logger) -> int:
    """Convert JSON file to 2DA format."""
    input_path = pathlib.Path(args.input)
    output_path = (
        pathlib.Path(args.output)
        if args.output
        else _default_binary_output_path(input_path, ResourceType.TwoDA)
    )
    return _run_conversion(input_path, output_path, convert_json_to_2da, logger)


def cmd_to_json(args: Namespace, logger: Logger) -> int:
    """Convert a supported resource file to its JSON representation."""
    if getattr(args, "all_detected", False):
        if getattr(args, "input", None):
            logger.error("--all-detected cannot be combined with an explicit input path.")
            return 1
        from pykotor.cli.commands.installation_to_json import cmd_installation_to_json

        return cmd_installation_to_json(args, logger)

    input_value = getattr(args, "input", None)
    if input_value:
        input_path = pathlib.Path(input_value)
    else:
        resolved_path = resolve_source_path_from_args(args, logger)
        if resolved_path is None:
            return 1
        input_path = resolved_path

    if input_path.is_dir():
        output_path = (
            pathlib.Path(args.output) if args.output else _default_json_tree_output_path(input_path)
        )
        if getattr(args, "clean", False) and output_path.exists():
            if output_path.is_dir():
                shutil.rmtree(output_path)
            else:
                output_path.unlink()
        return export_path_tree_to_json(input_path, output_path, logger)

    output_path = (
        pathlib.Path(args.output) if args.output else _default_json_output_path(input_path)
    )
    restype = _resource_type_from_hint(getattr(args, "type", None))
    if restype.is_invalid:
        restype = _resource_type_from_path(input_path)
    return _run_to_json_conversion(
        input_path,
        output_path,
        restype,
        logger,
        key_file=getattr(args, "key_file", None),
        no_plaintext=getattr(args, "no_plaintext", False),
    )


def cmd_from_json(args: Namespace, logger: Logger) -> int:
    """Convert JSON produced by PyKotor back to a binary resource."""
    input_path = pathlib.Path(args.input)
    target_type = _infer_default_output_type(input_path, getattr(args, "type", None))
    output_path = (
        pathlib.Path(args.output)
        if args.output
        else _default_binary_output_path(input_path, target_type)
    )
    if getattr(args, "output", None):
        explicit_type = _resource_type_from_path(output_path)
        if explicit_type.is_invalid:
            explicit_type = _resource_type_from_hint(getattr(args, "type", None))
        if not explicit_type.is_invalid:
            target_type = explicit_type
    return _run_from_json_conversion(input_path, output_path, target_type, logger)


def cmd_archive_to_json(args: Namespace, logger: Logger) -> int:
    """Convert archive (ERF/RIM/MOD/SAV/BIF) to JSON with plaintext resources."""
    from pykotor.tools.archive_serializer import convert_archive_to_json

    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".json")
    key_path = (
        pathlib.Path(args.key_file)
        if getattr(args, "key_file", None)
        else (input_path.parent / "chitin.key")
    )
    try:
        convert_archive_to_json(
            input_path,
            output_path,
            key_path=key_path if key_path.exists() else None,
            embed_plaintext=not getattr(args, "no_plaintext", False),
        )
        logger.info(f"Converted {input_path.name} to {output_path.name}")  # noqa: G004
    except Exception:
        logger.exception(f"Failed to convert {input_path}")  # noqa: G004
        return 1
    return 0


def cmd_json_to_archive(args: Namespace, logger: Logger) -> int:
    """Convert JSON from capsule2json back to binary capsule (ERF/RIM/BIF)."""
    from pykotor.tools.archive_serializer import convert_json_to_archive

    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output)
    try:
        convert_json_to_archive(input_path, output_path)
        logger.info(f"Converted {input_path.name} to {output_path.name}")  # noqa: G004
    except Exception:
        logger.exception(f"Failed to convert {input_path}")  # noqa: G004
        return 1
    return 0
