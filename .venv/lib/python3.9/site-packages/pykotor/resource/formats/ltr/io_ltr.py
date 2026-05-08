"""Binary LTR (letter) read/write: Markov chain tables for random name generation."""

from __future__ import annotations

import itertools

from typing import TYPE_CHECKING

import kaitaistruct

from bioware_kaitai_formats.ltr import Ltr

from pykotor.common.stream import BinaryReader
from pykotor.resource.formats.ltr.ltr_data import LTR
from pykotor.resource.type import ResourceReader, ResourceWriter

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


def _ltr_from_kaitai(parsed: Ltr) -> LTR | None:
    """Map a parsed ``Ltr`` into :class:`LTR` when it matches KotOR's fixed 28-letter alphabet."""
    if parsed.file_type != "LTR " or parsed.file_version != "V1.0":
        return None
    if parsed.letter_count != 28:
        return None
    ltr = LTR()
    singles = parsed.single_letter_block
    ltr._singles._start = list(singles.start_probabilities)
    ltr._singles._middle = list(singles.middle_probabilities)
    ltr._singles._end = list(singles.end_probabilities)
    for i, block in enumerate(parsed.double_letter_blocks.blocks):
        ltr._doubles[i]._start = list(block.start_probabilities)
        ltr._doubles[i]._middle = list(block.middle_probabilities)
        ltr._doubles[i]._end = list(block.end_probabilities)
    for i, row in enumerate(parsed.triple_letter_blocks.rows):
        for j, block in enumerate(row.blocks):
            ltr._triples[i][j]._start = list(block.start_probabilities)
            ltr._triples[i][j]._middle = list(block.middle_probabilities)
            ltr._triples[i][j]._end = list(block.end_probabilities)
    return ltr


class LTRBinaryReader(ResourceReader):
    """Reads LTR (Letter) files.

    LTR files contain Markov chain probability data for generating random names
    during character creation. They use a 3rd-order Markov chain model with
    single-letter, double-letter (bigram), and triple-letter (trigram) probability tables.

    Observed retail behavior:
    ----------
        KotOR loads ``LTR `` / ``V1.0`` tables from the resource tree for the random-name
        picker; structure matches ``ltr_data`` (single-, double-, and triple-letter blocks).

    Note: LTR files are used for random name generation during character creation.
    """

    def __init__(
        self,
        source: SOURCE_TYPES,
        offset: int = 0,
        size: int = 0,
    ):
        super().__init__(source, offset, size)

        # LTR instance to be populated during loading
        self._ltr: LTR | None = None

    def load(
        self,
        auto_close: bool = True,
    ) -> LTR:
        # Initialize LTR instance
        self._ltr = LTR()

        data = self._reader.read_all()
        try:
            parsed_ltr = Ltr.from_bytes(data)
        except kaitaistruct.KaitaiStructError:
            parsed_ltr = None
        else:
            mapped = _ltr_from_kaitai(parsed_ltr)
            if mapped is not None:
                self._ltr = mapped
                if auto_close:
                    self._reader.close()
                return self._ltr

        self._reader = BinaryReader.from_bytes(data, 0)

        # Read header: file type ("LTR ") and version ("V1.0")
        file_type = self._reader.read_string(4)
        file_version = self._reader.read_string(4)

        if file_type != "LTR ":
            msg = "The file type that was loaded is invalid."
            raise TypeError(msg)

        if file_version != "V1.0":
            msg = "The LTR version that was loaded is not supported."
            raise TypeError(msg)

        # Read letter count (must be 28 for KotOR, 26 or 28 for NWN)
        letter_count = self._reader.read_uint8()
        if letter_count != 28:
            msg = "LTR files that do not handle exactly 28 characters are not supported."
            raise TypeError(msg)

        # Read single-letter probability block (start, middle, end arrays)
        self._ltr._singles._start = [self._reader.read_single() for _ in range(28)]
        self._ltr._singles._middle = [self._reader.read_single() for _ in range(28)]
        self._ltr._singles._end = [self._reader.read_single() for _ in range(28)]

        # Read double-letter probability blocks (28 blocks, one per previous character)
        for i in range(28):
            self._ltr._doubles[i]._start = [self._reader.read_single() for _ in range(28)]
            self._ltr._doubles[i]._middle = [self._reader.read_single() for _ in range(28)]
            self._ltr._doubles[i]._end = [self._reader.read_single() for _ in range(28)]

        # Read triple-letter probability blocks (28x28 blocks, indexed by previous two characters)
        for i in range(28):
            for j in range(28):
                self._ltr._triples[i][j]._start = [self._reader.read_single() for _ in range(28)]
                self._ltr._triples[i][j]._middle = [self._reader.read_single() for _ in range(28)]
                self._ltr._triples[i][j]._end = [self._reader.read_single() for _ in range(28)]

        if auto_close:
            self._reader.close()

        return self._ltr


class LTRBinaryWriter(ResourceWriter):
    def __init__(
        self,
        ltr: LTR,
        target: TARGET_TYPES,
    ):
        super().__init__(target)
        self._ltr: LTR = ltr

    def write(
        self,
        auto_close: bool = True,
    ):
        self._writer.write_string("LTR V1.0")
        self._writer.write_uint8(28)

        for chance in self._ltr._singles._start:
            self._writer.write_single(chance)
        for chance in self._ltr._singles._middle:
            self._writer.write_single(chance)
        for chance in self._ltr._singles._end:
            self._writer.write_single(chance)

        for i in range(28):
            for chance in self._ltr._doubles[i]._start:
                self._writer.write_single(chance)
            for chance in self._ltr._doubles[i]._middle:
                self._writer.write_single(chance)
            for chance in self._ltr._doubles[i]._end:
                self._writer.write_single(chance)

        for i, j in itertools.product(range(28), range(28)):
            for chance in self._ltr._triples[i][j]._start:
                self._writer.write_single(chance)
            for chance in self._ltr._triples[i][j]._middle:
                self._writer.write_single(chance)
            for chance in self._ltr._triples[i][j]._end:
                self._writer.write_single(chance)

        if auto_close:
            self._writer.close()
