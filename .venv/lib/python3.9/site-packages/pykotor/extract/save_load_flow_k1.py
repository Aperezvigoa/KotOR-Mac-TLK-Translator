"""K1 save/load flow helpers aligned with the current helper implementation.

This module mirrors the high-level steps seen when the retail game saves or loads
a save folder: free-space threshold, directory creation (with optional clean-and-retry),
path construction under the save root, screenshot write, then persisting
SAVENFO, PARTYTABLE, GLOBALVARS, and SAVEGAME.sav in a fixed order.

Executable-derived notes were migrated to ``wiki/reverse_engineering_findings.md``.

Use ``run_save_flow`` / ``run_load_flow`` with ``pykotor.tools.heuristics.determine_game``;
K1 uses this module, K2/TSL uses ``save_load_flow_tsl``.
"""

from __future__ import annotations

import shutil

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from pykotor.common.misc import Game
from pykotor.extract.save_load_flow_tsl import run_tsl_load_flow, run_tsl_save_flow
from pykotor.tools.heuristics import determine_game

if TYPE_CHECKING:
    from pykotor.extract.savedata import SaveFolderEntry

_GAMES_K1 = {Game.K1, Game.K1_XBOX, Game.K1_IOS, Game.K1_ANDROID}
_GAMES_K2_TSL = {Game.K2, Game.K2_XBOX, Game.K2_IOS, Game.K2_ANDROID}

# Minimum free-space gate used by this helper.
K1_MIN_FREE_BYTES_ENGINE: int = 0x640 * (1 << 14)  # 26_214_400 (~25 MiB)

# Save-path identifiers used by this helper.
K1_ALIAS_SAVE_PATH: int = 0x745174
K1_CURRENTGAME: int = 0x73D8F4
K1_FORMAT_PATH: int = 0x7454D4
K1_FORMAT_SCREENSHOT_PATTERN: int = 0x7454AC
K1_PATH_SKIP_SCREENSHOT_CMP: int = 0x73D71C


def get_free_disk_space_k1(path: Path) -> int:
    """Return free bytes on the volume containing ``path`` (``shutil.disk_usage``)."""
    stat = shutil.disk_usage(path)
    return stat.free


def get_directory_size_k1(path: Path) -> int:
    """Return total byte size of all files under ``path`` (recursive); 0 if missing or error."""
    if not path.is_dir():
        return 0
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
    except OSError:
        return 0
    return total


def clean_directory_k1(path: Path) -> bool:
    """Remove all entries under ``path`` so the directory is empty; keep ``path`` itself."""
    if not path.is_dir():
        return True
    try:
        for p in path.iterdir():
            if p.is_file():
                p.unlink()
            else:
                shutil.rmtree(p)
        return True
    except OSError:
        return False


def create_directory_k1(path: Path) -> bool:
    """Create ``path`` and parents; return True if created or already exists."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False


def has_enough_disk_space_for_save_game_k1(path: Path) -> bool:
    """True when ``(free >> 14) >= 0x640`` (retail K1 gate)."""
    free = get_free_disk_space_k1(path)
    return (free >> 14) >= 0x640


def get_alias_path_k1(alias_id: int, base_path: Path) -> Path:
    """Resolve save-root path; ``K1_ALIAS_SAVE_PATH`` maps to ``base_path``."""
    if alias_id == K1_ALIAS_SAVE_PATH:
        return base_path.resolve()
    return base_path.resolve()


def format_path_k1(pattern_id: int, currentgame_path: Path, save_name: str) -> Path:
    """Join ``currentgame_path`` and ``save_name`` (path vs screenshot pattern ids share this shape here)."""
    if pattern_id == K1_FORMAT_PATH:
        return (currentgame_path / save_name).resolve()
    if pattern_id == K1_FORMAT_SCREENSHOT_PATTERN:
        return (currentgame_path / save_name).resolve()
    return (currentgame_path / save_name).resolve()


def exo_string_operator_plus_k1(prefix: Path, suffix: str) -> Path:
    """Path concatenation helper (prefix / suffix)."""
    return (prefix / suffix).resolve()


def cstr_from_path_k1(path: Path) -> str:
    """Posix string for a path (API interop stand-in)."""
    return path.as_posix()


def build_full_save_path_k1(save_root: Path, save_name: str) -> Path:
    """Build full save directory path from save root and slot/folder name."""
    alias_path = get_alias_path_k1(K1_ALIAS_SAVE_PATH, save_root)
    full_path = format_path_k1(K1_FORMAT_PATH, alias_path, save_name)
    return full_path


def send_server_to_player_save_load_status_k1(
    type_val: int,
    subtype: int,
    player: Any,
) -> None:
    """No-op stand-in for client save/load status messaging (structure assembled, not sent)."""
    _type = type_val  # 1
    _subtype = subtype  # 2
    _byte = 1
    _zero_8 = 0
    _zero_c = 0
    _str_18 = ""
    _str_20 = ""
    _zero_38 = 0
    _ = (player, _type, _subtype, _byte, _zero_8, _zero_c, _str_18, _str_20, _zero_38)


def send_server_to_player_load_bar_start_stall_event_k1(event_type: int) -> None:
    """No-op stand-in for load-bar / stall-event notification."""
    _ = event_type


def _do_save_game_screenshot_k1(
    screenshot_path: Path,
    screenshot_data: Optional[bytes],
) -> None:
    """Write screenshot bytes to ``screenshot_path`` when provided."""
    if screenshot_data is None:
        return
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    screenshot_path.write_bytes(screenshot_data)


def run_k1_save_flow(
    entry: SaveFolderEntry,
    *,
    min_free_bytes: int = K1_MIN_FREE_BYTES_ENGINE,
    required_save_bytes: Optional[int] = None,
    required_max_directory_bytes: Optional[int] = None,
    skip_screenshot_if_path_equal: Optional[str] = None,
    retry_create_after_clean: bool = True,
    write_components: bool = True,
) -> int:
    """Run the K1-ordered save sequence. Returns 1 on success, 0 on failure.

    Steps (retail-shaped, see wiki for binary-level mapping): enforce free space;
    create save directory (optional clean + retry); optional max directory size check;
    build paths; no-op status / load-bar hooks; optional screenshot skip when path
    matches ``skip_screenshot_if_path_equal``; write save components when
    ``write_components`` is True.
    """
    save_path = entry.save_path
    root: Path = Path(save_path).parent
    path_obj: Path = Path(save_path)

    free: int = get_free_disk_space_k1(root)
    if free < min_free_bytes:
        return 0
    if required_save_bytes is not None and free < required_save_bytes:
        return 0

    if not create_directory_k1(path_obj):
        if retry_create_after_clean:
            clean_directory_k1(path_obj)
            if not create_directory_k1(path_obj):
                return 0
        else:
            return 0

    if required_max_directory_bytes is not None:
        dir_size = get_directory_size_k1(path_obj)
        if dir_size >= required_max_directory_bytes:
            return 0

    save_name = path_obj.name
    path_obj = build_full_save_path_k1(root, save_name)
    _path_cstr = cstr_from_path_k1(path_obj)

    send_server_to_player_save_load_status_k1(1, 2, None)

    send_server_to_player_load_bar_start_stall_event_k1(2)

    skip_screenshot = (
        skip_screenshot_if_path_equal is not None
        and path_obj.resolve().as_posix()
        == Path(skip_screenshot_if_path_equal).resolve().as_posix()
    )

    if not skip_screenshot:
        screenshot_path = path_obj / entry.SCREENSHOT_NAME.resname
        _do_save_game_screenshot_k1(screenshot_path, entry.screenshot)

    if write_components:
        entry.save_info.save()
        entry.partytable.save()
        entry.globals.save()
        entry.sav.save()

    return 1


def run_k1_load_flow(entry: SaveFolderEntry) -> Any:
    """Run the K1-ordered load sequence and return ``entry``.

    Loads PARTYTABLE, save info, globals, nested SAVEGAME.sav, then optional screenshot bytes.
    Wiki documents the retail load-bar and resource-directory ordering this mirrors.
    """
    entry.partytable.load()

    entry.save_info.load()
    entry.globals.load()

    entry.sav.load()

    screenshot_path: Path = Path(entry.save_path) / entry.SCREENSHOT_NAME.resname
    if screenshot_path.is_file():
        entry.screenshot = screenshot_path.read_bytes()
    else:
        entry.screenshot = None

    return entry


def run_save_flow(
    entry: SaveFolderEntry,
    game_install_path: str | Path,
    **kwargs: Any,
) -> int:
    """Dispatch save flow by ``determine_game(game_install_path)`` (K1 vs TSL).

    Extra ``kwargs`` pass through where supported (TSL only forwards a subset).

    Returns:
        1 on success, 0 on failure or indeterminate game.
    """
    game = determine_game(game_install_path)
    if game is None:
        return 0
    if game in _GAMES_K1:
        return run_k1_save_flow(entry, **kwargs)
    if game in _GAMES_K2_TSL:
        tsl_kw = {k: v for k, v in kwargs.items() if k in ("min_free_bytes", "write_components")}
        return run_tsl_save_flow(entry, **tsl_kw)
    return 0


def run_load_flow(
    entry: SaveFolderEntry,
    game_install_path: str | Path,
) -> Any:
    """Dispatch load flow by ``determine_game(game_install_path)`` (K1 vs TSL).

    Raises:
        ValueError: If the game cannot be determined or is unsupported for this flow.
    """
    game = determine_game(game_install_path)
    if game is None:
        raise ValueError(f"Cannot determine game for path: {game_install_path}")
    if game in _GAMES_K1:
        return run_k1_load_flow(entry)
    if game in _GAMES_K2_TSL:
        return run_tsl_load_flow(entry)
    raise ValueError(f"Unsupported game for save/load flow: {game!r}")
