"""InstallationWorkspace: additive write facade for KEY/BIF and capsule (ERF/MOD/RIM) targets.

Provides find_* (delegates to Installation), add_resource(destination, resref, restype, data),
and atomic commit() to write modified archives and KEY.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from pykotor.common.misc import ResRef
from pykotor.extract.installation import Installation
from pykotor.resource.formats.bif import read_bif, write_bif
from pykotor.resource.formats.erf import read_erf, write_erf
from pykotor.resource.formats.erf.erf_data import ERF, ERFType
from pykotor.resource.formats.key import read_key, write_key
from pykotor.resource.formats.rim import read_rim, write_rim
from pykotor.resource.formats.rim.rim_data import RIM
from pykotor.resource.type import ResourceType
from pykotor.tools.misc import is_bif_file, is_erf_file, is_mod_file, is_rim_file
from pykotor.tools.path import CaseAwarePath

if TYPE_CHECKING:
    from pathlib import Path

    from pykotor.extract.file import (
        LocationResult,
        ResourceIdentifier,
        ResourceQuery,
        ResourceResult,
    )
    from pykotor.extract.installation import SearchScope
    from pykotor.resource.formats.bif.bif_data import BIF
    from pykotor.resource.formats.key.key_data import KEY


class InstallationWorkspace:
    """High-level facade for reading and adding resources with atomic commit.

    Wraps an Installation for read (find_one, find_many, find_locations, get_decoded)
    and adds a write path: add_resource(destination, resref, restype, data) then commit().
    """

    def __init__(self, path: Path | str):
        self._path: CaseAwarePath = CaseAwarePath(path)
        self._installation: Installation = Installation(self._path)
        key_path = self._path / "chitin.key"
        self._key: KEY = read_key(key_path)
        # BIF path (normalized, e.g. "data/templates.bif") -> loaded BIF
        self._bif_cache: dict[str, BIF] = {}
        # Capsule path -> ERF or RIM
        self._capsule_cache: dict[CaseAwarePath, ERF | RIM] = {}

    @classmethod
    def from_path(cls, path: Path | str) -> InstallationWorkspace:
        """Create a workspace from a game installation root (directory containing chitin.key)."""
        return cls(path)

    @property
    def path(self) -> CaseAwarePath:
        return self._path

    @property
    def installation(self) -> Installation:
        return self._installation

    def find_one(
        self,
        query: ResourceQuery,
        scope: SearchScope | None = None,
        **kwargs: Any,
    ) -> ResourceResult | None:
        return self._installation.find_one(query, scope=scope, **kwargs)

    def find_many(
        self,
        queries: Sequence[ResourceQuery],
        scope: SearchScope | None = None,
        **kwargs: Any,
    ) -> dict[ResourceIdentifier, ResourceResult | None]:
        return self._installation.find_many(queries, scope=scope, **kwargs)

    def find_locations(
        self,
        queries: Sequence[ResourceQuery],
        scope: SearchScope | None = None,
        **kwargs: Any,
    ) -> dict[ResourceIdentifier, list[LocationResult]]:
        return self._installation.find_locations(queries, scope=scope, **kwargs)

    def decode(self, result: ResourceResult, as_type: ResourceType | None = None) -> Any:
        return result.decode(as_type=as_type)

    def get_decoded(
        self,
        resref: str | ResRef,
        restype: ResourceType,
        scope: SearchScope | None = None,
        **kwargs: Any,
    ) -> Any | None:
        return self._installation.get_decoded(resref, restype, scope=scope, **kwargs)

    def add_resource(
        self,
        destination: str | Path,
        resref: str | ResRef,
        restype: ResourceType,
        data: bytes,
    ) -> None:
        """Stage a resource to be written at commit().

        destination: Path to a BIF file (e.g. "data/templates.bif") or to an ERF/MOD/RIM capsule.
        resref: Resource name.
        restype: Resource type.
        data: Raw bytes of the resource.
        """
        dest = CaseAwarePath(destination)
        dest_str = str(dest).replace("\\", "/").lstrip("/")
        resref = ResRef(resref) if isinstance(resref, str) else resref

        if is_bif_file(dest):
            self._add_resource_to_bif(dest_str, resref, restype, data)
        elif is_erf_file(dest) or is_mod_file(dest) or is_rim_file(dest):
            self._add_resource_to_capsule(dest, resref, restype, data)
        else:
            msg = f"Unsupported destination for add_resource: {destination}"
            raise ValueError(msg)

    def _add_resource_to_bif(
        self, bif_path_norm: str, resref: ResRef, restype: ResourceType, data: bytes
    ) -> None:
        key = self._key
        bif_index: int | None = None
        for i, bif_entry in enumerate(key.bif_entries):
            if bif_entry.filename.replace("\\", "/").lower() == bif_path_norm.lower():
                bif_index = i
                break
        if bif_index is None:
            msg = f"BIF path '{bif_path_norm}' is not in chitin.key"
            raise ValueError(msg)

        if bif_path_norm not in self._bif_cache:
            full_path = self._path / bif_path_norm
            self._bif_cache[bif_path_norm] = read_bif(
                full_path, key_source=self._path / "chitin.key"
            )

        bif = self._bif_cache[bif_path_norm]
        res_index = len(bif.resources)
        resource_id = key.calculate_resource_id(bif_index, res_index)
        bif.set_data(resref, restype, data, res_id=resource_id)
        key.add_key_entry(resref, restype, bif_index, res_index)

    def _add_resource_to_capsule(
        self, capsule_path: CaseAwarePath, resref: ResRef, restype: ResourceType, data: bytes
    ) -> None:
        if capsule_path not in self._capsule_cache:
            full = self._path / capsule_path if not capsule_path.is_absolute() else capsule_path
            if not full.is_file():
                # Create new ERF or RIM
                if is_rim_file(capsule_path):
                    self._capsule_cache[capsule_path] = RIM()
                else:
                    erf_type = ERFType.MOD if is_mod_file(capsule_path) else ERFType.ERF
                    self._capsule_cache[capsule_path] = ERF(erf_type=erf_type)
            else:
                with full.open("rb") as f:
                    if is_rim_file(capsule_path):
                        self._capsule_cache[capsule_path] = read_rim(f)
                    else:
                        self._capsule_cache[capsule_path] = read_erf(f)

        archive = self._capsule_cache[capsule_path]
        archive.set_data(resref, restype, data)

    def commit(self) -> None:
        """Write all modified BIFs and the KEY file, then capsule archives, in safe order."""
        path = self._path

        for bif_path_norm, bif in self._bif_cache.items():
            full = path / bif_path_norm
            full.parent.mkdir(parents=True, exist_ok=True)
            write_bif(bif, full)
            bif_index = next(
                i
                for i, e in enumerate(self._key.bif_entries)
                if e.filename.replace("\\", "/").lower() == bif_path_norm.lower()
            )
            self._key.bif_entries[bif_index].filesize = full.stat().st_size

        if self._bif_cache or self._key.is_modified:
            write_key(self._key, path / "chitin.key")

        for capsule_path, archive in self._capsule_cache.items():
            full = path / capsule_path if not capsule_path.is_absolute() else capsule_path
            full.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(archive, RIM):
                write_rim(archive, full)
            else:
                fmt = ResourceType.MOD if is_mod_file(capsule_path) else ResourceType.ERF
                write_erf(archive, full, file_format=fmt)
