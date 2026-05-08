# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class Bzf(KaitaiStruct):
    """BZF (BioWare Zipped File) files are LZMA-compressed BIF files used primarily in iOS
    (and maybe Android) ports of KotOR. The BZF header contains "BZF " + "V1.0", followed
    by LZMA-compressed BIF data. Decompression reveals a standard BIF structure.
    
    Format Structure:
    - Header (8 bytes): File type signature "BZF " and version "V1.0"
    - Compressed Data: LZMA-compressed BIF file data
    
    After decompression, the data follows the standard BIF format structure.
    
    References:
    - BIF.ksy - Standard BIF format (decompressed BZF data matches this)
    """
    def __init__(self, _io, _parent=None, _root=None):
        super(Bzf, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.file_type = (self._io.read_bytes(4)).decode(u"ASCII")
        if not self.file_type == u"BZF ":
            raise kaitaistruct.ValidationNotEqualError(u"BZF ", self.file_type, self._io, u"/seq/0")
        self.version = (self._io.read_bytes(4)).decode(u"ASCII")
        if not self.version == u"V1.0":
            raise kaitaistruct.ValidationNotEqualError(u"V1.0", self.version, self._io, u"/seq/1")
        self.compressed_data = []
        i = 0
        while not self._io.is_eof():
            self.compressed_data.append(self._io.read_u1())
            i += 1



    def _fetch_instances(self):
        pass
        for i in range(len(self.compressed_data)):
            pass



