# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class ItpXml(KaitaiStruct):
    """ITP XML format is a human-readable XML representation of ITP (Palette) binary files.
    ITP files use GFF format (FileType "ITP " in GFF header).
    Uses GFF XML structure with root element <gff3> containing <struct> elements.
    Each field has a label attribute and appropriate type element (byte, uint32, exostring, etc.).
    
    """
    def __init__(self, _io, _parent=None, _root=None):
        super(ItpXml, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.xml_content = (self._io.read_bytes_full()).decode(u"UTF-8")


    def _fetch_instances(self):
        pass


