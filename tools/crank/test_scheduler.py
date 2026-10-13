"""Staged scheduler/lifecycle POLICY tests with runtime/hardware stubs only.

No Lua, native framebuffer, electrical I/O or audible output is simulated here.
Set CRANKFRUIT_APP_DIR to a copied package's app directory. Run with python -B.
SPDX-License-Identifier: MIT
"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
DEFAULT_APP = HERE.parent / 'app' if (HERE.parent / 'app').is_dir() else HERE.parent
APP = Path(os.environ.get('CRANKFRUIT_APP_DIR', str(DEFAULT_APP)))


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


with patch.dict(sys.modules, {'_crankfruit_pcm': None}):
    STREAM = module_at('reviewed_stream', APP / 'stream.py')
with patch.dict(sys.modules, {'stream': STREAM}):
    PLAYER = module_at('reviewed_player', APP / 'player.py')
with patch.dict(sys.modules, {'player': PLAYER,
                             'cartridges': types.SimpleNamespace(discover=lambda root: [], load=lambda item: b'fixture')}):
    MAIN = module_at('reviewed_crankfruit', APP / 'crankfruit.py')


class ClockFixture:
    def __init__(self):
        self.ms = 0
    def now(self):
        return self.ms
    def advance(self, ms):
        self.ms += ms


class TransportFixture:
    """Policy-only immediate acceptance and explicit pending/stop state."""
    def __init__(self, events):
        self.events = events
        self.audio_pending = 0
    def audio_write(self, pcm, sample_rate=32000):
        room = max(0, 2880 - self.audio_pending * 2)
        n = min(room, len(pcm))
        self.audio_pending += n // 2
        return n
    def audio_stop(self):
        self.events.append('audio_stop')
        self.audio_pending = 0


class RuntimeFixture:
    def __init__(self, events):
        self.events = events
        self.steps = []
    def refresh_rate(self):
        return 30
    def step(self, buttons, angle, delta, elapsed):
        self.steps.append((buttons, angle, delta, elapsed))
        self.events.append('runtime_step')
    def audio_into(self, target, rate=32000):
        target[:] = bytes(len(target))
        return len(target)
    def heap_stats(self):
        return (0,0,32768,0)
    def close(self):
        self.events.append('runtime_close')


class CrankFixture:
    kind = 'fixture'
    enabled = True
    def __init__(self, events):
        self.events = events
        self.reads = 0
        self.result = (355.0, -15.0)
        self.failure = None
    def read(self):
        self.events.append('crank_read')
        self.reads += 1
        if self.failure:
            raise self.failure
        return self.result
    def close(self):
        self.events.append('crank_close')


class HardwareFixture:
    def __init__(self, events):
        self.events = events
        self.clock = ClockFixture()
        self.fb = TransportFixture(events)
        self.runtime = RuntimeFixture(events)
        self.runtime_class = lambda source, heap_cap: self.runtime
        self.cleanup_error = None
    def initialize(self):
        self.events.append('hardware_initialize')
    def present(self, runtime):
        return True
    def read_buttons(self):
        return 0
    def close(self):
        self.events.append('hardware_close')
        self.fb.audio_stop()
        return True


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.hardware = HardwareFixture(self.events)
        self.crank = CrankFixture(self.events)
        self.game = PLAYER.GamePlayer(self.hardware.runtime, self.hardware, self.hardware.fb,
                                      self.hardware.clock, crank=self.crank)
        self.game.start()
    def test_prefill_and_before_deadline_do_not_read(self):
        self.assertEqual(self.crank.reads, 0)
        for now in range(33):
            self.hardware.clock.ms = now
            self.game.tick()
        self.assertEqual(self.crank.reads, 0)
        self.assertEqual(len(self.hardware.runtime.steps), 2)
    def test_capacity_backpressure_does_not_consume_input(self):
        self.game.stream.used = self.game.stream.capacity
        self.hardware.fb.audio_pending = 1440
        self.hardware.clock.ms = 33
        self.game.tick()
        self.assertEqual(self.crank.reads, 0)
        self.assertEqual(self.game.metrics['queue_backpressure'], 1)
        self.assertEqual(len(self.hardware.runtime.steps), 2)
    def test_exact_one_read_and_propagation_per_admitted_frame(self):
        self.hardware.clock.ms = 33
        self.game.tick(2, angle=100, delta=99)
        self.assertEqual(self.hardware.runtime.steps[-1], (2,355.0,-15.0,66))
        self.assertEqual(self.crank.reads, 1)
        for _ in range(20):
            self.game.tick()
        self.assertEqual(self.crank.reads, 1)
        self.crank.result = (10.0,15.0)
        self.hardware.clock.ms = 66
        self.game.tick(1)
        self.assertEqual(self.hardware.runtime.steps[-1], (1,10.0,15.0,99))
        self.assertEqual(self.crank.reads, 2)
        self.assertEqual(self.events[-2:], ['crank_read','runtime_step'])
    def test_no_crank_preserves_explicit_angle_delta(self):
        self.game.crank = None
        self.hardware.clock.ms = 33
        self.game.tick(1, angle=22, delta=-7)
        self.assertEqual(self.hardware.runtime.steps[-1][1:3], (22,-7))
        self.assertEqual(self.crank.reads, 0)
    def test_read_failure_stops_audio_before_runtime_close(self):
        self.crank.failure = OSError('crank disconnected')
        self.hardware.clock.ms = 33
        with self.assertRaisesRegex(OSError, 'crank disconnected'):
            self.game.tick()
        self.assertTrue(self.game.finished)
        self.assertEqual(self.game.metrics['errors'], 1)
        self.assertEqual(len(self.hardware.runtime.steps), 2)
        self.assertEqual(self.hardware.fb.audio_pending, 0)
        self.game.close_runtime()
        self.assertLess(self.events.index('audio_stop'), self.events.index('runtime_close'))
    def test_scene_failure_completes_stop_before_close(self):
        self.events.clear()
        self.hardware.fb.audio_pending = 0
        self.hardware.runtime.steps.clear()
        self.crank.failure = OSError('scene crank failure')
        with patch.object(MAIN.time, 'sleep', lambda seconds: self.hardware.clock.advance(1)), \
                patch.object(MAIN.gc, 'mem_free', lambda: 12345, create=True), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(OSError, 'scene crank failure'):
                MAIN.run_scene(self.hardware, dict(slug='fixture',kind='lua',heap_cap=32768),
                               duration=100, crank=self.crank)
        self.assertLess(self.events.index('audio_stop'), self.events.index('runtime_close'))
        self.assertNotIn('crank_close', self.events)  # shared app input, not scene owned
        self.assertEqual(self.hardware.fb.audio_pending, 0)


class PrefillTests(unittest.TestCase):
    def player(self, prefill):
        hardware = HardwareFixture([])
        return hardware, PLAYER.GamePlayer(hardware.runtime, hardware, hardware.fb, hardware.clock,
                                           prefill_frames=prefill)

    def test_four_frame_prefill_fits_larger_queue(self):
        hardware, game = self.player(4)
        self.assertEqual(game.stream.capacity, 12288)
        self.assertEqual(game.lead_ms, 100)
        game.start()
        self.assertEqual(game.metrics['primed_frames'], 4)
        self.assertEqual(len(hardware.runtime.steps), 4)
        self.assertEqual(game.metrics['errors'], 0)

    def test_two_and_three_keep_original_queue(self):
        for prefill in (2, 3):
            _, game = self.player(prefill)
            self.assertEqual(game.stream.capacity, 8192)
        for bad in (1, 5, 3.0):
            with self.assertRaises(ValueError):
                self.player(bad)

    def test_app_uses_four_frame_prefill(self):
        self.assertIn('prefill_frames=4', (APP / 'crankfruit.py').read_text())


class StopMain(BaseException):
    pass


class MainPolicyTests(unittest.TestCase):
    def run_main(self, kind, config_error=None):
        events = []
        hardware = HardwareFixture(events)
        crank = CrankFixture(events)
        seen = []
        def config(path):
            events.append(('config',path))
            if config_error:
                raise config_error
            return {'enabled':False}
        def make_crank(value):
            events.append(('constructed',value))
            return crank
        def scene(hw, item=None, **kw):
            seen.append((item,kw))
            if item is not None and item.get('slug') == 'fixture':
                raise StopMain()
            return 0
        with patch.dict(sys.modules, {
            'direct_hardware':types.SimpleNamespace(DirectHardware=lambda:hardware),
            'crank_input':types.SimpleNamespace(CrankInput=make_crank,load_config=config),
        }), patch.object(MAIN, 'entries', lambda:[dict(slug='fixture',kind=kind,enabled=True)]), \
                patch.object(MAIN, 'run_scene', scene), contextlib.redirect_stdout(io.StringIO()):
            expected = type(config_error) if config_error and config_error.args[0] != 2 else StopMain
            with self.assertRaises(expected):
                MAIN.main()
        return events, seen, crank
    def test_config_path_game_only_routing_and_final_close(self):
        events, seen, crank = self.run_main('lua')
        self.assertIn(('config','/crank.json'), events)
        self.assertIsNone(seen[0][1].get('crank'))  # splash
        self.assertIs(seen[1][1].get('crank'), crank)  # library: crank moves the highlight
        self.assertIs(seen[2][1]['crank'], crank)
        self.assertLess(events.index('crank_close'), events.index('hardware_close'))
    def test_sound_builtin_receives_crank(self):
        events, seen, crank = self.run_main('builtin')
        self.assertIs(seen[2][1]['crank'], crank)  # Sound Explorer: crank changes values
    def test_only_missing_config_selects_disabled_default(self):
        events, _, _ = self.run_main('lua', OSError(2,'missing'))
        self.assertIn(('constructed',None), events)
        events, _, _ = self.run_main('lua', OSError(13,'permission'))
        self.assertFalse(any(isinstance(x,tuple) and x[0]=='constructed' for x in events))
        self.assertIn('hardware_close', events)
    def test_invalid_json_is_not_treated_as_missing(self):
        events, _, _ = self.run_main('lua', ValueError('invalid JSON'))
        self.assertFalse(any(isinstance(x,tuple) and x[0]=='constructed' for x in events))
        self.assertIn('hardware_close', events)

    def run_library(self, failures, error_type=RuntimeError, spacing_ms=0):
        events = []
        hardware = HardwareFixture(events)
        library_calls = []
        def scene(hw, item=None, **kw):
            if kw.get('items') is not None:
                library_calls.append(kw.get('message'))
                hw.clock.advance(spacing_ms)
                if len(library_calls) <= failures:
                    raise error_type('game scheduling deadline exceeded (100ms)')
                return 0
            if item is not None and item.get('slug') == 'fixture':
                raise StopMain()
            return 0
        out = io.StringIO()
        with patch.dict(sys.modules, {
            'direct_hardware': types.SimpleNamespace(DirectHardware=lambda: hardware),
            'crank_input': types.SimpleNamespace(CrankInput=lambda value: CrankFixture(events),
                                                 load_config=lambda path: {'enabled': False}),
        }), patch.object(MAIN, 'entries', lambda: [dict(slug='fixture', kind='lua', enabled=True)]), \
                patch.object(MAIN, 'run_scene', scene), contextlib.redirect_stdout(out):
            try:
                MAIN.main()
                outcome = None
            except StopMain:
                outcome = 'game'
            except BaseException as exc:
                outcome = exc
        return outcome, library_calls, out.getvalue(), events

    def test_library_failure_reopens_library(self):
        outcome, calls, output, events = self.run_library(2)
        self.assertEqual(outcome, 'game')                       # reached the game after recovering
        self.assertEqual(len(calls), 3)
        self.assertTrue(calls[1].startswith('RECOVERED: '))     # footer explains the restart
        self.assertEqual(output.count('LIBRARY_ERROR'), 2)
        self.assertIn('hardware_close', events)

    def test_repeated_library_failures_still_stop(self):
        outcome, calls, output, events = self.run_library(5)
        self.assertIsInstance(outcome, RuntimeError)            # 3 within 60s: give up
        self.assertEqual(len(calls), 3)
        self.assertIn('hardware_close', events)

    def test_spaced_library_failures_keep_recovering(self):
        outcome, calls, _, _ = self.run_library(4, spacing_ms=40000)
        self.assertEqual(outcome, 'game')                       # never 3 inside one minute
        self.assertEqual(len(calls), 5)

    def test_audio_stop_failure_in_library_is_fatal(self):
        outcome, calls, _, _ = self.run_library(1, error_type=MAIN.SceneCleanupError)
        self.assertIsInstance(outcome, MAIN.SceneCleanupError)
        self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
