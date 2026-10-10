"""Bounded OFFLINE Playdate PDA PCM decoder and fixture encoder.

SPDX-License-Identifier: MIT
Format reference: cranksters/playdate-reverse-engineering, formats/pda.md,
revision e7be3ff0141b7cd3b9f008737eda1f0539aca45c (CC0 documentation).
No device use: normalization runs before deployment, never in an audio callback.
"""
import struct

MAGIC = b'Playdate AUD'
MAX_INPUT = 1048576
MAX_FRAMES = 320000
TARGET_RATE = 32000


def decode(data):
    """Return metadata + interleaved signed16 channel frames; reject ambiguity."""
    if len(data) < 16 or len(data) > MAX_INPUT or data[:12] != MAGIC:
        raise ValueError('invalid or oversized PDA header')
    rate = int.from_bytes(data[12:15], 'little')
    kind = data[15]
    if not 8000 <= rate <= 96000:
        raise ValueError('PDA sample rate outside supported 8-96kHz range')
    if kind in (4, 5):
        raise ValueError('IMA ADPCM PDA is not supported; convert offline to PCM PDA')
    if kind not in (0, 1, 2, 3):
        raise ValueError('unknown PDA encoding')
    channels = 1 + (kind & 1)
    width = 1 if kind < 2 else 2
    body = memoryview(data)[16:]
    frame_bytes = channels * width
    if not body or len(body) % frame_bytes:
        raise ValueError('empty or truncated PDA frame')
    frames = len(body) // frame_bytes
    if frames > MAX_FRAMES or frames * TARGET_RATE // rate > MAX_FRAMES:
        raise ValueError('decoded duration exceeds bounded frame budget')
    values = ([(value - 128) * 256 for value in body] if width == 1 else
              [value[0] for value in struct.iter_unpack('<h', body)])
    return dict(rate=rate, channels=channels, format=kind, frames=frames, samples=values)


def normalize(data):
    """32000Hz mono PCM16LE, integer stereo downmix + linear resampling.

    Linear interpolation is not a mastering-quality anti-alias filter. Generated
    demo inputs already use 32000Hz and therefore require no rate conversion.
    """
    decoded = decode(data)
    values, channels = decoded['samples'], decoded['channels']
    mono = values if channels == 1 else [(values[i] + values[i + 1]) // 2
                                        for i in range(0, len(values), 2)]
    count = len(mono) * TARGET_RATE // decoded['rate']
    if count < 1:
        raise ValueError('PDA too short after resampling')
    result = bytearray(count * 2)
    for i in range(count):
        numerator = i * decoded['rate']
        index, fraction = divmod(numerator, TARGET_RATE)
        a = mono[index]
        b = mono[min(index + 1, len(mono) - 1)]
        value = a + ((b - a) * fraction) // TARGET_RATE
        struct.pack_into('<h', result, i * 2, value)
    return bytes(result)


def encode_pcm(samples, rate=32000, channels=1, bits=16):
    """Build original PCM fixtures. samples are interleaved signed16 integers."""
    if channels not in (1, 2) or bits not in (8, 16) or not 8000 <= rate <= 96000:
        raise ValueError('unsupported PCM parameters')
    if not samples or len(samples) % channels or len(samples) // channels > MAX_FRAMES:
        raise ValueError('invalid PCM frames')
    if any(type(n) is not int or not -32768 <= n <= 32767 for n in samples):
        raise ValueError('PCM samples must be signed16 integers')
    kind = (2 if bits == 16 else 0) + channels - 1
    body = (b''.join(struct.pack('<h', n) for n in samples) if bits == 16 else
            bytes((n + 32768) >> 8 for n in samples))
    result = MAGIC + rate.to_bytes(3, 'little') + bytes((kind,)) + body
    if len(result) > MAX_INPUT:
        raise ValueError('encoded PDA exceeds input budget')
    return result
