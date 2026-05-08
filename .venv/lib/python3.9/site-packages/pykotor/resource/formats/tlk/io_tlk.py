"""Binary TLK (talk table) read/write: string entries, sound refs, and flags."""

from __future__ import annotations

import struct

from typing import TYPE_CHECKING

import kaitaistruct

from bioware_kaitai_formats.tlk import Tlk

from pykotor.common.language import Language
from pykotor.common.misc import ResRef, WrappedInt
from pykotor.common.stream import ArrayHead, BinaryReader
from pykotor.resource.formats.tlk.tlk_data import TLK
from pykotor.resource.type import ResourceReader, ResourceWriter, autoclose

if TYPE_CHECKING:
    from pykotor.resource.formats.tlk.tlk_data import TLKEntry
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES

_FILE_HEADER_SIZE = 20
_ENTRY_SIZE = 40


def _sound_resref_from_tlk_field(raw16: str) -> str:
    if "\0" in raw16:
        return raw16[: raw16.index("\0")].rstrip("\0").replace("\0", "")
    return raw16.replace("\0", "")


def _load_tlk_from_kaitai(data: bytes, language: Language | None) -> TLK:
    parsed = Tlk.from_bytes(data)
    h = parsed.header
    if h.file_type != "TLK ":
        msg = "Invalid file type."
        raise ValueError(msg)
    if h.file_version != "V3.0":
        msg = "Invalid file version."
        raise ValueError(msg)

    tlk = TLK()
    tlk.language = Language(h.language_id) if language is None else language
    tlk.resize(h.string_count)

    enc = tlk.language.get_encoding()
    for i, k in enumerate(parsed.string_data_table.entries):
        entry = tlk.entries[i]
        entry.text_present = k.text_present
        entry.sound_present = k.sound_present
        entry.soundlength_present = k.sound_length_present
        entry.voiceover = ResRef(_sound_resref_from_tlk_field(k.sound_resref))
        entry.sound_length = k.sound_length
        off = h.entries_offset + k.text_offset
        raw = data[off : off + k.text_length]
        if entry.text_present and k.text_length > 0:
            entry.text = raw.decode(enc or "cp1252", errors="replace")
            if "\0" in entry.text:
                entry.text = entry.text[: entry.text.index("\0")]
        else:
            entry.text = ""

    return tlk


def _load_tlk_legacy(reader: BinaryReader, language: Language | None) -> TLK:
    tlk = TLK()
    texts_offset = 0
    text_headers: list[ArrayHead] = []

    file_type = reader.read_string(4)
    file_version = reader.read_string(4)
    language_id = reader.read_uint32()
    string_count = reader.read_uint32()
    entries_offset = reader.read_uint32()

    if file_type != "TLK ":
        msg = "Invalid file type."
        raise ValueError(msg)
    if file_version != "V3.0":
        msg = "Invalid file version."
        raise ValueError(msg)

    tlk.language = Language(language_id) if language is None else language
    tlk.resize(string_count)
    texts_offset = entries_offset

    if string_count == 0:
        return tlk

    entries_start = _FILE_HEADER_SIZE
    entries_size = string_count * _ENTRY_SIZE
    reader.seek(entries_start)
    entries_data = reader.read_bytes(entries_size)

    for stringref in range(string_count):
        entry = tlk.entries[stringref]
        offset = stringref * _ENTRY_SIZE
        (entry_flags,) = struct.unpack("<I", entries_data[offset : offset + 4])
        sound_resref_bytes = entries_data[offset + 4 : offset + 20]
        null_pos = sound_resref_bytes.find(b"\x00")
        if null_pos >= 0:
            sound_resref_bytes = sound_resref_bytes[:null_pos]
        sound_resref = sound_resref_bytes.decode("ascii", errors="ignore")
        _volume_variance, _pitch_variance, text_offset, text_length = struct.unpack(
            "<IIII", entries_data[offset + 20 : offset + 36]
        )
        (entry.sound_length,) = struct.unpack("<f", entries_data[offset + 36 : offset + 40])

        entry.text_present = (entry_flags & 0x0001) != 0
        entry.sound_present = (entry_flags & 0x0002) != 0
        entry.soundlength_present = (entry_flags & 0x0004) != 0
        entry.voiceover = ResRef(sound_resref)
        text_headers.append(ArrayHead(text_offset, text_length))

    for stringref in range(string_count):
        th = text_headers[stringref]
        reader.seek(th.offset + texts_offset)
        text = reader.read_string(th.length, encoding=tlk.language.get_encoding())
        tlk.entries[stringref].text = text

    return tlk


class TLKBinaryReader(ResourceReader):
    """Reads TLK (Talk Table) files.

    TLK files store localized strings used throughout the game for dialog, item descriptions,
    and other text content. Each entry can have text, sound references, and flags.

    Observed retail behavior:
    ----------
        Matches the binary ``TLK `` / ``V3.0`` layout described in ``tlk_data``.

        Missing Features:
        ----------------
        - ResRef lowercasing for embedded sound ResRefs (not applied on read)

    """

    def __init__(
        self,
        source: SOURCE_TYPES,
        offset: int = 0,
        size: int = 0,
        language: Language | None = None,
    ):
        super().__init__(source, offset, size)
        self._tlk: TLK
        self._language: Language | None = language

    @autoclose
    def load(self, *, auto_close: bool = True) -> TLK:  # noqa: FBT001, FBT002, ARG002
        data = self._reader.read_all()
        try:
            self._tlk = _load_tlk_from_kaitai(data, self._language)
        except kaitaistruct.KaitaiStructError:
            self._tlk = _load_tlk_legacy(BinaryReader.from_bytes(data, 0), self._language)
        return self._tlk


class TLKBinaryWriter(ResourceWriter):
    def __init__(
        self,
        tlk: TLK,
        target: TARGET_TYPES,
    ):
        super().__init__(target)
        self._tlk: TLK = tlk

    @autoclose
    def write(self, auto_close: bool = True):  # noqa: FBT001, FBT002, ARG002
        self._write_file_header()

        text_offset = WrappedInt(0)
        encoding: str | None = self._tlk.language.get_encoding()
        for entry in self._tlk.entries:
            self._write_entry(entry, text_offset)

        for entry in self._tlk.entries:
            self._writer.write_string(entry.text, encoding or "cp1252", errors="replace")

    def _calculate_entries_offset(self) -> int:
        return _FILE_HEADER_SIZE + len(self._tlk) * _ENTRY_SIZE

    def _write_file_header(self):
        language_id: int = self._tlk.language.value
        string_count: int = len(self._tlk)
        entries_offset: int = self._calculate_entries_offset()

        self._writer.write_string("TLK ", string_length=4)
        self._writer.write_string("V3.0", string_length=4)
        self._writer.write_uint32(language_id)
        self._writer.write_uint32(string_count)
        self._writer.write_uint32(entries_offset)

    def _write_entry(
        self,
        entry: TLKEntry,
        previous_offset: WrappedInt,
    ):
        sound_resref = str(entry.voiceover)
        text_offset = previous_offset.get()
        text_length = len(entry.text)

        entry_flags = 0  # Initialize entry_flags as zero
        if entry.text_present:
            entry_flags |= (
                0x0001  # TEXT_PRESENT: As we're writing text, let's assume it's always present
            )
        if entry.sound_present:
            entry_flags |= 0x0002  # SND_PRESENT: If sound_resref is defined in this entry.
        if entry.soundlength_present:
            entry_flags |= 0x0004  # SND_LENGTH: Unused by KOTOR1 and 2. Determines whether the sound length field is utilized.

        self._writer.write_uint32(entry_flags)
        self._writer.write_string(sound_resref, string_length=16)
        self._writer.write_uint32(0)  # unused - volume variance
        self._writer.write_uint32(0)  # unused - pitch variance
        self._writer.write_uint32(text_offset)
        self._writer.write_uint32(text_length)
        self._writer.write_uint32(0)  # unused - sound length

        previous_offset += text_length
