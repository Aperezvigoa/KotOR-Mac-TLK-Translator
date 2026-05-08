"""Export all resources from a KotOR installation to JSON files."""

from __future__ import annotations

import shutil

from pathlib import Path
from typing import TYPE_CHECKING

from pykotor.extract.path_source import parse_game_arg, resolve_source_path_from_args
from pykotor.tools.path import get_kotor_paths_from_default
from pykotor.tools.resource_json import export_installation_to_json_tree

if TYPE_CHECKING:
    from argparse import Namespace

    from loggerplus import RobustLogger as Logger


def cmd_installation_to_json(args: Namespace, logger: Logger) -> int:
    output_root = Path(getattr(args, "output", "installation-json")).resolve()
    clean_output = bool(getattr(args, "clean", False))

    if getattr(args, "all_detected", False):
        explicit_path = getattr(args, "path", None)
        if explicit_path:
            logger.error("--all-detected cannot be combined with --path.")
            return 1

        game_arg = getattr(args, "game", None)
        game_filter = parse_game_arg(game_arg)
        if game_arg and game_filter is None:
            logger.error("Unknown game '%s'. Use k1 or k2.", game_arg)
            return 1

        discovered = get_kotor_paths_from_default()
        install_targets = [
            (game, index, Path(path))
            for game, game_paths in discovered.items()
            if game_filter in (None, game)
            for index, path in enumerate(game_paths)
        ]
        if not install_targets:
            logger.error(
                "No default installations were found%s.",
                f" for {game_filter.name}" if game_filter else "",
            )
            return 1

        if clean_output and output_root.exists():
            shutil.rmtree(output_root)
        output_root.mkdir(parents=True, exist_ok=True)

        exit_codes: list[int] = []
        for game, index, installation_path in install_targets:
            install_output_root = output_root / game.name.lower() / str(index)
            logger.info(
                "Exporting auto-detected %s installation [%s] from %s to %s",
                game.name,
                index,
                installation_path,
                install_output_root,
            )
            exit_codes.append(
                export_installation_to_json_tree(installation_path, install_output_root, logger)
            )

        if any(code == 1 for code in exit_codes):
            return 1
        if any(code == 2 for code in exit_codes):
            return 2
        return 0

    installation_path = resolve_source_path_from_args(args, logger)
    if installation_path is None:
        return 1

    if clean_output and output_root.exists():
        shutil.rmtree(output_root)
    return export_installation_to_json_tree(Path(installation_path), output_root, logger)
