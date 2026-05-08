# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO
from enum import IntEnum


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class Lip(KaitaiStruct):
    """LIP (LIP Synchronization) files drive mouth animation for voiced dialogue in BioWare games.
    Each file contains a compact series of keyframes that map timestamps to discrete viseme
    (mouth shape) indices so that the engine can interpolate character lip movement while
    playing the companion WAV audio line.
    
    LIP files are always binary and contain only animation data. They are paired with WAV
    voice-over resources of identical duration; the LIP length field must match the WAV
    playback time for glitch-free animation.
    
    Keyframes are sorted chronologically and store a timestamp (float seconds) plus a
    1-byte viseme index (0-15). The format uses the 16-shape Preston Blair phoneme set.
    
    """

    class LipShapes(IntEnum):
        neutral = 0
        ee = 1
        eh = 2
        ah = 3
        oh = 4
        ooh = 5
        y = 6
        sts = 7
        fv = 8
        ng = 9
        th = 10
        mpb = 11
        td = 12
        sh = 13
        l = 14
        kg = 15
    def __init__(self, _io, _parent=None, _root=None):
        super(Lip, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.file_type = (self._io.read_bytes(4)).decode(u"ASCII")
        self.file_version = (self._io.read_bytes(4)).decode(u"ASCII")
        self.length = self._io.read_f4le()
        self.num_keyframes = self._io.read_u4le()
        self.keyframes = []
        for i in range(self.num_keyframes):
            self.keyframes.append(Lip.KeyframeEntry(self._io, self, self._root))



    def _fetch_instances(self):
        pass
        for i in range(len(self.keyframes)):
            pass
            self.keyframes[i]._fetch_instances()


    class KeyframeEntry(KaitaiStruct):
        """A single keyframe entry mapping a timestamp to a viseme (mouth shape).
        Keyframes are used by the engine to interpolate between mouth shapes during
        audio playback to create lip sync animation.
        """
        def __init__(self, _io, _parent=None, _root=None):
            super(Lip.KeyframeEntry, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.timestamp = self._io.read_f4le()
            self.shape = KaitaiStream.resolve_enum(Lip.LipShapes, self._io.read_u1())


        def _fetch_instances(self):
            pass



