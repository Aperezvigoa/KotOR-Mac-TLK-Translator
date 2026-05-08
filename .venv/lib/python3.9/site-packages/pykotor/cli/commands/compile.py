"""Compile command implementation."""

from __future__ import annotations

import glob
import shutil
import subprocess

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace
    from logging import Logger

    from pykotor.cli.cfg_parser import KotorCLIConfig

from pykotor.cli.cfg_parser import load_config
from pykotor.common.misc import Game
from pykotor.resource.formats.ncs.compilers import (
    ExternalNCSCompiler,
    InbuiltNCSCompiler,
)


def get_game_from_config() -> Game:
    """Determine which game version to compile for (K1 or K2)."""
    # This could be enhanced to read from config
    # For now, default to K2 which is more compatible
    return Game.K2


def find_nss_compiler() -> Path | None:
    """Find the NWScript compiler executable.

    Searches for external compilers in this order:
    1. nwnnsscomp (preferred, compatible with both K1 and K2)
    2. nwnsc (legacy, Neverwinter Nights compiler)

    """
    import platform

    system = platform.system()
    if system == "Windows":
        compiler_names = ["nwnnsscomp.exe", "nwnsc.exe"]
    else:
        compiler_names = ["nwnnsscomp", "nwnsc"]

    # Check PATH
    for name in compiler_names:
        result = shutil.which(name)
        if result:
            return Path(result)

    return None


def use_builtin_compiler(
    nss_files: list[Path],
    cache_dir: Path,
    game: Game,
    logger: Logger,
) -> tuple[int, int]:
    """Use PyKotor's built-in NSS compiler.

    Args:
    ----
        nss_files: List of NSS files to compile
        cache_dir: Directory to output NCS files
        game: Which game version to compile for
        logger: Logger instance

    Returns:
    -------
        Tuple of (compiled_count, error_count)

    NWScript bytecode generation uses the in-tree compiler under ``resource/formats/ncs/``.
    Former **References** (retail NCS loader symbol names / RVAs, KotOR.js compiler URL)
    are migrated to ``wiki/reverse_engineering_findings.md`` (*cli/commands/compile.py —
    built-in compile path*).
    """
    compiler = InbuiltNCSCompiler()
    compiled_count: int = 0
    error_count: int = 0

    for nss_path in nss_files:
        try:
            output_file: Path = cache_dir / nss_path.with_suffix(".ncs").name
            compiler.compile_script(
                source_file=nss_path,
                output_file=output_file,
                game=game,
                debug=False,
            )
            logger.debug(f"Compiled: {nss_path.name} -> {output_file.name}")  # noqa: G004
            compiled_count += 1
        except Exception:
            logger.exception(f"Compilation failed for {nss_path.name}")  # noqa: G004
            error_count += 1

    return compiled_count, error_count


def cmd_compile(
    args: Namespace,
    logger: Logger,
) -> int:
    """Handle compile command - compile NWScript sources.

    Args:
    ----
        args: Parsed command line arguments
        logger: Logger instance

    Returns:
    -------
        Exit code (0 for success, non-zero for error)
    """
    # Load configuration
    config: KotorCLIConfig | None = load_config(logger)
    if config is None:
        return 1

    # Check for external compiler (optional)
    external_compiler: Path | None = find_nss_compiler()
    use_external: bool = external_compiler is not None

    if use_external:
        logger.info(f"Using external compiler: {external_compiler}")
    else:
        logger.info("Using PyKotor's built-in NSS compiler")

    # Determine game version
    game: Game = get_game_from_config()

    # Determine targets
    target_names = args.targets if args.targets else [None]
    if "all" in target_names:
        targets = config.targets
    else:
        targets = []
        for name in target_names:
            target = config.get_target(name)
            if target is None:
                if name:
                    logger.error(f"Target not found: {name}")  # noqa: G004
                else:
                    logger.error("No default target found")
                return 1
            targets.append(target)

    # Process each target
    for target in targets:
        target_name = target.get("name", "unnamed")
        logger.info(f"Compiling target: {target_name}")  # noqa: G004

        # Get cache directory
        cache_dir: Path = config.root_dir / ".pykotorcli" / "cache" / target_name
        if args.clean and cache_dir.exists():
            logger.info(f"Cleaning cache: {cache_dir}")  # noqa: G004
            shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Get source patterns
        sources: dict[str, list[str]] = config.get_target_sources(target)
        include_patterns: list[str] = sources.get("include", [])
        exclude_patterns: list[str] = sources.get("exclude", [])
        skip_compile_patterns: list[str] = sources.get("skipCompile", [])

        # Add command-line skipCompile patterns
        if hasattr(args, "skipCompile") and args.skipCompile:
            skip_compile_patterns.extend(args.skipCompile or [])

        # Find NSS files to compile
        nss_files: list[Path] = []
        if hasattr(args, "files") and args.files:
            # Specific files specified
            for file_spec in args.files:
                file_path: Path = Path(file_spec)
                if file_path.exists() and file_path.suffix == ".nss":
                    nss_files.append(file_path)
                else:
                    # Try to find by name
                    for pattern in include_patterns:
                        pattern_path: str = str(config.root_dir / pattern)
                        matches: list[str] = glob.glob(pattern_path, recursive=True)
                        for match in matches:
                            match_path: Path = Path(match)
                            if match_path.name in (file_spec, f"{file_spec}.nss"):
                                nss_files.append(match_path)
                                break
        else:
            # Find all NSS files matching patterns
            for pattern in include_patterns:
                pattern_path = str(config.root_dir / pattern)
                matches = glob.glob(pattern_path, recursive=True)
                for match in matches:
                    match_path = Path(match)
                    if match_path.suffix == ".nss":
                        # Check against exclude patterns
                        excluded = False
                        for exclude_pattern in exclude_patterns:
                            import fnmatch  # noqa: PLC0415

                            if fnmatch.fnmatch(
                                str(match_path), str(config.root_dir / exclude_pattern)
                            ):
                                excluded = True
                                break

                        # Check against skipCompile patterns
                        for skip_pattern in skip_compile_patterns:
                            import fnmatch  # noqa: PLC0415

                            if fnmatch.fnmatch(match_path.name, skip_pattern):
                                excluded = True
                                logger.debug(f"Skipping compilation: {match_path.name}")
                                break

                        if not excluded:
                            nss_files.append(match_path)

        logger.info(f"Found {len(nss_files)} scripts to compile")

        if not nss_files:
            logger.warning("No scripts found to compile")
            continue

        # Compile scripts
        if use_external and external_compiler:
            # Use external compiler with correct argv for this nwnnsscomp variant (V1, TSLPatcher, KOTOR Tool, etc.)
            compiled_count = 0
            error_count = 0
            try:
                compiler = ExternalNCSCompiler(external_compiler)
                # Verify binary is known (NwnnsscompConfig will raise ValueError if SHA256 not in KnownExternalCompilers)
                _ = compiler.config(
                    nss_files[0],
                    cache_dir / nss_files[0].with_suffix(".ncs").name,
                    game,
                )
            except ValueError as e:
                logger.warning(
                    f"External compiler at {external_compiler} is not a recognized nwnnsscomp variant: {e}. "
                    "Falling back to built-in compiler.",
                )
                compiler = None
                use_external = False

            if compiler is not None:
                for nss_path in nss_files:
                    try:
                        output_file = cache_dir / nss_path.with_suffix(".ncs").name
                        cfg = compiler.config(nss_path, output_file, game)
                        cmd: list[str] = cfg.get_compile_args(str(compiler.nwnnsscomp_path))

                        result: subprocess.CompletedProcess[str] = subprocess.run(
                            cmd,
                            check=False,
                            capture_output=True,
                            text=True,
                            cwd=config.root_dir,
                        )

                        if result.returncode == 0:
                            logger.debug(f"Compiled: {nss_path.name} -> {output_file.name}")
                            compiled_count += 1
                        else:
                            logger.error(f"Compilation failed for {nss_path.name}:")
                            if result.stdout:
                                logger.error(result.stdout)
                            if result.stderr:
                                logger.error(result.stderr)
                            error_count += 1

                    except Exception as e:
                        logger.error(f"Failed to compile {nss_path.name}: {e}")
                        error_count += 1

            if not use_external or compiler is None:
                compiled_count, error_count = use_builtin_compiler(
                    nss_files, cache_dir, game, logger
                )
        else:
            # Use built-in PyKotor compiler
            compiled_count, error_count = use_builtin_compiler(nss_files, cache_dir, game, logger)

        logger.info(f"Compiled {compiled_count} scripts, {error_count} errors")

        if error_count > 0 and hasattr(args, "abortOnCompileError") and args.abortOnCompileError:
            logger.error("Aborting due to compilation errors")
            return 1

    return 0
