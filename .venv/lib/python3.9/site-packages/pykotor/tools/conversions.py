"""Format conversion utility functions for KOTOR game resources.

This module provides reusable, abstract functions for converting between different
formats (GFF<->XML, TLK<->XML, SSF<->XML, 2DA<->CSV, etc.). These functions are tool-agnostic
and can be used by any application that needs format conversions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from pykotor.resource.formats.gff.gff_auto import read_gff, write_gff
from pykotor.resource.formats.lip.lip_auto import read_lip, write_lip
from pykotor.resource.formats.ssf.ssf_auto import read_ssf, write_ssf
from pykotor.resource.formats.tlk.tlk_auto import read_tlk, write_tlk
from pykotor.resource.formats.twoda.twoda_auto import read_2da, write_2da
from pykotor.resource.type import RESOURCE_FORMAT, ResourceType, ToolsetFormat

if TYPE_CHECKING:
    from pathlib import Path

    from pykotor.common.language import Language


def _convert_resource(
    input_path: Path,
    output_path: Path,
    reader: Callable[..., Any],
    writer: Callable[..., None],
    *,
    read_format: RESOURCE_FORMAT | None = None,
    write_format: RESOURCE_FORMAT | None = None,
    **reader_kwargs: Any,
) -> None:
    """Convert a resource by reading then writing with optional explicit formats."""
    read_kwargs = dict(reader_kwargs)
    if read_format is not None:
        read_kwargs["file_format"] = read_format

    resource = reader(input_path, **read_kwargs)

    write_kwargs: dict[str, Any] = {}
    if write_format is not None:
        write_kwargs["file_format"] = write_format
    writer(resource, output_path, **write_kwargs)


def _create_conversion_function(
    reader: Callable[..., Any],
    writer: Callable[..., None],
    read_format: RESOURCE_FORMAT | None = None,
    write_format: RESOURCE_FORMAT | None = None,
    **default_kwargs: Any,
) -> Callable[..., None]:
    """Factory to create conversion functions with consistent patterns."""

    def convert(input_path: Path, output_path: Path, **kwargs: Any) -> None:
        merged_kwargs = {**default_kwargs, **kwargs}
        _convert_resource(
            input_path,
            output_path,
            reader,
            writer,
            read_format=read_format,
            write_format=write_format,
            **merged_kwargs,
        )

    return convert


def convert_gff_to_xml(input_path: Path, output_path: Path) -> None:
    """Convert a GFF file to XML format.

    Args:
    ----
        input_path: Path to the input GFF file (binary or JSON)
        output_path: Path to write the output XML file
    """
    _convert_resource(
        input_path, output_path, read_gff, write_gff, write_format=ToolsetFormat.GFF_XML
    )


def convert_xml_to_gff(
    input_path: Path, output_path: Path, *, gff_content_type: str | None = None
) -> None:
    """Convert an XML file to GFF format.

    Args:
    ----
        input_path: Path to the input XML file
        output_path: Path to write the output GFF file
        gff_content_type: Optional GFF content type (e.g., "IFO ", "UTC ") - auto-detected if None
    """
    _convert_resource(
        input_path,
        output_path,
        read_gff,
        write_gff,
        read_format=ToolsetFormat.GFF_XML,
        write_format=ResourceType.GFF,
    )


def convert_tlk_to_xml(input_path: Path, output_path: Path) -> None:
    """Convert a TLK file to XML format.

    Args:
    ----
        input_path: Path to the input TLK file
        output_path: Path to write the output XML file
    """
    _convert_resource(
        input_path, output_path, read_tlk, write_tlk, write_format=ToolsetFormat.TLK_XML
    )


def convert_xml_to_tlk(
    input_path: Path, output_path: Path, *, language: Language | None = None
) -> None:
    """Convert an XML file to TLK format.

    Args:
    ----
        input_path: Path to the input XML file
        output_path: Path to write the output TLK file
        language: Optional language specification - auto-detected from XML if None
    """
    _convert_resource(
        input_path,
        output_path,
        read_tlk,
        write_tlk,
        read_format=ToolsetFormat.TLK_XML,
        write_format=ResourceType.TLK,
        language=language,
    )


def convert_ssf_to_xml(input_path: Path, output_path: Path) -> None:
    """Convert an SSF file to XML format.

    Args:
    ----
        input_path: Path to the input SSF file
        output_path: Path to write the output XML file
    """
    _convert_resource(
        input_path, output_path, read_ssf, write_ssf, write_format=ToolsetFormat.SSF_XML
    )


def convert_xml_to_ssf(input_path: Path, output_path: Path) -> None:
    """Convert an XML file to SSF format.

    Args:
    ----
        input_path: Path to the input XML file
        output_path: Path to write the output SSF file
    """
    _convert_resource(
        input_path,
        output_path,
        read_ssf,
        write_ssf,
        read_format=ToolsetFormat.SSF_XML,
        write_format=ResourceType.SSF,
    )


def convert_2da_to_csv(input_path: Path, output_path: Path, *, delimiter: str = ",") -> None:
    """Convert a 2DA file to CSV format.

    Args:
    ----
        input_path: Path to the input 2DA file (binary or ASCII)
        output_path: Path to write the output CSV file
        delimiter: CSV delimiter character (default: comma)
    """
    _convert_resource(
        input_path, output_path, read_2da, write_2da, write_format=ToolsetFormat.TwoDA_CSV
    )


def convert_csv_to_2da(input_path: Path, output_path: Path, *, delimiter: str = ",") -> None:
    """Convert a CSV file to 2DA format.

    Args:
    ----
        input_path: Path to the input CSV file
        output_path: Path to write the output 2DA file
        delimiter: CSV delimiter character (default: comma)
    """
    _convert_resource(
        input_path,
        output_path,
        read_2da,
        write_2da,
        read_format=ToolsetFormat.TwoDA_CSV,
        write_format=ResourceType.TwoDA,
    )


def convert_2da_to_json(input_path: Path, output_path: Path) -> None:
    """Convert a 2DA file to JSON format."""
    _convert_resource(
        input_path, output_path, read_2da, write_2da, write_format=ToolsetFormat.TwoDA_JSON
    )


def convert_json_to_2da(input_path: Path, output_path: Path) -> None:
    """Convert a JSON file to 2DA format."""
    _convert_resource(
        input_path,
        output_path,
        read_2da,
        write_2da,
        read_format=ToolsetFormat.TwoDA_JSON,
        write_format=ResourceType.TwoDA,
    )


def convert_gff_to_json(input_path: Path, output_path: Path) -> None:
    """Convert a GFF file to JSON format.

    Args:
    ----
        input_path: Path to the input GFF file (binary or XML)
        output_path: Path to write the output JSON file
    """
    _convert_resource(
        input_path, output_path, read_gff, write_gff, write_format=ToolsetFormat.GFF_JSON
    )


def convert_json_to_gff(
    input_path: Path, output_path: Path, *, gff_content_type: str | None = None
) -> None:
    """Convert a JSON file to GFF format.

    Args:
    ----
        input_path: Path to the input JSON file
        output_path: Path to write the output GFF file
        gff_content_type: Optional GFF content type (e.g., "IFO ", "UTC ") - auto-detected if None
    """
    _convert_resource(
        input_path,
        output_path,
        read_gff,
        write_gff,
        read_format=ToolsetFormat.GFF_JSON,
        write_format=ResourceType.GFF,
    )


def convert_tlk_to_json(input_path: Path, output_path: Path) -> None:
    """Convert a TLK file to JSON format.

    Args:
    ----
        input_path: Path to the input TLK file
        output_path: Path to write the output JSON file
    """
    _convert_resource(
        input_path, output_path, read_tlk, write_tlk, write_format=ToolsetFormat.TLK_JSON
    )


def convert_json_to_tlk(input_path: Path, output_path: Path) -> None:
    """Convert a JSON file to TLK format.

    Args:
    ----
        input_path: Path to the input JSON file
        output_path: Path to write the output TLK file
    """
    _convert_resource(
        input_path,
        output_path,
        read_tlk,
        write_tlk,
        read_format=ToolsetFormat.TLK_JSON,
        write_format=ResourceType.TLK,
    )


def convert_lip_to_json(input_path: Path, output_path: Path) -> None:
    """Convert a LIP file to JSON format."""
    _convert_resource(
        input_path, output_path, read_lip, write_lip, write_format=ToolsetFormat.LIP_JSON
    )


def convert_json_to_lip(input_path: Path, output_path: Path) -> None:
    """Convert a JSON file to LIP format."""
    _convert_resource(
        input_path,
        output_path,
        read_lip,
        write_lip,
        read_format=ToolsetFormat.LIP_JSON,
        write_format=ResourceType.LIP,
    )


def convert_ssf_to_json(input_path: Path, output_path: Path) -> None:
    """Convert a SSF file to JSON format."""
    _convert_resource(
        input_path, output_path, read_ssf, write_ssf, write_format=ToolsetFormat.SSF_JSON
    )


def convert_json_to_ssf(input_path: Path, output_path: Path) -> None:
    """Convert a JSON file to SSF format."""
    _convert_resource(
        input_path,
        output_path,
        read_ssf,
        write_ssf,
        read_format=ToolsetFormat.SSF_JSON,
        write_format=ResourceType.SSF,
    )
