"""Real crankjam synth checks. Canvas/native-copy here are explicit host fixtures.

SPDX-License-Identifier: MIT
Run with the existing CircuitPython UNIX crankjam interpreter, from this folder.
"""
import sys
import struct
import json
import crankjam


class CopyFixture:
    @staticmethod
    def copy_into(dst, src, doff, soff, count):
        dst[doff:doff+count] = src[soff:soff+count]
        return count


class CanvasFixture:
    def __init__(self, path):
        self.ids = {}
    def begin(self, name):
        assert name == 'explorer'
    def text(self, text, x, y, scale=1):
        pass
    def render(self):
        pass
    def close(self):
        pass


class CanvasModule:
    Canvas = CanvasFixture


sys.modules['_crankfruit_pcm'] = CopyFixture()
sys.modules['canvas'] = CanvasModule()
from sound_explorer import SoundExplorer, SOUND_SOURCE

assert sys.implementation.name == 'circuitpython'
runtime = crankjam.Runtime(SOUND_SOURCE, heap_cap=32768)
block = bytearray(2134)
peak = 0
try:
    for config in range(64):
        runtime.step(config, 0, 1, config * 1000)
        assert runtime.audio_into(block, rate=32000) == len(block)
        assert any(block), 'synth protocol produced silence'
        for i in range(0, len(block), 2):
            peak = max(peak, abs(struct.unpack_from('<h', block, i)[0]))
        runtime.step(config, 0, -1, config * 1000 + 34)
        runtime.audio_into(block, rate=32000)
        assert not any(block), 'negative trigger did not stop synth'
    heap = list(runtime.heap_stats())
finally:
    runtime.close()

explorer = SoundExplorer(crankjam.Runtime, 'assets')
sample_output = bytearray()
try:
    explorer.step(0,0,0,0)
    assert explorer.audio_into(block) == len(block) and any(block)
    explorer.step(1,0,0,33)  # square -> PDA
    explorer.step(0,0,0,66)
    for frame in range(20):
        explorer.audio_into(block)
        sample_output.extend(block)
        explorer.step(0,0,0,99+frame*33)
    expected = explorer.samples[0]
    assert sample_output[:len(expected)] == expected
    assert not any(sample_output[len(expected):])
    explorer.step(2,0,0,800)  # PDA -> square
    assert explorer.audio_into(block) == len(block) and any(block)
finally:
    explorer.close()
print(json.dumps(dict(real_runtime=True, synth_configs=64, all_nonzero_pcm=True,
                      stop_protocol_zero=True, synth_peak=peak, heap=heap,
                      cached_sample_exact=True, canvas_and_copy_are_fixtures=True)))
