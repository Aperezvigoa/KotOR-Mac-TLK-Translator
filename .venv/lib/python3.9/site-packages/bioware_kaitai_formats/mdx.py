# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class Mdx(KaitaiStruct):
    """MDX (Model Extension) files contain vertex data for MDL models. MDX files work in tandem
    with MDL files which define the model structure, hierarchy, and metadata. The MDX file
    contains the actual vertex positions, normals, texture coordinates, colors, and other
    per-vertex attributes.
    
    Format Structure:
    - Vertex data is organized by mesh and stored at offsets specified in the MDL file
    - Each mesh can have different vertex formats depending on what attributes are present
    - Vertex attributes include: positions, normals, texture coordinates (up to 4 sets),
      vertex colors, tangent space data, and bone weights/indices for skinned meshes
    
    MDX data is referenced from MDL trimesh headers via offsets. The MDL file specifies:
    - mdx_data_offset: Absolute offset to this mesh's vertex data in MDX file
    - mdx_vertex_size: Size in bytes of each vertex
    - mdx_data_flags: Bitmask indicating which vertex attributes are present
    
    References:
    - MDL.ksy - Model structure that references MDX data
    """
    def __init__(self, _io, _parent=None, _root=None):
        super(Mdx, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.vertex_data = []
        i = 0
        while not self._io.is_eof():
            self.vertex_data.append(self._io.read_u1())
            i += 1



    def _fetch_instances(self):
        pass
        for i in range(len(self.vertex_data)):
            pass



