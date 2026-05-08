"""TSL (K2) save/load flow helpers aligned with observed retail The Sith Lords sequencing.

High-level ordering matches K1 (disk check, directory creation, optional screenshot,
then core save components). TSL-specific file roles (for example PIFO / galaxy map)
are handled by ``SaveFolderEntry`` when the game is K2.

Internal engine labels, structure offsets, and the disassembly-derived load sequence
previously referenced in this module are **migrated** to ``wiki/reverse_engineering_findings.md``
under *PyKotor package: migrated library notes* -> ``extract/save_load_flow_tsl.py``.

Use ``run_tsl_save_flow`` and ``run_tsl_load_flow`` from ``run_save_flow`` / ``run_load_flow``
when ``determine_game`` selects K2.
"""

from __future__ import annotations

import shutil

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pykotor.extract.savedata import SaveFolderEntry


def get_free_disk_space_tsl(path: Path) -> int:
    """Return free bytes on the filesystem for path."""
    stat = shutil.disk_usage(path)
    return stat.free


def create_directory_tsl(path: Path) -> bool:
    """Create directory and parents. Returns True if created or exists."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False


def run_tsl_save_flow(
    entry: SaveFolderEntry,
    *,
    min_free_bytes: int = 1024 * 1024,
    write_components: bool = True,
) -> int:
    """Execute the TSL-shaped save flow. Returns 1 on success, 0 on failure.

    Sequence: disk check, create save directory, optional screenshot write,
    then persist core components (see ``SaveFolderEntry.save`` paths).
    """
    save_path = entry.save_path
    root = Path(save_path).parent

    free = get_free_disk_space_tsl(root)
    if free < min_free_bytes:
        return 0

    if not create_directory_tsl(Path(save_path)):
        return 0

    if entry.screenshot is not None:
        screenshot_path = Path(save_path) / entry.SCREENSHOT_NAME.resname
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot_path.write_bytes(entry.screenshot)

    if write_components:
        entry.save_info.save()
        entry.partytable.save()
        entry.globals.save()
        entry.sav.save()

    return 1


def run_tsl_load_flow(entry: SaveFolderEntry) -> Any:
    """Execute the TSL-shaped load flow and return ``entry``.

    Loads party table, save info, globals, nested capsule, then optional screenshot bytes.
    """
    entry.partytable.load()
    entry.save_info.load()
    entry.globals.load()
    entry.sav.load()

    screenshot_path = Path(entry.save_path) / entry.SCREENSHOT_NAME.resname
    if screenshot_path.is_file():
        entry.screenshot = screenshot_path.read_bytes()
    else:
        entry.screenshot = None

    return entry
