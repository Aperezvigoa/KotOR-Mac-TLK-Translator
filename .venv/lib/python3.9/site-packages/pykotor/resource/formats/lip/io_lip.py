"""Binary LIP (lip sync) read/write: LIP V1.0 format with keyframe time and shape data."""

from __future__ import annotations

from typing import TYPE_CHECKING

import kaitaistruct

from bioware_kaitai_formats.lip import Lip

from pykotor.common.stream import BinaryReader
from pykotor.resource.formats.lip.lip_data import LIP, LIPShape
from pykotor.resource.type import ResourceReader, ResourceWriter, autoclose

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


def _lip_shape_from_kaitai(shape) -> LIPShape:
    v = shape if isinstance(shape, int) else int(shape.value)
    return LIPShape(v)


def _load_lip_from_kaitai(data: bytes) -> LIP:
    parsed = Lip.from_bytes(data)
    if parsed.file_type != "LIP ":
        msg = "The file type that was loaded is invalid."
        raise TypeError(msg)
    if parsed.file_version != "V1.0":
        msg = "The LIP version that was loaded is not supported."
        raise TypeError(msg)
    lip = LIP()
    lip.length = parsed.length
    for k in parsed.keyframes:
        lip.add(k.timestamp, _lip_shape_from_kaitai(k.shape))
    return lip


def _load_lip_legacy(reader: BinaryReader) -> LIP:
    lip = LIP()
    file_type = reader.read_string(4)
    file_version = reader.read_string(4)

    if file_type != "LIP ":
        msg = "The file type that was loaded is invalid."
        raise TypeError(msg)

    if file_version != "V1.0":
        msg = "The LIP version that was loaded is not supported."
        raise TypeError(msg)

    lip.length = reader.read_single()
    entry_count = reader.read_uint32()

    for _ in range(entry_count):
        time = reader.read_single()
        shape = LIPShape(reader.read_uint8())
        lip.add(time, shape)

    return lip


class LIPBinaryReader(ResourceReader):
    """Reads LIP (Lip Sync) files.

    LIP files store lip-sync animation data for character speech, mapping time points
    to mouth shapes for synchronized lip movement during voice-over playback.

    Observed retail behavior:
    ----------
        KotOR resolves ``.lip`` resources for VO lines and plays the keyframe stream against the
        matching WAV; layout matches ``lip_data``.

    """

    def __init__(
        self,
        source: SOURCE_TYPES,
        offset: int = 0,
        size: int = 0,
    ):
        super().__init__(source, offset, size)
        self._lip: LIP | None = None

    @autoclose
    def load(self, *, auto_close: bool = True) -> LIP:  # noqa: FBT001, FBT002, ARG002
        data = self._reader.read_all()
        try:
            self._lip = _load_lip_from_kaitai(data)
        except kaitaistruct.KaitaiStructError:
            self._lip = _load_lip_legacy(BinaryReader.from_bytes(data, 0))
        return self._lip


class LIPBinaryWriter(ResourceWriter):
    HEADER_SIZE = 16
    LIP_ENTRY_SIZE = 5

    def __init__(
        self,
        lip: LIP,
        target: TARGET_TYPES,
    ):
        super().__init__(target)
        self._lip: LIP = lip

    @autoclose
    def write(self, *, auto_close: bool = True):  # noqa: FBT001, FBT002, ARG002  # pyright: ignore[reportUnusedParameters]
        self._writer.write_string("LIP ")
        self._writer.write_string("V1.0")
        self._writer.write_single(self._lip.length)
        self._writer.write_uint32(len(self._lip))

        for keyframe in self._lip:
            self._writer.write_single(keyframe.time)
            self._writer.write_uint8(keyframe.shape.value)
