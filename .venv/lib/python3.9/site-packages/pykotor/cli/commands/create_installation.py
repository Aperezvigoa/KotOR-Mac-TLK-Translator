"""CLI command for scaffolding a minimal KotOR game-root layout."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace

    from loggerplus import RobustLogger as Logger


def cmd_create_installation(args: Namespace, logger: Logger) -> int:
    """Scaffold a minimal KotOR game-root directory layout.

    Creates a fully valid but empty installation tree — chitin.key, dialog.tlk,
    all canonical subdirectories, and game-specific sentinel files — suitable
    for development environments, CI pipelines, or any context where a real
    game root is unavailable.
    """
    from pykotor.common.misc import Game
    from pykotor.tools.create_installation import create_minimal_installation

    dest = Path(args.path)

    game_str = (args.game or "k1").lower().strip()
    game_map: dict[str, Game] = {
        "k1": Game.K1,
        "kotor": Game.K1,
        "kotor1": Game.K1,
        "k2": Game.K2,
        "tsl": Game.K2,
        "kotor2": Game.K2,
    }
    game = game_map.get(game_str)
    if game is None:
        logger.error("Unknown game %r — use k1 or k2.", game_str)
        return 1

    if dest.exists() and (dest / "chitin.key").exists() and not getattr(args, "force", False):
        logger.info("Game root already exists at %s (use --force to overwrite).", dest)
        return 0

    if getattr(args, "force", False) and dest.exists():
        import shutil

        shutil.rmtree(dest)

    root = create_minimal_installation(dest, game)
    logger.info("Created %s game-root scaffold at: %s", game_str.upper(), root)
    return 0
