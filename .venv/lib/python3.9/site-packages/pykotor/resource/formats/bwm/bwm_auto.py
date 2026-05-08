"""BWM (walkmesh) format detection and read/write dispatch (binary WOK)."""

from __future__ import annotations

import io
import os

from typing import TYPE_CHECKING, Any, cast

from pykotor.resource.formats.bwm.io_bwm import BWMBinaryReader, BWMBinaryWriter
from pykotor.resource.formats.bwm.io_bwm_ascii import BWMAsciiReader, BWMAsciiWriter
from pykotor.resource.type import ResourceType
from pykotor.tools.walkmesh_render_diagram import (
    BWM_VALIDATION_DIAGRAM_MAGIC,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    render_bwm_validation_diagram_lines,
)

if TYPE_CHECKING:
    from pykotor.resource.formats.bwm.bwm_data import BWM
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES

PEEK_SIZE = 256
BWM_MAGIC = b"BWM "

__all__ = [
    "BWM_VALIDATION_DIAGRAM_MAGIC",  # re-exported for pykotor.resource.formats.bwm
]


def _get_bwm_peek(
    source: SOURCE_TYPES,
    offset: int,
    size: int | None,
) -> bytes:
    """Read the first PEEK_SIZE bytes from source for format detection."""
    if isinstance(source, (bytes, bytearray)):
        data = bytes(source)
        start = offset
        end = offset + PEEK_SIZE if size is None else min(offset + (size or 0), offset + PEEK_SIZE)
        return data[start:end]
    if isinstance(source, memoryview):
        data = bytes(source)
        return data[offset : offset + PEEK_SIZE]
    if isinstance(source, (os.PathLike, str)):
        path = os.fspath(source) if isinstance(source, os.PathLike) else os.path.normpath(source)
        with open(path, "rb") as f:  # noqa: PTH123
            f.seek(offset)
            return f.read(PEEK_SIZE if size is None else min(size, PEEK_SIZE))
    # Stream-like: read then rewind
    stream = source
    peek = stream.read(PEEK_SIZE)
    if hasattr(stream, "seek"):
        stream.seek(0)
    return peek if isinstance(peek, bytes) else bytes(peek)  # pyright: ignore[reportArgumentType]


def _read_full_source(
    source: SOURCE_TYPES,
    offset: int,
    size: int | None,
) -> bytes:
    """Read full content from source for ASCII loading."""
    if isinstance(source, (bytes, bytearray)):
        data = bytes(source)
        if size is None:
            return data[offset:]
        return data[offset : offset + size]
    if isinstance(source, memoryview):
        data = bytes(source)
        return data[offset:] if size is None else data[offset : offset + size]
    if isinstance(source, (os.PathLike, str)):
        path = os.fspath(source) if isinstance(source, os.PathLike) else os.path.normpath(source)
        with open(path, "rb") as f:  # noqa: PTH123
            f.seek(offset)
            return f.read() if size is None else f.read(size)  # pyright: ignore[reportCallIssue]
    stream = source
    if hasattr(stream, "seek"):
        stream.seek(offset)
    out = stream.read() if size is None else stream.read(size)  # pyright: ignore[reportCallIssue]
    return out if isinstance(out, bytes) else bytes(out)  # pyright: ignore[reportArgumentType]


def _is_ascii_bwm(peek: bytes) -> bool:
    """Return True if peek looks like ASCII walkmesh (starts with 'node')."""
    try:
        decoded = peek.decode("latin-1").lstrip()
        return decoded.startswith("node")
    except UnicodeDecodeError:
        return False


def read_bwm(
    source: SOURCE_TYPES,
    offset: int = 0,
    size: int | None = None,
    *,
    regenerate_derived: bool = True,
) -> BWM:
    """Returns an WOK instance from the source.

    Auto-detects binary (BWM magic) vs ASCII (starts with 'node') format.
    Supports .wok, .dwk, .pwk binary files and ASCII walkmesh files.

    Args:
    ----
        source: The source of the data (path, bytes, or stream).
        offset: The byte offset of the file inside the data
        size: Number of bytes to allowed to read from the stream. If not specified, uses the whole stream.
        regenerate_derived: If True (default), enforce transition invariant (perimeter-only) and assert after load.

    Raises:
    ------
        FileNotFoundError: If the file could not be found.
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be accessed.
        ValueError: If the file was corrupted.
        AssertionError: If regenerate_derived is True and transitions on non-perimeter edges remain after enforce.

    Returns:
    -------
        An WOK instance.
    """
    peek = _get_bwm_peek(source, offset, size)
    if len(peek) >= 4 and peek[:4] == BWM_MAGIC:
        bwm = BWMBinaryReader(source, offset, size or 0).load()
    elif _is_ascii_bwm(peek):
        data = _read_full_source(source, offset, size)
        bwm = BWMAsciiReader(io.BytesIO(data), 0, 0).load()
    else:
        bwm = BWMBinaryReader(source, offset, size or 0).load()
    if regenerate_derived:
        bwm.enforce_transition_invariant()
        bwm.assert_transition_arrows_invariant()
    return bwm


def write_bwm(
    wok: BWM,
    target: TARGET_TYPES,
    file_format: ResourceType = ResourceType.WOK,
    *,
    regenerate_derived: bool = True,
    logger: Any | None = None,
):
    """Writes the WOK data to the target location with the specified format (WOK only).

    Args:
    ----
        wok: The WOK file being written.
        target: The location to write the data to.
        file_format: The file format.
        regenerate_derived: If True (default), enforce transition invariant and assert before writing.
        logger: Optional logger for write-phase progress (e.g. INFO messages).

    Raises:
    ------
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be written to the specified destination.
        ValueError: If the specified format was unsupported.
        AssertionError: If regenerate_derived is True and invariant fails after enforce.
    """
    if file_format == ResourceType.WOK:
        BWMBinaryWriter(wok, target, regenerate_derived=regenerate_derived, logger=logger).write()
    else:
        msg = "Unsupported format specified; use WOK."
        raise ValueError(msg)


def write_bwm_ascii(
    wok: BWM,
    target: TARGET_TYPES,
) -> None:
    """Writes the BWM to the target as ASCII walkmesh format.

    Args:
    ----
        wok: The BWM instance to write.
        target: The location to write (path, stream, or bytearray).

    Raises:
    ------
        IsADirectoryError: If the target is a directory.
        PermissionError: If the file could not be written.
        ValueError: If the data is invalid.
    """
    BWMAsciiWriter(wok, target).write()


def write_bwm_validation_diagram(
    bwm: BWM,
    target: TARGET_TYPES,
    *,
    max_physical_width: int = 200,
    max_physical_height: int = 120,
    use_color: bool = True,
    error_positions: list[tuple[float, float]] | None = None,
) -> None:
    """Writes the BWM text validation diagram to the target.

    Format: first line is BWM_VALIDATION_DIAGRAM_MAGIC; then Summary (including
    outer perimeter vertex/edge counts), Legend, Top-down map with optional
    "X" at error_positions, and Transitions sections. Use .diagram or .txt when writing to a path.
    Distinct from the BWM ASCII file format (.wok.ascii).

    Args:
    ----
        bwm: The BWM instance to summarize.
        target: Where to write (path, stream, or bytearray).
        max_physical_width: Maximum character width of the map (logical cols = this/5).
        max_physical_height: Maximum character height of the map (logical rows = this/5).
        use_color: If True, embed ANSI color codes (walkable=blue, etc.).
        error_positions: Optional (x, y) world positions to mark with "X" on the map (e.g. validation failures).

    Raises:
    ------
        IsADirectoryError: If the target is a directory.
        PermissionError: If the file could not be written.
    """
    from pykotor.common.stream import BinaryWriter

    lines: list[str] = render_bwm_validation_diagram_lines(
        bwm,
        width=max_physical_width,
        height=max_physical_height,
        use_color=use_color,
        error_positions=error_positions,
    )
    data: bytes = ("\n".join(lines) + "\n").encode("utf-8")
    if isinstance(target, (os.PathLike, str)):
        path: str = (
            os.fspath(target) if isinstance(target, os.PathLike) else os.path.normpath(target)
        )
        with open(path, "wb") as f:  # noqa: PTH123
            f.write(data)
    elif isinstance(target, bytearray):
        target.extend(data)
    elif isinstance(target, BinaryWriter):
        target.write_bytes(data)
    elif isinstance(target, io.TextIOBase):
        target.write(data.decode("utf-8"))
    elif isinstance(target, io.BytesIO):
        cast("io.BytesIO", target).write(data)
    else:
        raise ValueError(f"Unsupported target type: {type(target)}")


def bytes_bwm(
    bwm: BWM,
    file_format: ResourceType = ResourceType.WOK,
    *,
    regenerate_derived: bool = True,
) -> bytes:
    """Returns the BWM data in the specified format (WOK only) as a bytes object.

    This is a convenience method that wraps the write_bwm() method.

    Args:
    ----
        bwm: The target BWM.
        file_format: The file format.
        regenerate_derived: If True (default), enforce transition invariant and assert before writing.

    Raises:
    ------
        ValueError: If the specified format was unsupported.
        AssertionError: If regenerate_derived is True and invariant fails after enforce.

    Returns:
    -------
        The BWM data.
    """
    data = bytearray()
    write_bwm(bwm, data, file_format, regenerate_derived=regenerate_derived)
    return bytes(data)
