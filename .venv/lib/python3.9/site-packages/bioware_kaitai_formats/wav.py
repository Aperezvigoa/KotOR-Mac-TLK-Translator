# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class Wav(KaitaiStruct):
    """WAV (Waveform Audio Format) files used in KotOR. KotOR stores both standard WAV voice-over lines
    and Bioware-obfuscated sound-effect files. Voice-over assets are regular RIFF containers with PCM
    headers, while SFX assets prepend a 470-byte custom block before the RIFF data.
    
    Format Types:
    - VO (Voice-over): Plain RIFF/WAVE PCM files readable by any media player
    - SFX (Sound effects): Contains a Bioware 470-byte obfuscation header followed by RIFF data
    - MP3-in-WAV: Special RIFF container with MP3 data (RIFF size = 50)
    
    Note: This Kaitai Struct definition documents the core RIFF/WAVE structure. SFX and VO headers
    (470-byte and 20-byte prefixes respectively) are handled by application-level deobfuscation.
    
    """
    def __init__(self, _io, _parent=None, _root=None):
        super(Wav, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.riff_header = Wav.RiffHeader(self._io, self, self._root)
        self.chunks = []
        i = 0
        while True:
            _ = Wav.Chunk(self._io, self, self._root)
            self.chunks.append(_)
            if self._io.is_eof():
                break
            i += 1


    def _fetch_instances(self):
        pass
        self.riff_header._fetch_instances()
        for i in range(len(self.chunks)):
            pass
            self.chunks[i]._fetch_instances()


    class Chunk(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Wav.Chunk, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.id = (self._io.read_bytes(4)).decode(u"ASCII")
            self.size = self._io.read_u4le()
            _on = self.id
            if _on == u"data":
                pass
                self.body = Wav.DataChunkBody(self._io, self, self._root)
            elif _on == u"fact":
                pass
                self.body = Wav.FactChunkBody(self._io, self, self._root)
            elif _on == u"fmt ":
                pass
                self.body = Wav.FormatChunkBody(self._io, self, self._root)
            else:
                pass
                self.body = Wav.UnknownChunkBody(self._io, self, self._root)


        def _fetch_instances(self):
            pass
            _on = self.id
            if _on == u"data":
                pass
                self.body._fetch_instances()
            elif _on == u"fact":
                pass
                self.body._fetch_instances()
            elif _on == u"fmt ":
                pass
                self.body._fetch_instances()
            else:
                pass
                self.body._fetch_instances()


    class DataChunkBody(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Wav.DataChunkBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.data = self._io.read_bytes(self._parent.size)


        def _fetch_instances(self):
            pass


    class FactChunkBody(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Wav.FactChunkBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.sample_count = self._io.read_u4le()


        def _fetch_instances(self):
            pass


    class FormatChunkBody(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Wav.FormatChunkBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.audio_format = self._io.read_u2le()
            self.channels = self._io.read_u2le()
            self.sample_rate = self._io.read_u4le()
            self.bytes_per_sec = self._io.read_u4le()
            self.block_align = self._io.read_u2le()
            self.bits_per_sample = self._io.read_u2le()
            if self._parent.size > 16:
                pass
                self.extra_format_bytes = self._io.read_bytes(self._parent.size - 16)



        def _fetch_instances(self):
            pass
            if self._parent.size > 16:
                pass


        @property
        def is_ima_adpcm(self):
            """True if audio format is IMA ADPCM (compressed)."""
            if hasattr(self, '_m_is_ima_adpcm'):
                return self._m_is_ima_adpcm

            self._m_is_ima_adpcm = self.audio_format == 17
            return getattr(self, '_m_is_ima_adpcm', None)

        @property
        def is_mp3(self):
            """True if audio format is MP3."""
            if hasattr(self, '_m_is_mp3'):
                return self._m_is_mp3

            self._m_is_mp3 = self.audio_format == 85
            return getattr(self, '_m_is_mp3', None)

        @property
        def is_pcm(self):
            """True if audio format is PCM (uncompressed)."""
            if hasattr(self, '_m_is_pcm'):
                return self._m_is_pcm

            self._m_is_pcm = self.audio_format == 1
            return getattr(self, '_m_is_pcm', None)


    class RiffHeader(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Wav.RiffHeader, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.riff_id = (self._io.read_bytes(4)).decode(u"ASCII")
            if not self.riff_id == u"RIFF":
                raise kaitaistruct.ValidationNotEqualError(u"RIFF", self.riff_id, self._io, u"/types/riff_header/seq/0")
            self.riff_size = self._io.read_u4le()
            self.wave_id = (self._io.read_bytes(4)).decode(u"ASCII")
            if not self.wave_id == u"WAVE":
                raise kaitaistruct.ValidationNotEqualError(u"WAVE", self.wave_id, self._io, u"/types/riff_header/seq/2")


        def _fetch_instances(self):
            pass

        @property
        def is_mp3_in_wav(self):
            """MP3-in-WAV format detected when RIFF size = 50
            """
            if hasattr(self, '_m_is_mp3_in_wav'):
                return self._m_is_mp3_in_wav

            self._m_is_mp3_in_wav = self.riff_size == 50
            return getattr(self, '_m_is_mp3_in_wav', None)


    class UnknownChunkBody(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            super(Wav.UnknownChunkBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.data = self._io.read_bytes(self._parent.size)
            if self._parent.size % 2 == 1:
                pass
                self.padding = self._io.read_u1()



        def _fetch_instances(self):
            pass
            if self._parent.size % 2 == 1:
                pass




