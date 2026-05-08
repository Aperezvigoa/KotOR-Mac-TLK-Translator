# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class Da2s(KaitaiStruct):
    """DA2S (Dragon Age 2 Save) files are binary save game files used by the Eclipse Engine
    (Dragon Age 2). They contain save game metadata and optionally full game state.
    
    DA2S files are binary format files with the following structure:
    - Signature (4 bytes): "DA2S" (Dragon Age 2 Save)
    - Version (int32): Save format version (1 for DA2)
    - Metadata fields (strings, integers, timestamps, etc.)
    - Optional: Full game state (party, inventory, journal, globals)
    
    Based on DragonAge2.exe: SaveGameMessage @ 0x00be37a8, DeleteSaveGameMessage @ 0x00be389c
    Located via string references: "SaveGameMessage" @ 0x00be37a8, "GameModeController::HandleMessage(SaveGameMessage)" @ 0x00d2b330
    Original implementation: UnrealScript message-based save system, binary serialization
    Note: DA2 save format may differ from DA:O format (different game engine version)
    
    References:
    - src/Andastra/Runtime/Games/Eclipse/DragonAge2/Save/DragonAge2SaveSerializer.cs
    - src/Andastra/Runtime/Games/Eclipse/Save/EclipseSaveSerializer.cs (base class)
    """
    def __init__(self, _io, _parent=None, _root=None):
        super(Da2s, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.signature = (self._io.read_bytes(4)).decode(u"ASCII")
        if not self.signature == u"DA2S":
            raise kaitaistruct.ValidationNotEqualError(u"DA2S", self.signature, self._io, u"/seq/0")
        self.version = self._io.read_s4le()
        if not self.version == 1:
            raise kaitaistruct.ValidationNotEqualError(1, self.version, self._io, u"/seq/1")
        self.save_name = Da2s.LengthPrefixedString(self._io, self, self._root)
        self.module_name = Da2s.LengthPrefixedString(self._io, self, self._root)
        self.area_name = Da2s.LengthPrefixedString(self._io, self, self._root)
        self.time_played_seconds = self._io.read_s4le()
        self.timestamp_filetime = self._io.read_s8le()
        self.screenshot_length = self._io.read_s4le()
        if self.screenshot_length > 0:
            pass
            self.screenshot_data = []
            for i in range(self.screenshot_length):
                self.screenshot_data.append(self._io.read_u1())


        self.portrait_length = self._io.read_s4le()
        if self.portrait_length > 0:
            pass
            self.portrait_data = []
            for i in range(self.portrait_length):
                self.portrait_data.append(self._io.read_u1())


        self.player_name = Da2s.LengthPrefixedString(self._io, self, self._root)
        self.party_member_count = self._io.read_s4le()
        self.player_level = self._io.read_s4le()


    def _fetch_instances(self):
        pass
        self.save_name._fetch_instances()
        self.module_name._fetch_instances()
        self.area_name._fetch_instances()
        if self.screenshot_length > 0:
            pass
            for i in range(len(self.screenshot_data)):
                pass


        if self.portrait_length > 0:
            pass
            for i in range(len(self.portrait_data)):
                pass


        self.player_name._fetch_instances()

    class LengthPrefixedString(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Da2s.LengthPrefixedString, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.length = self._io.read_s4le()
            self.value = (KaitaiStream.bytes_terminate(self._io.read_bytes(self.length), 0, False)).decode(u"UTF-8")


        def _fetch_instances(self):
            pass

        @property
        def value_trimmed(self):
            """String value.
            Note: trailing null bytes are already excluded via `terminator: 0` and `include: false`.
            """
            if hasattr(self, '_m_value_trimmed'):
                return self._m_value_trimmed

            self._m_value_trimmed = self.value
            return getattr(self, '_m_value_trimmed', None)



