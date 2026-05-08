"""Headless TPC/TGA batch conversion and editor load helpers.

Used by HolocronToolset, pykotorcli-style tools, and KotorBlender. Converts ``.tpc``
↔ ``.tga`` via :func:`read_tpc` / :func:`write_tpc` with Holocron-aligned TXI sidecar
behavior and small-TGA detection fallback.
"""

from __future__ import annotations

import os

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Union

from pykotor.common.stream import BinaryReader
from pykotor.resource.formats.tpc import TPC, read_tpc, write_tpc
from pykotor.resource.formats.tpc.io_tga import TPCTGAReader
from pykotor.resource.type import ResourceType
from pykotor.tools.path import CaseAwarePath

PathLike = Union[str, os.PathLike[str]]


@dataclass
class TextureBatchOutcome:
    """Tallies for :func:`batch_convert_textures`."""

    success_count: int = 0
    skipped_count: int = 0
    errors: List[str] = field(default_factory=list)


def _load_tga_for_convert(path: Path) -> TPC:
    """Load a ``.tga`` like :func:`read_tpc`, including optional ``.txi`` sidecar.

    Falls back to :class:`TPCTGAReader` when ``detect_tpc`` misclassifies small TGAs.
    """
    try:
        return read_tpc(path)
    except ValueError:
        loaded = TPCTGAReader(path).load()
    txi_path = CaseAwarePath(path).with_suffix(".txi")
    if txi_path.is_file():
        with BinaryReader.from_auto(txi_path) as f:
            loaded.txi = f.read_all().decode(encoding="ascii", errors="ignore")
    return loaded


def read_tpc_for_editor(
    filepath: PathLike,
    data: bytes | bytearray,
) -> TPC:
    """Load TPC/TGA from in-memory bytes with optional ``.txi`` beside ``filepath``.

    Matches Holocron ``TPCEditor.load`` for TPC/TGA: sidecar is
    ``Path(filepath).with_suffix('.txi')`` when present. Uses the same
    small-TGA fallback as :func:`_load_tga_for_convert` when auto-detect
    misreads raw bytes.
    """
    path = Path(os.fspath(filepath)).resolve()
    txi_path = path.with_suffix(".txi")
    txi_src = txi_path if txi_path.is_file() else None
    try:
        return read_tpc(data, txi_source=txi_src)
    except ValueError:
        raw = bytes(data)
        loaded = TPCTGAReader(raw, 0, len(raw)).load()
        if txi_path.is_file():
            with BinaryReader.from_auto(txi_path) as f:
                loaded.txi = f.read_all().decode(encoding="ascii", errors="ignore")
        return loaded


def _write_txi_sidecar_for_tga(image_path: Path, texture: TPC) -> None:
    """Write ``.txi`` next to ``.tga`` when the TPC carries TXI text (Holocron sidecar pattern)."""
    payload = str(texture.txi).strip()
    if not payload:
        return
    if not payload.endswith("\n"):
        payload += "\n"
    image_path.with_suffix(".txi").write_text(payload, encoding="ascii", errors="ignore")


def convert_single_texture(
    src: PathLike,
    *,
    overwrite: bool = False,
    write_txi_sidecar_for_tga: bool = True,
) -> Path:
    """Convert one ``.tpc`` to ``.tga`` or one ``.tga`` to ``.tpc``.

    Returns:
        Path to the written file.

    Raises:
        FileNotFoundError: If ``src`` is missing.
        FileExistsError: If the destination exists and ``overwrite`` is False.
        ValueError: If the suffix is not ``.tpc`` or ``.tga``.

    """
    path = Path(os.fspath(src)).resolve()
    if not path.is_file():
        raise FileNotFoundError(os.fspath(path))
    suf = path.suffix.lower()
    if suf == ".tpc":
        dst = path.with_suffix(".tga")
        out_fmt = ResourceType.TGA
    elif suf == ".tga":
        dst = path.with_suffix(".tpc")
        out_fmt = ResourceType.TPC
    else:
        msg = f"Not a TPC or TGA file: {path}"
        raise ValueError(msg)
    if not overwrite and dst.exists():
        raise FileExistsError(os.fspath(dst))
    if suf == ".tpc":
        tpc = read_tpc(path)
    else:
        tpc = _load_tga_for_convert(path)
    write_tpc(tpc, dst, file_format=out_fmt)
    if out_fmt == ResourceType.TGA and write_txi_sidecar_for_tga:
        _write_txi_sidecar_for_tga(dst, tpc)
    return dst


def iter_texture_paths(root: PathLike, *, recursive: bool) -> List[Path]:
    """List ``.tpc`` / ``.tga`` files under ``root`` (file or directory)."""
    p = Path(os.fspath(root)).resolve()
    if p.is_file():
        return [p] if p.suffix.lower() in (".tpc", ".tga") else []
    if not p.is_dir():
        return []
    out: List[Path] = []
    if recursive:
        for child in p.rglob("*"):
            if child.is_file() and child.suffix.lower() in (".tpc", ".tga"):
                out.append(child)
    else:
        for child in p.iterdir():
            if child.is_file() and child.suffix.lower() in (".tpc", ".tga"):
                out.append(child)
    return sorted(out)


def batch_convert_textures(
    path: PathLike,
    *,
    recursive: bool = True,
    overwrite: bool = False,
    write_txi_sidecar_for_tga: bool = True,
) -> TextureBatchOutcome:
    """Batch-convert every ``.tpc`` / ``.tga`` under a directory (or a single file).

    Skips outputs that already exist when ``overwrite`` is False.
    Collects per-file error strings and continues.
    """
    outcome = TextureBatchOutcome()
    targets = iter_texture_paths(path, recursive=recursive)
    for src in targets:
        dst_suffix = ".tga" if src.suffix.lower() == ".tpc" else ".tpc"
        dst = src.with_suffix(dst_suffix)
        if not overwrite and dst.exists():
            outcome.skipped_count += 1
            continue
        try:
            convert_single_texture(
                src,
                overwrite=overwrite,
                write_txi_sidecar_for_tga=write_txi_sidecar_for_tga,
            )
            outcome.success_count += 1
        except OSError as exc:
            outcome.errors.append(f"{src}: {exc}")
        except ValueError as exc:
            outcome.errors.append(f"{src}: {exc}")
    return outcome
