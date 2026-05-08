"""Reading and writing KEY (BIF index) files.

KEY files list BIF archives and map ResRef+ResourceType to (bif_index, res_index).
Used by the game to resolve resource names to data in BIF files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import kaitaistruct

from bioware_kaitai_formats.key import Key

from pykotor.common.misc import ResRef
from pykotor.common.stream import BinaryReader
from pykotor.resource.formats.key.key_data import KEY, BifEntry, KeyEntry
from pykotor.resource.type import ResourceReader, ResourceType, ResourceWriter, autoclose

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES

_KEY_VERSIONS_LEGACY = (KEY.FILE_VERSION, "V1.1")


def _load_key_from_kaitai(data: bytes) -> KEY:
    parsed = Key.from_bytes(data)
    key = KEY()
    key.file_type = parsed.file_type
    key.file_version = parsed.file_version
    key.build_year = parsed.build_year
    key.build_day = parsed.build_day
    ft = parsed.file_table
    if ft is not None and ft.entries:
        for fe in ft.entries:
            bif = BifEntry()
            bif.filesize = fe.file_size
            bif.filename = fe.filename.rstrip("\0").replace("\\", "/").lstrip("/")
            bif.drives = fe.drives
            key.bif_entries.append(bif)
    kt = parsed.key_table
    if kt is not None and kt.entries:
        for ke in kt.entries:
            entry = KeyEntry()
            resref_str = ke.resref.split("\0", 1)[0].rstrip("\0").lower()
            entry.resref = ResRef(resref_str)
            entry.restype = ResourceType.from_id(int(ke.resource_type))
            entry.resource_id = ke.resource_id
            key.key_entries.append(entry)
    key.build_lookup_tables()
    return key


def _load_key_legacy(reader: BinaryReader) -> KEY:
    key = KEY()

    key.file_type = reader.read_string(4)
    key.file_version = reader.read_string(4)

    if key.file_type != KEY.FILE_TYPE:
        msg = f"Invalid KEY file type: {key.file_type}"
        raise ValueError(msg)

    if key.file_version not in _KEY_VERSIONS_LEGACY:
        msg = f"Unsupported KEY version: {key.file_version}"
        raise ValueError(msg)

    bif_count: int = reader.read_uint32()
    key_count: int = reader.read_uint32()
    file_table_offset: int = reader.read_uint32()
    key_table_offset: int = reader.read_uint32()

    key.build_year = reader.read_uint32()
    key.build_day = reader.read_uint32()

    reader.skip(32)

    reader.seek(file_table_offset)
    for _ in range(bif_count):
        bif = BifEntry()
        bif.filesize = reader.read_uint32()
        filename_offset: int = reader.read_uint32()
        filename_size: int = reader.read_uint16()
        bif.drives = reader.read_uint16()

        current_pos: int = reader.position()

        reader.seek(filename_offset)
        bif.filename = reader.read_string(filename_size).rstrip("\0").replace("\\", "/").lstrip("/")

        reader.seek(current_pos)
        key.bif_entries.append(bif)

    reader.seek(key_table_offset)
    for _ in range(key_count):
        entry = KeyEntry()
        resref_str = reader.read_string(16).rstrip("\0").lower()
        entry.resref = ResRef(resref_str)
        entry.restype = ResourceType.from_id(reader.read_uint16())
        entry.resource_id = reader.read_uint32()
        key.key_entries.append(entry)

    key.build_lookup_tables()
    return key


class KEYBinaryReader(ResourceReader):
    """Reads KEY files.

    KEY files index game resources stored in BIF files. They contain references to BIF files
    and resource entries that map ResRefs to locations within those BIF files.

    Observed retail behavior:
    ----------
        The PC builds mmap ``chitin.key`` (and related tables) at startup, walking BIF entries
        before resolving individual resources. Duplicate-key and teardown edge cases match the
        Aurora family.

        Missing Features:
        ----------------
        - ResRef lowercasing (not applied consistently here; some tools normalize case)
        - Resource ID split into BIF index / resource index (packed id handling is minimal)

    """

    def __init__(
        self,
        source: SOURCE_TYPES,
        offset: int = 0,
        size: int = 0,
    ):
        super().__init__(source, offset, size)
        self.key: KEY = KEY()

    @autoclose
    def load(self, *, auto_close: bool = True) -> KEY:  # noqa: FBT001, FBT002, ARG002
        """Load KEY data from source."""
        data = self._reader.read_all()
        try:
            self.key = _load_key_from_kaitai(data)
        except kaitaistruct.KaitaiStructError:
            self.key = _load_key_legacy(BinaryReader.from_bytes(data, 0))
        return self.key


class KEYBinaryWriter(ResourceWriter):
    """Writes KEY files."""

    def __init__(
        self,
        key: KEY,
        target: TARGET_TYPES,
    ):
        super().__init__(target)
        self.key: KEY = key

    @autoclose
    def write(self, *, auto_close: bool = True) -> None:  # noqa: FBT001, FBT002, ARG002  # pyright: ignore[reportUnusedParameters]
        """Write KEY data to target."""
        self._write_header()
        self._write_file_table()
        self._write_key_table()

    def _write_header(self) -> None:
        """Write KEY file header."""
        # Write signature
        self._writer.write_string(self.key.file_type)
        self._writer.write_string(self.key.file_version)

        # Write counts
        self._writer.write_uint32(len(self.key.bif_entries))
        self._writer.write_uint32(len(self.key.key_entries))

        # Write table offsets
        self._writer.write_uint32(self.key.calculate_file_table_offset())
        self._writer.write_uint32(self.key.calculate_key_table_offset())

        # Write build info
        self._writer.write_uint32(self.key.build_year)
        self._writer.write_uint32(self.key.build_day)

        # Write reserved bytes
        self._writer.write_bytes(b"\0" * 32)

    def _write_file_table(self) -> None:
        """Write BIF file table."""
        # Write file entries
        for i, bif in enumerate(self.key.bif_entries):
            self._writer.write_uint32(bif.filesize)
            self._writer.write_uint32(self.key.calculate_filename_offset(i))
            self._writer.write_uint16(len(bif.filename) + 1)  # +1 for null terminator
            self._writer.write_uint16(bif.drives)

        # Write filenames
        for bif in self.key.bif_entries:
            self._writer.write_string(bif.filename)
            self._writer.write_uint8(0)  # Null terminator

    def _write_key_table(self) -> None:
        """Write resource key table."""
        for entry in self.key.key_entries:
            # Write ResRef (padded with nulls to 16 bytes)
            resref: str = str(entry.resref)
            self._writer.write_string(resref)
            self._writer.write_bytes(b"\0" * (16 - len(resref)))

            # Write type and ID
            self._writer.write_uint16(entry.restype.type_id)
            self._writer.write_uint32(entry.resource_id)
