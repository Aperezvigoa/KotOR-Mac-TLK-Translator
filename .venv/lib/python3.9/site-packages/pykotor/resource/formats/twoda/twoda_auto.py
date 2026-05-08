"""2DA format detection and auto read/write dispatch (binary, CSV, JSON)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pykotor.common.stream import BinaryReader
from pykotor.resource.formats._base import BiowareEncoder
from pykotor.resource.formats.twoda.io_twoda import TwoDABinaryReader, TwoDABinaryWriter
from pykotor.resource.formats.twoda.io_twoda_csv import TwoDACSVReader, TwoDACSVWriter
from pykotor.resource.type import RESOURCE_FORMAT, ResourceType, ToolsetFormat
from pykotor.tools.encoding import decode_bytes_with_fallbacks

if TYPE_CHECKING:
    from pykotor.resource.formats.twoda.twoda_data import TwoDA
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


def detect_2da(
    source: SOURCE_TYPES,
    offset: int = 0,
) -> ResourceType:
    """Returns what format the TwoDA data is believed to be in.

    This function performs a basic check and does not guarantee accuracy of the result or integrity of the data.

    Args:
    ----
        source: Source of the TwoDA data.
        offset: Offset into the data.

    Raises:
    ------
        FileNotFoundError: If the file could not be found.
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be accessed.

    Returns:
    -------
        The format of the TwoDA data.
    """

    def check(
        first4,
    ) -> RESOURCE_FORMAT:
        if first4 == "2DA ":
            return ResourceType.TwoDA
        if "{" in first4:
            return ToolsetFormat.TwoDA_JSON
        if "," in first4:
            return ToolsetFormat.TwoDA_CSV
        # if "<" in first4:
        #    return ResourceType.TwoDA_XML
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


def read_2da(
    source: SOURCE_TYPES,
    offset: int = 0,
    size: int | None = None,
    file_format: RESOURCE_FORMAT | None = None,
) -> TwoDA:
    """Returns an TwoDA instance from the source.

    The file format (TwoDA, TwoDA_CSV, TwoDA_JSON) is automatically determined before parsing the data.

    Args:
    ----
        source: The source of the data.
        offset: The byte offset of the file inside the data.
        size: Number of bytes to allowed to read from the stream. If not specified, uses the whole stream.
        file_format: The file format to use (ResourceType.TwoDA, ToolsetFormat.TwoDA_CSV, ToolsetFormat.TwoDA_JSON). If not specified, it will be detected automatically.

    Raises:
    ------
        FileNotFoundError: If the file could not be found.
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be accessed.
        ValueError: If the file was corrupted or the format could not be determined.

    Returns:
    -------
        An TwoDA instance.
    """
    if file_format is None:
        file_format = detect_2da(source, offset)

    if file_format == ResourceType.INVALID:
        msg = "Failed to determine the format of the 2DA file."
        raise ValueError(msg)

    if file_format == ResourceType.TwoDA:
        return TwoDABinaryReader(source, offset, size or 0).load()
    if file_format == ToolsetFormat.TwoDA_CSV:
        return TwoDACSVReader(source, offset, size or 0).load()
    if file_format == ToolsetFormat.TwoDA_JSON:
        from pykotor.resource.formats.twoda.twoda_data import TwoDA

        with BinaryReader.from_auto(source, offset) as reader:
            raw = reader.read_all()
        decoded = decode_bytes_with_fallbacks(raw)
        return TwoDA.from_json(json.loads(decoded))
    msg = "detect_2da failed unexpectedly"
    raise ValueError(msg)


def write_2da(
    twoda: TwoDA,
    target: TARGET_TYPES,
    file_format: RESOURCE_FORMAT = ResourceType.TwoDA,
):
    """Writes the TwoDA data to the target location with the specified format.

    Currently, the supported formats are: TwoDA, TwoDA_CSV and TwoDA_JSON.

    Args:
    ----
        twoda: The TwoDA file being written.
        target: The location to write the data to.
        file_format: The file format.

    Raises:
    ------
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be written to the specified destination.
        ValueError: If the specified format was unsupported.
    """
    if file_format == ResourceType.TwoDA:
        TwoDABinaryWriter(twoda, target).write()
    elif file_format == ToolsetFormat.TwoDA_CSV:
        TwoDACSVWriter(twoda, target).write()
    elif file_format == ToolsetFormat.TwoDA_JSON:
        json_dump = json.dumps(twoda, cls=BiowareEncoder, indent=4)
        from pykotor.common.stream import BinaryWriter

        with BinaryWriter.to_auto(target) as writer:
            writer.write_bytes(json_dump.encode())
    else:
        msg = "Unsupported format specified; use TwoDA, TwoDA_CSV or TwoDA_JSON."
        raise ValueError(msg)


def bytes_2da(
    twoda: TwoDA,
    file_format: RESOURCE_FORMAT = ResourceType.TwoDA,
) -> bytes:
    """Returns the TwoDA data in the specified format (TwoDA, TwoDA_CSV or TwoDA_JSON) as a bytes object.

    This is a convenience method that wraps the write_2da() method.

    Args:
    ----
        twoda: The target TwoDA object.
        file_format: The file format.

    Raises:
    ------
        ValueError: If the specified format was unsupported.

    Returns:
    -------
        The TwoDA data.
    """
    data = bytearray()
    write_2da(twoda, data, file_format)
    return bytes(data)
