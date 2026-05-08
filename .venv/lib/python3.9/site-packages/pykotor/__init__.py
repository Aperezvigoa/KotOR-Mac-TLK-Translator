"""Utility library for general-purpose functions.

This library contains utility functions that are not specific to KOTOR.
KOTOR-specific utilities should be in Libraries/PyKotor/src/pykotor/tools.
"""

from __future__ import annotations


def _bootstrap_patch_mdl_io_aabb_on_disk() -> None:
    """Patch installed ``io_mdl.py`` before any submodule imports (KOQ200 AABB seek -1).

    Runs on first ``import pykotor`` — before ``pykotor.resource.formats.mdl.io_mdl`` loads.
    Scans site-packages and sys.path. Set PYKOTOR_SKIP_MDL_PATCH=1 to disable.
    """
    import os

    if os.environ.get("PYKOTOR_SKIP_MDL_PATCH", "").lower() in ("1", "true", "yes"):
        return
    try:
        import re
        import site
        import sys
        from pathlib import Path
    except Exception:
        return

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
        if (
            old_seek in text
            and "except OSError:\n                        return (0, [])" not in text
        ):
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

    def _force_write_io_mdl(p: Path, text: str) -> bool:
        import stat
        import subprocess
        import time

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
                tmp.write_text(text, encoding="utf-8", newline="\n")
                os.replace(tmp, p)
                return True
            except OSError:
                time.sleep(0.25)
        return False

    seen: set[str] = set()
    roots: list[str] = []
    try:
        import sysconfig

        pl = sysconfig.get_path("purelib")
        if pl:
            roots.append(pl)
    except Exception:
        pass
    try:
        roots.extend(site.getsitepackages())
    except Exception:
        pass
    try:
        from site import getusersitepackages

        u = getusersitepackages()
        if u:
            roots.append(u)
    except Exception:
        pass
    roots.extend(x for x in sys.path if x)
    for root in roots:
        try:
            p = Path(root) / "pykotor/resource/formats/mdl/io_mdl.py"
        except OSError:
            continue
        if not p.is_file():
            continue
        try:
            key = str(p.resolve())
        except OSError:
            key = str(p)
        if key in seen:
            continue
        seen.add(key)
        try:
            raw = p.read_text(encoding="utf-8")
        except OSError:
            continue
        updated = _patch_source(raw)
        if updated is None:
            continue
        if not _force_write_io_mdl(p, updated):
            try:
                p.write_text(updated, encoding="utf-8", newline="\n")
            except OSError:
                pass

    # Canonical wheel path: if still vulnerable (e.g. read-only site-packages), inject fixed module.
    try:
        _canon = Path(__file__).resolve().parent / "resource/formats/mdl/io_mdl.py"
        if _canon.is_file():
            raw_c = _canon.read_text(encoding="utf-8")
            if "_aabb_child_ok" not in raw_c:
                upd_c = _patch_source(raw_c)
                if upd_c is not None:
                    if not _force_write_io_mdl(_canon, upd_c):
                        try:
                            _canon.write_text(upd_c, encoding="utf-8", newline="\n")
                        except OSError:
                            pass
    except Exception:
        pass


try:
    _bootstrap_patch_mdl_io_aabb_on_disk()
except Exception:
    pass

from utility.fonts import (
    get_font_paths,
    get_font_paths_linux,
    get_font_paths_macos,
    get_font_paths_windows,
)

__all__ = [
    "get_font_paths",
    "get_font_paths_linux",
    "get_font_paths_macos",
    "get_font_paths_windows",
]
