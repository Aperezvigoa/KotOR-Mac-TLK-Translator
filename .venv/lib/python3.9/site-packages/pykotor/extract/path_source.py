"""Shared resource-source resolution for CLI commands and diff workflows."""

from __future__ import annotations

import fnmatch

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from pykotor.common.misc import Game
from pykotor.common.module import KModuleType, Module
from pykotor.extract.capsule import Capsule
from pykotor.extract.file import FileResource, LocationResult, ResourceIdentifier, ResourceResult
from pykotor.extract.installation import Installation, SearchLocation
from pykotor.resource.type import ResourceType
from pykotor.tools.misc import is_capsule_file
from pykotor.tools.path import get_kotor_paths_from_default

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Iterable, Sequence

    from loggerplus import RobustLogger as Logger


def parse_game_arg(game_str: str | None) -> Game | None:
    if not game_str or not game_str.strip():
        return None

    normalized = game_str.strip().lower()
    if normalized in {"k1", "kotor", "kotor1"}:
        return Game.K1
    if normalized in {"k2", "tsl", "kotor2"}:
        return Game.K2
    return None


def resolve_source_path_from_args(
    args: Namespace,
    logger: Logger,
    *,
    attribute_names: Sequence[str] = ("path",),
) -> Path | None:
    for attribute_name in attribute_names:
        explicit_path = getattr(args, attribute_name, None)
        if explicit_path:
            return Path(str(explicit_path))

    game = parse_game_arg(getattr(args, "game", None))
    if game is None:
        logger.error("No source path. Use --path or --game to auto-detect a default game root.")
        return None

    discovered_paths = get_kotor_paths_from_default().get(game, [])
    if not discovered_paths:
        logger.error("No default %s game roots were found.", game.name)
        return None

    path_index = getattr(args, "path_index", 0)
    if path_index < 0 or path_index >= len(discovered_paths):
        logger.error(
            "Default source index %s is out of range for %s. Found %s path(s).",
            path_index,
            game.name,
            len(discovered_paths),
        )
        return None

    chosen_path = Path(discovered_paths[path_index])
    if len(discovered_paths) > 1:
        logger.info("Using auto-detected %s game root [%s]: %s", game.name, path_index, chosen_path)
    else:
        logger.info("Using auto-detected %s game root: %s", game.name, chosen_path)
    return chosen_path


def detect_source_path_type(path: Path) -> str:
    if not path.exists():
        if is_capsule_file(path):
            return "capsule"
        return "file"

    if path.is_dir():
        if (path / "chitin.key").is_file():
            return "game_root"
        return "folder"

    if path.is_file() and is_capsule_file(path):
        return "module" if _module_piece_candidates(path) else "capsule"

    return "file"


@dataclass(frozen=True)
class ResolvedResourceSource:
    path: Path
    kind: str
    game: Game | None = None
    installation: Installation | None = None
    folders: tuple[Path, ...] = field(default_factory=tuple)
    capsules: tuple[Capsule, ...] = field(default_factory=tuple)

    def iter_identifiers(self) -> list[ResourceIdentifier]:
        seen: set[ResourceIdentifier] = set()
        identifiers: list[ResourceIdentifier] = []

        if self.installation is not None:
            for resource in self.installation.iter_all_resources():
                identifier = resource.identifier()
                if identifier in seen:
                    continue
                seen.add(identifier)
                identifiers.append(identifier)
            return identifiers

        for folder in self.folders:
            for file_path in folder.rglob("*"):
                if not file_path.is_file():
                    continue
                identifier = ResourceIdentifier.from_path(file_path)
                if identifier.restype.is_invalid or identifier in seen:
                    continue
                seen.add(identifier)
                identifiers.append(identifier)

        for capsule in self.capsules:
            for resource in capsule.resources():
                identifier = resource.identifier()
                if identifier in seen:
                    continue
                seen.add(identifier)
                identifiers.append(identifier)

        if self.kind == "file" and self.path.is_file():
            identifier = ResourceIdentifier.from_path(self.path)
            if not identifier.restype.is_invalid and identifier not in seen:
                identifiers.append(identifier)

        return identifiers

    def matching_identifiers(
        self,
        *,
        glob_pattern: str | None = None,
        restype: ResourceType | None = None,
    ) -> list[ResourceIdentifier]:
        identifiers = self.iter_identifiers()
        matched: list[ResourceIdentifier] = []
        seen: set[ResourceIdentifier] = set()
        for identifier in identifiers:
            if (
                restype is not None
                and restype != ResourceType.INVALID
                and identifier.restype != restype
            ):
                continue
            if (
                glob_pattern
                and not fnmatch.fnmatch(str(identifier).lower(), glob_pattern.lower())
                and not fnmatch.fnmatch(identifier.resname.lower(), glob_pattern.lower())
            ):
                continue
            if identifier in seen:
                continue
            seen.add(identifier)
            matched.append(identifier)
        return matched

    def resource(
        self,
        resname: str,
        restype: ResourceType,
        *,
        order: Sequence[SearchLocation] | None = None,
    ) -> ResourceResult | None:
        if self.installation is not None:
            return self.installation.resource(resname, restype, order=order)

        identifier = ResourceIdentifier(resname, restype)
        return self.resources([identifier], order=order).get(identifier)

    def resources(
        self,
        queries: Iterable[ResourceIdentifier],
        *,
        order: Sequence[SearchLocation] | None = None,
    ) -> dict[ResourceIdentifier, ResourceResult | None]:
        locations = self.locations(list(queries), order=order)
        results: dict[ResourceIdentifier, ResourceResult | None] = {}
        for query, query_locations in locations.items():
            if not query_locations:
                results[query] = None
                continue
            location = query_locations[0]
            file_resource = location.as_file_resource()
            data = (
                file_resource.data()
                if (file_resource.inside_capsule or file_resource.inside_bif)
                else Path(file_resource.filepath()).read_bytes()
            )
            result = ResourceResult(
                query.resname, query.restype, Path(file_resource.filepath()), data
            )
            result.set_file_resource(file_resource)
            results[query] = result
        return results

    def locations(
        self,
        queries: list[ResourceIdentifier],
        *,
        order: Sequence[SearchLocation] | None = None,
    ) -> dict[ResourceIdentifier, list[LocationResult]]:
        if self.installation is not None:
            order_list = list(order) if order is not None else None
            return self.installation.locations(queries, order=order_list)

        results: dict[ResourceIdentifier, list[LocationResult]] = {query: [] for query in queries}
        query_map = {query: query for query in queries}

        if self.kind == "file":
            file_identifier = ResourceIdentifier.from_path(self.path)
            if file_identifier in query_map and self.path.is_file():
                file_resource = FileResource(
                    file_identifier.resname,
                    file_identifier.restype,
                    self.path.stat().st_size,
                    0,
                    self.path,
                )
                location = LocationResult(self.path, 0, self.path.stat().st_size)
                location.set_file_resource(file_resource)
                results[file_identifier].append(location)
            return results

        for folder in self.folders:
            for file_path in folder.rglob("*"):
                if not file_path.is_file():
                    continue
                identifier = ResourceIdentifier.from_path(file_path)
                query = query_map.get(identifier)
                if query is None:
                    continue
                file_resource = FileResource(
                    identifier.resname,
                    identifier.restype,
                    file_path.stat().st_size,
                    0,
                    file_path,
                )
                location = LocationResult(file_path, 0, file_path.stat().st_size)
                location.set_file_resource(file_resource)
                results[query].append(location)

        for capsule in self.capsules:
            for resource in capsule.resources():
                query = query_map.get(resource.identifier())
                if query is None:
                    continue
                location = LocationResult(
                    Path(resource.filepath()), resource.offset(), resource.size()
                )
                location.set_file_resource(resource)
                results[query].append(location)

        return results


def resolve_resource_source(pathlike: str | Path) -> ResolvedResourceSource:
    path = Path(pathlike)
    source_type = detect_source_path_type(path)
    game_root = _find_game_root(path)
    game: Game | None = None
    installation: Installation | None = None
    if source_type == "game_root":
        installation = Installation(path)
        game = installation.game()
    elif game_root is not None:
        installation = Installation(game_root)
        game = installation.game()

    if source_type == "game_root":
        return ResolvedResourceSource(
            path=path, kind=source_type, game=game, installation=installation
        )
    if source_type == "folder":
        return ResolvedResourceSource(path=path, kind=source_type, game=game, folders=(path,))
    if source_type == "capsule":
        return ResolvedResourceSource(
            path=path, kind=source_type, game=game, capsules=(Capsule(path),)
        )
    if source_type == "module":
        return ResolvedResourceSource(
            path=path,
            kind=source_type,
            game=game,
            capsules=tuple(Capsule(candidate) for candidate in _module_piece_candidates(path)),
        )
    return ResolvedResourceSource(path=path, kind=source_type, game=game)


def _find_game_root(path: Path) -> Path | None:
    current = path if path.is_dir() else path.parent
    for candidate in (current, *current.parents):
        if (candidate / "chitin.key").is_file():
            return candidate
    return None


def _module_piece_candidates(path: Path) -> list[Path]:
    if not is_capsule_file(path):
        return []
    filename = path.name.lower()
    composite_suffixes = (
        KModuleType.MOD.value,
        KModuleType.DATA.value,
        KModuleType.AREA.value,
        KModuleType.AREA_EXTENDED.value,
        KModuleType.K2_DLG.value,
    )
    if not filename.endswith(composite_suffixes):
        root = Module.name_to_root(path.name)
        sibling_suffixes = (
            KModuleType.DATA.value,
            KModuleType.AREA.value,
            KModuleType.AREA_EXTENDED.value,
            KModuleType.K2_DLG.value,
            KModuleType.MOD.value,
        )
        if not any((path.parent / f"{root}{suffix}").is_file() for suffix in sibling_suffixes):
            return []
    try:
        root = Module.name_to_root(path.name)
    except Exception:
        return []

    candidates = [path.parent / f"{root}{modtype.value}" for modtype in _module_search_order()]
    existing = [
        candidate for candidate in candidates if candidate.is_file() and is_capsule_file(candidate)
    ]
    if path in existing:
        return existing
    return []


def _module_search_order() -> tuple[KModuleType, ...]:
    return (
        KModuleType.MOD,
        KModuleType.K2_DLG,
        KModuleType.DATA,
        KModuleType.AREA,
        KModuleType.AREA_EXTENDED,
        KModuleType.MAIN,
    )
