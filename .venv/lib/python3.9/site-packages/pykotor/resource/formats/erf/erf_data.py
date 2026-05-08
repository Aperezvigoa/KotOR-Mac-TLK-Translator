"""This module handles classes relating to editing ERF files.

ERF (Encapsulated Resource File) files are self-contained archives used for modules, save games,
texture packs, and hak paks. Unlike BIF files which require a KEY file for filename lookups,
ERF files store both resource names (ResRefs) and data in the same file. They also support
localized strings for descriptions in multiple languages.

Observed retail behavior:
----------
        KotOR I and TSL load modules, saves, and texture packs from self-contained ERF-family
        capsules (``ERF ``, ``MOD ``, ``SAV ``, ``HAK `` headers) without a separate KEY row per
        resource.

        ERF file format specification
        Binary Format:
        -------------
        Header (160 bytes):
        Offset | Size | Type   | Description
        -------|------|--------|-------------
        0x00   | 4    | char[] | File Type ("ERF ", "MOD ", "SAV ")
        0x04   | 4    | char[] | File Version ("V1.0")
        0x08   | 4    | uint32 | Language Count
        0x0C   | 4    | uint32 | Localized String Size (total bytes)
        0x10   | 4    | uint32 | Entry Count (number of resources)
        0x14   | 4    | uint32 | Offset to Localized String List
        0x18   | 4    | uint32 | Offset to Key List
        0x1C   | 4    | uint32 | Offset to Resource List
        0x20   | 4    | uint32 | Build Year (years since 1900)
        0x24   | 4    | uint32 | Build Day (days since Jan 1)
        0x28   | 4    | uint32 | Description StrRef (TLK reference)
        0x2C   | 116  | byte[] | Reserved (padding, usually zeros)
        Localized String Entry (variable length per language):
        - 4 bytes: Language ID (see Language enum)
        - 4 bytes: String Size (length in bytes)
        - N bytes: String Data (windows-1252 encoded text)
        Key Entry (24 bytes each):
        Offset | Size | Type   | Description
        -------|------|--------|-------------
        0x00   | 16   | char[] | ResRef (filename, null-padded, max 16 chars)
        0x10   | 4    | uint32 | Resource ID (index into resource list)
        0x14   | 2    | uint16 | Resource Type
        0x16   | 2    | uint16 | Unused (padding)
        Resource Entry (8 bytes each):
        Offset | Size | Type   | Description
        -------|------|--------|-------------
        0x00   | 4    | uint32 | Offset to Resource Data
        0x04   | 4    | uint32 | Resource Size
        Resource Data:
        Raw binary data for each resource at specified offsets
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pykotor.common.misc import ResRef
from pykotor.resource.bioware_archive import ArchiveResource, BiowareArchive
from pykotor.resource.type import ResourceType
from pykotor.tools.misc import is_erf_file, is_mod_file, is_sav_file

if TYPE_CHECKING:
    import os

    from pykotor.common.misc import ResRef


class ERFResource(ArchiveResource):
    """A single resource stored in an ERF/MOD/SAV file.

    Unlike BIF resources, ERF resources include their ResRef (filename) directly in the
    archive. Each resource is identified by a unique ResRef and ResourceType combination.

    See Also:
    ----------


    Attributes:
    ----------
        All attributes inherited from ArchiveResource (resref, restype, data, size)
        ERF resources have no additional attributes beyond the base ArchiveResource
    """

    def __init__(self, resref: ResRef, restype: ResourceType, data: bytes):
        # ResRef stored in Key Entry (16 bytes, null-padded)
        # ResourceType stored in Key Entry (2 bytes, uint16)
        # Resource data referenced via Resource Entry (offset + size)
        super().__init__(resref=resref, restype=restype, data=data)


class ERFType(Enum):
    """The type of ERF file based on file header signature.

    ERF files can have different type signatures depending on their purpose:
    - ERF: Generic encapsulated resource file (texture packs, etc.)
    - MOD: Module file (game areas/levels)
    - SAV: Save game file
    - HAK: Hak pak file (custom content, unused in KotOR)

    See Also:
    ----------

    """

    ERF = "ERF "  # Generic ERF archive (texture packs, etc.)
    MOD = "MOD "  # Module file (game levels/areas)
    SAV = "SAV "  # Save game (same binary layout as ERF/MOD)

    @classmethod
    def from_extension(cls, ext_or_filepath: os.PathLike | str) -> ERFType:
        if is_erf_file(ext_or_filepath):
            return cls.ERF
        if is_mod_file(ext_or_filepath):
            return cls.MOD
        if is_sav_file(
            ext_or_filepath
        ):  # .SAV files still use the 'MOD ' signature in its first 4 bytes of the file header
            return cls.MOD
        msg = f"Invalid ERF extension in filepath '{ext_or_filepath}'."
        raise ValueError(msg)


class ERF(BiowareArchive):
    """Represents an ERF/MOD/SAV file.

    ERF (Encapsulated Resource File) is a self-contained archive format used for game modules,
    save games, and resource packs. Unlike BIF+KEY pairs, ERF files contain both resource names
    and data in a single file, making them ideal for distributable content like mods.

    See Also:
    ----------


    Attributes:
    ----------
        erf_type: File type signature (ERF, MOD, SAV, HAK)
            Determines intended use of the archive
            ERF = texture packs, MOD = game modules, SAV = save games

        is_save: Flag indicating if this is a save game ERF
            Save games use MOD signature but have different structure
            Affects how certain fields are interpreted (e.g., build date)
            PyKotor-specific flag for save game handling

        build_year: Years since 1900 (e.g., 103 = 2003)

        build_day: Day of the year (1-366)

        description_strref: TLK String Reference for module description
            Reference: ERF File Format Specification (Offset 0x28)
            Note: Kotor.NET stops reading at 0x24 (BuildDay), skipping this field.
            Defaults: -1 for MOD/NWM, 0 for SAV

        localized_strings: Dictionary providing descriptions in multiple languages (LanguageID -> String)
            Reference: ERF File Format Specification (Offsets 0x08, 0x0C, 0x14)
            Note: some third-party readers stop before these fields; PyKotor keeps them for MOD metadata.
            Used primarily in MOD files for module names/loading screens
    """

    BINARY_TYPE = ResourceType.ERF
    ARCHIVE_TYPE: type[ArchiveResource] = ERFResource
    COMPARABLE_FIELDS = (
        "erf_type",
        "is_save_erf",
        "build_year",
        "build_day",
        "description_strref",
        "localized_strings",
    )
    COMPARABLE_SET_FIELDS = ("_resources",)

    def __init__(
        self,
        erf_type: ERFType = ERFType.ERF,
        *,
        is_save: bool = False,
        build_year: int = 0,
        build_day: int = 0,
        description_strref: int = -1,
        localized_strings: dict[int, str] | None = None,
    ):
        super().__init__()

        # File type signature (ERF, MOD, SAV, HAK)
        self.erf_type: ERFType = erf_type

        # PyKotor-specific flag for save game handling
        # Save games use MOD signature but have different behavior
        self.is_save: bool = is_save

        self.build_year: int = build_year
        self.build_day: int = build_day
        self.description_strref: int = description_strref
        self.localized_strings: dict[int, str] = (
            localized_strings if localized_strings is not None else {}
        )

    @property
    def is_save_erf(self) -> bool:
        """Alias for ComparableMixin compatibility."""
        return self.is_save

    @is_save_erf.setter
    def is_save_erf(self, value: bool) -> None:
        self.is_save = value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.erf_type!r}, is_save={self.is_save}, desc_strref={self.description_strref})"

    def __eq__(self, other: object):
        from pykotor.resource.formats.rim import RIM  # Prevent circular imports  # noqa: PLC0415

        if not isinstance(other, (ERF, RIM)):
            return NotImplemented  # type: ignore[no-any-return]
        return set(self._resources) == set(other._resources)

    def __hash__(self) -> int:
        return hash((self.erf_type, tuple(self._resources), self.is_save, self.description_strref))

    def get_resource_offset(self, resource: ArchiveResource) -> int:
        """Return the byte offset of a resource's data in serialized archive order."""
        from pykotor.resource.formats.erf.io_erf import ERFBinaryWriter

        entry_count = len(self._resources)
        data_start = (
            ERFBinaryWriter.FILE_HEADER_SIZE + ERFBinaryWriter.KEY_ELEMENT_SIZE * entry_count
        )

        offset = data_start
        for res in self._resources:
            if res == resource:
                return offset
            offset += len(res.data)
        raise ValueError("Resource is not present in ERF resource list")
