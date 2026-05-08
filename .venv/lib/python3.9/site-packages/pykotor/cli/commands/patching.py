"""Batch patching command implementations for Pykotorcli.

This module provides CLI commands for batch patching operations:
- Converting GFF files between K1 and TSL
- Converting TGA/TPC textures
- Setting dialogs as unskippable
- Batch patching game roots, folders, and files

Batch patch flows use ``pykotor.tools.patching`` (originating from Tools/BatchPatcher).
Former module **References** (retail executable names and GFF/DLG loader notes with addresses)
are migrated to ``wiki/reverse_engineering_findings.md`` (*cli/commands/patching.py*).
"""

from __future__ import annotations

import pathlib

from typing import TYPE_CHECKING

from pykotor.tools.patching import (
    PatchingConfig,
    determine_input_path,
    is_kotor_install_dir,
    patch_file,
    patch_folder,
    patch_install,
)

if TYPE_CHECKING:
    from argparse import Namespace

    from loggerplus import RobustLogger as Logger


def cmd_batch_patch(args: Namespace, logger: Logger) -> int:
    """Batch patch files, folders, archives, or game roots.

    Usage:
        pykotorcli batch-patch --path "C:/Games/KOTOR" --set-unskippable
        pykotorcli batch-patch --path "C:/Games/KOTOR" --convert-gffs-to-k1
        pykotorcli batch-patch --path "C:/Games/KOTOR" --convert-tga "TGA to TPC"
    """
    config = PatchingConfig()
    config.set_unskippable = args.set_unskippable
    config.convert_tga = args.convert_tga
    config.k1_convert_gffs = args.convert_gffs_to_k1
    config.tsl_convert_gffs = args.convert_gffs_to_tsl
    config.always_backup = args.always_backup
    config.max_threads = args.max_threads
    config.log_callback = lambda msg: logger.info(msg)

    try:
        input_path = pathlib.Path(args.path)
        processed_files: set[pathlib.Path] = set()
        determine_input_path(input_path, config, processed_files)
        logger.info(f"Batch patching completed. Processed {len(processed_files)} files.")  # noqa: G004
        return 0
    except Exception:
        logger.exception("Error during batch patching")
        return 1


def cmd_patch_file(args: Namespace, logger: Logger) -> int:
    """Patch a single file.

    Usage:
        pykotorcli patch-file --file "mymodule.mod" --set-unskippable
    """
    config = PatchingConfig()
    config.set_unskippable = args.set_unskippable
    config.convert_tga = args.convert_tga
    config.k1_convert_gffs = args.convert_gffs_to_k1
    config.tsl_convert_gffs = args.convert_gffs_to_tsl
    config.always_backup = args.always_backup
    config.log_callback = lambda msg: logger.info(msg)

    try:
        file_path = pathlib.Path(args.file)
        patch_file(file_path, config)
        logger.info(f"Patched file: {file_path}")  # noqa: G004
        return 0
    except Exception:
        logger.exception("Error patching file")
        return 1


def cmd_patch_folder(args: Namespace, logger: Logger) -> int:
    """Patch all files in a folder recursively.

    Usage:
        pykotorcli patch-folder --folder "C:/MyMod" --set-unskippable
    """
    config = PatchingConfig()
    config.set_unskippable = args.set_unskippable
    config.convert_tga = args.convert_tga
    config.k1_convert_gffs = args.convert_gffs_to_k1
    config.tsl_convert_gffs = args.convert_gffs_to_tsl
    config.always_backup = args.always_backup
    config.max_threads = args.max_threads
    config.log_callback = lambda msg: logger.info(msg)

    try:
        folder_path = pathlib.Path(args.folder)
        patch_folder(folder_path, config)
        logger.info(f"Patched folder: {folder_path}")  # noqa: G004
        return 0
    except Exception:
        logger.exception("Error patching folder")
        return 1


def cmd_patch_installation(args: Namespace, logger: Logger) -> int:
    """Patch a KotOR game root.

    Usage:
        pykotorcli patch-game-root --path "C:/Games/KOTOR" --set-unskippable
    """
    config = PatchingConfig()
    config.set_unskippable = args.set_unskippable
    config.convert_tga = args.convert_tga
    config.k1_convert_gffs = args.convert_gffs_to_k1
    config.tsl_convert_gffs = args.convert_gffs_to_tsl
    config.always_backup = args.always_backup
    config.max_threads = args.max_threads
    config.log_callback = lambda msg: logger.info(msg)

    try:
        install_path = pathlib.Path(args.path)
        if not is_kotor_install_dir(install_path):
            logger.error(f"Path is not a KotOR game root: {install_path}")
            return 1

        patch_install(install_path, config)
        logger.info(f"Patched game root: {install_path}")  # noqa: G004
        return 0
    except Exception:
        logger.exception("Error patching installation")
        return 1
