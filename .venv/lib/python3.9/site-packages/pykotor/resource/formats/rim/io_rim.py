"""Binary RIM read/write: container format for module resources (ResRef + data)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import kaitaistruct

from bioware_kaitai_formats.rim import Rim

from pykotor.common.stream import BinaryReader
from pykotor.resource.formats.rim.rim_data import RIM
from pykotor.resource.type import ResourceReader, ResourceType, ResourceWriter, autoclose

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


def _rim_resource_type_id(entry: Rim.ResourceEntry) -> int:
    return int(entry.resource_type)


def _load_rim_from_kaitai(data: bytes) -> RIM:
    parsed = Rim.from_bytes(data)
    rim = RIM()
    table = parsed.resource_entry_table
    if table is None or not table.entries:
        return rim
    for entry in table.entries:
        resref = entry.resref.split("\0", 1)[0]
        resref = resref.rstrip("\0")
        restype = ResourceType.from_id(_rim_resource_type_id(entry))
        raw = entry.data
        resdata = bytes(raw) if raw is not None else b""
        rim.set_data(resref, restype, resdata)
    return rim


def _load_rim_legacy(reader: BinaryReader) -> RIM:
    rim = RIM()

    file_type = reader.read_string(4)
    file_version = reader.read_string(4)

    if file_type != "RIM ":
        msg = "The RIM file type that was loaded was unrecognized."
        raise ValueError(msg)

    if file_version != "V1.0":
        msg = "The RIM version that was loaded is not supported."
        raise ValueError(msg)

    reader.skip(4)  # Skip 0x08 (4 bytes)
    entry_count = reader.read_uint32()  # 0x0C
    offset_to_keys = reader.read_uint32()  # 0x10
    reader.skip(4)  # RIM header: reserved field at file offset 0x14 (see rim_data layout table)

    if offset_to_keys == 0:
        offset_to_keys = 120

    _read_rim_entries(rim, reader, entry_count, offset_to_keys, reader.size())
    return rim


def _read_rim_entries(
    rim: RIM, reader: BinaryReader, entry_count: int, offset_to_keys: int, stream_size: int
):
    resrefs: list[str] = []
    resids: list[int] = []
    restypes: list[int] = []
    resoffsets: list[int] = []
    ressizes: list[int] = []

    if entry_count > 0 and offset_to_keys >= stream_size:
        msg = "The RIM file is malformed: offset to keys is out of bounds."
        raise ValueError(msg)

    if offset_to_keys < stream_size:
        reader.seek(offset_to_keys)
        for _ in range(entry_count):
            resref_str = reader.read_string(16).rstrip("\0")
            resrefs.append(resref_str)
            restypes.append(reader.read_uint32())
            resids.append(reader.read_uint32())
            resoffsets.append(reader.read_uint32())
            ressizes.append(reader.read_uint32())

        for i in range(len(resrefs)):
            reader.seek(resoffsets[i])
            resdata = reader.read_bytes(ressizes[i])
            rim.set_data(resrefs[i], ResourceType.from_id(restypes[i]), resdata)


class RIMBinaryReader(ResourceReader):
    """Reads RIM (Resource Information Manager) files.

    RIM files are container formats similar to ERF files, used for module resources.
    They store multiple game resources with ResRef, type, and data.

    References:
    ----------
        RIM IO mirrors the on-disk layout described in ``rim_data``.

        Note: RIM files use similar structure to ERF files but are read-only templates.
        The engine loads RIM files as module blueprints and exports to ERF for runtime mutation.
        Missing Features:
        ----------------
        - ResRef lowercasing (not applied on read)
        - Other readers may permute header/table field order; this module follows ``rim_data``.

    """

    def __init__(
        self,
        source: SOURCE_TYPES,
        offset: int = 0,
        size: int = 0,
    ):
        super().__init__(source, offset, size)
        self._rim: RIM | None = None

    @autoclose
    def load(self, *, auto_close: bool = True) -> RIM:  # noqa: FBT001, FBT002, ARG002
        data = self._reader.read_all()
        try:
            self._rim = _load_rim_from_kaitai(data)
        except kaitaistruct.KaitaiStructError:
            self._rim = _load_rim_legacy(BinaryReader.from_bytes(data, 0))
        return self._rim


class RIMBinaryWriter(ResourceWriter):
    FILE_HEADER_SIZE = 120
    KEY_ELEMENT_SIZE = 32

    def __init__(
        self,
        rim: RIM,
        target: TARGET_TYPES,
    ):
        super().__init__(target)
        self._rim: RIM = rim

    @autoclose
    def write(self, *, auto_close: bool = True):  # noqa: FBT001, FBT002, ARG002  # pyright: ignore[reportUnusedParameters]
        entry_count = len(self._rim)
        # Vanilla uses explicit offsets for keys (120), but 0 for resources (implicit)
        header_offset_to_keys = RIMBinaryWriter.FILE_HEADER_SIZE
        header_offset_to_resources = 0

        # Actual locations
        offset_to_keys = RIMBinaryWriter.FILE_HEADER_SIZE

        self._writer.write_string("RIM ")
        self._writer.write_string("V1.0")
        self._writer.write_uint32(0)  # 0x08
        self._writer.write_uint32(entry_count)  # 0x0C
        self._writer.write_uint32(header_offset_to_keys)  # 0x10
        self._writer.write_uint32(header_offset_to_resources)  # 0x14
        self._writer.write_bytes(b"\0" * 96)  # Padding to 120

        # Align data start to 16 bytes (Vanilla RIM behavior)
        keys_end = offset_to_keys + RIMBinaryWriter.KEY_ELEMENT_SIZE * entry_count
        key_padding = (16 - (keys_end % 16)) % 16

        current_data_offset = keys_end + key_padding
        resource_offsets = []

        # Pass 1: Calculate Offsets with strict vanilla alignment
        for resource in self._rim:
            resource_offsets.append(current_data_offset)

            # Vanilla Resource Padding Logic:
            # 1. Write Data
            # 2. Align to 4 bytes
            # 3. Write 16 bytes of null padding
            # This applies to ALL resources, including the last one (based on file size analysis)

            data_len = len(resource.data)
            current_data_offset += data_len

            padding = (4 - (current_data_offset % 4)) % 4
            current_data_offset += padding + 16

        for resid, resource in enumerate(self._rim):
            self._writer.write_string(str(resource.resref), string_length=16)
            self._writer.write_uint32(resource.restype.type_id)
            self._writer.write_uint32(resid)
            self._writer.write_uint32(resource_offsets[resid])
            self._writer.write_uint32(len(resource.data))

        self._writer.write_bytes(b"\0" * key_padding)

        for resource in self._rim:
            self._writer.write_bytes(resource.data)

            # Write Padding matches calculation
            current_pos = self._writer.position()
            padding = (4 - (current_pos % 4)) % 4
            self._writer.write_bytes(b"\0" * (padding + 16))
