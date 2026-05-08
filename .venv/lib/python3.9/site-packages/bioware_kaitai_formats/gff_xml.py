# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class GffXml(KaitaiStruct):
    """GFF XML format is a human-readable XML representation of GFF (Generic File Format) binary files.
    Used by xoreos-tools and other modding tools for easier editing than binary GFF format.
    
    The XML format represents the hierarchical GFF structure using XML elements:
    - Root element: <gff3>
    - Contains a <struct> element with id attribute
    - Struct contains field elements (byte, uint32, exostring, locstring, resref, list, etc.)
    - Each field has a label attribute
    - Lists contain nested <struct> elements
    
    """
    def __init__(self, _io, _parent=None, _root=None):
        super(GffXml, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.xml_content = (self._io.read_bytes_full()).decode(u"UTF-8")


    def _fetch_instances(self):
        pass


