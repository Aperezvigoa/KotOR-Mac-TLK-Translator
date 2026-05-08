"""CSV read/write for 2DA; first column is row label, rest are data columns."""

from __future__ import annotations

import csv
import io

from typing import TYPE_CHECKING

import kaitaistruct

from bioware_kaitai_formats.twoda_csv import TwodaCsv

from pykotor.resource.formats.twoda.twoda_data import TwoDA
from pykotor.resource.type import ResourceReader, ResourceWriter, autoclose
from pykotor.tools.encoding import decode_bytes_with_fallbacks

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


class TwoDACSVReader(ResourceReader):
    """Reads 2DA files from CSV format.

    CSV is a PyKotor-specific convenience format for easier editing in spreadsheet applications.
    Format: First column is row label, remaining columns are headers.

    Observed retail behavior:
    ----------
        KotOR reads binary ``2DA V2.b`` and ASCII ``2DA V2.0`` sheets from the resource tree.
        Missing core tables produce log lines modders already recognize (for example failures to
        load ``featgain.2da``, ``feat.2da``, ``skills.2da``, or ``spells.2da``).

        Note: CSV format is PyKotor-specific, not a standard game format.
        The engine uses binary 2DA format exclusively. CSV conversion allows easier editing
        in spreadsheet applications.
    """

    def __init__(
        self,
        source: SOURCE_TYPES,
        offset: int = 0,
        size: int = 0,
    ):
        super().__init__(source, offset, size)
        self._twoda: TwoDA | None = None

    @autoclose
    def load(self, *, auto_close: bool = True) -> TwoDA:  # noqa: FBT001, FBT002, ARG002
        self._twoda = TwoDA()
        raw = self._reader.read_all()
        try:
            TwodaCsv.from_bytes(raw)
        except kaitaistruct.KaitaiStructError:
            pass
        data: str = decode_bytes_with_fallbacks(raw)
        _csv = csv.reader(io.StringIO(data))

        try:
            headers: list[str] = next(_csv)[1:]
            if not headers:
                msg = "CSV header is missing or not formatted correctly."
                raise ValueError(msg)

            for header in headers:
                if not header.strip():
                    msg = "Empty header detected, CSV is not valid."
                    raise ValueError(msg)
                self._twoda.add_column(header.strip())

            for i, row in enumerate(_csv, start=1):
                if len(row) != len(headers) + 1:
                    msg = f"Row {i} does not have the correct number of columns."
                    raise ValueError(msg)

                label = row[0]
                if not label.strip():
                    msg = f"Row {i} does not have a valid label."
                    raise ValueError(msg)

                cells = dict(zip(headers, row[1:]))
                self._twoda.add_row(label.strip(), cells)
        except csv.Error as e:
            msg = f"CSV reader error: {e!r}"
            raise ValueError(msg) from e

        return self._twoda


class TwoDACSVWriter(ResourceWriter):
    def __init__(
        self,
        twoda: TwoDA,
        target: TARGET_TYPES,
    ):
        super().__init__(target)
        self._twoda: TwoDA = twoda
        self._csv_string = io.StringIO("")
        self._csv_writer = csv.writer(self._csv_string)

    @autoclose
    def write(self, *, auto_close: bool = True):  # noqa: FBT001, FBT002, ARG002  # pyright: ignore[reportUnusedParameters]
        headers: list[str] = self._twoda.get_headers()

        insert: list[str] = [""]
        insert.extend(iter(headers))
        self._csv_writer.writerow(insert)

        for row in self._twoda:
            insert = [str(row.label())]
            insert.extend(row.get_string(header) for header in headers)
            self._csv_writer.writerow(insert)

        data: bytes = self._csv_string.getvalue().encode("ascii")
        self._writer.write_bytes(data)
