"""Patch ``io_mdl.py`` on disk before first import (KOQ200 / AABB child -1).

Holocron and older ``mdl_auto`` call ``MDLBinaryReader.load()`` with no recovery.
This runs from ``mdl`` package ``__init__`` before ``io_mdl`` is loaded.

Set ``PYKOTOR_SKIP_MDL_PATCH=1`` to disable.
"""

from __future__ import annotations

import os
import re

from pathlib import Path


def _patch_source(text: str) -> str | None:
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

    return text if text != orig else None


def ensure_io_mdl_aabb_patched_on_disk() -> None:
    if os.environ.get("PYKOTOR_SKIP_MDL_PATCH", "").lower() in ("1", "true", "yes"):
        return
    path = Path(__file__).resolve().parent / "io_mdl.py"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return
    updated = _patch_source(raw)
    if updated is None:
        return
    try:
        path.write_text(updated, encoding="utf-8", newline="\n")
    except OSError:
        return
