from .wav_auto import read_wav, write_wav, get_playable_bytes, bytes_wav, detect_audio_type
from .wav_data import WAV, AudioFormat, WAVType, WaveEncoding
from .wav_obfuscation import (
    get_deobfuscation_result,
    obfuscate_audio,
    DeobfuscationResult,
    SFX_MAGIC_BYTES,
    RIFF_MAGIC,
    RIFF_MAGIC_LE,
    SFX_MAGIC_LE,
    SFX_HEADER_SIZE,
    MP3_IN_WAV_RIFF_SIZE,
    MP3_IN_WAV_HEADER_SIZE,
    VO_HEADER_SIZE,
    detect_audio_format,
)
from .io_wav import WAVBinaryReader, WAVBinaryWriter
from .io_wav_standard import WAVStandardWriter

__all__ = [
    "MP3_IN_WAV_HEADER_SIZE",
    "MP3_IN_WAV_RIFF_SIZE",
    "RIFF_MAGIC",
    "RIFF_MAGIC_LE",
    "SFX_HEADER_SIZE",
    "SFX_MAGIC_BYTES",
    "SFX_MAGIC_LE",
    "VO_HEADER_SIZE",
    "WAV",
    "AudioFormat",
    "DeobfuscationResult",
    "WAVBinaryReader",
    "WAVBinaryWriter",
    "WAVStandardWriter",
    "WAVType",
    "WaveEncoding",
    "bytes_wav",
    "detect_audio_format",
    "detect_audio_type",
    "get_deobfuscation_result",
    "get_playable_bytes",
    "obfuscate_audio",
    "read_wav",
    "read_wav",
    "write_wav",
    "write_wav",
]
