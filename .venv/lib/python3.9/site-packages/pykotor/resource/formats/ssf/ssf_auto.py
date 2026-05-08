"""SSF auto: detect format and read/write sound set (binary/XML)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pykotor.common.stream import BinaryReader
from pykotor.resource.formats._base import BiowareEncoder
from pykotor.resource.formats.ssf.io_ssf import SSFBinaryReader, SSFBinaryWriter
from pykotor.resource.formats.ssf.io_ssf_xml import SSFXMLReader, SSFXMLWriter
from pykotor.resource.type import RESOURCE_FORMAT, ResourceType, ToolsetFormat
from pykotor.tools.encoding import decode_bytes_with_fallbacks

if TYPE_CHECKING:
    from pykotor.resource.formats.ssf.ssf_data import SSF
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


def detect_ssf(
    source: SOURCE_TYPES,
    offset: int = 0,
) -> ResourceType:
    """Returns what format the SSF data is believed to be in.

    This function performs a basic check and does not guarantee accuracy of the result or integrity of the data.

    Args:
    ----
        source: Source of the SSF data.
        offset: Offset into the data.

    Raises:
    ------
        FileNotFoundError: If the file could not be found.
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be accessed.

    Returns:
    -------
        The format of the SSF data.
    """

    def check(first4: str) -> RESOURCE_FORMAT:
        if first4 == "SSF ":
            return ResourceType.SSF
        if "<" in first4:
            return ToolsetFormat.SSF_XML
        if "{" in first4:
            return ToolsetFormat.SSF_JSON
        # if "," in first4:
        #    return ResourceType.SSF_CSV
        return ResourceType.INVALID

    file_format: RESOURCE_FORMAT
    try:
        with BinaryReader.from_auto(source, offset) as reader:
            file_format = check(reader.read_string(4))
    except (FileNotFoundError, PermissionError, IsADirectoryError):
        raise
    except OSError:
        file_format = ResourceType.INVALID

    return file_format


def read_ssf(
    source: SOURCE_TYPES,
    offset: int = 0,
    size: int | None = None,
    file_format: RESOURCE_FORMAT | None = None,
) -> SSF:
    """Returns an SSF instance from the source.

    The file format (SSF or SSF_XML) is automatically determined before parsing the data.

    Args:
    ----
        source: The source of the data.
        offset: The byte offset of the file inside the data.
        size: Number of bytes to allowed to read from the stream. If not specified, uses the whole stream.
        file_format: The file format to use (ResourceType.SSF, ToolsetFormat.SSF_XML, ToolsetFormat.SSF_JSON). If not specified, it will be detected automatically.

    Raises:
    ------
        FileNotFoundError: If the file could not be found.
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be accessed.
        ValueError: If the file was corrupted or the format could not be determined.

    Returns:
    -------
        An SSF instance.
    """
    if file_format is None:
        file_format = detect_ssf(source, offset)

    if file_format == ResourceType.INVALID:
        msg = "Failed to determine the format of the GFF file."
        raise ValueError(msg)

    if file_format == ResourceType.SSF:
        return SSFBinaryReader(source, offset, size or 0).load()
    if file_format == ToolsetFormat.SSF_XML:
        return SSFXMLReader(source, offset, size or 0).load()
    if file_format == ToolsetFormat.SSF_JSON:
        from pykotor.resource.formats.ssf.ssf_data import SSF

        with BinaryReader.from_auto(source, offset) as reader:
            raw = reader.read_all()
        decoded = decode_bytes_with_fallbacks(raw)
        return SSF.from_json(json.loads(decoded))
    msg = "Failed to determine the format of the SSF file."
    raise ValueError(msg)


def write_ssf(
    ssf: SSF,
    target: TARGET_TYPES,
    file_format: RESOURCE_FORMAT = ResourceType.SSF,
):
    """Writes the SSF data to the target location with the specified format.

    Args:
    ----
        ssf: The SSF file being written.
        target: The location to write the data to.
        file_format: The file format.

    Raises:
    ------
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be written to the specified destination.
        ValueError: If the specified format was unsupported.
    """
    if file_format == ResourceType.SSF:
        SSFBinaryWriter(ssf, target).write()
    elif file_format == ToolsetFormat.SSF_XML:
        SSFXMLWriter(ssf, target).write()
    elif file_format == ToolsetFormat.SSF_JSON:
        json_dump = json.dumps(ssf, cls=BiowareEncoder, indent=4)
        from pykotor.common.stream import BinaryWriter

        with BinaryWriter.to_auto(target) as writer:
            writer.write_bytes(json_dump.encode())
    else:
        msg = "Unsupported format specified; use SSF, SSF_XML or SSF_JSON."
        raise ValueError(msg)


def bytes_ssf(
    ssf: SSF,
    file_format: RESOURCE_FORMAT = ResourceType.SSF,
) -> bytes:
    """Returns the SSF data in the specified format as a bytes object.

    This is a convenience method that wraps the write_ssf() method.

    Args:
    ----
        ssf: The target SSF object.
        file_format: The file format.

    Raises:
    ------
        ValueError: If the specified format was unsupported.

    Returns:
    -------
        The SSF data.
    """
    data = bytearray()
    write_ssf(ssf, data, file_format)
    return bytes(data)
