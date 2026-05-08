"""Resource type definitions for BioWare game engines.

This module contains comprehensive resource type definitions for all known BioWare game engines,
including Infinity, Aurora, Odyssey, and Eclipse engines. Resource types are identified by
numeric IDs and file extensions, with engine support tracking via the BiowareEngine enum.

The ResourceType enum aggregates types used across BioWare engine families. Numeric IDs and
extensions for Odyssey (KotOR I / TSL) match observed retail resolution behavior and the
published resource-type tables; see project wiki cross-links below.

Each resource type includes:
- type_id: Numeric identifier used by game engines
- extension: File extension (lowercase, no leading dot)
- category: Descriptive category (e.g., "Models", "Textures", "Scripts")
- contents: Data format ("binary", "plaintext", "gff", "erf", "lips", "video", "xml")
- supported_engines: Tuple of BiowareEngine values indicating which engines support this type

References:
----------
    wiki/Resource-Formats-and-Resolution.md (hex resource type ID table)
    wiki/Bioware-Aurora-KeyBIF.md (Aurora engine resource type documentation)
"""

from __future__ import annotations

import io
import mmap
import os
import struct
import uuid

from enum import Enum
from functools import lru_cache
from io import BytesIO
from typing import TYPE_CHECKING, NamedTuple, TypeVar, Union, cast
from xml.etree.ElementTree import ParseError

from pykotor.common.stream import BinaryReader, BinaryWriter
from pykotor.resource.formats._base import BiowareResource, ComparableMixin  # type: ignore[import-untyped]
from utility.common.misc_string.mutable_str import WrappedStr

if TYPE_CHECKING:
    from collections.abc import Callable

    from typing_extensions import Literal, Self  # pyright: ignore[reportMissingModuleSource]


class BiowareEngine(Enum):
    """BioWare game engine identifiers.

    Represents the different BioWare game engines that use resource type systems.
    Used to track which engines support which resource types.

    Members:
    --------
        Infinity: Engine for Baldur's Gate, Baldur's Gate II, Icewind Dale, Planescape: Torment
        Aurora: Engine for Neverwinter Nights, Neverwinter Nights 2, Neverwinter Nights: Enhanced Edition
        Odyssey: Engine for Knights of the Old Republic and Knights of the Old Republic II: The Sith Lords
        Eclipse: Engine for Dragon Age: Origins and Dragon Age II

    References:
    -----------
        Observed KotOR I / TSL resource pipelines (Odyssey) and broader BioWare engine lineage.
    """

    Infinity = "infinity"  # Baldur's Gate, Icewind Dale, Planescape: Torment
    Aurora = "aurora"  # Neverwinter Nights series
    Odyssey = "odyssey"  # KotOR I & II
    Eclipse = "eclipse"  # Dragon Age: Origins, Dragon Age II


STREAM_TYPES = Union[io.BufferedIOBase, io.RawIOBase, mmap.mmap]
BASE_SOURCE_TYPES = Union[os.PathLike, str, bytes, bytearray, memoryview]
SOURCE_TYPES = Union[BASE_SOURCE_TYPES, STREAM_TYPES, BytesIO, io.StringIO, BinaryReader]
TARGET_TYPES = Union[os.PathLike, str, bytearray, BytesIO, io.StringIO, BinaryWriter]


R = TypeVar("R")


def autoclose(func: Callable[..., R]) -> Callable[..., R]:
    def _autoclose(self: ResourceReader | ResourceWriter, auto_close: bool = True) -> R:  # noqa: FBT002, FBT001
        try:
            resource: R = func(self, auto_close=auto_close)
        except (OSError, ParseError, ValueError, IndexError, StopIteration, struct.error) as e:
            msg = "Tried to save or load an unsupported or corrupted file."
            raise ValueError(msg) from e
        finally:
            if auto_close:
                self.close()
        return resource

    return _autoclose


class ResourceReader(ComparableMixin):
    def __init__(
        self,
        source: SOURCE_TYPES,
        offset: int = 0,
        size: int | None = None,
        *,
        use_binary_reader: bool = True,
    ):
        if use_binary_reader:
            self._reader: BinaryReader = BinaryReader.from_auto(source, offset)
            self._size: int = size or self._reader.remaining()
        else:
            if isinstance(source, memoryview):
                loaded_src: bytearray = bytearray(source)
            elif isinstance(source, (bytes, bytearray)):
                loaded_src = source if isinstance(source, bytearray) else bytearray(source)
            elif isinstance(source, (os.PathLike, str)):
                with open(  # noqa: PTH123
                    os.path.normpath(source) if isinstance(source, str) else os.fspath(source),
                    "rb",
                ) as f:
                    loaded_src = bytearray(f.read())
            elif isinstance(source, io.BufferedIOBase):
                loaded_src = bytearray(source.read())
            elif isinstance(source, mmap.mmap):
                loaded_src = bytearray(source)
            else:
                assert isinstance(source, BinaryReader)
                loaded_src = bytearray(source.read_all())

            self._offset: int = offset
            self._size = len(loaded_src)
            self._source: bytearray = loaded_src[offset : self._size]

    def close(self):
        self._reader.close()


class ResourceWriter(ComparableMixin):
    def __init__(
        self,
        target: TARGET_TYPES,
    ):
        self._writer: BinaryWriter = BinaryWriter.to_auto(target)  # type: ignore[assignment]

    def close(self):
        self._writer.close()


class ResourceTuple(NamedTuple):
    """Tuple representing a resource type definition.

    Attributes:
    -----------
        type_id: Integer ID of the resource type as recognized by the game engines.
        extension: File extension associated with the resource type (lowercase, no leading dot).
        category: Short description of what kind of data the resource type stores.
        contents: How the resource type stores data: "binary", "plaintext", "gff", "erf", "lips", "video", or "xml".
        is_invalid: Whether this resource type is invalid/undefined.
        target_member: For toolset-only types, the name of the target ResourceType member this maps to.
        supported_engines: Set of BiowareEngine values indicating which engines support this resource type.
            Defaults to empty set if not specified (unknown support).

    References:
    -----------
        Observed extension-to-type mapping in retail KotOR builds; see wiki resource-type tables.
    """

    type_id: int
    extension: str
    category: Literal[ "Chitin", "Archives", "Crowd Attributes", "Paths", "Lips", "Quests", "Walkmeshes", "Waypoints", "Journals", "Merchants", "Materials", "Cutscenes", "Items", "Fonts", "Soundsets", "Save Data", "Images", "Videos", "Audio", "Text Files", "Other", "Models", "Textures", "Scripts", "Modules", "Module Data", "Creatures", "2D Arrays", "Talk Tables", "Dialogs", "Palettes", "Triggers", "Sounds", "Factions", "Encounters", "Doors", "Placeables", "Defaults", "GUIs", "Unused", ]
    contents: Literal["binary", "plaintext", "gff", "erf", "lips", "video", "xml"]
    is_invalid: bool = False
    target_member: ( Literal[ "LIP", "DLG", "2DA", "TLK", "SSF", "PTH", "UTW", "IFO", "JRL", "UTM", "GUI", "UTP", "FAC", "UTD", "UTS", "UTE", "UTT", "UTI", "UTC", "GIT", "GFF", "RES", "BMP", "MVE", "TGA", "WAV", "PLT", "INI", "BMU", "MPG", "TXT", "WMA", "WMV", "XMV", "PLH", "TEX", "MDL", "THG", "FNT", "LUA", "SLT", "NSS", "NCS", "MOD", "ARE", "SET", "BIP", "JPG2", "PWC"] | None ) = None
    supported_engines: tuple[BiowareEngine, ...] = ()  # Empty tuple as default, use tuple for immutability


def _resolve_resource_target_member(target_member: str | None) -> ResourceType | None:
    if target_member is None:
        return None

    members = ResourceType.__members__
    if target_member in members:
        return members[target_member]

    legacy_aliases = {
        "2DA": "TwoDA",
    }
    resolved_member = legacy_aliases.get(target_member)
    if resolved_member is not None and resolved_member in members:
        return members[resolved_member]
    return None


class ResourceType(Enum):
    """Represents a resource type used across BioWare game engines.

    This enum contains comprehensive resource type definitions informed by observed retail KotOR
    behavior and published tables, representing known resource types across BioWare's Infinity, Aurora,
    Odyssey, and Eclipse engines.

    Each enum member is a ResourceTuple containing:
    - type_id: Integer ID recognized by game engines (consistent across implementations)
    - extension: File extension (lowercase, no leading dot)
    - category: Descriptive category grouping
    - contents: Data storage format
    - is_invalid: Whether this type is invalid/undefined
    - target_member: For toolset-only types, the target ResourceType this maps to
    - supported_engines: Tuple of BiowareEngine values indicating engine support

    Resource type IDs are treated as stable across vendor builds for a given title. Types marked as "Unused" are reserved IDs that
    are not currently used by any known engine.

    Engine Support:
    --------------
        Infinity: Baldur's Gate, Icewind Dale, Planescape: Torment
        Aurora: Neverwinter Nights series
        Odyssey: Knights of the Old Republic I & II
        Eclipse: Dragon Age: Origins, Dragon Age II

    Toolset-only types (supported_engines=()) are used by modding tools but not by
    game engines directly. These typically provide human-readable formats (XML, JSON)
    for editing game resources.

    References:
    ----------
        wiki/Resource-Formats-and-Resolution.md, wiki/Bioware-Aurora-KeyBIF.md
    """

    INVALID = ResourceTuple(-1, "", "Undefined", "binary", is_invalid=True)  # type: ignore[arg-type]  # pyright: ignore[reportCallIssue]
    RES = ResourceTuple(
        0,
        "res",
        "Save Data",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey, BiowareEngine.Eclipse),
    )  # pyright: ignore[reportCallIssue]  # Generic GFF
    BMP = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Image, Windows bitmap
        1,
        "bmp",
        "Images",
        "binary",
        supported_engines=(
            BiowareEngine.Infinity,
            BiowareEngine.Aurora,
            BiowareEngine.Odyssey,
            BiowareEngine.Eclipse,
        ),
    )
    MVE = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Video, Infinity Engine
        2,
        "mve",
        "Videos",
        "video",
        supported_engines=(BiowareEngine.Infinity,),
    )
    TGA = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Image, Truevision TARGA image
        3,
        "tga",
        "Textures",
        "binary",
        supported_engines=(
            BiowareEngine.Infinity,
            BiowareEngine.Aurora,
            BiowareEngine.Odyssey,
            BiowareEngine.Eclipse,
        ),
    )
    WAV = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Audio, Waveform
        4,
        "wav",
        "Audio",
        "binary",
        supported_engines=(
            BiowareEngine.Infinity,
            BiowareEngine.Aurora,
            BiowareEngine.Odyssey,
            BiowareEngine.Eclipse,
        ),
    )
    # Type ID 5 is reserved/unused in all BioWare engines
    PLT = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Packed layer texture
        6,
        "plt",
        "Other",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )
    INI = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Configuration, Windows INI
        7,
        "ini",
        "Text Files",
        "plaintext",
        supported_engines=(
            BiowareEngine.Infinity,
            BiowareEngine.Aurora,
            BiowareEngine.Odyssey,
            BiowareEngine.Eclipse,
        ),
    )
    BMU = ResourceTuple(8, "bmu", "Audio", "binary", supported_engines=(BiowareEngine.Odyssey,))  # pyright: ignore[reportCallIssue]  # Audio, MP3 with extra header (TSL uses MP3 extension with this type ID)
    MPG = ResourceTuple(9, "mpg", "Videos", "binary", supported_engines=(BiowareEngine.Odyssey,))  # pyright: ignore[reportCallIssue]  # Video, MPEG
    TXT = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Text, raw
        10,
        "txt",
        "Text Files",
        "plaintext",
        supported_engines=(
            BiowareEngine.Infinity,
            BiowareEngine.Aurora,
            BiowareEngine.Odyssey,
            BiowareEngine.Eclipse,
        ),
    )
    WMA = ResourceTuple(11, "wma", "Audio", "binary", supported_engines=(BiowareEngine.Odyssey,))  # pyright: ignore[reportCallIssue]  # Audio, Windows media (K1 only, not in TSL)
    WMV = ResourceTuple(12, "wmv", "Videos", "binary", supported_engines=(BiowareEngine.Odyssey,))  # pyright: ignore[reportCallIssue]  # Video, Windows media
    XMV = ResourceTuple(13, "xmv", "Videos", "binary", supported_engines=(BiowareEngine.Odyssey,))  # pyright: ignore[reportCallIssue]  # Video, Xbox
    PLH = ResourceTuple(
        2000,
        "plh",
        "Models",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]
    TEX = ResourceTuple(
        2001,
        "tex",
        "Textures",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Texture
    MDL = ResourceTuple(
        2002,
        "mdl",
        "Models",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey, BiowareEngine.Eclipse),
    )  # pyright: ignore[reportCallIssue]  # Geometry, BioWare model
    THG = ResourceTuple(2003, "thg", "Unused", "binary", supported_engines=(BiowareEngine.Odyssey,))  # pyright: ignore[reportCallIssue]
    # Type ID 2004 is reserved/unused
    FNT = ResourceTuple(
        2005,
        "fnt",
        "Fonts",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Font
    # Type ID 2006 is reserved/unused
    LUA = ResourceTuple(
        2007,
        "lua",
        "Scripts",
        "plaintext",
        supported_engines=(BiowareEngine.Odyssey, BiowareEngine.Eclipse),
    )  # pyright: ignore[reportCallIssue]  # Script, LUA source
    SLT = ResourceTuple(2008, "slt", "Unused", "binary", supported_engines=(BiowareEngine.Odyssey,))  # pyright: ignore[reportCallIssue]
    NSS = ResourceTuple(
        2009,
        "nss",
        "Scripts",
        "plaintext",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Script, NWScript source
    NCS = ResourceTuple(
        2010,
        "ncs",
        "Scripts",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Script, NWScript bytecode
    MOD = ResourceTuple(
        2011,
        "mod",
        "Modules",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Module, ERF
    ARE = ResourceTuple(
        2012,
        "are",
        "Module Data",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Static area data, GFF
    SET = ResourceTuple(
        2013,
        "set",
        "Unused",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Tileset
    IFO = ResourceTuple(
        2014,
        "ifo",
        "Module Data",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Module information, GFF
    BIC = ResourceTuple(
        2015,
        "bic",
        "Creatures",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Character data, GFF
    WOK = ResourceTuple(
        2016,
        "wok",
        "Walkmeshes",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Walk mesh
    TwoDA = ResourceTuple(
        2017,
        "2da",
        "2D Arrays",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey, BiowareEngine.Eclipse),
    )  # pyright: ignore[reportCallIssue]  # Table data, 2-dimensional text array
    TLK = ResourceTuple(
        2018,
        "tlk",
        "Talk Tables",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey, BiowareEngine.Eclipse),
    )  # pyright: ignore[reportCallIssue]  # Talk table
    # Type IDs 2019-2021 are reserved/unused
    TXI = ResourceTuple(
        2022,
        "txi",
        "Textures",
        "plaintext",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Texture information
    GIT = ResourceTuple(
        2023,
        "git",
        "Module Data",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Dynamic area data, GFF
    BTI = ResourceTuple(
        2024, "bti", "Items", "gff", supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey)
    )  # pyright: ignore[reportCallIssue]  # Item template (BioWare), GFF
    UTI = ResourceTuple(
        2025, "uti", "Items", "gff", supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey)
    )  # pyright: ignore[reportCallIssue]  # Item template (user), GFF
    BTC = ResourceTuple(
        2026,
        "btc",
        "Creatures",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Creature template (BioWare), GFF
    UTC = ResourceTuple(
        2027,
        "utc",
        "Creatures",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Creature template (user), GFF
    # Type ID 2028 is reserved/unused
    DLG = ResourceTuple(
        2029,
        "dlg",
        "Dialogs",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey, BiowareEngine.Eclipse),
    )  # pyright: ignore[reportCallIssue]  # Dialog tree, GFF
    ITP = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Toolset "palette" (tree of tiles or object templates), GFF
        2030,
        "itp",
        "Palettes",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )
    BTT = ResourceTuple(
        2031,
        "btt",
        "Triggers",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Trigger template (BioWare), GFF
    UTT = ResourceTuple(
        2032,
        "utt",
        "Triggers",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Trigger template (user), GFF
    DDS = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Texture, DirectDraw Surface
        2033,
        "dds",
        "Textures",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey, BiowareEngine.Eclipse),
    )
    BTS = ResourceTuple(
        2034,
        "bts",
        "Sounds",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Sound template (BioWare), GFF
    UTS = ResourceTuple(
        2035,
        "uts",
        "Sounds",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Sound template (user), GFF
    LTR = ResourceTuple(
        2036,
        "ltr",
        "Other",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Letter combo probability information
    GFF = ResourceTuple(
        2037,
        "gff",
        "Other",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey, BiowareEngine.Eclipse),
    )  # pyright: ignore[reportCallIssue]  # Generic GFF
    FAC = ResourceTuple(
        2038,
        "fac",
        "Factions",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Faction information, GFF
    BTE = ResourceTuple(
        2039,
        "bte",
        "Encounters",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Encounter template (BioWare), GFF
    UTE = ResourceTuple(
        2040,
        "ute",
        "Encounters",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Encounter template (user), GFF
    BTD = ResourceTuple(
        2041, "btd", "Doors", "gff", supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey)
    )  # pyright: ignore[reportCallIssue]  # Door template (BioWare), GFF
    UTD = ResourceTuple(
        2042, "utd", "Doors", "gff", supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey)
    )  # pyright: ignore[reportCallIssue]  # Door template (user), GFF
    BTP = ResourceTuple(
        2043,
        "btp",
        "Placeables",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Placeable template (BioWare), GFF
    UTP = ResourceTuple(
        2044,
        "utp",
        "Placeables",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Placeable template (user), GFF
    DFT = ResourceTuple(
        2045,
        "dft",
        "Defaults",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Default values
    DTF = ResourceTuple(
        2045,
        "dtf",
        "Defaults",
        "plaintext",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Default value file, INI
    GIC = ResourceTuple(
        2046,
        "gic",
        "Module Data",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Game instance comments, GFF
    GUI = ResourceTuple(
        2047,
        "gui",
        "GUIs",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey, BiowareEngine.Eclipse),
    )  # pyright: ignore[reportCallIssue]  # GUI definition, GFF
    CSS = ResourceTuple(
        2048,
        "css",
        "Scripts",
        "plaintext",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Script, conditional source script
    CCS = ResourceTuple(
        2049,
        "ccs",
        "Scripts",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Script, conditional compiled script
    BTM = ResourceTuple(
        2050,
        "btm",
        "Merchants",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Store template (BioWare), GFF
    UTM = ResourceTuple(
        2051,
        "utm",
        "Merchants",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Store template (user), GFF
    DWK = ResourceTuple(
        2052,
        "dwk",
        "Walkmeshes",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Door walk mesh
    PWK = ResourceTuple(
        2053,
        "pwk",
        "Walkmeshes",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Placeable walk mesh
    BTG = ResourceTuple(
        2054, "btg", "Items", "gff", supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey)
    )  # pyright: ignore[reportCallIssue]  # Random item generator template (BioWare), GFF
    UTG = ResourceTuple(
        2055, "utg", "Items", "gff", supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey)
    )  # pyright: ignore[reportCallIssue]  # Random item generator template (user), GFF
    JRL = ResourceTuple(
        2056,
        "jrl",
        "Journals",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Journal data, GFF
    SAV = ResourceTuple(
        2057,
        "sav",
        "Save Data",
        "erf",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Game save, ERF
    UTW = ResourceTuple(
        2058,
        "utw",
        "Waypoints",
        "gff",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Waypoint template, GFF
    FourPC = ResourceTuple(
        2059, "4pc", "Textures", "binary", supported_engines=(BiowareEngine.Odyssey,)
    )  # pyright: ignore[reportCallIssue]  # Texture, custom 16-bit RGBA
    SSF = ResourceTuple(
        2060,
        "ssf",
        "Soundsets",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Sound Set File
    HAK = ResourceTuple(
        2061,
        "hak",
        "Modules",
        "erf",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Resource hak pak, ERF (K1 only, not in TSL)
    NWM = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Neverwinter Nights original campaign module, ERF (K1 only, not in TSL)
        2062,
        "nwm",
        "Modules",
        "erf",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )
    BIK = ResourceTuple(2063, "bik", "Videos", "binary", supported_engines=(BiowareEngine.Odyssey,))  # pyright: ignore[reportCallIssue]  # Video, RAD Game Tools Bink
    NDB = ResourceTuple(
        2064,
        "ndb",
        "Other",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Script debugger file
    PTM = ResourceTuple(
        2065,
        "ptm",
        "Other",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Plot instance/manager, GFF
    PTT = ResourceTuple(
        2066,
        "ptt",
        "Other",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey),
    )  # pyright: ignore[reportCallIssue]  # Plot wizard template, GFF
    NCM = ResourceTuple(2067, "ncm", "Unused", "binary")  # pyright: ignore[reportCallIssue]  # Unused type, reserved
    MFX = ResourceTuple(2068, "mfx", "Unused", "binary")  # pyright: ignore[reportCallIssue]  # Unused type, reserved
    MAT = ResourceTuple(2069, "mat", "Materials", "binary", supported_engines=())  # pyright: ignore[reportCallIssue]  # Material
    MDB = ResourceTuple(2070, "mdb", "Models", "binary", supported_engines=())  # pyright: ignore[reportCallIssue]  # Geometry, BioWare model
    SAY = ResourceTuple(2071, "say", "Unused", "binary")  # pyright: ignore[reportCallIssue]  # Unused type, reserved
    TTF = ResourceTuple(2072, "ttf", "Fonts", "binary", supported_engines=())  # pyright: ignore[reportCallIssue]  # Font, True Type
    TTC = ResourceTuple(2073, "ttc", "Unused", "binary")  # pyright: ignore[reportCallIssue]  # Unused type, reserved
    CUT = ResourceTuple(2074, "cut", "Cutscenes", "gff", supported_engines=())  # pyright: ignore[reportCallIssue]  # Cutscene, GFF
    KA = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Karma, XML  # noqa: E221
        2075,
        "ka",
        "Other",
        "xml",
    )
    JPG = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Image, JPEG
        2076,
        "jpg",
        "Images",
        "binary",
        supported_engines=(BiowareEngine.Eclipse,),
    )
    ICO = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Icon, Windows ICO
        2077,
        "ico",
        "Images",
        "binary",
        supported_engines=(BiowareEngine.Eclipse,),
    )
    OGG = ResourceTuple(2078, "ogg", "Audio", "binary", supported_engines=(BiowareEngine.Eclipse,))  # pyright: ignore[reportCallIssue]  # Audio, Ogg Vorbis
    SPT = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Tree data, SpeedTree
        2079,
        "spt",
        "Other",
        "binary",
    )
    SPW = ResourceTuple(  # pyright: ignore[reportCallIssue]
        2080,
        "spw",
        "Other",
        "binary",
    )
    WFX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Woot effect class, XML
        2081,
        "wfx",
        "Other",
        "xml",
    )
    UGM = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2082,
        "ugm",
        "Unused",
        "binary",
    )
    QDB = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Quest database, GFF
        2083,
        "qdb",
        "Quests",
        "gff",
    )
    QST = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Quest, GFF
        2084,
        "qst",
        "Quests",
        "gff",
    )
    NPC = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2085,
        "npc",
        "Unused",
        "binary",
    )
    SPN = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2086,
        "spn",
        "Unused",
        "binary",
    )
    UTX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2087,
        "utx",
        "Unused",
        "binary",
    )
    MMD = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2088,
        "mmd",
        "Unused",
        "binary",
    )
    SMM = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2089,
        "smm",
        "Unused",
        "binary",
    )
    UTA = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2090,
        "uta",
        "Unused",
        "binary",
    )
    MDE = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2091,
        "mde",
        "Unused",
        "binary",
    )
    MDV = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2092,
        "mdv",
        "Unused",
        "binary",
    )
    MDA = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2093,
        "mda",
        "Unused",
        "binary",
    )
    MBA = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2094,
        "mba",
        "Unused",
        "binary",
    )
    OCT = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2095,
        "oct",
        "Unused",
        "binary",
    )
    BFX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2096,
        "bfx",
        "Unused",
        "binary",
    )
    PDB = ResourceTuple(2097, "pdb", "Unused", "binary")  # pyright: ignore[reportCallIssue]  # Unused type, reserved
    THEWITCHERSAVE = ResourceTuple(2098, "thewitchersave", "Save Data", "binary")  # pyright: ignore[reportCallIssue]  # The Witcher save file, not BioWare engine
    PVS = ResourceTuple(2099, "pvs", "Unused", "binary")  # pyright: ignore[reportCallIssue]  # Unused type, reserved
    CFX = ResourceTuple(2100, "cfx", "Unused", "binary")  # pyright: ignore[reportCallIssue]  # Unused type, reserved
    LUC = ResourceTuple(
        2101, "luc", "Scripts", "binary", supported_engines=(BiowareEngine.Eclipse,)
    )  # pyright: ignore[reportCallIssue]  # Script, LUA bytecode
    # Type ID 2102 is reserved/unused
    PRB = ResourceTuple(2103, "prb", "Unused", "binary")  # pyright: ignore[reportCallIssue]  # Unused type, reserved
    CAM = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Campaign information, Aurora only
        2104,
        "cam",
        "Module Data",
        "binary",
        supported_engines=(BiowareEngine.Aurora,),
    )
    VDS = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2105,
        "vds",
        "Unused",
        "binary",
    )
    BIN = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2106,
        "bin",
        "Unused",
        "binary",
    )
    WOB = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2107,
        "wob",
        "Unused",
        "binary",
    )
    API = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2108,
        "api",
        "Unused",
        "binary",
    )
    Properties = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        2109,
        "properties",
        "Unused",
        "binary",
    )
    PNG = ResourceTuple(  # pyright: ignore[reportCallIssue]  # PNG image format
        2110,
        "png",
        "Images",
        "binary",
        supported_engines=(BiowareEngine.Odyssey, BiowareEngine.Eclipse),
    )
    LYT = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Layout file, defines area layout
        3000,
        "lyt",
        "Module Data",
        "plaintext",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    VIS = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Visibility file, area visibility data
        3001,
        "vis",
        "Module Data",
        "plaintext",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    RIM = ResourceTuple(  # pyright: ignore[reportCallIssue]  # RIM archive file, Odyssey module format
        3002,
        "rim",
        "Modules",
        "binary",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    PTH = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Path file, creature pathfinding data
        3003,
        "pth",
        "Paths",
        "gff",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    LIP = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Lip sync file, facial animation data
        3004,
        "lip",
        "Lips",
        "lips",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    BWM = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Walkmesh file
        3005,
        "bwm",
        "Walkmeshes",
        "binary",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    TXB = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Texture file
        3006,
        "txb",
        "Textures",
        "binary",
    )
    TPC = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Texture file
        3007,
        "tpc",
        "Textures",
        "binary",
    )
    MDX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Geometry, model mesh data
        3008,
        "mdx",
        "Models",
        "binary",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    RSV = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        3009,
        "rsv",
        "Unused",
        "binary",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    SIG = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        3010,
        "sig",
        "Unused",
        "binary",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    MAB = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Material, binary
        3011,
        "mab",
        "Materials",
        "binary",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    QST2 = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Quest, GFF
        3012,
        "qst2",
        "Quests",
        "gff",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    STO = ResourceTuple(  # pyright: ignore[reportCallIssue]  # GFF
        3013,
        "sto",
        "Other",
        "gff",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    # Type ID 3014 is reserved/unused
    HEX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Hex grid file
        3015,
        "hex",
        "Other",
        "binary",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    MDX2 = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Geometry, model mesh data
        3016,
        "mdx2",
        "Models",
        "binary",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    TXB2 = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Texture
        3017,
        "txb2",
        "Textures",
        "binary",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    # Type IDs 3018-3021 are reserved/unused
    FSM = ResourceTuple(  # pyright: ignore[reportCallIssue]      # Finite State Machine data
        3022,
        "fsm",
        "Other",
        "binary",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    ART = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Area environment settings, INI
        3023,
        "art",
        "Module Data",
        "plaintext",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    AMP = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Brightening control
        3024,
        "amp",
        "Other",
        "binary",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    CWA = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Crowd attributes, GFF
        3025,
        "cwa",
        "Crowd Attributes",
        "gff",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    # Type IDs 3026-3027 are reserved/unused
    BIP = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Lipsync data, binary LIP
        3028,
        "bip",
        "Lips",
        "lips",
        supported_engines=(BiowareEngine.Odyssey,),
    )
    MDB2 = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Model database v2, Eclipse only
        4000,
        "mdb2",
        "Models",
        "binary",
        supported_engines=(BiowareEngine.Eclipse,),
    )
    MDA2 = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Model animation v2, Eclipse only
        4001,
        "mda2",
        "Models",
        "binary",
        supported_engines=(BiowareEngine.Eclipse,),
    )
    SPT2 = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Unused type, reserved
        4002,
        "spt2",
        "Unused",
        "binary",
    )
    GR2 = ResourceTuple(  # pyright: ignore[reportCallIssue]  # GR2 file, Eclipse only
        4003,
        "gr2",
        "Other",
        "binary",
        supported_engines=(BiowareEngine.Eclipse,),
    )
    FXA = ResourceTuple(  # pyright: ignore[reportCallIssue]  # FXA file, Eclipse only
        4004,
        "fxa",
        "Other",
        "binary",
        supported_engines=(BiowareEngine.Eclipse,),
    )
    FXE = ResourceTuple(  # pyright: ignore[reportCallIssue]  # FXE file, Eclipse only
        4005,
        "fxe",
        "Other",
        "binary",
        supported_engines=(BiowareEngine.Eclipse,),
    )
    # Type ID 4006 is reserved/unused
    JPG2 = ResourceTuple(  # pyright: ignore[reportCallIssue]  # JPEG v2, Eclipse only
        4007,
        "jpg2",
        "Images",
        "binary",
        supported_engines=(BiowareEngine.Eclipse,),
    )
    PWC = ResourceTuple(  # pyright: ignore[reportCallIssue]  # PWC file, Eclipse only
        4008,
        "pwc",
        "Other",
        "binary",
        supported_engines=(BiowareEngine.Eclipse,),
    )
    EXE = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Windows PE EXE file
        19000,
        "exe",
        "Other",
        "binary",
    )
    DBF = ResourceTuple(  # pyright: ignore[reportCallIssue]  # xBase database
        19001,
        "dbf",
        "Other",
        "binary",
    )
    CDX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # FoxPro database index
        19002,
        "cdx",
        "Other",
        "binary",
    )
    FPT = ResourceTuple(  # pyright: ignore[reportCallIssue]  # FoxPro database memo file
        type_id=19003,
        extension="fpt",
        category="Other",
        contents="binary",
    )
    ZIP = ResourceTuple(  # pyright: ignore[reportCallIssue]  # ZIP archive
        20000,
        "zip",
        "Archives",
        "binary",
    )
    FXM = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Face metadata, FaceFX
        20001,
        "fxm",
        "Other",
        "binary",
    )
    FXS = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Face metadata, FaceFX
        20002,
        "fxs",
        "Other",
        "binary",
    )
    XML = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Extensible Markup Language
        20003,
        "xml",
        "Other",
        "plaintext",
    )
    WLK = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Walk mesh
        20004,
        "wlk",
        "Walkmeshes",
        "binary",
    )
    UTR = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Tree template (user), GFF
        20005,
        "utr",
        "Other",
        "gff",
    )
    SEF = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Special effect file
        20006,
        "sef",
        "Other",
        "binary",
    )
    PFX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Particle effect
        20007,
        "pfx",
        "Other",
        "binary",
    )
    TFX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Trail effect
        20008,
        "tfx",
        "Other",
        "binary",
    )
    IFX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # IFX file
        20009,
        "ifx",
        "Other",
        "binary",
    )
    LFX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Line effect
        20010,
        "lfx",
        "Other",
        "binary",
    )
    BBX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Billboard effect
        20011,
        "bbx",
        "Other",
        "binary",
    )
    PFB = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Prefab blueprint
        20012,
        "pfb",
        "Other",
        "binary",
    )
    UPE = ResourceTuple(  # pyright: ignore[reportCallIssue]  # UPE file
        20013,
        "upe",
        "Unused",
        "binary",
    )
    USC = ResourceTuple(  # pyright: ignore[reportCallIssue]  # USC file
        20014,
        "usc",
        "Unused",
        "binary",
    )
    ULT = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Light template (user), GFF
        20015,
        "ult",
        "Other",
        "gff",
    )
    FX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # FX file
        20016,
        "fx",
        "Other",
        "binary",
    )
    MAX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # 3ds Max file
        20017,
        "max",
        "Other",
        "binary",
    )
    DOC = ResourceTuple(  # pyright: ignore[reportCallIssue]  # DOC file
        20018,
        "doc",
        "Other",
        "binary",
    )
    SCC = ResourceTuple(  # pyright: ignore[reportCallIssue]  # SCC file
        20019,
        "scc",
        "Other",
        "binary",
    )
    WMP = ResourceTuple(  # pyright: ignore[reportCallIssue]  # World map, GFF
        20020,
        "wmp",
        "Other",
        "gff",
    )
    OSC = ResourceTuple(  # pyright: ignore[reportCallIssue]  # OSC file
        20021,
        "osc",
        "Other",
        "binary",
    )
    TRN = ResourceTuple(  # pyright: ignore[reportCallIssue]  # TRN file
        20022,
        "trn",
        "Other",
        "binary",
    )
    UEN = ResourceTuple(  # pyright: ignore[reportCallIssue]  # UEN file
        20023,
        "uen",
        "Unused",
        "binary",
    )
    ROS = ResourceTuple(  # pyright: ignore[reportCallIssue]  # ROS file
        20024,
        "ros",
        "Other",
        "binary",
    )
    RST = ResourceTuple(  # pyright: ignore[reportCallIssue]  # RST file
        20025,
        "rst",
        "Other",
        "binary",
    )
    PTX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # PTX file
        20026,
        "ptx",
        "Other",
        "binary",
    )
    LTX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # LTX file
        20027,
        "ltx",
        "Other",
        "binary",
    )
    TRX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # TRX file
        20028,
        "trx",
        "Other",
        "binary",
    )
    NDS = ResourceTuple(21000, "nds", "Archives", "binary")  # pyright: ignore[reportCallIssue]  # Archive, Nintendo DS ROM file
    HERF = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Archive, hashed ERF
        21001,
        "herf",
        "Archives",
        "binary",
    )
    DICT = ResourceTuple(  # pyright: ignore[reportCallIssue]  # HERF file name -> hashes dictionary
        21002,
        "dict",
        "Other",
        "binary",
    )
    SMALL = ResourceTuple(21003, "small", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Compressed file, Nintendo LZSS
    CBGT = ResourceTuple(21004, "cbgt", "Other", "binary")  # pyright: ignore[reportCallIssue]
    CDPTH = ResourceTuple(21005, "cdpth", "Other", "binary")  # pyright: ignore[reportCallIssue]
    EMIT = ResourceTuple(21006, "emit", "Other", "binary")  # pyright: ignore[reportCallIssue]
    ITM = ResourceTuple(21007, "itm", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Items, 2DA
    NANR = ResourceTuple(21008, "nanr", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Animation, Nitro ANimation Resource
    NBFP = ResourceTuple(21009, "nbfp", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Palette, Nitro Basic File Palette
    NBFS = ResourceTuple(21010, "nbfs", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Image/Map, Nitro Basic File Screen
    NCER = ResourceTuple(21011, "ncer", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Image, Nitro CEll Resource
    NCGR = ResourceTuple(21012, "ncgr", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Image, Nitro Character Graphic Resource
    NCLR = ResourceTuple(21013, "nclr", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Palette, Nitro CoLoR
    NFTR = ResourceTuple(21014, "nftr", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Font
    NSBCA = ResourceTuple(21015, "nsbca", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Model Animation
    NSBMD = ResourceTuple(21016, "nsbmd", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Model
    NSBTA = ResourceTuple(21017, "nsbta", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Texture animation
    NSBTP = ResourceTuple(21018, "nsbtp", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Texture part
    NSBTX = ResourceTuple(21019, "nsbtx", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Texture
    PAL = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Palette file
        21020,
        "pal",
        "Palettes",
        "binary",
    )
    RAW = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Raw data file
        21021,
        "raw",
        "Other",
        "binary",
    )
    SADL = ResourceTuple(21022, "sadl", "Other", "binary")  # pyright: ignore[reportCallIssue]
    SDAT = ResourceTuple(21023, "sdat", "Audio", "binary")  # pyright: ignore[reportCallIssue]  # Audio, Sound DATa
    SMP = ResourceTuple(21024, "smp", "Other", "binary")  # pyright: ignore[reportCallIssue]
    SPL = ResourceTuple(21025, "spl", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Spells, 2DA
    VX = ResourceTuple(21026, "vx", "Videos", "binary")  # pyright: ignore[reportCallIssue]  # Video, Actimagine
    ANB = ResourceTuple(22000, "anb", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Animation blend
    ANI = ResourceTuple(22001, "ani", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Animation sequence
    CNS = ResourceTuple(22002, "cns", "Scripts", "binary")  # pyright: ignore[reportCallIssue]  # Script, client script source
    CUR = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Cursor, Windows cursor
        22003,
        "cur",
        "Other",
        "binary",
    )
    EVT = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Animation event
        22004,
        "evt",
        "Other",
        "binary",
    )
    FDL = ResourceTuple(22005, "fdl", "Other", "binary")  # pyright: ignore[reportCallIssue]
    FXO = ResourceTuple(22006, "fxo", "Other", "binary")  # pyright: ignore[reportCallIssue]
    GAD = ResourceTuple(22007, "gad", "Other", "binary")  # pyright: ignore[reportCallIssue]  # GOB Animation Data
    GDA = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Table data, GFF'd 2DA, 2-dimensional text array
        22008,
        "gda",
        "2D Arrays",
        "binary",
        supported_engines=(BiowareEngine.Eclipse,),
    )
    GFX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Vector graphics animation, Scaleform GFx
        22009,
        "gfx",
        "Other",
        "binary",
    )
    LDF = ResourceTuple(22010, "ldf", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Language definition file
    LST = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Area list
        22011,
        "lst",
        "Other",
        "plaintext",
    )
    MAL = ResourceTuple(22012, "mal", "Materials", "binary")  # pyright: ignore[reportCallIssue]  # Material Library
    MAO = ResourceTuple(22013, "mao", "Materials", "binary")  # pyright: ignore[reportCallIssue]  # Material Object
    MMH = ResourceTuple(22014, "mmh", "Models", "binary")  # pyright: ignore[reportCallIssue]  # Model Mesh Hierarchy
    MOP = ResourceTuple(22015, "mop", "Other", "binary")  # pyright: ignore[reportCallIssue]
    MOR = ResourceTuple(22016, "mor", "Models", "binary")  # pyright: ignore[reportCallIssue]  # Head Morph
    MSH = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Mesh
        22017,
        "msh",
        "Models",
        "binary",
    )
    MTX = ResourceTuple(22018, "mtx", "Other", "binary")  # pyright: ignore[reportCallIssue]
    NCC = ResourceTuple(22019, "ncc", "Scripts", "binary")  # pyright: ignore[reportCallIssue]  # Script, compiled client script
    PHY = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Physics, Novodex collision info
        22020,
        "phy",
        "Other",
        "binary",
    )
    PLO = ResourceTuple(22021, "plo", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Plot information
    STG = ResourceTuple(22022, "stg", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Cutscene stage
    TBI = ResourceTuple(22023, "tbi", "Other", "binary")  # pyright: ignore[reportCallIssue]
    TNT = ResourceTuple(22024, "tnt", "Materials", "binary")  # pyright: ignore[reportCallIssue]  # Material tint
    ARL = ResourceTuple(22025, "arl", "Module Data", "binary")  # pyright: ignore[reportCallIssue]  # Area layout
    FEV = ResourceTuple(22026, "fev", "Audio", "binary")  # pyright: ignore[reportCallIssue]  # FMOD Event
    FSB = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Audio, FMOD sound bank
        22027,
        "fsb",
        "Audio",
        "binary",
    )
    OPF = ResourceTuple(22028, "opf", "Other", "binary")  # pyright: ignore[reportCallIssue]
    CRF = ResourceTuple(22029, "crf", "Other", "binary")  # pyright: ignore[reportCallIssue]
    RIMP = ResourceTuple(22030, "rimp", "Other", "binary")  # pyright: ignore[reportCallIssue]
    MET = ResourceTuple(22031, "met", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Resource meta information
    META = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Resource meta information
        22032,
        "meta",
        "Other",
        "binary",
    )
    FXR = ResourceTuple(22033, "fxr", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Face metadata, FaceFX
    FXT = ResourceTuple(22033, "fxt", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Face metadata, FaceFX
    CIF = ResourceTuple(22034, "cif", "Other", "gff")  # pyright: ignore[reportCallIssue]  # Campaign Information File, GFF4
    CUB = ResourceTuple(22035, "cub", "Other", "binary")  # pyright: ignore[reportCallIssue]
    DLB = ResourceTuple(22036, "dlb", "Other", "binary")  # pyright: ignore[reportCallIssue]
    NSC = ResourceTuple(22037, "nsc", "Scripts", "binary")  # pyright: ignore[reportCallIssue]  # NWScript client script source
    MOV = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Video, QuickTime/MPEG-4
        23000,
        "mov",
        "Videos",
        "binary",
    )
    CURS = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Cursor, Mac CURS format
        23001,
        "curs",
        "Other",
        "binary",
    )
    PICT = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Image, Mac PICT format
        23002,
        "pict",
        "Images",
        "binary",
    )
    RSRC = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Mac resource fork
        23003,
        "rsrc",
        "Other",
        "binary",
    )
    PLIST = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Mac property list, XML
        23004,
        "plist",
        "Other",
        "plaintext",
    )
    CRE = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Creature, GFF
        24000,
        "cre",
        "Creatures",
        "gff",
    )
    PSO = ResourceTuple(24001, "pso", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Shader
    VSO = ResourceTuple(24002, "vso", "Other", "binary")  # pyright: ignore[reportCallIssue]  # Shader
    ABC = ResourceTuple(24003, "abc", "Fonts", "binary")  # pyright: ignore[reportCallIssue]  # Font, character descriptions
    SBM = ResourceTuple(24004, "sbm", "Fonts", "binary")  # pyright: ignore[reportCallIssue]  # Font, character bitmap data
    PVD = ResourceTuple(24005, "pvd", "Other", "binary")  # pyright: ignore[reportCallIssue]
    PLA = ResourceTuple(24006, "pla", "Placeables", "gff")  # pyright: ignore[reportCallIssue]  # Placeable, GFF
    TRG = ResourceTuple(24007, "trg", "Triggers", "gff")  # pyright: ignore[reportCallIssue]  # Trigger, GFF
    PK = ResourceTuple(24008, "pk", "Other", "binary")  # pyright: ignore[reportCallIssue]
    ALS = ResourceTuple(25000, "als", "Other", "binary")  # pyright: ignore[reportCallIssue]
    APL = ResourceTuple(25001, "apl", "Other", "binary")  # pyright: ignore[reportCallIssue]
    ASSEMBLY = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Assembly file
        25002,
        "assembly",
        "Other",
        "binary",
    )
    BAK = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Backup file
        25003,
        "bak",
        "Other",
        "binary",
    )
    BNK = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Audio bank
        25004,
        "bnk",
        "Audio",
        "binary",
    )
    CL = ResourceTuple(25005, "cl", "Other", "binary")  # pyright: ignore[reportCallIssue]
    CNV = ResourceTuple(25006, "cnv", "Other", "binary")  # pyright: ignore[reportCallIssue]
    CON = ResourceTuple(25007, "con", "Other", "binary")  # pyright: ignore[reportCallIssue]
    DAT = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Data file
        25008,
        "dat",
        "Other",
        "binary",
    )
    DX11 = ResourceTuple(  # pyright: ignore[reportCallIssue]  # DirectX 11 file
        25009,
        "dx11",
        "Other",
        "binary",
    )
    IDS = ResourceTuple(  # pyright: ignore[reportCallIssue]  # IDS file
        25010,
        "ids",
        "Other",
        "plaintext",
    )
    LOG = ResourceTuple(
        25011, "log", "Other", "plaintext", supported_engines=(BiowareEngine.Odyssey,)
    )  # pyright: ignore[reportCallIssue]
    MAP = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Map file
        25012,
        "map",
        "Other",
        "binary",
    )
    MML = ResourceTuple(25013, "mml", "Other", "binary")  # pyright: ignore[reportCallIssue]
    PCK = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Audio package
        25015,
        "pck",
        "Audio",
        "binary",
    )
    RML = ResourceTuple(25016, "rml", "Other", "binary")  # pyright: ignore[reportCallIssue]
    S = ResourceTuple(25017, "s", "Other", "binary")  # pyright: ignore[reportCallIssue]
    STA = ResourceTuple(25018, "sta", "Other", "binary")  # pyright: ignore[reportCallIssue]
    SVR = ResourceTuple(25019, "svr", "Other", "binary")  # pyright: ignore[reportCallIssue]
    VLM = ResourceTuple(25020, "vlm", "Other", "binary")  # pyright: ignore[reportCallIssue]
    WBD = ResourceTuple(25021, "wbd", "Other", "binary")  # pyright: ignore[reportCallIssue]
    XBX = ResourceTuple(25022, "xbx", "Other", "binary", supported_engines=(BiowareEngine.Odyssey,))  # pyright: ignore[reportCallIssue]
    XLS = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Excel file
        25023,
        "xls",
        "Other",
        "binary",
    )
    BZF = ResourceTuple(26000, "bzf", "Archives", "binary")  # pyright: ignore[reportCallIssue]  # Game resource data, LZMA-compressed BIF
    ADV = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Extra adventure modules, ERF
        27000,
        "adv",
        "Modules",
        "binary",
    )
    JSON = ResourceTuple(  # pyright: ignore[reportCallIssue]  # JSON file
        28000,
        "json",
        "Other",
        "plaintext",
    )
    TLK_EXPERT = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Talk table for extra expert-level control strings, plain text
        28001,
        "tlk_expert",
        "Talk Tables",
        "plaintext",
    )
    TLK_MOBILE = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Talk table for extra mobile port strings, plain text
        28002,
        "tlk_mobile",
        "Talk Tables",
        "plaintext",
    )
    TLK_TOUCH = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Talk table for extra touch control strings, plain text
        28003,
        "tlk_touch",
        "Talk Tables",
        "plaintext",
    )
    OTF = ResourceTuple(  # pyright: ignore[reportCallIssue]  # OpenType font
        28004,
        "otf",
        "Fonts",
        "binary",
    )
    PAR = ResourceTuple(28005, "par", "Other", "binary")  # pyright: ignore[reportCallIssue]
    XWB = ResourceTuple(  # pyright: ignore[reportCallIssue]  # XACT WaveBank
        29000,
        "xwb",
        "Audio",
        "binary",
    )
    XSB = ResourceTuple(  # pyright: ignore[reportCallIssue]  # XACT SoundBank
        29001,
        "xsb",
        "Audio",
        "binary",
    )
    XDS = ResourceTuple(30000, "xds", "Textures", "binary")  # pyright: ignore[reportCallIssue]  # Texture
    WND = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Window file
        30001,
        "wnd",
        "Other",
        "binary",
    )
    XEOSITEX = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Xeositex texture
        40000,
        "xeositex",
        "Textures",
        "binary",
    )
    WBM = ResourceTuple(41000, "wbm", "Videos", "binary")  # pyright: ignore[reportCallIssue]  # Video, WebM
    OneDA = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Table data, 1-dimensional text array
        9996,
        "1da",
        "2D Arrays",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey, BiowareEngine.Eclipse),
    )
    ERF = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Module resources
        9997,
        "erf",
        "Modules",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey, BiowareEngine.Eclipse),
    )
    BIF = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Game resource data
        9998,
        "bif",
        "Archives",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey, BiowareEngine.Eclipse),
    )
    KEY = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Game resource index
        9999,
        "key",
        "Chitin",
        "binary",
        supported_engines=(BiowareEngine.Aurora, BiowareEngine.Odyssey, BiowareEngine.Eclipse),
    )

    # Toolset/Editor-specific types (not used by game engine)
    # Define these here to ensure we don't reuse these numbers.
    GLSL = ResourceTuple(  # pyright: ignore[reportCallIssue]  # OpenGL Shading Language, toolset only
        0x1001,
        "glsl",
        "Scripts",
        "plaintext",
        supported_engines=(),
    )
    CURSOR = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Windows cursor, toolset only
        0x2000,
        "cursor",
        "Other",
        "binary",
        supported_engines=(),
    )
    CURSORGROUP = ResourceTuple(  # pyright: ignore[reportCallIssue]  # Windows cursor group, toolset only
        0x2001,
        "cursorgroup",
        "Other",
        "binary",
        supported_engines=(),
    )

    # For Toolset Use:
    # Note: MP3 is actually used by Odyssey engine (K1 has separate MP3 type, TSL uses type ID 8/BMU for MP3 extension)
    # This toolset-only entry is kept for compatibility but MP3 files in-game use BMU type ID 8 in TSL
    MP3 = ResourceTuple(  # pyright: ignore[reportCallIssue]  # MP3 audio, toolset only (BMU type ID 8 is used in-game for MP3 in TSL)
        25014,
        "mp3",
        "Audio",
        "binary",
        supported_engines=(),
    )
    # Toolset serialization variants now live in ToolsetFormat. Keep 50011 reserved/unused.

    def __init__(  # noqa: PLR0913
        self,
        type_id: int,
        extension: str,
        category: str,
        contents: str,
        is_invalid: bool = False,  # noqa: FBT001, FBT002
        target_member: str | None = None,
        supported_engines: tuple[BiowareEngine, ...] = (),
    ):
        self.type_id: int = type_id
        self.extension: str = extension.strip().lower()
        self.category: str = category
        self.contents: str = contents
        self.is_invalid: bool = is_invalid
        self.target_member: str | None = target_member
        self.supported_engines: tuple[BiowareEngine, ...] = supported_engines

    def is_gff(self) -> bool:
        """Returns True if this resourcetype is a gff, excluding the xml/json abstractions, False otherwise."""
        return self.contents == "gff"

    def target_type(self) -> Self:
        resolved = _resolve_resource_target_member(self.target_member)
        return self if resolved is None else cast(Self, resolved)

    @classmethod
    @lru_cache(maxsize=0xFFFF)
    def from_id(
        cls,
        type_id: int | str,
    ) -> ResourceType:
        """Returns the ResourceType for the specified id.

        Args:
        ----
            type_id: The resource id.

        Returns:
        -------
            The corresponding ResourceType object.
        """
        if isinstance(type_id, str):
            type_id = int(type_id)

        return next(
            (restype for restype in ResourceType.__members__.values() if type_id == restype),
            ResourceType.from_invalid(type_id=type_id),
        )

    @classmethod
    def from_extension(
        cls,
        extension: str,
    ) -> ResourceType:
        """Returns the ResourceType for the specified extension.

        This will slice off the leading dot in the extension, if it exists.

        Args:
        ----
            extension: The resource's extension. This is case-insensitive

        Returns:
        -------
            The corresponding ResourceType object.
        """
        lower_ext: str = extension.lower()
        if lower_ext.startswith("."):
            lower_ext = lower_ext[1:]
        resource_type = next(
            (
                restype
                for restype in ResourceType.__members__.values()
                if lower_ext == restype.extension
            ),
            ResourceType.from_invalid(extension=lower_ext),
        )
        if resource_type.is_invalid:
            toolset_format = ToolsetFormat.from_extension(lower_ext)
            if toolset_format is not None:
                return cast(ResourceType, toolset_format)
        return resource_type

    @classmethod
    def from_invalid(
        cls,
        **kwargs,
    ):
        if not kwargs:
            return cls.INVALID
        instance = object.__new__(cls)
        name = f"INVALID_{kwargs.get('extension', kwargs.get('type_id', cls.INVALID.extension)) or uuid.uuid4().hex}"
        while name in cls.__members__:
            name = f"INVALID_{kwargs.get('extension', kwargs.get('type_id', cls.INVALID.extension))}{uuid.uuid4().hex}"
        instance._name_ = name
        instance._value_ = ResourceTuple(
            type_id=kwargs.get("type_id", cls.INVALID.type_id),
            extension=kwargs.get("extension", cls.INVALID.extension),
            category=kwargs.get("category", cls.INVALID.category),
            contents=kwargs.get("contents", cls.INVALID.contents),
            is_invalid=kwargs.get("is_invalid", cls.INVALID.is_invalid),
            target_member=kwargs.get("target_member", cls.INVALID.target_member),
            supported_engines=kwargs.get("supported_engines", cls.INVALID.supported_engines),
        )
        instance.__init__(  # type: ignore[misc]
            type_id=kwargs.get("type_id", cls.INVALID.type_id),
            extension=kwargs.get("extension", cls.INVALID.extension),
            category=kwargs.get("category", cls.INVALID.category),
            contents=kwargs.get("contents", cls.INVALID.contents),
            is_invalid=kwargs.get("is_invalid", cls.INVALID.is_invalid),
            target_member=kwargs.get("target_member", cls.INVALID.target_member),
            supported_engines=kwargs.get("supported_engines", cls.INVALID.supported_engines),
        )
        return super().__new__(cls, instance)

    def validate(self):
        if not self:
            msg = f"Invalid ResourceType: '{self!r}'"
            raise ValueError(msg)
        return self

    def __bool__(self) -> bool:
        return not self.is_invalid


    def __repr__(self) -> str:
        if self.name == "INVALID" or not self.is_invalid:
            return f"{self.__class__.__name__}.{self.name}"

        return (  # For dynamically constructed invalid members
            f"{self.__class__.__name__}.from_invalid("
            f"{f'type_id={self.type_id}, '}"
            f"{f'extension={self.extension}, ' if self.extension else ''}"
            f"{f'category={self.category}, ' if self.category else ''}"
            f"contents={self.contents})"
        )

    def __str__(self) -> str:
        """Returns the extension in all caps."""
        return str(self.extension.upper())

    def __int__(self):
        """Returns the type_id."""
        return self.type_id

    def __eq__(
        self,
        other: ResourceType | str | int | object,
    ):
        """Two ResourceTypes are equal if they are the same.

        A ResourceType and a str are equal if the extension is case-sensitively equal to the string.
        A ResourceType and a int are equal if the type_id is equal to the integer.
        """
        if self is other:
            return True
        if isinstance(other, ResourceType):
            if self.is_invalid or other.is_invalid:
                return self.is_invalid and other.is_invalid
            return self.name == other.name
        if isinstance(other, (str, WrappedStr)):
            return self.extension == other.lower()
        if isinstance(other, int):
            return self.type_id == other
        return NotImplemented  # type: ignore[no-any-return]

    def __hash__(self):
        return hash(self.extension)

    def is_valid(self) -> bool:
        return not self.is_invalid


class ToolsetFormat(Enum):
    """Non-engine serialization and editor-only resource formats.

    These are intentionally not members of ResourceType because they are not real
    BioWare on-disk type ids. They describe alternate representations layered on top
    of canonical ResourceType values.
    """

    WAV_DEOB = (50000, "wav", "Audio", "binary", "WAV")
    TLK_XML = (50001, "tlk.xml", "Talk Tables", "plaintext", "TLK")
    MDL_ASCII = (50002, "mdl.ascii", "Models", "plaintext", "MDL")
    TwoDA_CSV = (50003, "2da.csv", "2D Arrays", "plaintext", "2DA")
    GFF_XML = (50004, "gff.xml", "Other", "plaintext", "GFF")
    GFF_JSON = (50005, "gff.json", "Other", "plaintext", "GFF")
    IFO_XML = (50006, "ifo.xml", "Module Data", "plaintext", "IFO")
    GIT_XML = (50007, "git.xml", "Module Data", "plaintext", "GIT")
    UTI_XML = (50008, "uti.xml", "Items", "plaintext", "UTI")
    UTC_XML = (50009, "utc.xml", "Creatures", "plaintext", "UTC")
    DLG_XML = (50010, "dlg.xml", "Dialogs", "plaintext", "DLG")
    UTT_XML = (50012, "utt.xml", "Triggers", "plaintext", "UTT")
    UTS_XML = (50013, "uts.xml", "Sounds", "plaintext", "UTS")
    FAC_XML = (50014, "fac.xml", "Factions", "plaintext", "FAC")
    UTE_XML = (50015, "ute.xml", "Encounters", "plaintext", "UTE")
    UTD_XML = (50016, "utd.xml", "Doors", "plaintext", "UTD")
    UTP_XML = (50017, "utp.xml", "Placeables", "plaintext", "UTP")
    GUI_XML = (50018, "gui.xml", "GUIs", "plaintext", "GUI")
    UTM_XML = (50019, "utm.xml", "Merchants", "plaintext", "UTM")
    JRL_XML = (50020, "jrl.xml", "Journals", "plaintext", "JRL")
    UTW_XML = (50021, "utw.xml", "Waypoints", "plaintext", "UTW")
    PTH_XML = (50022, "pth.xml", "Paths", "plaintext", "PTH")
    LIP_XML = (50023, "lip.xml", "Lips", "plaintext", "LIP")
    SSF_XML = (50024, "ssf.xml", "Soundsets", "plaintext", "SSF")
    ARE_XML = (50025, "are.xml", "Module Data", "plaintext", "ARE")
    TwoDA_JSON = (50026, "2da.json", "2D Arrays", "plaintext", "2DA")
    TLK_JSON = (50027, "tlk.json", "Talk Tables", "plaintext", "TLK")
    LIP_JSON = (50028, "lip.json", "Lips", "plaintext", "LIP")
    RES_XML = (50029, "res.xml", "Save Data", "plaintext", "RES")
    SSF_JSON = (50030, "ssf.json", "Soundsets", "plaintext", "SSF")

    def __init__(
        self,
        legacy_id: int,
        extension: str,
        category: str,
        contents: str,
        target_member: str,
    ):
        self.legacy_id: int = legacy_id
        self.extension: str = extension.strip().lower()
        self.category: str = category
        self.contents: str = contents
        self.target_member: str = target_member
        self.supported_engines: tuple[BiowareEngine, ...] = ()
        self.is_invalid: bool = False

    @classmethod
    @lru_cache(maxsize=0xFF)
    def from_extension(cls, extension: str) -> ToolsetFormat | None:
        lower_ext = extension.lower()
        if lower_ext.startswith("."):
            lower_ext = lower_ext[1:]
        return next((fmt for fmt in cls if fmt.extension == lower_ext), None)

    def target_type(self) -> ResourceType:
        resolved = _resolve_resource_target_member(self.target_member)
        if resolved is None:
            msg = (
                f"Unknown target resource type for toolset format {self.name}: {self.target_member}"
            )
            raise ValueError(msg)
        return resolved

    def is_gff(self) -> bool:
        return self.target_type().is_gff()

    def validate(self) -> ToolsetFormat:
        return self

    def is_valid(self) -> bool:
        return True

    def __bool__(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"

    def __str__(self) -> str:
        return str(self.extension.upper())

    def __eq__(self, other: object):
        if self is other:
            return True
        if isinstance(other, ToolsetFormat):
            return self.name == other.name
        if isinstance(other, (str, WrappedStr)):
            return self.extension == other.lower()
        return NotImplemented  # type: ignore[no-any-return]

    def __hash__(self):
        return hash(self.extension)


RESOURCE_FORMAT = Union[ResourceType, ToolsetFormat]


def get_toolset_format(ident: str | ToolsetFormat | None) -> ToolsetFormat | None:
    if ident is None:
        return None
    if isinstance(ident, ToolsetFormat):
        return ident
    return ToolsetFormat.from_extension(ident)


def get_toolset_formats_for_type(restype: ResourceType) -> tuple[ToolsetFormat, ...]:
    return tuple(fmt for fmt in ToolsetFormat if fmt.target_type() == restype)


def iter_resource_formats() -> tuple[RESOURCE_FORMAT, ...]:
    return (*tuple(ResourceType), *tuple(ToolsetFormat))


for _toolset_format in ToolsetFormat:
    setattr(ResourceType, _toolset_format.name, _toolset_format)
