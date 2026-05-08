"""GFF format detection and auto read/write dispatch (binary, JSON, XML)."""

from __future__ import annotations

import os
import struct

from pathlib import Path
from typing import TYPE_CHECKING

import json
from pykotor.common.stream import BinaryReader
from pykotor.resource.formats._base import BiowareEncoder
from pykotor.resource.formats.gff.gff_data import GFFContent
from pykotor.resource.formats.gff.io_gff import GFFBinaryReader, GFFBinaryWriter
from pykotor.resource.formats.gff.io_gff_xml import GFFXMLReader, GFFXMLWriter
from pykotor.resource.type import RESOURCE_FORMAT, ResourceType, ToolsetFormat
from pykotor.tools.encoding import decode_bytes_with_fallbacks

if TYPE_CHECKING:
    from pykotor.resource.formats.gff.gff_data import GFF
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES

_UTF8_BOM: bytes = b"\xef\xbb\xbf"


def _adjust_offset_after_utf8_bom(
    source: SOURCE_TYPES,
    offset: int,
    size: int | None,
) -> tuple[int, int | None]:
    """Skip a leading UTF-8 BOM at (source, offset) so binary GFF readers align on the file type id."""
    if isinstance(source, (bytes, bytearray, memoryview)):
        total: int = len(source)
        end: int = total if size is None else min(total, offset + size)
        if offset + 3 > end:
            return offset, size
        head = source[offset : offset + 3]
        if isinstance(head, memoryview):
            head = head.tobytes()
        elif isinstance(head, bytearray):
            head = bytes(head)
        if head != _UTF8_BOM:
            return offset, size
        new_offset = offset + 3
        if size is None:
            return new_offset, None
        return new_offset, size - 3

    if isinstance(source, (str, os.PathLike)):
        try:
            with Path(os.fspath(source)).open("rb") as handle:
                handle.seek(offset)
                bom_candidate = handle.read(3)
        except OSError:
            return offset, size
        if bom_candidate != _UTF8_BOM:
            return offset, size
        new_offset = offset + 3
        if size is None:
            return new_offset, None
        if size < 3:
            return offset, size
        return new_offset, size - 3

    return offset, size


def _is_binary_gff_v32_magic(magic8: bytes) -> bool:
    """True if bytes are a KotOR-style binary GFF magic (4-char type + b'V3.2')."""
    if len(magic8) < 8:
        return False
    type_id = magic8[:4].decode("windows-1252", errors="ignore")
    if not any(x.value == type_id for x in GFFContent):
        return False
    return magic8[4:8] == b"V3.2"


def _is_binary_gff_v32_at(peek: bytes, index: int) -> bool:
    """True if a KotOR-style binary GFF header (4-char type + b'V3.2') starts at index."""
    if index < 0 or index + 8 > len(peek):
        return False
    return _is_binary_gff_v32_magic(peek[index : index + 8])


def _gff_payload_span(source: SOURCE_TYPES, offset: int, size: int | None) -> int:
    """Length in bytes available from (source, offset) when constrained by size."""
    if isinstance(source, (bytes, bytearray, memoryview)):
        total: int = len(source)
        end: int = total if size is None else min(total, offset + size)
        return max(0, end - offset)
    if isinstance(source, (str, os.PathLike)):
        try:
            st = Path(os.fspath(source)).stat()
        except OSError:
            return 0
        if size is None:
            return max(0, st.st_size - offset)
        return max(0, min(st.st_size, offset + size) - offset)
    return 0


def _binary_gff_header_offsets_plausible(header48: bytes, span_from_header_start: int) -> bool:
    """True if the 48 bytes after GFF magic describe table offsets that fit within span_from_header_start."""
    if span_from_header_start < 56 or len(header48) < 48:
        return False
    (
        struct_off,
        struct_cnt,
        field_off,
        field_cnt,
        label_off,
        label_cnt,
        field_data_off,
        _field_data_cnt,
        field_idx_off,
        field_idx_cnt,
        list_idx_off,
        list_idx_cnt,
    ) = struct.unpack_from("<12I", header48, 0)
    ptrs = (
        struct_off,
        field_off,
        label_off,
        field_data_off,
        field_idx_off,
        list_idx_off,
    )
    for p in ptrs:
        if p < 56 or p >= span_from_header_start:
            return False
    if max(struct_cnt, field_cnt, label_cnt, field_idx_cnt, list_idx_cnt) > 0x100000:
        return False
    if label_off + label_cnt * 16 > span_from_header_start:
        return False
    if struct_off + struct_cnt * 12 > span_from_header_start:
        return False
    if field_off + field_cnt * 12 > span_from_header_start:
        return False
    # field_indices_count / list_indices_count often overstate reserved space; the reader does not
    # load those arrays wholesale. Bounds above match io_gff.load()'s upfront reads.
    return True


def _locate_binary_gff_header_structural(
    source: SOURCE_TYPES,
    offset: int,
    size: int | None,
    *,
    max_scan: int = 256,
) -> int | None:
    """Find binary GFF V3.2 start by validating header tables against stream span (allows non-padding prefixes)."""
    span = _gff_payload_span(source, offset, size)
    if span < 56:
        return None
    window_len = min(span, max_scan + 56)
    buf: bytes
    if isinstance(source, (bytes, bytearray, memoryview)):
        raw = memoryview(source)[offset : offset + window_len]
        buf = raw.tobytes()
    elif isinstance(source, (str, os.PathLike)):
        try:
            with Path(os.fspath(source)).open("rb") as handle:
                handle.seek(offset)
                buf = handle.read(window_len)
        except OSError:
            return None
    else:
        return None
    if len(buf) < 56:
        return None
    upper = min(max_scan, max(0, span - 56))
    for i in range(upper + 1):
        if i + 56 > len(buf):
            break
        if not _is_binary_gff_v32_magic(buf[i : i + 8]):
            continue
        header48 = buf[i + 8 : i + 56]
        if _binary_gff_header_offsets_plausible(header48, span - i):
            return i
    return None


def _leading_bytes_allow_gff_resync(peek: bytes, header_off: int) -> bool:
    """True if bytes before a candidate GFF header are only harmless padding (BOM / WS / NUL).

    Without this, a coincidental b\"ARE \"+b\"V3.2\" deep in arbitrary binary can be mistaken for
    a real header and produce corrupt parses (OSError: exceed stream boundaries).
    """
    if header_off <= 0:
        return True
    if header_off > len(peek):
        return False
    prefix = peek[:header_off]
    idx = 0
    if len(prefix) >= 3 and prefix[:3] == _UTF8_BOM:
        idx = 3
    allowed = frozenset(b" \t\r\n\x00")
    return all(b in allowed for b in prefix[idx:])


def _locate_binary_gff_header(peek: bytes, *, max_scan: int = 64) -> int | None:
    """Return byte offset of binary GFF V3.2 header within peek, or None if not found."""
    upper = min(max_scan + 1, max(0, len(peek) - 7))
    for i in range(upper):
        if not _leading_bytes_allow_gff_resync(peek, i):
            continue
        if _is_binary_gff_v32_at(peek, i):
            return i
    return None


def _classify_gff_peek(peek: bytes) -> RESOURCE_FORMAT:
    """Infer GFF container format from the first bytes (handles UTF-8 BOM and leading whitespace)."""
    if len(peek) < 4:
        return ResourceType.INVALID
    if peek.startswith(_UTF8_BOM):
        peek = peek[len(_UTF8_BOM) :]
    if len(peek) < 4:
        return ResourceType.INVALID
    first4 = peek[:4].decode("windows-1252", errors="ignore")
    if len(peek) >= 8 and any(x.value == first4 for x in GFFContent) and peek[4:8] == b"V3.2":
        return ResourceType.GFF
    stripped = peek.lstrip(b" \t\r\n")
    if not stripped:
        return ResourceType.INVALID
    if stripped[:1] == b"<":
        return ToolsetFormat.GFF_XML
    if stripped[:1] == b"{":
        return ToolsetFormat.GFF_JSON
    return ResourceType.INVALID


def detect_gff(
    source: SOURCE_TYPES,
    offset: int = 0,
) -> RESOURCE_FORMAT:
    """Returns what format the GFF data is believed to be in.

    This function performs a basic check and does not guarantee accuracy of the result or integrity of the data.

    Args:
    ----
        source: Source of the GFF data.
        offset: Offset into the data.

    Raises:
    ------
        FileNotFoundError: If the file could not be found.
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be accessed.

    Returns:
    -------
        The format of the GFF data.
    """
    file_format: RESOURCE_FORMAT
    try:
        with BinaryReader.from_auto(source, offset) as reader:
            remain = reader.remaining()
            chunk_len = min(512, max(0, remain))
            peek = reader.read_bytes(chunk_len)
        file_format = _classify_gff_peek(peek)
        if (
            file_format == ResourceType.INVALID and _locate_binary_gff_header(peek) is not None
        ) or (
            file_format == ResourceType.INVALID
            and _locate_binary_gff_header_structural(source, offset, None) is not None
        ):
            file_format = ResourceType.GFF
    except (FileNotFoundError, PermissionError, IsADirectoryError):
        raise
    except OSError:
        file_format = ResourceType.INVALID

    return file_format


def read_gff(
    source: SOURCE_TYPES,
    offset: int = 0,
    size: int | None = None,
    file_format: RESOURCE_FORMAT | None = None,
) -> GFF:
    """Returns an GFF instance from the source.

    The file format (GFF or GFF_XML) is automatically determined before parsing the data.

    Args:
    ----
        source: The source of the data.
        offset: The byte offset of the file inside the data.
        size: Number of bytes to allowed to read from the stream. If not specified, uses the whole stream.
        file_format: The file format to use (ResourceType.GFF or ToolsetFormat.*_XML or ToolsetFormat.*_JSON). If not specified, it will be detected automatically.

    Raises:
    ------
        FileNotFoundError: If the file could not be found.
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be accessed.
        ValueError: If the file was corrupted or the format could not be determined.

    Returns:
    -------
        A GFF instance.
    """
    offset, size = _adjust_offset_after_utf8_bom(source, offset, size)

    peek: bytes
    try:
        with BinaryReader.from_auto(source, offset) as reader:
            chunk_len = min(512, max(0, reader.remaining()))
            peek = reader.read_bytes(chunk_len)
    except (FileNotFoundError, PermissionError, IsADirectoryError):
        raise
    except OSError:
        peek = b""

    header_off = _locate_binary_gff_header(peek)
    if header_off is None:
        header_off = _locate_binary_gff_header_structural(source, offset, size)
    promoted_binary: bool = False
    if file_format is None:
        file_format = _classify_gff_peek(peek)
        if file_format == ResourceType.INVALID and header_off is not None:
            file_format = ResourceType.GFF
            promoted_binary = True
    if (
        file_format.target_type().is_gff()
        and not file_format.name.endswith("_XML")
        and not file_format.name.endswith("_JSON")
        and header_off is not None
        and (promoted_binary or header_off > 0)
    ):
        offset += header_off
        if size is not None:
            size = max(0, size - header_off)

    if (
        file_format.target_type().is_gff()
        and not file_format.name.endswith("_XML")
        and not file_format.name.endswith("_JSON")
    ):
        return GFFBinaryReader(source, offset, size or 0).load()
    if file_format.name.endswith("_XML") and file_format.target_type().is_gff():
        return GFFXMLReader(source, offset, size or 0).load()
    if file_format.name.endswith("_JSON") and file_format.target_type().is_gff():
        from pykotor.resource.formats.gff.gff_data import GFF

        with BinaryReader.from_auto(source, offset) as reader:
            raw = reader.read_all()
        decoded = decode_bytes_with_fallbacks(raw)
        return GFF.from_json(json.loads(decoded))

    msg = "Failed to determine the format of the GFF file."
    # if file_format == ResourceType.INVALID:
    raise ValueError(msg)


def write_gff(
    gff: GFF,
    target: TARGET_TYPES,
    file_format: RESOURCE_FORMAT = ResourceType.GFF,
):
    """Writes the GFF data to the target location with the specified format (GFF or GFF_XML).

    Args:
    ----
        gff: The GFF file being written.
        target: The location to write the data to.
        file_format: The file format.

    Raises:
    ------
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be written to the specified destination.
        ValueError: If the specified format was unsupported.
    """
    if (
        file_format.target_type().is_gff()
        and not file_format.name.endswith("_XML")
        and not file_format.name.endswith("_JSON")
    ):
        GFFBinaryWriter(gff, target).write()
    elif file_format.name.endswith("_XML") and file_format.target_type().is_gff():
        GFFXMLWriter(gff, target).write()
    elif file_format.name.endswith("_JSON") and file_format.target_type().is_gff():
        json_dump = json.dumps(gff, cls=BiowareEncoder, indent=4)
        from pykotor.common.stream import BinaryWriter

        with BinaryWriter.to_auto(target) as writer:
            writer.write_bytes(json_dump.encode())
    else:
        msg = "Unsupported format specified; use GFF, GFF_XML, or GFF_JSON."
        raise ValueError(msg)


def bytes_gff(
    gff: GFF,
    file_format: RESOURCE_FORMAT = ResourceType.GFF,
) -> bytes:
    """Returns the GFF data in the specified format (GFF or GFF_XML) as a bytes object.

    This is a convenience method that wraps the write_gff() and read_gff() methods.

    Args:
    ----
        gff: GFF: The target GFF.
        file_format: The file format.

    Raises:
    ------
        ValueError: If the specified format was unsupported.

    Returns:
    -------
        The GFF data.
    """
    data = bytearray()
    write_gff(gff, data, file_format)
    return bytes(data)
