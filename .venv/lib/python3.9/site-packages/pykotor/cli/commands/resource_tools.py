"""Resource conversion command implementations for Pykotorcli.

This module provides CLI commands for converting resources (textures, sounds, models)
using PyKotor utilities.
"""

from __future__ import annotations

import os
import pathlib
import sys

from typing import TYPE_CHECKING

from pykotor.resource.formats.bwm import BWM, read_bwm, write_bwm, write_bwm_ascii
from pykotor.resource.formats.bwm.bwm_data import BWMType
from pykotor.tools.resources import (
    convert_ascii_to_bwm,
    convert_ascii_to_mdl,
    convert_bwm_to_ascii,
    convert_clean_to_wav,
    convert_mdl_to_ascii,
    convert_tga_to_tpc,
    convert_tpc_to_tga,
    convert_wav_to_clean,
)

if TYPE_CHECKING:
    from argparse import Namespace

    from loggerplus import RobustLogger as Logger


def cmd_texture_convert(args: Namespace, logger: Logger) -> int:
    """Convert texture files (TPC<->TGA)."""
    input_path = pathlib.Path(args.input)

    try:
        if input_path.suffix.lower() == ".tpc":
            # TPC to TGA
            output_path = (
                pathlib.Path(args.output) if args.output else input_path.with_suffix(".tga")
            )
            txi_output = pathlib.Path(args.txi) if args.txi else None
            convert_tpc_to_tga(input_path, output_path, txi_output_path=txi_output)
            logger.info(f"Converted {input_path.name} to {output_path.name}")  # noqa: G004
        else:
            # TGA to TPC
            output_path = (
                pathlib.Path(args.output) if args.output else input_path.with_suffix(".tpc")
            )
            txi_path = pathlib.Path(args.txi) if args.txi else None
            convert_tga_to_tpc(
                input_path,
                output_path,
                txi_input_path=txi_path,
                target_format=None,  # Auto-detect format
            )
            logger.info(f"Converted {input_path.name} to {output_path.name}")  # noqa: G004
    except Exception:
        logger.exception(f"Failed to convert texture {input_path}")  # noqa: G004
        return 1
    else:
        return 0


def cmd_sound_convert(args: Namespace, logger: Logger) -> int:
    """Convert sound files (WAV<->clean WAV)."""
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output) if args.output else input_path.with_suffix(".wav")

    try:
        if args.to_clean:
            # WAV to clean (deobfuscated)
            convert_wav_to_clean(input_path, output_path)
            logger.info(f"Converted {input_path.name} to clean WAV: {output_path.name}")  # noqa: G004
        else:
            # Clean WAV to game format
            wav_type = args.type if hasattr(args, "type") else "SFX"
            convert_clean_to_wav(input_path, output_path, wav_type=wav_type)
            logger.info(f"Converted {input_path.name} to game WAV: {output_path.name}")  # noqa: G004
    except Exception:
        logger.exception(f"Failed to convert sound {input_path}")  # noqa: G004
        return 1
    else:
        return 0


def cmd_model_convert(args: Namespace, logger: Logger) -> int:
    """Convert model files (MDL<->ASCII)."""
    input_path = pathlib.Path(args.input)

    try:
        if args.to_ascii:
            # Binary MDL to ASCII
            output_path = (
                pathlib.Path(args.output) if args.output else input_path.with_suffix(".mdl")
            )
            mdx_path = pathlib.Path(args.mdx) if args.mdx else None
            convert_mdl_to_ascii(input_path, output_path, mdx_path=mdx_path)
            logger.info(f"Converted {input_path.name} to ASCII: {output_path.name}")  # noqa: G004
        else:
            # ASCII MDL to binary
            output_mdl = (
                pathlib.Path(args.output) if args.output else input_path.with_suffix(".mdl")
            )
            mdx_output = pathlib.Path(args.mdx) if args.mdx else None
            convert_ascii_to_mdl(input_path, output_mdl, output_mdx_path=mdx_output)
            logger.info(f"Converted {input_path.name} to binary: {output_mdl.name}")  # noqa: G004
    except Exception:
        logger.exception(f"Failed to convert model {input_path}")  # noqa: G004
        return 1
    else:
        return 0


def cmd_walkmesh_rebuild(args: Namespace, logger: Logger) -> int:
    """Rebuild BWM AABB/adjacency/edges from geometry (read then write regenerates derived data).

    Reference: KotOR.js src/odyssey/OdysseyWalkMesh.ts:729-754 (rebuild), 834-1019 (toExportBuffer).
    See .cursor/plans/kotorjs_walkmesh_port_plan.md for full port mapping.
    """
    input_path = pathlib.Path(args.input)

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")  # noqa: G004
        return 1

    # Default output: overwrite input for binary; for .ascii input use same stem with .wok
    if args.output is not None:
        output_path = pathlib.Path(args.output)
    elif input_path.suffix.lower() == ".ascii":
        output_path = input_path.with_suffix("").with_suffix(".wok")
    else:
        output_path = input_path

    try:
        # ---- Input and format ----
        input_size: int = input_path.stat().st_size
        with input_path.open("rb") as f:
            peek: bytes = f.read(min(256, input_size))
        if len(peek) >= 4 and peek[:4] == b"BWM ":
            format_name = "binary (BWM magic)"
        elif peek.decode("latin-1", errors="ignore").lstrip().startswith("node"):
            format_name = "ASCII (node block)"
        else:
            format_name = "binary (assumed)"
        logger.info(f"Input: {input_path} ({input_size} bytes)")  # noqa: G004
        logger.info(f"Detected format: {format_name}")  # noqa: G004

        # ---- Load ----
        logger.info("Loading walkmesh...")  # noqa: G004
        bwm = read_bwm(input_path)
        verts = bwm.vertices()
        walkable = [f for f in bwm.faces if f.material.walkable()]
        unwalkable = [f for f in bwm.faces if not f.material.walkable()]
        n_faces = len(bwm.faces)
        n_walkable = len(walkable)
        n_unwalkable = len(unwalkable)
        type_name = getattr(bwm.walkmesh_type, "name", str(bwm.walkmesh_type))

        logger.info(  # noqa: G004
            f"Loaded: {len(verts)} vertices, {n_faces} faces ({n_walkable} walkable, {n_unwalkable} unwalkable), type={type_name}",
        )

        def _count_transitions(w: BWM) -> int:
            return sum(1 for f in w.faces for t in (f.trans1, f.trans2, f.trans3) if t is not None)

        trans_before = _count_transitions(bwm)
        if trans_before:
            logger.info(
                f"Input: {trans_before} edge(s) with transitions (door/area links); keeping only those on outer boundary."
            )  # noqa: G004

        # ---- Regenerate derived data (AABB, adjacency, perimeter, normals) ----
        logger.info(
            "Rebuilding from geometry: AABB tree, adjacency, perimeter edges, loop markers, face normals."
        )  # noqa: G004

        # ---- Transition invariant: only perimeter edges may have transitions; arrow = inward ----
        cleared = bwm.enforce_transition_invariant()
        trans_after = _count_transitions(bwm)

        if bwm.walkmesh_type == BWMType.AreaModel:
            n_perimeter = len(bwm.perimeter_edge_set())
            logger.info(f"Perimeter: {n_perimeter} boundary edge(s) (outer walkable boundary).")  # noqa: G004
            if trans_after:
                if cleared:
                    logger.info(  # noqa: G004
                        f"Transitions: {trans_before} -> {trans_after} (cleared {cleared} from internal edges). {trans_after} arrow(s) on perimeter, pointing inward.",
                    )
                else:
                    logger.info(
                        f"Transitions: {trans_after} on perimeter (all valid). Arrows point inward."
                    )  # noqa: G004
            elif cleared:
                logger.info(
                    f"Transitions: cleared {cleared} (were on internal edges); 0 remain on perimeter."
                )  # noqa: G004
            else:
                logger.info("Transitions: 0 (no door/area links on this walkmesh).")  # noqa: G004
        else:
            logger.info("Transitions: preserved (placeable/door walkmesh).")  # noqa: G004

        # ---- Validation diagram (before write_bwm: writer mutates bwm.faces) ----
        if getattr(args, "render_png", False):
            verbose: bool = getattr(args, "verbose", False)
            if not verbose:
                os.environ.setdefault("MPLBACKEND", "Agg")
                import logging as _logging

                _logging.getLogger("matplotlib").setLevel(_logging.WARNING)
            try:
                from pykotor.tools.walkmesh_render import render_bwm_to_pngs
            except ImportError:
                logger.info(
                    "matplotlib not in this environment; writing validation diagram. "
                    "For PNGs: uv sync --extra render then re-run, or use the .diagram file.",
                )
                from pykotor.resource.formats.bwm.bwm_auto import write_bwm_validation_diagram
                from pykotor.tools.walkmesh_render_diagram import (
                    render_bwm_validation_diagram_lines,
                )

                diagram_path = output_path.parent / f"{output_path.stem}.diagram"
                write_bwm_validation_diagram(bwm, diagram_path)
                logger.info(f"Wrote validation diagram: {diagram_path}")  # noqa: G004
                for line in render_bwm_validation_diagram_lines(bwm):
                    logger.info(line)
            else:
                output_stem: pathlib.Path = output_path.parent / output_path.stem
                try:
                    paths: list[pathlib.Path] = render_bwm_to_pngs(bwm, output_stem)
                    logger.info(
                        "Wrote %s validation PNG(s): %s",
                        len(paths),
                        ", ".join(str(p) for p in paths),
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(
                        "PNG render failed (matplotlib 3D backend issue: %s); wrote validation diagram instead.",
                        e,
                    )
                    from pykotor.resource.formats.bwm.bwm_auto import write_bwm_validation_diagram
                    from pykotor.tools.walkmesh_render_diagram import (
                        render_bwm_validation_diagram_lines,
                    )

                    diagram_path = output_path.parent / f"{output_path.stem}.diagram"
                    write_bwm_validation_diagram(bwm, diagram_path)
                    logger.info(f"Wrote validation diagram: {diagram_path}")  # noqa: G004
                    for line in render_bwm_validation_diagram_lines(bwm):
                        logger.info(line)

        # ---- Write ----
        logger.info(f"Writing: {output_path}")  # noqa: G004
        sys.stdout.flush()
        sys.stderr.flush()
        write_bwm(bwm, output_path, logger=logger)
        out_size = output_path.stat().st_size
        logger.info(f"Wrote {out_size} bytes -> {output_path}")  # noqa: G004

        if getattr(args, "ascii", False):
            ascii_path = output_path.with_suffix(output_path.suffix + ".ascii")
            write_bwm_ascii(bwm, ascii_path)
            logger.info(f"Wrote ASCII: {ascii_path}")  # noqa: G004
    except AssertionError as e:
        logger.error(f"Transition invariant failed (perimeter-only transitions): {e}")  # noqa: G004
        return 1
    except Exception:
        logger.exception(f"Failed to rebuild walkmesh {input_path}")  # noqa: G004
        return 1
    return 0


def cmd_walkmesh_convert(args: Namespace, logger: Logger) -> int:
    """Convert walkmesh BWM/WOK to/from ASCII.

    Usage:
        pykotor walkmesh-convert --input 203tell.wok --to-ascii
        pykotor walkmesh-convert --input 203tell.wok.ascii --to-binary
    """
    input_path = pathlib.Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")  # noqa: G004
        return 1

    to_ascii = getattr(args, "to_ascii", False)
    to_binary = getattr(args, "to_binary", False)
    if to_ascii and to_binary:
        logger.error("Specify only one of --to-ascii or --to-binary")
        return 1
    if not to_ascii and not to_binary:
        # Auto-detect from extension
        if input_path.suffix.lower() == ".ascii":
            to_binary = True
        else:
            to_ascii = True

    if args.output:
        output_path = pathlib.Path(args.output)
    elif to_ascii:
        output_path = input_path.with_suffix(input_path.suffix + ".ascii")
    else:
        output_path = (
            input_path.with_suffix("").with_suffix(".wok")
            if input_path.suffix.lower() == ".ascii"
            else input_path.with_suffix(".wok")
        )

    try:
        if to_ascii:
            convert_bwm_to_ascii(input_path, output_path)
            logger.info(f"Converted {input_path.name} to ASCII: {output_path}")  # noqa: G004
        else:
            convert_ascii_to_bwm(input_path, output_path)
            logger.info(f"Converted {input_path.name} to binary: {output_path}")  # noqa: G004
    except Exception:
        logger.exception(f"Failed to convert walkmesh {input_path}")  # noqa: G004
        return 1
    return 0
