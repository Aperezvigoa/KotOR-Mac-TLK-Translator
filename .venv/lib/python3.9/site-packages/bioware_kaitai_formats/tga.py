# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO
from enum import IntEnum


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class Tga(KaitaiStruct):
    """TGA (Targa) is an uncompressed raster image format used in KotOR for textures.
    TGA files support RGB, RGBA, and greyscale formats with optional RLE compression.
    
    TGA files are commonly converted to TPC format for use in KotOR, but the game
    can also load TGA files directly in some contexts.
    
    Format Structure:
    - Header (18 bytes): Image metadata, dimensions, pixel format
    - Color Map (optional): Palette data for indexed color images
    - Image Data: Raw or RLE-compressed pixel data
    
    References:
    - Standard TGA format specification
    """

    class ColorMapType(IntEnum):
        none = 0
        present = 1

    class ImageType(IntEnum):
        no_image_data = 0
        uncompressed_color_mapped = 1
        uncompressed_rgb = 2
        uncompressed_greyscale = 3
        rle_color_mapped = 9
        rle_rgb = 10
        rle_greyscale = 11
    def __init__(self, _io, _parent=None, _root=None):
        super(Tga, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.id_length = self._io.read_u1()
        self.color_map_type = KaitaiStream.resolve_enum(Tga.ColorMapType, self._io.read_u1())
        self.image_type = KaitaiStream.resolve_enum(Tga.ImageType, self._io.read_u1())
        if self.color_map_type == Tga.ColorMapType.present:
            pass
            self.color_map_spec = Tga.ColorMapSpecification(self._io, self, self._root)

        self.image_spec = Tga.ImageSpecification(self._io, self, self._root)
        if self.id_length > 0:
            pass
            self.image_id = (self._io.read_bytes(self.id_length)).decode(u"ASCII")

        if self.color_map_type == Tga.ColorMapType.present:
            pass
            self.color_map_data = []
            for i in range(self.color_map_spec.length):
                self.color_map_data.append(self._io.read_u1())


        self.image_data = []
        i = 0
        while not self._io.is_eof():
            self.image_data.append(self._io.read_u1())
            i += 1



    def _fetch_instances(self):
        pass
        if self.color_map_type == Tga.ColorMapType.present:
            pass
            self.color_map_spec._fetch_instances()

        self.image_spec._fetch_instances()
        if self.id_length > 0:
            pass

        if self.color_map_type == Tga.ColorMapType.present:
            pass
            for i in range(len(self.color_map_data)):
                pass


        for i in range(len(self.image_data)):
            pass


    class ColorMapSpecification(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Tga.ColorMapSpecification, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.first_entry_index = self._io.read_u2le()
            self.length = self._io.read_u2le()
            self.entry_size = self._io.read_u1()


        def _fetch_instances(self):
            pass


    class ImageSpecification(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Tga.ImageSpecification, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.x_origin = self._io.read_u2le()
            self.y_origin = self._io.read_u2le()
            self.width = self._io.read_u2le()
            self.height = self._io.read_u2le()
            self.pixel_depth = self._io.read_u1()
            self.image_descriptor = self._io.read_u1()


        def _fetch_instances(self):
            pass



