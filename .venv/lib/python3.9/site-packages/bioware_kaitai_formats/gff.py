# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO
from bioware_kaitai_formats import bioware_common
from enum import IntEnum


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class Gff(KaitaiStruct):
    """GFF (Generic File Format) is BioWare's universal container format for structured game data.
    It is used by many KotOR file types including UTC (creature), UTI (item), DLG (dialogue),
    ARE (area), GIT (game instance template), IFO (module info), and many others.
    
    GFF uses a hierarchical structure with structs containing fields, which can be simple values,
    nested structs, or lists of structs. The format supports version V3.2 (KotOR) and later
    versions (V3.3, V4.0, V4.1) used in other BioWare games.
    
    Binary Format Structure:
    - File Header (56 bytes): File type signature (FourCC), version, counts, and offsets to all
      data tables (structs, fields, labels, field_data, field_indices, list_indices)
    - Label Array: Array of 16-byte null-padded field name labels
    - Struct Array: Array of struct entries (12 bytes each) - struct_id, data_or_offset, field_count
    - Field Array: Array of field entries (12 bytes each) - field_type, label_index, data_or_offset
    - Field Data: Storage area for complex field types (strings, binary, vectors, etc.)
    - Field Indices Array: Array of field index arrays (used when structs have multiple fields)
    - List Indices Array: Array of list entry structures (count + struct indices)
    
    Field Types:
    - Simple types (0-5, 8): Stored inline in data_or_offset (uint8, int8, uint16, int16, uint32,
      int32, float)
    - Complex types (6-7, 9-13, 16-17): Offset to field_data section (uint64, int64, double, string,
      resref, localized_string, binary, vector4, vector3)
    - Struct (14): Struct index stored inline (nested struct)
    - List (15): Offset to list_indices_array (list of structs)
    
    Struct Access Pattern:
    1. Root struct is always at struct_array index 0
    2. If struct.field_count == 1: data_or_offset contains direct field index
    3. If struct.field_count > 1: data_or_offset contains offset into field_indices_array
    4. Use field_index to access field_array entry
    5. Use field.label_index to get field name from label_array
    6. Use field.data_or_offset based on field_type (inline, offset, struct index, list offset)
    
    """

    class GffFieldType(IntEnum):
        uint8 = 0
        int8 = 1
        uint16 = 2
        int16 = 3
        uint32 = 4
        int32 = 5
        uint64 = 6
        int64 = 7
        single = 8
        double = 9
        string = 10
        resref = 11
        localized_string = 12
        binary = 13
        struct = 14
        list = 15
        vector4 = 16
        vector3 = 17
    def __init__(self, _io, _parent=None, _root=None):
        super(Gff, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.header = Gff.GffHeader(self._io, self, self._root)


    def _fetch_instances(self):
        pass
        self.header._fetch_instances()
        _ = self.field_array
        if hasattr(self, '_m_field_array'):
            pass
            self._m_field_array._fetch_instances()

        _ = self.field_data
        if hasattr(self, '_m_field_data'):
            pass
            self._m_field_data._fetch_instances()

        _ = self.field_indices_array
        if hasattr(self, '_m_field_indices_array'):
            pass
            self._m_field_indices_array._fetch_instances()

        _ = self.label_array
        if hasattr(self, '_m_label_array'):
            pass
            self._m_label_array._fetch_instances()

        _ = self.list_indices_array
        if hasattr(self, '_m_list_indices_array'):
            pass
            self._m_list_indices_array._fetch_instances()

        _ = self.root_struct_resolved
        if hasattr(self, '_m_root_struct_resolved'):
            pass
            self._m_root_struct_resolved._fetch_instances()

        _ = self.struct_array
        if hasattr(self, '_m_struct_array'):
            pass
            self._m_struct_array._fetch_instances()


    class FieldArray(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Gff.FieldArray, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.entries = []
            for i in range(self._root.header.field_count):
                self.entries.append(Gff.FieldEntry(self._io, self, self._root))



        def _fetch_instances(self):
            pass
            for i in range(len(self.entries)):
                pass
                self.entries[i]._fetch_instances()



    class FieldData(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Gff.FieldData, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.raw_data = self._io.read_bytes(self._root.header.field_data_count)


        def _fetch_instances(self):
            pass


    class FieldEntry(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Gff.FieldEntry, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.field_type = KaitaiStream.resolve_enum(Gff.GffFieldType, self._io.read_u4le())
            self.label_index = self._io.read_u4le()
            self.data_or_offset = self._io.read_u4le()


        def _fetch_instances(self):
            pass

        @property
        def field_data_offset_value(self):
            """Absolute file offset to field data for complex types."""
            if hasattr(self, '_m_field_data_offset_value'):
                return self._m_field_data_offset_value

            if self.is_complex_type:
                pass
                self._m_field_data_offset_value = self._root.header.field_data_offset + self.data_or_offset

            return getattr(self, '_m_field_data_offset_value', None)

        @property
        def is_complex_type(self):
            """True if field stores data in field_data section."""
            if hasattr(self, '_m_is_complex_type'):
                return self._m_is_complex_type

            self._m_is_complex_type =  ((self.field_type == Gff.GffFieldType.uint64) or (self.field_type == Gff.GffFieldType.int64) or (self.field_type == Gff.GffFieldType.double) or (self.field_type == Gff.GffFieldType.string) or (self.field_type == Gff.GffFieldType.resref) or (self.field_type == Gff.GffFieldType.localized_string) or (self.field_type == Gff.GffFieldType.binary) or (self.field_type == Gff.GffFieldType.vector4) or (self.field_type == Gff.GffFieldType.vector3)) 
            return getattr(self, '_m_is_complex_type', None)

        @property
        def is_list_type(self):
            """True if field is a list of structs."""
            if hasattr(self, '_m_is_list_type'):
                return self._m_is_list_type

            self._m_is_list_type = self.field_type == Gff.GffFieldType.list
            return getattr(self, '_m_is_list_type', None)

        @property
        def is_simple_type(self):
            """True if field stores data inline (simple types)."""
            if hasattr(self, '_m_is_simple_type'):
                return self._m_is_simple_type

            self._m_is_simple_type =  ((self.field_type == Gff.GffFieldType.uint8) or (self.field_type == Gff.GffFieldType.int8) or (self.field_type == Gff.GffFieldType.uint16) or (self.field_type == Gff.GffFieldType.int16) or (self.field_type == Gff.GffFieldType.uint32) or (self.field_type == Gff.GffFieldType.int32) or (self.field_type == Gff.GffFieldType.single)) 
            return getattr(self, '_m_is_simple_type', None)

        @property
        def is_struct_type(self):
            """True if field is a nested struct."""
            if hasattr(self, '_m_is_struct_type'):
                return self._m_is_struct_type

            self._m_is_struct_type = self.field_type == Gff.GffFieldType.struct
            return getattr(self, '_m_is_struct_type', None)

        @property
        def list_indices_offset_value(self):
            """Absolute file offset to list indices for list type fields."""
            if hasattr(self, '_m_list_indices_offset_value'):
                return self._m_list_indices_offset_value

            if self.is_list_type:
                pass
                self._m_list_indices_offset_value = self._root.header.list_indices_offset + self.data_or_offset

            return getattr(self, '_m_list_indices_offset_value', None)

        @property
        def struct_index_value(self):
            """Struct index for struct type fields."""
            if hasattr(self, '_m_struct_index_value'):
                return self._m_struct_index_value

            if self.is_struct_type:
                pass
                self._m_struct_index_value = self.data_or_offset

            return getattr(self, '_m_struct_index_value', None)


    class FieldIndicesArray(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Gff.FieldIndicesArray, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.indices = []
            for i in range(self._root.header.field_indices_count):
                self.indices.append(self._io.read_u4le())



        def _fetch_instances(self):
            pass
            for i in range(len(self.indices)):
                pass



    class GffHeader(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Gff.GffHeader, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.file_type = (self._io.read_bytes(4)).decode(u"ASCII")
            self.file_version = (self._io.read_bytes(4)).decode(u"ASCII")
            self.struct_offset = self._io.read_u4le()
            self.struct_count = self._io.read_u4le()
            self.field_offset = self._io.read_u4le()
            self.field_count = self._io.read_u4le()
            self.label_offset = self._io.read_u4le()
            self.label_count = self._io.read_u4le()
            self.field_data_offset = self._io.read_u4le()
            self.field_data_count = self._io.read_u4le()
            self.field_indices_offset = self._io.read_u4le()
            self.field_indices_count = self._io.read_u4le()
            self.list_indices_offset = self._io.read_u4le()
            self.list_indices_count = self._io.read_u4le()


        def _fetch_instances(self):
            pass


    class LabelArray(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Gff.LabelArray, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.labels = []
            for i in range(self._root.header.label_count):
                self.labels.append(Gff.LabelEntry(self._io, self, self._root))



        def _fetch_instances(self):
            pass
            for i in range(len(self.labels)):
                pass
                self.labels[i]._fetch_instances()



    class LabelEntry(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Gff.LabelEntry, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.name = (self._io.read_bytes(16)).decode(u"ASCII")


        def _fetch_instances(self):
            pass


    class LabelEntryTerminated(KaitaiStruct):
        """Label entry as a null-terminated ASCII string within a fixed 16-byte field.
        This avoids leaking trailing `\0` bytes into generated-code consumers.
        """
        def __init__(self, _io, _parent=None, _root=None):
            super(Gff.LabelEntryTerminated, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.name = (KaitaiStream.bytes_terminate(self._io.read_bytes(16), 0, False)).decode(u"ASCII")


        def _fetch_instances(self):
            pass


    class ListEntry(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Gff.ListEntry, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.num_struct_indices = self._io.read_u4le()
            self.struct_indices = []
            for i in range(self.num_struct_indices):
                self.struct_indices.append(self._io.read_u4le())



        def _fetch_instances(self):
            pass
            for i in range(len(self.struct_indices)):
                pass



    class ListIndicesArray(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Gff.ListIndicesArray, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.raw_data = self._io.read_bytes(self._root.header.list_indices_count)


        def _fetch_instances(self):
            pass


    class ResolvedField(KaitaiStruct):
        """A decoded field: includes resolved label string and decoded typed value.
        Exactly one `value_*` instance (or one of `value_struct` / `list_*`) will be non-null.
        """
        def __init__(self, field_index, _io, _parent=None, _root=None):
            super(Gff.ResolvedField, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self.field_index = field_index
            self._read()

        def _read(self):
            pass


        def _fetch_instances(self):
            pass
            _ = self.entry
            if hasattr(self, '_m_entry'):
                pass
                self._m_entry._fetch_instances()

            _ = self.label
            if hasattr(self, '_m_label'):
                pass
                self._m_label._fetch_instances()

            _ = self.list_entry
            if hasattr(self, '_m_list_entry'):
                pass
                self._m_list_entry._fetch_instances()

            _ = self.list_structs
            if hasattr(self, '_m_list_structs'):
                pass
                for i in range(len(self._m_list_structs)):
                    pass
                    self._m_list_structs[i]._fetch_instances()


            _ = self.value_binary
            if hasattr(self, '_m_value_binary'):
                pass
                self._m_value_binary._fetch_instances()

            _ = self.value_double
            if hasattr(self, '_m_value_double'):
                pass

            _ = self.value_int16
            if hasattr(self, '_m_value_int16'):
                pass

            _ = self.value_int32
            if hasattr(self, '_m_value_int32'):
                pass

            _ = self.value_int64
            if hasattr(self, '_m_value_int64'):
                pass

            _ = self.value_int8
            if hasattr(self, '_m_value_int8'):
                pass

            _ = self.value_localized_string
            if hasattr(self, '_m_value_localized_string'):
                pass
                self._m_value_localized_string._fetch_instances()

            _ = self.value_resref
            if hasattr(self, '_m_value_resref'):
                pass
                self._m_value_resref._fetch_instances()

            _ = self.value_single
            if hasattr(self, '_m_value_single'):
                pass

            _ = self.value_string
            if hasattr(self, '_m_value_string'):
                pass
                self._m_value_string._fetch_instances()

            _ = self.value_struct
            if hasattr(self, '_m_value_struct'):
                pass
                self._m_value_struct._fetch_instances()

            _ = self.value_uint16
            if hasattr(self, '_m_value_uint16'):
                pass

            _ = self.value_uint32
            if hasattr(self, '_m_value_uint32'):
                pass

            _ = self.value_uint64
            if hasattr(self, '_m_value_uint64'):
                pass

            _ = self.value_uint8
            if hasattr(self, '_m_value_uint8'):
                pass

            _ = self.value_vector3
            if hasattr(self, '_m_value_vector3'):
                pass
                self._m_value_vector3._fetch_instances()

            _ = self.value_vector4
            if hasattr(self, '_m_value_vector4'):
                pass
                self._m_value_vector4._fetch_instances()


        @property
        def entry(self):
            """Raw field entry at field_index."""
            if hasattr(self, '_m_entry'):
                return self._m_entry

            _pos = self._io.pos()
            self._io.seek(self._root.header.field_offset + self.field_index * 12)
            self._m_entry = Gff.FieldEntry(self._io, self, self._root)
            self._io.seek(_pos)
            return getattr(self, '_m_entry', None)

        @property
        def field_entry_pos(self):
            """Absolute file offset of this field entry (start of 12-byte record)."""
            if hasattr(self, '_m_field_entry_pos'):
                return self._m_field_entry_pos

            self._m_field_entry_pos = self._root.header.field_offset + self.field_index * 12
            return getattr(self, '_m_field_entry_pos', None)

        @property
        def label(self):
            """Resolved field label string."""
            if hasattr(self, '_m_label'):
                return self._m_label

            _pos = self._io.pos()
            self._io.seek(self._root.header.label_offset + self.entry.label_index * 16)
            self._m_label = Gff.LabelEntryTerminated(self._io, self, self._root)
            self._io.seek(_pos)
            return getattr(self, '_m_label', None)

        @property
        def list_entry(self):
            """Parsed list entry at offset (list indices)."""
            if hasattr(self, '_m_list_entry'):
                return self._m_list_entry

            if self.entry.field_type == Gff.GffFieldType.list:
                pass
                _pos = self._io.pos()
                self._io.seek(self._root.header.list_indices_offset + self.entry.data_or_offset)
                self._m_list_entry = Gff.ListEntry(self._io, self, self._root)
                self._io.seek(_pos)

            return getattr(self, '_m_list_entry', None)

        @property
        def list_structs(self):
            """Resolved structs referenced by this list."""
            if hasattr(self, '_m_list_structs'):
                return self._m_list_structs

            if self.entry.field_type == Gff.GffFieldType.list:
                pass
                self._m_list_structs = []
                for i in range(self.list_entry.num_struct_indices):
                    self._m_list_structs.append(Gff.ResolvedStruct(self.list_entry.struct_indices[i], self._io, self, self._root))


            return getattr(self, '_m_list_structs', None)

        @property
        def value_binary(self):
            if hasattr(self, '_m_value_binary'):
                return self._m_value_binary

            if self.entry.field_type == Gff.GffFieldType.binary:
                pass
                _pos = self._io.pos()
                self._io.seek(self._root.header.field_data_offset + self.entry.data_or_offset)
                self._m_value_binary = bioware_common.BiowareCommon.BiowareBinaryData(self._io)
                self._io.seek(_pos)

            return getattr(self, '_m_value_binary', None)

        @property
        def value_double(self):
            if hasattr(self, '_m_value_double'):
                return self._m_value_double

            if self.entry.field_type == Gff.GffFieldType.double:
                pass
                _pos = self._io.pos()
                self._io.seek(self._root.header.field_data_offset + self.entry.data_or_offset)
                self._m_value_double = self._io.read_f8le()
                self._io.seek(_pos)

            return getattr(self, '_m_value_double', None)

        @property
        def value_int16(self):
            if hasattr(self, '_m_value_int16'):
                return self._m_value_int16

            if self.entry.field_type == Gff.GffFieldType.int16:
                pass
                _pos = self._io.pos()
                self._io.seek(self.field_entry_pos + 8)
                self._m_value_int16 = self._io.read_s2le()
                self._io.seek(_pos)

            return getattr(self, '_m_value_int16', None)

        @property
        def value_int32(self):
            if hasattr(self, '_m_value_int32'):
                return self._m_value_int32

            if self.entry.field_type == Gff.GffFieldType.int32:
                pass
                _pos = self._io.pos()
                self._io.seek(self.field_entry_pos + 8)
                self._m_value_int32 = self._io.read_s4le()
                self._io.seek(_pos)

            return getattr(self, '_m_value_int32', None)

        @property
        def value_int64(self):
            if hasattr(self, '_m_value_int64'):
                return self._m_value_int64

            if self.entry.field_type == Gff.GffFieldType.int64:
                pass
                _pos = self._io.pos()
                self._io.seek(self._root.header.field_data_offset + self.entry.data_or_offset)
                self._m_value_int64 = self._io.read_s8le()
                self._io.seek(_pos)

            return getattr(self, '_m_value_int64', None)

        @property
        def value_int8(self):
            if hasattr(self, '_m_value_int8'):
                return self._m_value_int8

            if self.entry.field_type == Gff.GffFieldType.int8:
                pass
                _pos = self._io.pos()
                self._io.seek(self.field_entry_pos + 8)
                self._m_value_int8 = self._io.read_s1()
                self._io.seek(_pos)

            return getattr(self, '_m_value_int8', None)

        @property
        def value_localized_string(self):
            if hasattr(self, '_m_value_localized_string'):
                return self._m_value_localized_string

            if self.entry.field_type == Gff.GffFieldType.localized_string:
                pass
                _pos = self._io.pos()
                self._io.seek(self._root.header.field_data_offset + self.entry.data_or_offset)
                self._m_value_localized_string = bioware_common.BiowareCommon.BiowareLocstring(self._io)
                self._io.seek(_pos)

            return getattr(self, '_m_value_localized_string', None)

        @property
        def value_resref(self):
            if hasattr(self, '_m_value_resref'):
                return self._m_value_resref

            if self.entry.field_type == Gff.GffFieldType.resref:
                pass
                _pos = self._io.pos()
                self._io.seek(self._root.header.field_data_offset + self.entry.data_or_offset)
                self._m_value_resref = bioware_common.BiowareCommon.BiowareResref(self._io)
                self._io.seek(_pos)

            return getattr(self, '_m_value_resref', None)

        @property
        def value_single(self):
            if hasattr(self, '_m_value_single'):
                return self._m_value_single

            if self.entry.field_type == Gff.GffFieldType.single:
                pass
                _pos = self._io.pos()
                self._io.seek(self.field_entry_pos + 8)
                self._m_value_single = self._io.read_f4le()
                self._io.seek(_pos)

            return getattr(self, '_m_value_single', None)

        @property
        def value_string(self):
            if hasattr(self, '_m_value_string'):
                return self._m_value_string

            if self.entry.field_type == Gff.GffFieldType.string:
                pass
                _pos = self._io.pos()
                self._io.seek(self._root.header.field_data_offset + self.entry.data_or_offset)
                self._m_value_string = bioware_common.BiowareCommon.BiowareCexoString(self._io)
                self._io.seek(_pos)

            return getattr(self, '_m_value_string', None)

        @property
        def value_struct(self):
            """Nested struct (struct index = entry.data_or_offset)."""
            if hasattr(self, '_m_value_struct'):
                return self._m_value_struct

            if self.entry.field_type == Gff.GffFieldType.struct:
                pass
                self._m_value_struct = Gff.ResolvedStruct(self.entry.data_or_offset, self._io, self, self._root)

            return getattr(self, '_m_value_struct', None)

        @property
        def value_uint16(self):
            if hasattr(self, '_m_value_uint16'):
                return self._m_value_uint16

            if self.entry.field_type == Gff.GffFieldType.uint16:
                pass
                _pos = self._io.pos()
                self._io.seek(self.field_entry_pos + 8)
                self._m_value_uint16 = self._io.read_u2le()
                self._io.seek(_pos)

            return getattr(self, '_m_value_uint16', None)

        @property
        def value_uint32(self):
            if hasattr(self, '_m_value_uint32'):
                return self._m_value_uint32

            if self.entry.field_type == Gff.GffFieldType.uint32:
                pass
                _pos = self._io.pos()
                self._io.seek(self.field_entry_pos + 8)
                self._m_value_uint32 = self._io.read_u4le()
                self._io.seek(_pos)

            return getattr(self, '_m_value_uint32', None)

        @property
        def value_uint64(self):
            if hasattr(self, '_m_value_uint64'):
                return self._m_value_uint64

            if self.entry.field_type == Gff.GffFieldType.uint64:
                pass
                _pos = self._io.pos()
                self._io.seek(self._root.header.field_data_offset + self.entry.data_or_offset)
                self._m_value_uint64 = self._io.read_u8le()
                self._io.seek(_pos)

            return getattr(self, '_m_value_uint64', None)

        @property
        def value_uint8(self):
            if hasattr(self, '_m_value_uint8'):
                return self._m_value_uint8

            if self.entry.field_type == Gff.GffFieldType.uint8:
                pass
                _pos = self._io.pos()
                self._io.seek(self.field_entry_pos + 8)
                self._m_value_uint8 = self._io.read_u1()
                self._io.seek(_pos)

            return getattr(self, '_m_value_uint8', None)

        @property
        def value_vector3(self):
            if hasattr(self, '_m_value_vector3'):
                return self._m_value_vector3

            if self.entry.field_type == Gff.GffFieldType.vector3:
                pass
                _pos = self._io.pos()
                self._io.seek(self._root.header.field_data_offset + self.entry.data_or_offset)
                self._m_value_vector3 = bioware_common.BiowareCommon.BiowareVector3(self._io)
                self._io.seek(_pos)

            return getattr(self, '_m_value_vector3', None)

        @property
        def value_vector4(self):
            if hasattr(self, '_m_value_vector4'):
                return self._m_value_vector4

            if self.entry.field_type == Gff.GffFieldType.vector4:
                pass
                _pos = self._io.pos()
                self._io.seek(self._root.header.field_data_offset + self.entry.data_or_offset)
                self._m_value_vector4 = bioware_common.BiowareCommon.BiowareVector4(self._io)
                self._io.seek(_pos)

            return getattr(self, '_m_value_vector4', None)


    class ResolvedStruct(KaitaiStruct):
        """A decoded struct node: resolves field indices -> field entries -> typed values,
        and recursively resolves nested structs and lists.
        """
        def __init__(self, struct_index, _io, _parent=None, _root=None):
            super(Gff.ResolvedStruct, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self.struct_index = struct_index
            self._read()

        def _read(self):
            pass


        def _fetch_instances(self):
            pass
            _ = self.entry
            if hasattr(self, '_m_entry'):
                pass
                self._m_entry._fetch_instances()

            _ = self.field_indices
            if hasattr(self, '_m_field_indices'):
                pass
                for i in range(len(self._m_field_indices)):
                    pass


            _ = self.fields
            if hasattr(self, '_m_fields'):
                pass
                for i in range(len(self._m_fields)):
                    pass
                    self._m_fields[i]._fetch_instances()


            _ = self.single_field
            if hasattr(self, '_m_single_field'):
                pass
                self._m_single_field._fetch_instances()


        @property
        def entry(self):
            """Raw struct entry at struct_index."""
            if hasattr(self, '_m_entry'):
                return self._m_entry

            _pos = self._io.pos()
            self._io.seek(self._root.header.struct_offset + self.struct_index * 12)
            self._m_entry = Gff.StructEntry(self._io, self, self._root)
            self._io.seek(_pos)
            return getattr(self, '_m_entry', None)

        @property
        def field_indices(self):
            """Field indices for this struct (only present when field_count > 1).
            When field_count == 1, the single field index is stored directly in entry.data_or_offset.
            """
            if hasattr(self, '_m_field_indices'):
                return self._m_field_indices

            if self.entry.field_count > 1:
                pass
                _pos = self._io.pos()
                self._io.seek(self._root.header.field_indices_offset + self.entry.data_or_offset)
                self._m_field_indices = []
                for i in range(self.entry.field_count):
                    self._m_field_indices.append(self._io.read_u4le())

                self._io.seek(_pos)

            return getattr(self, '_m_field_indices', None)

        @property
        def fields(self):
            """Resolved fields (multi-field struct)."""
            if hasattr(self, '_m_fields'):
                return self._m_fields

            if self.entry.field_count > 1:
                pass
                self._m_fields = []
                for i in range(self.entry.field_count):
                    self._m_fields.append(Gff.ResolvedField(self.field_indices[i], self._io, self, self._root))


            return getattr(self, '_m_fields', None)

        @property
        def single_field(self):
            """Resolved field (single-field struct)."""
            if hasattr(self, '_m_single_field'):
                return self._m_single_field

            if self.entry.field_count == 1:
                pass
                self._m_single_field = Gff.ResolvedField(self.entry.data_or_offset, self._io, self, self._root)

            return getattr(self, '_m_single_field', None)


    class StructArray(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Gff.StructArray, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.entries = []
            for i in range(self._root.header.struct_count):
                self.entries.append(Gff.StructEntry(self._io, self, self._root))



        def _fetch_instances(self):
            pass
            for i in range(len(self.entries)):
                pass
                self.entries[i]._fetch_instances()



    class StructEntry(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Gff.StructEntry, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.struct_id = self._io.read_s4le()
            self.data_or_offset = self._io.read_u4le()
            self.field_count = self._io.read_u4le()


        def _fetch_instances(self):
            pass

        @property
        def field_indices_offset(self):
            """Byte offset into field_indices_array when struct has multiple fields."""
            if hasattr(self, '_m_field_indices_offset'):
                return self._m_field_indices_offset

            if self.has_multiple_fields:
                pass
                self._m_field_indices_offset = self.data_or_offset

            return getattr(self, '_m_field_indices_offset', None)

        @property
        def has_multiple_fields(self):
            """True if struct has multiple fields (offset to field indices in data_or_offset)."""
            if hasattr(self, '_m_has_multiple_fields'):
                return self._m_has_multiple_fields

            self._m_has_multiple_fields = self.field_count > 1
            return getattr(self, '_m_has_multiple_fields', None)

        @property
        def has_single_field(self):
            """True if struct has exactly one field (direct field index in data_or_offset)."""
            if hasattr(self, '_m_has_single_field'):
                return self._m_has_single_field

            self._m_has_single_field = self.field_count == 1
            return getattr(self, '_m_has_single_field', None)

        @property
        def single_field_index(self):
            """Direct field index when struct has exactly one field."""
            if hasattr(self, '_m_single_field_index'):
                return self._m_single_field_index

            if self.has_single_field:
                pass
                self._m_single_field_index = self.data_or_offset

            return getattr(self, '_m_single_field_index', None)


    @property
    def field_array(self):
        """Array of field entries (12 bytes each)."""
        if hasattr(self, '_m_field_array'):
            return self._m_field_array

        if self.header.field_count > 0:
            pass
            _pos = self._io.pos()
            self._io.seek(self.header.field_offset)
            self._m_field_array = Gff.FieldArray(self._io, self, self._root)
            self._io.seek(_pos)

        return getattr(self, '_m_field_array', None)

    @property
    def field_data(self):
        """Storage area for complex field types (strings, binary, vectors, etc.)."""
        if hasattr(self, '_m_field_data'):
            return self._m_field_data

        if self.header.field_data_count > 0:
            pass
            _pos = self._io.pos()
            self._io.seek(self.header.field_data_offset)
            self._m_field_data = Gff.FieldData(self._io, self, self._root)
            self._io.seek(_pos)

        return getattr(self, '_m_field_data', None)

    @property
    def field_indices_array(self):
        """Array of field index arrays (used when structs have multiple fields)."""
        if hasattr(self, '_m_field_indices_array'):
            return self._m_field_indices_array

        if self.header.field_indices_count > 0:
            pass
            _pos = self._io.pos()
            self._io.seek(self.header.field_indices_offset)
            self._m_field_indices_array = Gff.FieldIndicesArray(self._io, self, self._root)
            self._io.seek(_pos)

        return getattr(self, '_m_field_indices_array', None)

    @property
    def label_array(self):
        """Array of 16-byte null-padded field name labels."""
        if hasattr(self, '_m_label_array'):
            return self._m_label_array

        if self.header.label_count > 0:
            pass
            _pos = self._io.pos()
            self._io.seek(self.header.label_offset)
            self._m_label_array = Gff.LabelArray(self._io, self, self._root)
            self._io.seek(_pos)

        return getattr(self, '_m_label_array', None)

    @property
    def list_indices_array(self):
        """Array of list entry structures (count + struct indices)."""
        if hasattr(self, '_m_list_indices_array'):
            return self._m_list_indices_array

        if self.header.list_indices_count > 0:
            pass
            _pos = self._io.pos()
            self._io.seek(self.header.list_indices_offset)
            self._m_list_indices_array = Gff.ListIndicesArray(self._io, self, self._root)
            self._io.seek(_pos)

        return getattr(self, '_m_list_indices_array', None)

    @property
    def root_struct_resolved(self):
        """Convenience "decoded" view of the root struct (struct_array[0]).
        This resolves field indices to field entries, resolves labels to strings,
        and decodes field values (including nested structs and lists) into typed instances.
        """
        if hasattr(self, '_m_root_struct_resolved'):
            return self._m_root_struct_resolved

        self._m_root_struct_resolved = Gff.ResolvedStruct(0, self._io, self, self._root)
        return getattr(self, '_m_root_struct_resolved', None)

    @property
    def struct_array(self):
        """Array of struct entries (12 bytes each)."""
        if hasattr(self, '_m_struct_array'):
            return self._m_struct_array

        if self.header.struct_count > 0:
            pass
            _pos = self._io.pos()
            self._io.seek(self.header.struct_offset)
            self._m_struct_array = Gff.StructArray(self._io, self, self._root)
            self._io.seek(_pos)

        return getattr(self, '_m_struct_array', None)


