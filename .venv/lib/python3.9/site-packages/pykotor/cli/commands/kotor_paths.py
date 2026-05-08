"""List default KotOR game-root paths detected on the local machine."""

from __future__ import annotations

import json
import sys

from typing import TYPE_CHECKING

from pykotor.common.misc import Game
from pykotor.tools.path import get_kotor_paths_from_default

if TYPE_CHECKING:
    from argparse import Namespace

    from loggerplus import RobustLogger as Logger


def _parse_game(value: str | None) -> Game | None:
    if value is None:
        return None

    normalized = value.strip().lower()
    if normalized in {"k1", "kotor", "kotor1"}:
        return Game.K1
    if normalized in {"k2", "tsl", "kotor2"}:
        return Game.K2
    return None


def cmd_kotor_paths(args: Namespace, logger: Logger) -> int:
    """List default KotOR game-root paths discovered from platform defaults and registry."""
    game_filter = _parse_game(getattr(args, "game", None))
    if getattr(args, "game", None) and game_filter is None:
        logger.error("Unknown game '%s'. Use k1 or k2.", args.game)
        return 1

    paths = get_kotor_paths_from_default()
    items = [
        (game, found_paths) for game, found_paths in paths.items() if game_filter in (None, game)
    ]

    if getattr(args, "json", False):
        payload = {
            game.name.lower(): [str(path) for path in found_paths] for game, found_paths in items
        }
        sys.stdout.write(json.dumps(payload, indent=4) + "\n")
        return 0

    for game, found_paths in items:
        label = "KotOR I" if game == Game.K1 else "KotOR II"
        if not found_paths:
            logger.info("%s: no default game roots found", label)
            continue
        logger.info("%s:", label)
        for index, path in enumerate(found_paths):
            logger.info("  [%s] %s", index, path)
    return 0
