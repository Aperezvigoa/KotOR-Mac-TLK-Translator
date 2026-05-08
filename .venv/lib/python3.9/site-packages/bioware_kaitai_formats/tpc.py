# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class Tpc(KaitaiStruct):
    """TPC (Texture Pack Container) is KotOR's native texture format. It supports paletteless RGB/RGBA,
    greyscale, and block-compressed DXT1/DXT3/DXT5 data, optional mipmaps, cube maps, and flipbook
    animations controlled by companion TXI files.
    
    Binary Format Structure:
    - Header (128 bytes): data_size, alpha_test, width, height, pixel_encoding, mipmap_count, reserved
    - Texture Data: Per layer, per mipmap compressed/uncompressed pixel data
    - Optional TXI Footer: ASCII text metadata appended after texture data
    
    """
    def __init__(self, _io, _parent=None, _root=None):
        super(Tpc, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.header = Tpc.TpcHeader(self._io, self, self._root)
        self.texture_data = Tpc.TextureDataSection(self._io, self, self._root)
        if self._io.pos() < self._io.size():
            pass
            self.txi_footer = Tpc.TxiFooterSection(self._io, self, self._root)



    def _fetch_instances(self):
        pass
        self.header._fetch_instances()
        self.texture_data._fetch_instances()
        if self._io.pos() < self._io.size():
            pass
            self.txi_footer._fetch_instances()


    class PixelDataBlock(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Tpc.PixelDataBlock, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.data = []
            i = 0
            while True:
                _ = self._io.read_u1()
                self.data.append(_)
                if self._io.pos() >= self._io.size():
                    break
                i += 1


        def _fetch_instances(self):
            pass
            for i in range(len(self.data)):
                pass



    class TextureDataSection(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Tpc.TextureDataSection, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.layers = []
            for i in range((6 if  ((self._root.header.is_compressed) and (self._root.header.height != 0) and (self._root.header.width != 0) and (self._root.header.height // self._root.header.width == 6))  else 1)):
                self.layers.append(Tpc.TextureLayer(self._io, self, self._root))



        def _fetch_instances(self):
            pass
            for i in range(len(self.layers)):
                pass
                self.layers[i]._fetch_instances()



    class TextureLayer(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Tpc.TextureLayer, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.mipmaps = []
            for i in range(self._root.header.mipmap_count):
                self.mipmaps.append(Tpc.TextureMipmap(self._io, self, self._root))



        def _fetch_instances(self):
            pass
            for i in range(len(self.mipmaps)):
                pass
                self.mipmaps[i]._fetch_instances()



    class TextureMipmap(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Tpc.TextureMipmap, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.pixel_data = Tpc.PixelDataBlock(self._io, self, self._root)


        def _fetch_instances(self):
            pass
            self.pixel_data._fetch_instances()


    class TpcHeader(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Tpc.TpcHeader, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.data_size = self._io.read_u4le()
            self.alpha_test = self._io.read_f4le()
            self.width = self._io.read_u2le()
            self.height = self._io.read_u2le()
            self.pixel_encoding = self._io.read_u1()
            self.mipmap_count = self._io.read_u1()
            self.reserved = []
            for i in range(114):
                self.reserved.append(self._io.read_u1())



        def _fetch_instances(self):
            pass
            for i in range(len(self.reserved)):
                pass


        @property
        def is_compressed(self):
            """True if texture data is compressed (DXT format)."""
            if hasattr(self, '_m_is_compressed'):
                return self._m_is_compressed

            self._m_is_compressed = self.data_size != 0
            return getattr(self, '_m_is_compressed', None)

        @property
        def is_uncompressed(self):
            """True if texture data is uncompressed (raw pixels)."""
            if hasattr(self, '_m_is_uncompressed'):
                return self._m_is_uncompressed

            self._m_is_uncompressed = self.data_size == 0
            return getattr(self, '_m_is_uncompressed', None)


    class TxiFooterSection(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Tpc.TxiFooterSection, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.txi_data = (self._io.read_bytes_full()).decode(u"ASCII")


        def _fetch_instances(self):
            pass



