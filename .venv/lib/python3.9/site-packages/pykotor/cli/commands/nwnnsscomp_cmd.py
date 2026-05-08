"""Unified nwnnsscomp.exe-compatible CLI command.

Accepts all defined nwnnsscomp argument styles (V1, TSLPatcher, KOTOR Tool,
KOTOR Scripting Tool) and uses PyKotor's built-in compiler/decompiler, or
delegates to an external exe with the correct argv per variant.

References:
    wiki/NWNNSSCOMP-Command-Line-Reference.md
    Libraries/PyKotor/src/pykotor/resource/formats/ncs/compilers.py
"""

from __future__ import annotations

import subprocess

from pathlib import Path
from typing import TYPE_CHECKING

from pykotor.common.misc import Game
from pykotor.resource.formats.ncs.compilers import (
    ExternalNCSCompiler,
    InbuiltNCSCompiler,
)
from pykotor.tools.scripts import decompile_ncs_to_nss

if TYPE_CHECKING:
    from argparse import Namespace

    from loggerplus import RobustLogger


def _resolve_output_path(
    input_path: Path,
    mode: str,
    output_positional: str | None,
    output_opt: str | None,
    outputdir: str | None,
) -> Path:
    """Derive output path from second positional, -o, --outputdir + -o, or default."""
    if output_positional is not None:
        return Path(output_positional)
    if outputdir is not None and output_opt is not None:
        return Path(outputdir) / Path(output_opt).name
    if output_opt is not None:
        return Path(output_opt)
    if mode == "compile":
        return input_path.with_suffix(".ncs")
    return input_path.with_suffix(".nss")


def cmd_nwnnsscomp(args: Namespace, logger: RobustLogger) -> int:
    """Handle nwnnsscomp command: unified NSS compile/decompile with all variant argument styles."""
    input_path = Path(args.input)
    if not input_path.is_file():
        logger.error(f"Input file not found: {input_path}")
        return 1

    # Resolve mode: -c / -d or infer from extension
    suffix = input_path.suffix.lower()
    mode: str
    if getattr(args, "compile", False) or getattr(args, "do_compile", False):
        mode = "compile"
    elif getattr(args, "decompile", False) or getattr(args, "do_decompile", False):
        mode = "decompile"
    elif suffix == ".nss":
        mode = "compile"
    elif suffix == ".ncs":
        mode = "decompile"
    else:
        logger.error(
            "Could not infer mode (compile or decompile). Use -c or -d, or provide input with .nss or .ncs extension.",
        )
        return 1

    if mode == "compile" and suffix != ".nss":
        logger.error("Compile mode requires an .nss input file.")
        return 1
    if mode == "decompile" and suffix != ".ncs":
        logger.error("Decompile mode requires an .ncs input file.")
        return 1

    # Resolve output path (second positional, -o, or --outputdir + -o)
    output_path = _resolve_output_path(
        input_path,
        mode,
        getattr(args, "output_positional", None),
        getattr(args, "output", None),
        getattr(args, "outputdir", None),
    )

    # Resolve game: -g 1|2, --k1, --tsl
    game: Game
    if getattr(args, "game", None) is not None:
        g = args.game
        game = Game.K1 if g == "1" or g == "k1" else Game.K2
    elif getattr(args, "k1", False):
        game = Game.K1
    elif getattr(args, "tsl", False):
        game = Game.K2
    else:
        game = Game.K2

    use_external_path = getattr(args, "use_external", None)
    timeout = getattr(args, "timeout", 5)

    if use_external_path:
        exe_path = Path(use_external_path)
        if not exe_path.is_file():
            logger.error(f"External compiler not found: {exe_path}")
            return 1
        try:
            compiler = ExternalNCSCompiler(exe_path)
            config = compiler.config(str(input_path), str(output_path), game)
        except ValueError as e:
            logger.error(
                f"The specified executable is not a recognized nwnnsscomp variant. {e} "
                "Use built-in (omit --use-external) or a known nwnnsscomp.exe (TSLPatcher, KOTOR Tool, etc.).",
            )
            return 1

        if mode == "compile":
            cmd_args = config.get_compile_args(str(compiler.nwnnsscomp_path))
        else:
            if not config.chosen_compiler.value.commandline.get("decompile"):
                logger.error(
                    f"Compiler '{config.chosen_compiler.value.name}' does not support decompilation. "
                    "Omit --use-external to use PyKotor's built-in decompiler.",
                )
                return 1
            cmd_args = config.get_decompile_args(str(compiler.nwnnsscomp_path))

        try:
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.error(f"Compilation/decompilation timed out after {timeout} seconds")
            return 1
        except OSError as e:
            logger.error(f"Failed to run external compiler: {e}")
            return 1

        if result.returncode != 0:
            if result.stderr:
                logger.error(result.stderr)
            if result.stdout and "Error:" in result.stdout:
                logger.error(result.stdout)
            logger.error(f"External compiler exited with code {result.returncode}")
            return 1
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    logger.info(line)
        logger.info(f"Wrote {output_path}")
        return 0

    # Built-in path
    if mode == "compile":
        builtin = InbuiltNCSCompiler()
        try:
            builtin.compile_script(
                input_path,
                output_path,
                game,
                timeout=timeout,
                debug=getattr(args, "debug", False),
            )
        except Exception as e:
            logger.exception(f"Compilation failed: {e}")
            return 1
        logger.info(f"Compiled {input_path.name} -> {output_path.name}")
    else:
        try:
            decompile_ncs_to_nss(input_path, output_path, game=game)
        except Exception as e:
            logger.exception(f"Decompilation failed: {e}")
            return 1
        logger.info(f"Decompiled {input_path.name} -> {output_path.name}")

    return 0
