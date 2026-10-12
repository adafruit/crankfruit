"""Host fixtures and offline codec tests; no hardware/audio-output claims."""
import ast
import builtins
import inspect
import pathlib
import struct
import sys
import types
import unittest
from unittest.mock import patch
import pda

CALLS = []
def copy_fixture(dst, src, doff, soff, count):
    assert 0 <= count <= 1048576 and doff + count <= len(dst) and soff + count <= len(src)
    CALLS.append((doff, soff, count))
    dst[doff:doff+count] = src[soff:soff+count]
    return count

sys.modules['_crankfruit_pcm'] = types.SimpleNamespace(copy_into=copy_fixture)
from sound_explorer import SoundExplorer, SOUND_SOURCE


class CanvasFixture:
    def __init__(self, path):
        self.ids = dict.fromkeys(('wave_square','wave_triangle','wave_sample','envelope'))
        self.count = self.frames = 0
        self.closed = False
    def begin(self, name):
        assert name == 'explorer'
        self.count = 0
    def text(self, text, x, y, scale=1):
        assert x >= 0 and y >= 0 and x + len(text) * scale * 6 <= 400 and y + 7 * scale <= 240
        self.count += len(text)
    def sprite(self, name, x, y, flags=0):
        assert name in self.ids
        self.count += 1
    def render(self):
        assert self.count <= 256
        self.frames += 1
    def copy_framebuffer_into(self, target, stride=52):
        return 12000
    def close(self):
        self.closed = True


class RuntimeFixture:
    def __init__(self, source, heap_cap):
        assert source == SOUND_SOURCE and heap_cap == 32768
        self.steps = []
        self.closed = False
    def step(self, buttons, angle, delta, elapsed):
        self.steps.append((buttons, angle, delta, elapsed))
    def audio_into(self, target, rate=32000):
        assert rate == 32000
        target[:] = bytes(len(target))
        return len(target)
    def heap_stats(self):
        return (0,0,32768,0)
    def close(self):
        self.closed = True


class ExplorerTests(unittest.TestCase):
    def setUp(self):
        self.canvas_patch = patch.dict(sys.modules, {'canvas': types.SimpleNamespace(Canvas=CanvasFixture)})
        self.canvas_patch.start()
        self.e = SoundExplorer(RuntimeFixture, str(pathlib.Path(__file__).parent / 'assets'))
        self.now = 0
    def tearDown(self):
        self.e.close()
        self.canvas_patch.stop()
    def step(self, buttons):
        self.now += 33
        self.e.step(buttons, 0, 0, self.now)
    def tap(self, buttons):
        self.step(buttons)
        self.step(0)
    def test_initial_synth_and_persistent_runtime(self):
        runtime = self.e.sound
        self.step(0)
        self.assertEqual(runtime.steps[-1][2], 1)
        self.tap(2)
        self.assertEqual(self.e.wave, 1)
        self.assertIs(runtime, self.e.sound)
        self.assertEqual(self.e.canvas.frames, 2)
    def test_navigation_pitch_decay_and_replay(self):
        self.step(0)
        self.tap(32)
        self.assertEqual(self.e.field, 1)
        self.tap(2)
        self.assertEqual(self.e.pitch, 5)
        self.tap(32)
        self.tap(1)
        self.assertEqual(self.e.decay, 0)
        auditions = self.e.auditions
        self.tap(16)
        self.assertEqual(self.e.auditions, auditions + 1)
    def test_crank_click_changes_selected_value_and_auditions(self):
        self.step(0)
        auditions = self.e.auditions
        self.now += 33
        self.e.step(0, 0, 10.0, self.now)        # under one click
        self.assertEqual(self.e.wave, 0)
        self.now += 33
        self.e.step(0, 0, 8.0, self.now)         # 18 degrees: like B2
        self.assertEqual(self.e.wave, 1)
        self.assertEqual(self.e.auditions, auditions + 1)
        self.tap(32)                             # next field: pitch
        self.now += 33
        self.e.step(0, 0, -18.0, self.now)       # counter-clockwise: like B1
        self.assertEqual(self.e.pitch, 3)
        self.now += 33
        self.e.step(0, 0, 90.0, self.now)        # fast spin: one change per frame
        self.assertEqual(self.e.pitch, 4)
        self.now += 33
        self.e.step(0, 0, 0.0, self.now)         # no backlog afterwards
        self.assertEqual(self.e.pitch, 4)
    def test_long_b3_does_not_change_parameter(self):
        self.step(32)
        self.now += 1300
        self.step(0)
        self.assertEqual(self.e.field, 0)
    def test_cached_sample_exact_bytes_then_silence(self):
        self.step(0)
        self.tap(1)  # square -> PDA
        self.assertEqual(self.e.wave, 2)
        self.assertEqual(self.e.sound.steps[-2][2], -1)
        output = bytearray()
        with patch.object(builtins, 'open', side_effect=AssertionError('I/O during playback')):
            for _ in range(20):
                target = bytearray(2134)
                self.assertEqual(self.e.audio_into(target), 2134)
                output.extend(target)
                self.step(0)
        expected = self.e.samples[0]
        self.assertEqual(output[:len(expected)], expected)
        self.assertFalse(any(output[len(expected):]))
        self.tap(16)
        self.assertEqual(self.e.offset, 0)
    def test_sample_selection_and_two_fields(self):
        self.tap(1)
        self.tap(32)
        self.tap(2)
        self.assertEqual(self.e.sample, 1)
        self.tap(32)
        self.assertEqual(self.e.field, 0)
    def test_every_sample_payload_and_tail_are_exact(self):
        self.tap(1)
        self.tap(32)
        for index in range(3):
            self.assertEqual(self.e.sample, index)
            output = bytearray()
            for _ in range(17):
                block = bytearray(2132)
                self.e.audio_into(block)
                output.extend(block)
            sample = self.e.samples[index]
            self.assertEqual(output[:len(sample)], sample)
            self.assertFalse(any(output[len(sample):]))
            self.tap(2)
    def test_invalid_audio_requests_and_cleanup(self):
        for target, rate in ((bytearray(1),32000), (bytearray(2136),32000), (bytearray(2),44100)):
            with self.assertRaises(ValueError):
                self.e.audio_into(target, rate)
        runtime, canvas = self.e.sound, self.e.canvas
        self.e.close()
        self.e.close()
        self.assertTrue(runtime.closed and canvas.closed)
        with self.assertRaises(RuntimeError):
            self.step(0)
    def test_audio_path_has_no_python_sample_loop(self):
        tree = ast.parse(inspect.getsource(sys.modules['sound_explorer']))
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'audio_into')
        self.assertFalse(any(isinstance(n, (ast.For, ast.While, ast.ListComp, ast.GeneratorExp))
                             for n in ast.walk(method)))


class PdaTests(unittest.TestCase):
    def test_all_four_pcm_encodings(self):
        for channels in (1,2):
            for bits in (8,16):
                samples = [-32768, -256, 0, 256, 32512, 0] * channels
                encoded = pda.encode_pcm(samples, channels=channels, bits=bits)
                decoded = pda.decode(encoded)
                self.assertEqual(decoded['samples'], samples)
                self.assertEqual(decoded['channels'], channels)
    def test_stereo_downmix_known_vector(self):
        blob = pda.encode_pcm([1000,-1000, 32767,32767, -32768,-32768], channels=2)
        self.assertEqual(pda.normalize(blob), struct.pack('<hhh',0,32767,-32768))
    def test_integer_resample_vector(self):
        self.assertEqual(pda.normalize(pda.encode_pcm([0,1000],rate=16000)),
                         struct.pack('<hhhh',0,500,1000,1000))
    def test_malformed_and_unsupported(self):
        valid = pda.encode_pcm([0,1000])
        bad = [b'', b'x'*16, valid[:15], valid[:-1], valid[:16],
               valid[:12]+b'\0\0\0'+valid[15:], valid[:15]+b'\xff'+valid[16:],
               valid[:15]+b'\x04'+valid[16:], valid[:15]+b'\x05'+valid[16:],
               valid[:15]+b'\x03'+b'\0\0', valid+b'\0'*(pda.MAX_INPUT+1)]
        for blob in bad:
            with self.subTest(length=len(blob)):
                with self.assertRaises(ValueError):
                    pda.decode(blob)
    def test_duration_budget_before_output_allocation(self):
        blob = pda.MAGIC + (8000).to_bytes(3,'little') + b'\x00' + b'\x80'*80001
        with self.assertRaisesRegex(ValueError, 'budget'):
            pda.decode(blob)
    def test_generated_pda_roundtrip(self):
        root = pathlib.Path(__file__).parent / 'assets'
        for name in ('boot','coin','swoop'):
            self.assertEqual(pda.normalize((root/('sample_'+name+'.pda')).read_bytes()),
                             (root/('sample_'+name+'.pcm')).read_bytes())


if __name__ == '__main__':
    unittest.main()
