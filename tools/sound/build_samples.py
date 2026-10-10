"""Generate three original tones, PDA sources, normalized PCM and integer peaks.

SPDX-License-Identifier: MIT. Offline only; no third-party audio.
"""
import hashlib
import json
import math
from pathlib import Path
import struct
from pda import encode_pcm, normalize


def samples(kind, count):
    result = []
    phase = 0.0
    for i in range(count):
        t = i / 32000
        progress = i / (count - 1)
        if kind == 'boot':
            freq = (330, 440, 660)[min(2, i * 3 // count)]
            local = (i * 3 % count) / count
            env = min(1.0, local * 35) * (1 - local) ** 1.4
        elif kind == 'coin':
            freq = 700 + 900 * progress
            env = min(1.0, progress * 40) * (1 - progress) ** 2
        else:
            freq = 560 - 390 * progress
            env = min(1.0, progress * 45) * (1 - progress) ** 1.5
        phase += freq / 32000
        signal = math.sin(phase * 2 * math.pi) * 0.8 + math.sin(phase * 4 * math.pi) * 0.2
        # Fade the complete file edges; max amplitude stays under 0.30 full scale.
        fade = min(1.0, i / 128, (count - 1 - i) / 128)
        result.append(round(signal * env * fade * 9000))
    return result


def build():
    root = Path(__file__).resolve().parent / 'assets'
    root.mkdir(exist_ok=True)
    records = []
    for name, count in (('boot', 14400), ('coin', 6400), ('swoop', 16000)):
        pda = encode_pcm(samples(name, count))
        pcm = normalize(pda)
        (root / ('sample_' + name + '.pda')).write_bytes(pda)
        (root / ('sample_' + name + '.pcm')).write_bytes(pcm)
        values = [x[0] for x in struct.iter_unpack('<h', pcm)]
        bands = [max(abs(v) for v in values[i * count // 32:(i + 1) * count // 32])
                 for i in range(32)]
        records.append(dict(name=name, rate=32000, channels=1, bits=16,
                            bytes=len(pcm), peak=max(map(abs, values)), bands=bands,
                            pda_sha256=hashlib.sha256(pda).hexdigest(),
                            pcm_sha256=hashlib.sha256(pcm).hexdigest()))
    (root / 'samples.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps(records))


if __name__ == '__main__':
    build()
