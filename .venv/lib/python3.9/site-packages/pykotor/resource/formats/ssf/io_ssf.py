"""SSF (Sound Set File) files contain mappings from sound event types to string references (StrRefs)
in the TLK file. Each SSF defines a set of 28 sound effects that creatures can play during
various game events (battle cries, pain grunts, selection sounds, etc.). The StrRefs point
to entries in dialog.tlk which contain the actual WAV file references.

Observed retail behavior:
----------
    KotOR maps the 28 fixed creature sound slots to StrRefs in ``dialog.tlk`` using the
    ``SSF `` / ``V1.1`` header and table layout below.

        Binary Format:
        -------------
        Header (12 bytes):
        Offset | Size | Type   | Description
        -------|------|--------|-------------
        0x00   | 4    | char[] | File Type ("SSF ")
        0x04   | 4    | char[] | File Version ("V1.1")
        0x08   | 4    | uint32 | Offset to Sound Table (typically 12)
        Sound Table (112 bytes = 28 entries * 4 bytes):
        Offset | Size | Type   | Description
        -------|------|--------|-------------
        0x00   | 4    | int32  | StrRef for BATTLE_CRY_1
        0x04   | 4    | int32  | StrRef for BATTLE_CRY_2
        ...    | ...  | ...    | ...
        0x6C   | 4    | int32  | StrRef for POISONED
        Each entry is a StrRef (string reference) into dialog.tlk
        Value -1 indicates no sound for that event type
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import kaitaistruct

from bioware_kaitai_formats.ssf import Ssf

from pykotor.common.stream import BinaryReader
from pykotor.resource.formats.ssf.ssf_data import SSF, SSFSound
from pykotor.resource.type import ResourceReader, ResourceWriter, autoclose

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


def _ssf_strref_from_raw(raw: int) -> int:
    return -1 if raw == 0xFFFFFFFF else int(raw)


def _load_ssf_legacy(reader: BinaryReader) -> SSF:
    ssf = SSF()

    file_type = reader.read_string(4)
    file_version = reader.read_string(4)

    if file_type != "SSF ":
        msg = "Attempted to load an invalid SSF was loaded."
        raise ValueError(msg)

    if file_version != "V1.1":
        msg = "The supplied SSF file version is not supported."
        raise ValueError(msg)

    sounds_offset = reader.read_uint32()
    reader.seek(sounds_offset)

    ssf.set_data(SSFSound.BATTLE_CRY_1, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.BATTLE_CRY_2, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.BATTLE_CRY_3, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.BATTLE_CRY_4, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.BATTLE_CRY_5, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.BATTLE_CRY_6, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.SELECT_1, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.SELECT_2, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.SELECT_3, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.ATTACK_GRUNT_1, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.ATTACK_GRUNT_2, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.ATTACK_GRUNT_3, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.PAIN_GRUNT_1, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.PAIN_GRUNT_2, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.LOW_HEALTH, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.DEAD, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.CRITICAL_HIT, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.TARGET_IMMUNE, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.LAY_MINE, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.DISARM_MINE, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.BEGIN_STEALTH, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.BEGIN_SEARCH, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.BEGIN_UNLOCK, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.UNLOCK_FAILED, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.UNLOCK_SUCCESS, reader.read_uint32(max_neg1=True))
    ssf.set_data(
        SSFSound.SEPARATED_FROM_PARTY,
        reader.read_uint32(max_neg1=True),
    )
    ssf.set_data(SSFSound.REJOINED_PARTY, reader.read_uint32(max_neg1=True))
    ssf.set_data(SSFSound.POISONED, reader.read_uint32(max_neg1=True))

    return ssf


def _load_ssf_from_kaitai(data: bytes) -> SSF:
    parsed = Ssf.from_bytes(data)
    ssf = SSF()
    if parsed.sounds is None or parsed.sounds.entries is None:
        raise ValueError("Invalid SSF data")
    for i, entry in enumerate(parsed.sounds.entries):
        ssf.set_data(SSFSound(i), _ssf_strref_from_raw(entry.strref_raw))
    return ssf


class SSFBinaryReader(ResourceReader):
    """Reads SSF (Sound Set File) files.

    SSF files map sound event types to sound resource IDs. Used for creature sound sets
    that define battle cries, grunts, pain sounds, and other audio events.

    Observed retail behavior:
    ----------
        Matches the binary layout summarized in the module docstring and ``ssf_data``.

        Note: SSF files map sound event types (BattleCry, Attack, Pain, etc.) to sound
        resource IDs. Used for creature sound sets that define battle cries, grunts,
        pain sounds, and other audio events.
    """

    def __init__(
        self,
        source: SOURCE_TYPES,
        offset: int = 0,
        size: int = 0,
    ):
        super().__init__(source, offset, size)
        self._ssf: SSF | None = None

    @autoclose
    def load(self, *, auto_close: bool = True) -> SSF:  # noqa: FBT001, FBT002, ARG002
        data = self._reader.read_all()
        try:
            self._ssf = _load_ssf_from_kaitai(data)
        except kaitaistruct.KaitaiStructError:
            self._ssf = _load_ssf_legacy(BinaryReader.from_bytes(data, 0))
        return self._ssf


class SSFBinaryWriter(ResourceWriter):
    def __init__(
        self,
        ssf: SSF,
        target: TARGET_TYPES,
    ):
        super().__init__(target)
        self._ssf: SSF = ssf

    @autoclose
    def write(self, *, auto_close: bool = True):  # noqa: FBT001, FBT002, ARG002  # pyright: ignore[reportUnusedParameters]
        self._writer.write_string("SSF ")
        self._writer.write_string("V1.1")
        self._writer.write_uint32(12)

        for sound in SSFSound:
            self._writer.write_uint32(self._ssf.get(sound) or 0, max_neg1=True)

        for _ in range(12):
            self._writer.write_uint32(0xFFFFFFFF)
