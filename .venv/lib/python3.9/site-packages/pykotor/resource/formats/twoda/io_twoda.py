"""Binary 2DA read/write: ``2DA `` + ``V2.b`` on-disk layout (game archive format)."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import kaitaistruct

from bioware_kaitai_formats.twoda import Twoda
from kaitaistruct import KaitaiStream

from pykotor.common.stream import BinaryReader
from pykotor.resource.formats.twoda.twoda_data import TwoDA
from pykotor.resource.type import ResourceReader, ResourceWriter, autoclose

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


def _twoda_binary_column_tab_count(data: bytes) -> int:
    """Count tab separators in the V2.b column header blob (matches TwoDABinaryReader column loop)."""
    if len(data) < 10:
        return 0
    if data[:4] != b"2DA " or data[4:8] != b"V2.b" or data[8:9] != b"\n":
        return 0
    idx = 9
    while idx < len(data) and data[idx] != 0:
        idx += 1
    return data[9:idx].count(b"\t")


def _twoda_cell_string(raw: str, offset: int) -> str:
    if offset < 0 or offset >= len(raw):
        return ""
    nul = raw.find("\0", offset)
    if nul == -1:
        return raw[offset:]
    return raw[offset:nul]


def _load_twoda_from_kaitai(data: bytes) -> TwoDA:
    column_tab_count = _twoda_binary_column_tab_count(data)
    if column_tab_count <= 0:
        msg = "The 2DA column header section is invalid."
        raise ValueError(msg)
    parsed = Twoda(column_tab_count, KaitaiStream(BytesIO(data)))
    twoda = TwoDA()
    columns = [h for h in parsed.column_headers_raw.split("\t") if h]
    for header in columns:
        twoda.add_column(header)
    headers = twoda.get_headers()
    column_count = len(headers)
    if column_count != column_tab_count:
        msg = "The 2DA column header section does not match the tab-separated layout."
        raise ValueError(msg)
    for row_entry in parsed.row_labels_section.labels:
        twoda.add_row(row_entry.label_value)
    raw_cells = parsed.cell_values_section.raw_data
    for i, off in enumerate(parsed.cell_offsets):
        column_id = i % column_count
        row_id = i // column_count
        twoda.set_cell(row_id, headers[column_id], _twoda_cell_string(raw_cells, off))
    return twoda


def _load_twoda_legacy(reader: BinaryReader) -> TwoDA:
    twoda = TwoDA()

    file_type: str = reader.read_string(4)
    file_version: str = reader.read_string(4)

    if file_type != "2DA ":
        msg = "The file type that was loaded is invalid."
        raise TypeError(msg)

    if file_version != "V2.b":
        msg = "The 2DA version that was loaded is not supported."
        raise TypeError(msg)

    reader.read_uint8()  # \n

    columns: list[str] = []
    while reader.peek() != b"\0":
        column_header: str = reader.read_terminated_string("\t")
        twoda.add_column(column_header)
        columns.append(column_header)

    reader.read_uint8()  # \0

    row_count: int = reader.read_uint32()
    column_count: int = twoda.get_width()
    cell_count: int = row_count * column_count
    for _ in range(row_count):
        row_header: str = reader.read_terminated_string("\t")
        row_label: str = row_header
        twoda.add_row(row_label)

    cell_offsets: list[int] = []
    for _ in range(cell_count):
        cell_offsets.append(reader.read_uint16())

    _cell_data_size: int = reader.read_uint16()
    cell_data_offset: int = reader.position()

    for i in range(cell_count):
        column_id: int = i % column_count
        row_id: int = i // column_count
        column_header = columns[column_id]
        reader.seek(cell_data_offset + cell_offsets[i])

        cell_value: str = reader.read_terminated_string("\0")
        twoda.set_cell(row_id, column_header, cell_value)

    return twoda


class TwoDABinaryReader(ResourceReader):
    """Reads 2DA (Two-Dimensional Array) files.

    2DA files store tabular data used throughout KotOR for game configuration, item stats,
    spell data, and other structured information.

    Observed retail behavior:
    ----------
        Shipped data overwhelmingly uses compact binary ``2DA V2.b``; ASCII ``2DA V2.0`` also
        appears in tools and some distributions.

        ASCII V2.0 / CSV / JSON are handled by other modules in this package (e.g. ``io_twoda_csv``).

    Implementation note: cells are read with terminated-string semantics; other stacks may use
    different C-string helpers with explicit limits.

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
        """Loads a 2DA file from the provided reader.

        Args:
        ----
            auto_close: Whether to close the reader after loading - default True

        Returns:
        -------
            TwoDA: The loaded TwoDA object

        Processing Logic:
        ----------------
            - Read file header and validate type and version
            - Read column headers
            - Read row count and populate rows
            - Read cell offsets
            - Seek to cell data and populate cells
        """
        data = self._reader.read_all()
        try:
            self._twoda = _load_twoda_from_kaitai(data)
        except (kaitaistruct.KaitaiStructError, ValueError):
            self._twoda = _load_twoda_legacy(BinaryReader.from_bytes(data, 0))
        return self._twoda


class TwoDABinaryWriter(ResourceWriter):
    def __init__(
        self,
        twoda: TwoDA,
        target: TARGET_TYPES,
    ):
        super().__init__(target)
        self._twoda: TwoDA = twoda

    @autoclose
    def write(self, *, auto_close: bool = True) -> None:  # noqa: FBT001, FBT002, ARG002  # pyright: ignore[reportUnusedParameters]
        """Writes the 2DA data to a binary file.

        Args:
        ----
            auto_close: {Whether to close the writer after writing is complete}

        Returns:
        -------
            None: {Nothing is returned}

        Processing Logic:
        ----------------
            - Get the headers and row labels from the 2DA
            - Write the header string and version
            - Write the headers and row labels
            - Loop through each cell and writes the value offsets and data
            - Close the writer if auto_close is True
        """
        headers: list[str] = self._twoda.get_headers()

        self._writer.write_string("2DA ")
        self._writer.write_string("V2.b")

        self._writer.write_string("\n")
        for header in headers:
            self._writer.write_string(header + "\t")
        self._writer.write_string("\0")

        self._writer.write_uint32(self._twoda.get_height())
        for row_label in self._twoda.get_labels():
            self._writer.write_string(str(row_label) + "\t")

        values: list[str] = []
        value_offsets: list[int] = []
        value_to_offset: dict[str, int] = {}  # O(1) lookup instead of values.index(value) per cell
        cell_offsets: list[int] = []
        data_size: int = 0

        for row in self._twoda:
            for header in self._twoda.get_headers():
                value = row.get_string(header) + "\0"
                if value not in value_to_offset:
                    value_offset = len(values[-1]) + value_offsets[-1] if value_offsets else 0
                    value_to_offset[value] = value_offset
                    values.append(value)
                    value_offsets.append(value_offset)
                    data_size += len(value)
                cell_offsets.append(value_to_offset[value])

        for cell_offset in cell_offsets:
            self._writer.write_uint16(cell_offset)
        self._writer.write_uint16(data_size)

        for value in values:
            self._writer.write_string(value)
