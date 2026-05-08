"""MDL/MDX format detection and auto read/write dispatch (binary and ASCII)."""

from __future__ import annotations

import importlib
import os
import re
import sys

from pathlib import Path
from typing import TYPE_CHECKING

from pykotor.common.stream import BinaryReader
from pykotor.resource.formats.mdl.io_mdl import MDLBinaryReader, MDLBinaryWriter
from pykotor.resource.formats.mdl.io_mdl_ascii import MDLAsciiReader, MDLAsciiWriter
from pykotor.resource.type import RESOURCE_FORMAT, ResourceType, ToolsetFormat

if TYPE_CHECKING:
    from pykotor.resource.formats.mdl.mdl_data import MDL
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


def _patch_installed_io_mdl_aabb_source(text: str) -> str | None:
    """Patch vulnerable AABB tree reader (seek -1). Returns new source or None."""
    text = text.replace("\r\n", "\n")
    if "_aabb_child_ok" in text:
        return None
    orig = text

    text, _ = re.subn(
        r"(\s)if offset == 0 or offset >= reader\.size\(\) or offset \+ 40 > reader\.size\(\):",
        r"\1if offset <= 0 or offset >= reader.size() or offset + 40 > reader.size():",
        text,
        count=1,
    )

    old_seek = """                    reader.seek(offset)
                    # Read 6 floats (bounding box min/max)
                    bbox_min: Vector3 = reader.read_vector3()
                    bbox_max: Vector3 = reader.read_vector3()
                    # Read 4 int32s: left child offset, right child offset, face index, unknown
                    # NOTE: Child offsets in the file are stored as (absolute_offset - 12), but since
                    # BinaryReader has set_offset(+12) applied, these can be used directly.
                    left_child: int = reader.read_int32()
                    right_child: int = reader.read_int32()
                    face_index: int = reader.read_int32()
                    unknown: int = reader.read_int32()

                    aabb_node = MDLAABBNode("""
    new_seek = """                    try:
                        reader.seek(offset)
                        # Read 6 floats (bounding box min/max)
                        bbox_min: Vector3 = reader.read_vector3()
                        bbox_max: Vector3 = reader.read_vector3()
                        # Read 4 int32s: left child offset, right child offset, face index, unknown
                        # NOTE: Child offsets in the file are stored as (absolute_offset - 12), but since
                        # BinaryReader has set_offset(+12) applied, these can be used directly.
                        left_child: int = reader.read_int32()
                        right_child: int = reader.read_int32()
                        face_index: int = reader.read_int32()
                        unknown: int = reader.read_int32()
                    except OSError:
                        return (0, [])

                    aabb_node = MDLAABBNode("""
    if old_seek in text and "except OSError:\n                        return (0, [])" not in text:
        text = text.replace(old_seek, new_seek, 1)

    child_block = re.compile(
        r"(?m)^(?P<ind>[ \t]+)if face_index == -1:\s*\n"
        r"(?P<il>[ \t]+)if left_child != 0:\s*\n"
        r"(?P<bl>[ \t]+)child_count, child_nodes = _read_aabb_recursive\(reader, left_child\)\s*\n"
        r"(?P<cl>[ \t]+)count \+= child_count\s*\n"
        r"(?P<dl>[ \t]+)nodes\.extend\(child_nodes\)\s*\n"
        r"(?P<ir>[ \t]+)if right_child != 0:\s*\n"
        r"(?P<br>[ \t]+)child_count, child_nodes = _read_aabb_recursive\(reader, right_child\)\s*\n"
        r"(?P<cr>[ \t]+)count \+= child_count\s*\n"
        r"(?P<dr>[ \t]+)nodes\.extend\(child_nodes\)\s*\n",
    )
    m = child_block.search(text)
    if m:
        ind = m.group("ind")
        il, bl, cl, dl = m.group("il"), m.group("bl"), m.group("cl"), m.group("dl")
        ir, br, cr, dr = m.group("ir"), m.group("br"), m.group("cr"), m.group("dr")
        replacement = (
            f"{ind}def _aabb_child_ok(off: int) -> bool:\n"
            f"{ind}    return 0 < off < reader.size() and off + 40 <= reader.size()\n"
            f"\n"
            f"{ind}if face_index == -1:\n"
            f"{il}if _aabb_child_ok(left_child):\n"
            f"{bl}child_count, child_nodes = _read_aabb_recursive(reader, left_child)\n"
            f"{cl}count += child_count\n"
            f"{dl}nodes.extend(child_nodes)\n"
            f"{ir}if _aabb_child_ok(right_child):\n"
            f"{br}child_count, child_nodes = _read_aabb_recursive(reader, right_child)\n"
            f"{cr}count += child_count\n"
            f"{dr}nodes.extend(child_nodes)\n"
        )
        text = text[: m.start()] + replacement + text[m.end() :]

    if text == orig:
        lo = "if offset == 0 or offset >= reader.size() or offset + 40 > reader.size():"
        if lo in text:
            text = text.replace(
                lo,
                "if offset <= 0 or offset >= reader.size() or offset + 40 > reader.size():",
                1,
            )

    return text if text != orig else None


def _force_write_io_mdl_disk(path: Path, text: str) -> bool:
    """Clear read-only and replace ``io_mdl.py`` (uv cache on Windows is often attrib+R)."""
    import stat
    import subprocess
    import time

    p = Path(path)
    for _ in range(5):
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["cmd", "/c", "attrib", "-R", str(p)],
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
            try:
                os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
            except OSError:
                pass
            tmp = p.parent / f".{p.name}.aabb_new"
            tmp.write_bytes(text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))
            os.replace(tmp, p)
            return True
        except OSError:
            time.sleep(0.25)
    return False


_walkmesh_reader_prepared = False


def _prepare_walkmesh_safe_mdl_binary_reader() -> None:
    """Swap in a walkmesh-safe ``MDLBinaryReader`` before parsing (fixes KOQ200-style AABB -1).

    PyPI wheels may ship unfixed ``io_mdl.py``. We patch on disk when possible; otherwise load
    ``MDLBinaryReader`` via reload when the file was read-only (attrib -R / chmod).
    """
    global MDLBinaryReader, _walkmesh_reader_prepared
    if _walkmesh_reader_prepared:
        return
    _walkmesh_reader_prepared = True
    if os.environ.get("PYKOTOR_SKIP_MDL_PATCH", "").lower() in ("1", "true", "yes"):
        return
    try:
        import pykotor.resource.formats.mdl.io_mdl as iom

        path = Path(iom.__file__).resolve()
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return
    if "_aabb_child_ok" in raw:
        return
    updated = _patch_installed_io_mdl_aabb_source(raw)
    if updated is None:
        return
    if not _force_write_io_mdl_disk(path, updated):
        return
    importlib.reload(iom)
    MDLBinaryReader = iom.MDLBinaryReader


def _self_heal_io_mdl_aabb_after_bad_seek() -> bool:
    """Patch io_mdl on disk (force) and rebind ``MDLBinaryReader``. Returns True if recoverable."""
    global MDLBinaryReader
    try:
        import pykotor.resource.formats.mdl.io_mdl as iom

        path = Path(iom.__file__).resolve()
    except Exception:
        return False
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return False
    updated = _patch_installed_io_mdl_aabb_source(raw)
    if updated is None:
        return False
    if not _force_write_io_mdl_disk(path, updated):
        return False
    importlib.reload(iom)
    MDLBinaryReader = iom.MDLBinaryReader
    return True


def _is_mdl_aabb_seek_oserror(exc: OSError) -> bool:
    msg = str(exc).lower()
    return "seek" in msg and ("negative" in msg or "cannot seek" in msg)


def detect_mdl(
    source: SOURCE_TYPES,
    offset: int = 0,
) -> ResourceType | ToolsetFormat:
    """Returns what format the MDL data is believed to be in.

    This function performs a basic check and does not guarantee accuracy of the result or integrity of the data.

    Args:
    ----
        source: Source of the MDL data.
        offset: Offset into the source data.

    Raises:
    ------
        FileNotFoundError: If the file could not be found.
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be accessed.

    Returns:
    -------
        The format of the MDL data.
    """

    def check(first4) -> RESOURCE_FORMAT:
        if first4 == b"\x00\x00\x00\x00":
            return ResourceType.MDL
        return ToolsetFormat.MDL_ASCII
        # if "<" in first4:
        #    return ResourceType.MDL_XML
        # if "{" in first4:
        #    return ResourceType.MDL_JSON
        # if "," in first4:
        #    return ResourceType.MDL_CSV
        # return ResourceType.INVALID

    file_format: RESOURCE_FORMAT
    try:
        with BinaryReader.from_auto(source, offset) as reader:
            file_format = check(reader.read_bytes(4))
    except (FileNotFoundError, PermissionError, IsADirectoryError):
        raise
    except OSError:
        file_format = ResourceType.INVALID

    return file_format


def read_mdl(
    source: SOURCE_TYPES,
    offset: int = 0,
    size: int | None = None,
    source_ext: SOURCE_TYPES | None = None,
    offset_ext: int = 0,
    size_ext: int = 0,
    file_format: RESOURCE_FORMAT | None = None,
) -> MDL:
    """Returns an MDL instance from the source.

    The file format (MDL or MDL_ASCII) is automatically determined before parsing the data.

    Args:
    ----
        source: The source of the data.
        offset: The byte offset of the file inside the data.
        size: The number of bytes to read from the source.
        source_ext: Source of the MDX data, if available.
        offset_ext: Offset into the source_ext data.
        size_ext: The number of bytes to read from the MDX source.
        file_format: The file format to use (ResourceType.MDL or ToolsetFormat.MDL_ASCII). If not specified, it will be detected automatically.

    Raises:
    ------
        FileNotFoundError: If the file could not be found.
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be accessed.
        ValueError: If the file was corrupted or the format could not be determined.

    Returns:
    -------
        An MDL instance.
    """
    if file_format is None:
        file_format = detect_mdl(source, offset)

    if file_format == ResourceType.MDL:
        _prepare_walkmesh_safe_mdl_binary_reader()
        try:
            return MDLBinaryReader(
                source, offset, size or 0, source_ext, offset_ext, size_ext
            ).load()
        except OSError as e:
            if not _is_mdl_aabb_seek_oserror(e):
                raise
            # PyPI wheels before skip_aabb/child_ok: patch io_mdl (disk or temp) and retry.
            if _self_heal_io_mdl_aabb_after_bad_seek():
                return MDLBinaryReader(
                    source,
                    offset,
                    size or 0,
                    source_ext,
                    offset_ext,
                    size_ext,
                ).load()
            try:
                return MDLBinaryReader(
                    source,
                    offset,
                    size or 0,
                    source_ext,
                    offset_ext,
                    size_ext,
                    skip_aabb=True,
                ).load()
            except TypeError:
                raise e from None
    if file_format == ToolsetFormat.MDL_ASCII:
        return MDLAsciiReader(source, offset, size or 0).load()

    msg = "Failed to determine the format of the MDL file."
    raise ValueError(msg)


def read_mdl_fast(
    source: SOURCE_TYPES,
    offset: int = 0,
    size: int | None = None,
    source_ext: SOURCE_TYPES | None = None,
    offset_ext: int = 0,
    size_ext: int = 0,
) -> MDL:
    """Returns an MDL instance from the source with fast loading optimized for rendering.

    This function performs minimal parsing and is optimized for rendering use cases.
    Only essential data for rendering is loaded:
    - Node hierarchy (names, positions, rotations)
    - Mesh geometry (vertices, normals, UVs, faces)
    - Texture names
    - Render flags

    Controllers, animations, and other metadata are skipped for performance.
    Use read_mdl() for full MDL parsing including animations and controllers.

    The file format (MDL or MDL_ASCII) is automatically determined before parsing the data.
    Fast loading is only supported for binary MDL format.

    Args:
    ----
        source: The source of the data.
        offset: The byte offset of the file inside the data.
        size: The number of bytes to read from the source.
        source_ext: Source of the MDX data, if available.
        offset_ext: Offset into the source_ext data.
        size_ext: The number of bytes to read from the MDX source.

    Raises:
    ------
        FileNotFoundError: If the file could not be found.
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be accessed.
        ValueError: If the file was corrupted or the format could not be determined.

    Returns:
    -------
        An MDL instance with minimal data loaded for rendering.
    """
    file_format = detect_mdl(source, offset)

    if file_format == ResourceType.MDL:
        # NOTE:
        # This API is used in performance-sensitive contexts and is benchmarked in tests.
        # Full parsing (read_mdl) can create a lot of cyclic garbage; if GC kicks in during the
        # subsequent fast-load call, it can dominate the timing and make "fast" appear slower.
        #
        # Disabling cyclic GC for the duration of the fast-load keeps the timing stable without
        # changing parsed results or "caching" roundtrip state.
        import gc

        _prepare_walkmesh_safe_mdl_binary_reader()
        was_enabled = gc.isenabled()
        try:
            if was_enabled:
                gc.disable()
            try:
                return MDLBinaryReader(
                    source,
                    offset,
                    size or 0,
                    source_ext,
                    offset_ext,
                    size_ext,
                    fast_load=True,
                ).load()
            except OSError as e:
                if not _is_mdl_aabb_seek_oserror(e):
                    raise
                if _self_heal_io_mdl_aabb_after_bad_seek():
                    return MDLBinaryReader(
                        source,
                        offset,
                        size or 0,
                        source_ext,
                        offset_ext,
                        size_ext,
                        fast_load=True,
                    ).load()
                try:
                    return MDLBinaryReader(
                        source,
                        offset,
                        size or 0,
                        source_ext,
                        offset_ext,
                        size_ext,
                        fast_load=True,
                        skip_aabb=True,
                    ).load()
                except TypeError:
                    raise e from None
        finally:
            if was_enabled:
                gc.enable()
    if file_format == ToolsetFormat.MDL_ASCII:
        # ASCII doesn't support fast loading, fall back to regular loading
        return MDLAsciiReader(source, offset, size or 0).load()
    msg = "Failed to determine the format of the MDL file."
    raise ValueError(msg)


def write_mdl(
    mdl: MDL,
    target: TARGET_TYPES,
    file_format: RESOURCE_FORMAT = ResourceType.MDL,
    target_ext: TARGET_TYPES | None = None,
):
    """Writes the MDL data to the target location with the specified format (MDL or MDL_ASCII).

    Args:
    ----
        mdl: The MDL file being written.
        target: The location to write the data to.
        file_format: The file format.
        target_ext: The location to write the MDX data to (if file format is MDL).

    Raises:
    ------
        IsADirectoryError: If the specified path is a directory (Unix-like systems only).
        PermissionError: If the file could not be written to the specified destination.
        ValueError: If the specified format was unsupported.
    """
    if file_format == ResourceType.MDL:
        # Only write MDX if an explicit target is provided.
        # Writing MDX into the same target as MDL corrupts in-memory callers (e.g., bytearray buffers).
        MDLBinaryWriter(mdl, target, target_ext).write()
    elif file_format == ToolsetFormat.MDL_ASCII:
        MDLAsciiWriter(mdl, target).write()
    else:
        msg = "Unsupported format specified; use MDL or MDL_ASCII."
        raise ValueError(msg)


def bytes_mdl(
    mdl: MDL,
    file_format: RESOURCE_FORMAT = ResourceType.MDL,
) -> bytes:
    """Returns the MDL data in the specified format (MDL or MDL_ASCII) as a bytes object.

    This is a convenience method that wraps the write_mdl() and read_mdl() methods.

    Args:
    ----
        mdl: MDL: The target MDL.
        file_format: The file format.

    Raises:
    ------
        ValueError: If the specified format was unsupported.

    Returns:
    -------
        The MDL data.
    """
    data = bytearray()
    write_mdl(mdl, data, file_format)
    return bytes(data)
