"""Utilities for authoring valid KotOR installation layouts.

This module provides a shared write-side backend for synthetic or curated
installations used by tests, CLI workflows, and tooling. The generated output is
structurally valid and readable by ``Installation``.

CLI usage::

    pykotor create-installation /tmp/my_kotor --game k1
    pykotor create-installation /tmp/my_tsl --game k2

Programmatic usage::

    from pathlib import Path
    from pykotor.common.misc import Game
    from pykotor.tools.create_installation import create_installation

    create_installation(
        Path("/tmp/my_kotor"),
        Game.K1,
        bif_resources={"party.bif": {"c_bantha.utc": b"..."}},
        override_resources={"my_script.ncs": b"..."},
    )
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from pykotor.common.misc import Game

log = logging.getLogger(__name__)

_DEFAULT_TLK_TEXT = "ERROR: FATAL COMPILER ERROR"


def _parse_resource_name(resource_name: str, default_type: str) -> tuple[str, str]:
    if "." in resource_name:
        resref, ext = resource_name.rsplit(".", 1)
        return resref, ext.lower()
    return resource_name, default_type.lower()


def _resource_type_from_extension(extension: str, fallback: str) -> object:
    from pykotor.resource.type import ResourceType

    try:
        return ResourceType[extension.upper()]
    except KeyError:
        return ResourceType[fallback.upper()]


def _ensure_valid_tpc_bytes(data: bytes) -> bytes:
    from pykotor.resource.formats.tpc.tpc_auto import bytes_tpc
    from pykotor.resource.formats.tpc.tpc_data import TPC
    from pykotor.resource.type import ResourceType

    if data.startswith((b"TPC V1.0", b"TPC V1.1")):
        return data
    return bytes_tpc(TPC.from_blank(), ResourceType.TPC)


def _normalize_resource_bytes(restype: object, data: bytes) -> bytes:
    from pykotor.resource.type import ResourceType

    if restype == ResourceType.TPC:
        return _ensure_valid_tpc_bytes(data)
    return data


def _write_stream_resources(directory: Path, resources: Mapping[str, bytes] | None) -> None:
    if not resources:
        return
    directory.mkdir(parents=True, exist_ok=True)
    for resource_name, data in resources.items():
        resource_path = directory / resource_name
        resource_path.parent.mkdir(parents=True, exist_ok=True)
        resource_path.write_bytes(data)


def _write_archive_resources(
    archive: object, resources: Mapping[str, bytes], default_type: str
) -> None:
    for resource_name, data in resources.items():
        resref, ext = _parse_resource_name(resource_name, default_type)
        restype = _resource_type_from_extension(ext, default_type)
        archive.set_data(resref, restype, _normalize_resource_bytes(restype, data))


def _write_talk_tables(
    root: Path,
    *,
    dialog_tlk_data: bytes | None,
    dialogf_tlk_data: bytes | None,
    dialog_entries: Sequence[str | tuple[str, str]] | None,
) -> None:
    from pykotor.common.language import Language
    from pykotor.resource.formats.tlk.tlk_auto import write_tlk
    from pykotor.resource.formats.tlk.tlk_data import TLK

    dialog_path = root / "dialog.tlk"
    dialogf_path = root / "dialogf.tlk"

    if dialog_tlk_data is not None:
        dialog_path.write_bytes(dialog_tlk_data)
        dialogf_path.write_bytes(dialog_tlk_data if dialogf_tlk_data is None else dialogf_tlk_data)
        return

    dialog_tlk = TLK(language=Language.ENGLISH)
    dialogf_tlk = TLK(language=Language.ENGLISH)

    entries = list(dialog_entries or ("", "", _DEFAULT_TLK_TEXT))
    for entry in entries:
        if isinstance(entry, tuple):
            text, sound = entry
        else:
            text, sound = entry, ""
        dialog_tlk.add(text, sound)
        dialogf_tlk.add(text, sound)

    write_tlk(dialog_tlk, dialog_path)
    write_tlk(dialogf_tlk, dialogf_path)


def _prepare_root_layout(root: Path, game: Game) -> None:
    from pykotor.common.misc import Game

    is_k2 = game in (Game.K2, Game.K2_XBOX, Game.K2_IOS, Game.K2_ANDROID)

    for subdir in (
        "data",
        "modules",
        "override",
        "streammusic",
        "streamsounds",
        "texturepacks",
        "lips",
    ):
        (root / subdir).mkdir(parents=True, exist_ok=True)

    (root / ("streamvoice" if is_k2 else "streamwaves")).mkdir(parents=True, exist_ok=True)

    if is_k2:
        (root / "swkotor2.exe").touch()
        (root / "swkotor2.ini").touch()
        (root / "LocalVault").mkdir(exist_ok=True)
        (root / "LocalVault" / "test.bic").touch()
        (root / "LocalVault" / "testold.bic").touch()
    else:
        (root / "swkotor.exe").touch()
        (root / "swkotor.ini").touch()
        (root / "rims").mkdir(exist_ok=True)
        (root / "utils").mkdir(exist_ok=True)

    (root / "miles").mkdir(exist_ok=True)


def create_installation(
    path: Path,
    game: Game,
    *,
    with_override: bool = True,
    bif_resources: Mapping[str, Mapping[str, bytes]] | None = None,
    override_resources: Mapping[str, bytes] | None = None,
    modules_resources: Mapping[str, Mapping[str, bytes]] | None = None,
    voice_resources: Mapping[str, bytes] | None = None,
    music_resources: Mapping[str, bytes] | None = None,
    sound_resources: Mapping[str, bytes] | None = None,
    lips_resources: Mapping[str, Mapping[str, bytes]] | None = None,
    texture_tpa_resources: Mapping[str, bytes] | None = None,
    texture_tpb_resources: Mapping[str, bytes] | None = None,
    texture_tpc_resources: Mapping[str, bytes] | None = None,
    texture_gui_resources: Mapping[str, bytes] | None = None,
    patch_erf_resources: Mapping[str, bytes] | None = None,
    dialog_tlk_data: bytes | None = None,
    dialogf_tlk_data: bytes | None = None,
    dialog_entries: Sequence[str | tuple[str, str]] | None = None,
) -> Path:
    """Create a valid KotOR installation with real archives and TLK data."""
    from pykotor.common.misc import Game, ResRef
    from pykotor.resource.formats.bif.bif_auto import write_bif
    from pykotor.resource.formats.bif.bif_data import BIF
    from pykotor.resource.formats.erf.erf_auto import write_erf
    from pykotor.resource.formats.erf.erf_data import ERF, ERFType
    from pykotor.resource.formats.key.key_auto import write_key
    from pykotor.resource.formats.key.key_data import KEY
    from pykotor.resource.formats.rim.rim_auto import write_rim
    from pykotor.resource.formats.rim.rim_data import RIM
    from pykotor.resource.type import ResourceType

    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    _prepare_root_layout(root, game)

    if not with_override:
        override_dir = root / "override"
        if override_dir.exists():
            for child in override_dir.iterdir():
                if child.is_file():
                    child.unlink()

    key = KEY()
    bif_resources = dict(bif_resources or {})
    is_k2 = game in (Game.K2, Game.K2_XBOX, Game.K2_IOS, Game.K2_ANDROID)

    if is_k2:
        bif_resources.setdefault("Dialogs.bif", {})
    else:
        bif_resources.setdefault("party.bif", {})
        bif_resources.setdefault("player.bif", {})

    for bif_filename, resources in bif_resources.items():
        bif_entry = key.add_bif(f"data/{bif_filename}")
        bif_index = len(key.bif_entries) - 1
        bif = BIF()

        for res_index, (resource_name, raw_data) in enumerate(resources.items()):
            resref, ext = _parse_resource_name(resource_name, "utc")
            restype = _resource_type_from_extension(ext, "utc")
            resource_id = key.calculate_resource_id(bif_index, res_index)
            bif.set_data(
                ResRef(resref),
                restype,
                _normalize_resource_bytes(restype, raw_data),
                res_id=resource_id,
            )
            key.add_key_entry(ResRef(resref), restype, bif_index, res_index)

        bif_path = root / "data" / bif_filename
        write_bif(bif, bif_path)
        bif_entry.filesize = bif_path.stat().st_size

    write_key(key, root / "chitin.key")

    if with_override:
        _write_stream_resources(root / "override", override_resources)

    modules_dir = root / "modules"
    modules_resources = dict(modules_resources or {})
    if not is_k2:
        modules_resources.setdefault("global.mod", {})

    for module_filename, resources in modules_resources.items():
        module_path = modules_dir / module_filename
        lower_name = module_filename.lower()
        if lower_name.endswith(".rim"):
            archive = RIM()
            _write_archive_resources(archive, resources, "are")
            write_rim(archive, module_path)
        else:
            archive = ERF(erf_type=ERFType.MOD if lower_name.endswith(".mod") else ERFType.ERF)
            _write_archive_resources(archive, resources, "are")
            write_erf(
                archive,
                module_path,
                file_format=ResourceType.MOD if lower_name.endswith(".mod") else ResourceType.ERF,
            )

    for mod_filename, resources in (lips_resources or {}).items():
        final_name = (
            mod_filename if mod_filename.lower().endswith(".mod") else f"{mod_filename}.mod"
        )
        archive = ERF(erf_type=ERFType.MOD)
        _write_archive_resources(archive, resources, "lip")
        write_erf(archive, root / "lips" / final_name, file_format=ResourceType.MOD)

    for filename, resources in (
        ("swpc_tex_tpa.erf", texture_tpa_resources),
        ("swpc_tex_tpb.erf", texture_tpb_resources),
        ("swpc_tex_tpc.erf", texture_tpc_resources),
        ("swpc_tex_gui.erf", texture_gui_resources),
    ):
        if not resources:
            continue
        archive = ERF()
        _write_archive_resources(archive, resources, "tpc")
        write_erf(archive, root / "texturepacks" / filename)

    if patch_erf_resources:
        archive = ERF(erf_type=ERFType.ERF)
        _write_archive_resources(archive, patch_erf_resources, "utc")
        write_erf(archive, root / "patch.erf", file_format=ResourceType.ERF)

    _write_stream_resources(root / ("streamvoice" if is_k2 else "streamwaves"), voice_resources)
    _write_stream_resources(root / "streammusic", music_resources)
    _write_stream_resources(root / "streamsounds", sound_resources)

    _write_talk_tables(
        root,
        dialog_tlk_data=dialog_tlk_data,
        dialogf_tlk_data=dialogf_tlk_data,
        dialog_entries=dialog_entries,
    )

    log.info("Created %s installation at: %s", "K2/TSL" if is_k2 else "K1", root)
    return root


def create_minimal_installation(
    path: Path,
    game: Game,
    *,
    validate_existing: bool = False,
) -> Path:
    """Scaffold a minimal but readable KotOR installation.

    If ``chitin.key`` already exists and ``validate_existing`` is False (default),
    returns immediately without creating or modifying other files. Use this when
    you only need a valid KEY and want to avoid overwriting an existing layout.

    When ``validate_existing=True`` (e.g. for tests or CI), a partial root is
    completed: directory layout and missing required files (e.g. dialog.tlk,
    dialogf.tlk) are created even if ``chitin.key`` is already present. Existing
    chitin.key and BIFs are not overwritten. Use this to ensure a minimal
    installation is fully usable when the root may have been partially created.
    """
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    if (root / "chitin.key").exists() and not validate_existing:
        return root
    if (root / "chitin.key").exists() and validate_existing:
        _prepare_root_layout(root, game)
        if not (root / "dialog.tlk").is_file():
            _write_talk_tables(
                root,
                dialog_tlk_data=None,
                dialogf_tlk_data=None,
                dialog_entries=("", "", _DEFAULT_TLK_TEXT),
            )
        return root
    return create_installation(root, game)
