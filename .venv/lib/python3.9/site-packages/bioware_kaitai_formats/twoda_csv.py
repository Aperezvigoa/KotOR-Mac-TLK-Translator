# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class TwodaCsv(KaitaiStruct):
    """TwoDA CSV format is a human-readable CSV (Comma-Separated Values) representation of TwoDA files.
    Provides easier editing in spreadsheet applications than binary TwoDA format.
    
    Each row represents a data row, with the first row containing column headers.
    
    """
    def __init__(self, _io, _parent=None, _root=None):
        super(TwodaCsv, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.csv_content = (self._io.read_bytes_full()).decode(u"UTF-8")


    def _fetch_instances(self):
        pass


