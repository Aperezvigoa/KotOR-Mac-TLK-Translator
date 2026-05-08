"""Binary BIF/BZF read/write: resource table and optional LZMA payload for BZF."""

from __future__ import annotations

import lzma

from typing import TYPE_CHECKING

import kaitaistruct

from bioware_kaitai_formats.bif import Bif
from bioware_kaitai_formats.bzf import Bzf

from pykotor.common.misc import ResRef
from pykotor.common.stream import BinaryReader
from pykotor.resource.formats.bif.bif_data import BIF, BIFResource, BIFType
from pykotor.resource.type import ResourceReader, ResourceType, ResourceWriter, autoclose

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


_LZMA_RAW_FILTERS: list[dict[str, int]] = [{"id": lzma.FILTER_LZMA1}]


def _decompress_bzf_payload(payload: bytes, expected_size: int) -> bytes:
    """Handle both raw and containerised LZMA payloads, tolerating 4-byte padding."""
    try:
        data = lzma.decompress(payload, format=lzma.FORMAT_RAW, filters=_LZMA_RAW_FILTERS)
    except lzma.LZMAError:
        cleaned_payload = payload
        while True:
            try:
                decompressor = lzma.LZMADecompressor()
                data = decompressor.decompress(cleaned_payload)
            except lzma.LZMAError:
                stripped = cleaned_payload.rstrip(b"\0")
                if len(stripped) == len(cleaned_payload):
                    raise
                cleaned_payload = stripped
                continue

            leftover = getattr(decompressor, "unused_data", b"")
            if leftover and any(byte != 0 for byte in leftover):
                cleaned_payload = cleaned_payload[: len(cleaned_payload) - len(leftover)]
                continue

            break

    if len(data) != expected_size:
        msg = f"Decompressed size mismatch: got {len(data)}, expected {expected_size}"
        raise lzma.LZMAError(msg)

    return data


def _load_bif_from_kaitai(data: bytes) -> BIF:
    """Parse uncompressed BIFF via Kaitai (table only); load payloads with PyKotor WOK rules."""
    parsed = Bif.from_bytes(data)
    bif = BIF()
    bif.bif_type = BIFType.BIF
    vt = parsed.var_resource_table
    if vt is None or not vt.entries:
        bif.build_lookup_tables()
        return bif
    for e in vt.entries:
        res_type = ResourceType.from_id(int(e.resource_type))
        resource = BIFResource(
            ResRef.from_blank(), res_type, b"", int(e.resource_id), int(e.file_size)
        )
        resource.offset = int(e.offset)
        bif.resources.append(resource)
    reader_size = len(data)
    for i in range(1, len(bif.resources)):
        prev = bif.resources[i - 1]
        prev.packed_size = bif.resources[i].offset - prev.offset
    if bif.resources:
        bif.resources[-1].packed_size = reader_size - bif.resources[-1].offset
    br = BinaryReader.from_bytes(data, 0)
    for resource in bif.resources:
        br.seek(resource.offset)
        read_len = resource.size
        if (
            resource.restype == ResourceType.WOK
            and getattr(resource, "packed_size", 0)
            and resource.packed_size > resource.size
        ):
            read_len = resource.packed_size
        resource.data = br.read_bytes(read_len)
    bif.build_lookup_tables()
    return bif


def _load_bif_legacy(reader: BinaryReader) -> BIF:
    """Original BIF/BZF reader (BZF and Kaitai fallback)."""
    bif = BIF()

    signature: str = reader.read_string(8)

    if signature[:4] == BIFType.BIF.value:
        bif.bif_type = BIFType.BIF
    elif signature[:4] == BIFType.BZF.value:
        bif.bif_type = BIFType.BZF
    else:
        msg = f"Invalid BIF/BZF file type: {signature[:4]}"
        raise ValueError(msg)

    if signature[4:] != "V1  " and signature[4:] != "V1.1":
        msg = f"Unsupported BIF/BZF version: {signature[4:]}"
        raise ValueError(msg)

    var_res_count = reader.read_uint32()
    fixed_res_count = reader.read_uint32()
    data_offset = reader.read_uint32()

    if fixed_res_count > 0:
        msg = "Fixed resources not supported"
        raise ValueError(msg)

    reader.seek(data_offset)

    for i in range(var_res_count):
        key_id: int = reader.read_uint32()
        offset: int = reader.read_uint32()
        size: int = reader.read_uint32()
        res_type: ResourceType = ResourceType.from_id(reader.read_uint32())

        resource = BIFResource(ResRef.from_blank(), res_type, b"", key_id, size)
        resource.offset = offset

        if bif.bif_type == BIFType.BZF and i > 0:
            prev_resource: BIFResource = bif.resources[-1]
            prev_resource.packed_size = offset - prev_resource.offset

        bif.resources.append(resource)

    if bif.bif_type == BIFType.BZF and bif.resources:
        last_resource: BIFResource = bif.resources[-1]
        last_resource.packed_size = reader.size() - last_resource.offset

    if bif.bif_type == BIFType.BIF and bif.resources:
        for idx in range(1, len(bif.resources)):
            prev = bif.resources[idx - 1]
            prev.packed_size = bif.resources[idx].offset - prev.offset
        bif.resources[-1].packed_size = reader.size() - bif.resources[-1].offset

    for resource in bif.resources:
        reader.seek(resource.offset)

        if bif.bif_type == BIFType.BZF:
            compressed: bytes = reader.read_bytes(resource.packed_size)
            try:
                resource.data = _decompress_bzf_payload(compressed, resource.size)
            except lzma.LZMAError as e:  # noqa: PERF203
                msg = f"Failed to decompress BZF resource: {e}"
                raise ValueError(msg) from e
        else:
            read_len = resource.size
            if (
                resource.restype == ResourceType.WOK
                and getattr(resource, "packed_size", 0)
                and resource.packed_size > resource.size
            ):
                read_len = resource.packed_size
            resource.data = reader.read_bytes(read_len)

    bif.build_lookup_tables()
    return bif


class BIFBinaryReader(ResourceReader):
    """Reads BIF/BZF files.

    BIF (BioWare Index File) files contain game resources indexed by KEY files.
    BZF files are compressed BIF files using LZMA compression.

    References:
    ----------
        Resolution follows the packed resource identifiers described in ``key_data``.

        Note: BIF (BioWare Index File) files contain game resources indexed by KEY files.
        BZF files are compressed BIF files using LZMA compression. The engine uses BIF
        files as the primary resource storage format, with KEY files providing the index.

    Missing Features:
    ----------------
        - Fixed-slot BIF entries (not modeled here)
    """

    def __init__(
        self,
        source: SOURCE_TYPES,
        offset: int = 0,
        size: int = 0,
    ):
        super().__init__(source, offset, size)
        self.bif: BIF = BIF()

    @autoclose
    def load(self, *, auto_close: bool = True) -> BIF:  # noqa: FBT001, FBT002, ARG002
        """Load BIF/BZF data from source."""
        data = self._reader.read_all()
        if len(data) >= 4 and data[:4] == b"BIFF":
            try:
                self.bif = _load_bif_from_kaitai(data)
                return self.bif
            except kaitaistruct.KaitaiStructError:
                pass
        elif len(data) >= 4 and data[:4] == b"BZF ":
            try:
                Bzf.from_bytes(data)
            except kaitaistruct.KaitaiStructError:
                pass
        self.bif = _load_bif_legacy(BinaryReader.from_bytes(data, 0))
        return self.bif


class BIFBinaryWriter(ResourceWriter):
    """Writes BIF/BZF files."""

    def __init__(
        self,
        bif: BIF,
        target: TARGET_TYPES,
    ):
        super().__init__(target)
        self.bif: BIF = bif
        self._data_offset: int = 0

    @autoclose
    def write(self, *, auto_close: bool = True) -> None:  # noqa: FBT001, FBT002, ARG002  # pyright: ignore[reportUnusedParameters]
        """Write BIF/BZF data to target."""
        self._write_header()
        self._write_resource_table()
        self._write_resource_data()

    def _write_header(self) -> None:
        """Write BIF/BZF file header."""
        # Write signature
        self._writer.write_string(self.bif.bif_type.value)
        self._writer.write_string("V1  ")

        # Write counts and offset to resource table (always right after header)
        self._writer.write_uint32(self.bif.var_count)
        self._writer.write_uint32(self.bif.fixed_count)
        self._writer.write_uint32(BIF.HEADER_SIZE)  # Offset to variable resource table (20 bytes)

    def _write_resource_table(self) -> None:
        """Write BIF/BZF resource table."""
        # Calculate absolute file offsets for resource data
        # Data section starts after header and resource table
        data_section_offset = BIF.HEADER_SIZE + (self.bif.var_count * BIF.VAR_ENTRY_SIZE)
        current_offset = data_section_offset

        for resource in self.bif.resources:
            # Align resource data to 4-byte boundary
            if current_offset % 4 != 0:
                current_offset += 4 - (current_offset % 4)
            resource.offset = current_offset

            if self.bif.bif_type == BIFType.BZF:
                # For BZF, compress the data to get size using raw LZMA1 format
                compressed: bytes = lzma.compress(
                    resource.data, format=lzma.FORMAT_RAW, filters=_LZMA_RAW_FILTERS
                )
                resource.packed_size = len(compressed)
                current_offset += resource.packed_size
            else:
                current_offset += resource.size

        # Write resource table entries with absolute file offsets
        for resource in self.bif.resources:
            self._writer.write_uint32(resource.resname_key_index)
            self._writer.write_uint32(resource.offset)  # Absolute file offset
            self._writer.write_uint32(resource.size)
            self._writer.write_uint32(resource.restype.type_id)

    def _write_resource_data(self) -> None:
        """Write BIF/BZF resource data."""
        for resource in self.bif.resources:
            # Align to 4-byte boundary
            current_pos: int = self._writer.position()
            calc: int = current_pos % 4
            if calc != 0:
                self._writer.write_bytes(bytes(4 - calc))

            if self.bif.bif_type == BIFType.BZF:
                # Write compressed data for BZF using raw LZMA1 format
                compressed: bytes = lzma.compress(
                    resource.data, format=lzma.FORMAT_RAW, filters=_LZMA_RAW_FILTERS
                )
                self._writer.write_bytes(compressed)
            else:
                # Write raw data for BIF
                self._writer.write_bytes(resource.data)
