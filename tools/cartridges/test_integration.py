"""Host-only parent UI/lifecycle policy tests; Canvas/runtime/hardware are stubs.

Real parent Library, entries/run_scene and (where found) GamePlayer/PcmStream
are imported. This is NOT Lua execution, native pixel or hardware evidence.
Set CRANKFRUIT_APP_DIR to test a copied package's app directory.
"""
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

import cartridge_loader as loader
from test_loader import SOURCE, manifest
import json

HERE = Path(__file__).resolve().parent
DEFAULT_APP = HERE.parent/'app' if (HERE.parent/'app'/'crankfruit.py').exists() else HERE.parent
APP = Path(os.environ.get('CRANKFRUIT_APP_DIR', str(DEFAULT_APP)))
SCHEDULER = APP if (APP / 'player.py').exists() else HERE.parents[2] / 'impossible-crankfruit' / 'deployment'


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCanvas:
    made = []
    def __init__(self, path):
        self.count = self.max_commands = 0
        self.closed = False
        self.ids = {'crank_badapple%d'%i:i for i in range(4)}
        self.framebuffer = bytearray(12480)
        self.backgrounds = {'library': bytes([255])*12000}
        self.background_name = 'library'
        self.built_pages = []
        self.render_history = []
        self.text_calls = 0
        self.sprite_calls = []
        self.texts = []
        self.made.append(self)
    def begin(self, name):
        self.count = 0; self.texts = []; self.sprite_calls = []
        self.background_name = name
    def text(self, text, x, y, scale=1):
        # Conservative: actual Canvas may replace a cached label with1 sprite.
        # Otherwise each char including whitespace becomes exactly1 command.
        self.count += len(text); self.texts.append(text); self.text_calls += 1
    def sprite(self, name, x, y, flags=0):
        self.count += 1; self.sprite_calls.append((name,x,y,flags))
    def render(self):
        self.max_commands = max(self.max_commands, self.count)
        if self.count > 256: raise ValueError('sprite command budget exceeded')
        # Synthetic page-identification bytes only, NOT simulated game pixels.
        # This lets policy tests check exact cache selection without pretending
        # that the native compositor or glyph renderer has been exercised.
        background = self.backgrounds[self.background_name]
        for row in range(240):
            self.framebuffer[row*52:row*52+50] = background[row*50:(row+1)*50]
        if self.background_name == 'library':
            marker=hashlib.sha256(repr((self.texts,self.sprite_calls)).encode()).digest()
            self.framebuffer[:32]=marker
            packed=b''.join(self.framebuffer[row*52:row*52+50] for row in range(240))
            self.built_pages.append(dict(texts=list(self.texts),commands=self.count,frame=packed))
        self.render_history.append(dict(background=self.background_name,commands=self.count,
                                        text_calls=len(self.texts),sprites=list(self.sprite_calls)))
    def copy_framebuffer_into(self, target, stride=52): return 12000
    def close(self): self.closed = True


class FakeRuntime:
    made = []
    fail_step = None
    def __init__(self, source, heap_cap=65536):
        self.source = source; self.closed = False; self.steps = 0
        self.made.append(self)
    def refresh_rate(self): return 30
    def step(self, buttons, angle, delta, elapsed):
        self.steps += 1
        if self.fail_step and self.steps >= self.fail_step: raise RuntimeError('injected step failure')
    def audio_into(self, target, rate=32000):
        target[:] = bytes(len(target)); return len(target)
    def copy_framebuffer_into(self, target, stride=52): return 12000
    def heap_stats(self): return (0, 0, 65536, 0)
    def close(self): self.closed = True


class FakeClock:
    def __init__(self): self.ms = 0
    def now(self): self.ms += 1; return self.ms


class FakeHardware:
    def __init__(self):
        self.runtime_class = FakeRuntime
        self.clock = FakeClock(); self.fb = self
        self.stops = 0; self.writes = 0
    @property
    def audio_pending(self): return 0
    def audio_write(self, pcm, sample_rate=32000): self.writes += 1; return len(pcm)
    def audio_stop(self): self.stops += 1
    def read_buttons(self): return 0
    def present(self, runtime): return True


@unittest.skipUnless((APP/'library.py').exists() and (APP/'crankfruit.py').exists(),
                     'parent app files not available; use CRANKFRUIT_APP_DIR')
class ParentPolicyTests(unittest.TestCase):
    def setUp(self):
        FakeCanvas.made = []; FakeRuntime.made = []; FakeRuntime.fail_step = None
        self.modules = mock.patch.dict(sys.modules, {
            'canvas': types.SimpleNamespace(Canvas=FakeCanvas),
            'cartridges': loader,
        })
        self.modules.start()
        self.paths = list(sys.path)
        sys.path.insert(0, str(SCHEDULER)); sys.path.insert(0, str(APP))
        self.library = module_at('parent_library_policy', APP/'library.py')
        # Real scheduler import is optional only when copied package omitted it.
        self.app = module_at('parent_crankfruit_policy', APP/'crankfruit.py') if (SCHEDULER/'player.py').exists() else None
        self.temp = tempfile.TemporaryDirectory()
        self.games = Path(self.temp.name).resolve()/'games'; self.games.mkdir()

    def tearDown(self):
        self.temp.cleanup(); sys.path[:] = self.paths; self.modules.stop()
        FakeRuntime.fail_step = None

    def add_game(self, name, **values):
        folder = self.games/name; folder.mkdir()
        (folder/'manifest.json').write_text(json.dumps(manifest(title=name, **values)))
        (folder/'main.lua').write_bytes(SOURCE)

    def press(self, library, button, elapsed=100):
        library.step(0,0,0,elapsed-1); library.step(button,0,0,elapsed)

    def test_dynamic_discovery_four_plus_items_and_pagination(self):
        if self.app is None: self.skipTest('real scheduler missing')
        for name in ('one-new-game','two-new-game','three-new-game','four-new-game'):
            self.add_game(name)
        items = self.app.entries(str(self.games))
        self.assertEqual(len(items),5)
        self.assertEqual([i['slug'] for i in items[:-1]], sorted(('one-new-game','two-new-game','three-new-game','four-new-game')))
        self.assertEqual(items[-1]['kind'],'builtin')
        library = self.library.Library(FakeRuntime,items)
        for n in range(3): self.press(library,2,100+n*100)
        self.assertEqual(library.selected,3)
        cached=library.canvas.built_pages[3]
        self.assertIn(items[3]['title'][:27], cached['texts'])
        self.assertNotIn(items[0]['title'][:27], cached['texts'])
        self.assertEqual(library.canvas.backgrounds['_page'],library.pages[3])
        self.assertEqual(library.pages[3],cached['frame'])
        self.press(library,32,500); self.assertEqual(library.action,3)
        library.close(); self.assertTrue(library.canvas.closed)

    def test_disabled_selection_never_launches(self):
        self.add_game('disabled',profile='missing-profile')
        library = self.library.Library(FakeRuntime,loader.discover(str(self.games)))
        self.assertIn(library.items[0]['reason'][:60],library.canvas.built_pages[0]['texts'])
        before=library.canvas.text_calls
        self.press(library,32)
        self.assertIsNone(library.action)
        self.assertIn('profile',library.message)
        self.assertEqual(library.canvas.text_calls,before)
        self.assertEqual(library.canvas.backgrounds['_page'],library.pages[0])
        library.close()

    def test_wrap_navigation(self):
        items=[dict(title='GAME%d'%i,description='',enabled=True,reason='') for i in range(5)]
        library=self.library.Library(FakeRuntime,items)
        self.press(library,1); self.assertEqual(library.selected,4)
        self.press(library,2,200); self.assertEqual(library.selected,0)
        library.close()

    def test_maximum_metadata_stays_below_command_budget(self):
        items=[dict(title='T'*48,description='D'*160,reason='R'*160,enabled=i%2==0) for i in range(33)]
        for selected in (0,1,2,3,30,32):
            library=self.library.Library(FakeRuntime,items,selected=selected,message='M'*160)
            self.assertEqual(len(library.pages),33)
            self.assertEqual(sum(len(page) for page in library.pages),396000)
            self.assertEqual(len(library.error_page),12000)
            self.assertTrue(all(type(page) is bytes and len(page)==12000 for page in library.pages))
            library.step(0,0,0,0)
            self.assertLessEqual(library.canvas.max_commands,256)
            self.assertLessEqual(library.canvas.count,1)
            library.close()

    def test_no_text_or_page_rebuild_during_live_step(self):
        items=[dict(title='GAME%d'%i,description='DETAILS'*20,
                    enabled=i%2==0,reason='disabled explanation '*8) for i in range(33)]
        library=self.library.Library(FakeRuntime,items)
        before_calls=library.canvas.text_calls
        before_pages=tuple(library.pages)
        before_builds=len(library.canvas.built_pages)
        for frame in range(150):
            buttons=2 if frame%4==1 else 32 if frame%4==3 else 0
            library.step(buttons,0,0,frame*1000//30)
            self.assertLessEqual(library.canvas.count,1)
        self.assertEqual(library.canvas.text_calls,before_calls)
        self.assertEqual(tuple(library.pages),before_pages)
        self.assertEqual(len(library.canvas.built_pages),before_builds)
        self.assertTrue(all(row['text_calls']==0 for row in library.canvas.render_history[before_builds:]))
        library.close()

    def test_error_footer_is_prebuilt_and_navigation_uses_normal_cache(self):
        items=[dict(title='GAME%d'%i,description='',enabled=True,reason='') for i in range(4)]
        message='GAME ERROR: '+'E'*80
        library=self.library.Library(FakeRuntime,items,selected=1,message=message)
        self.assertIn(message[:60],library.canvas.built_pages[-1]['texts'])
        before=library.canvas.text_calls
        error_page=library.error_page
        library.step(0,0,0,0)
        self.assertEqual(library.canvas.backgrounds['_page'],error_page)
        self.press(library,2,100)
        self.assertIsNone(library.error_page)
        self.assertEqual(library.canvas.backgrounds['_page'],library.pages[2])
        self.assertEqual(library.canvas.text_calls,before)
        library.close()

    def test_scene_runtime_constructor_failure_propagates_without_player(self):
        if self.app is None: self.skipTest('real scheduler missing')
        self.add_game('failure'); item=loader.discover(str(self.games))[0]
        hardware=FakeHardware()
        def fail(source,heap_cap): raise RuntimeError('injected constructor failure')
        hardware.runtime_class=fail
        with self.assertRaisesRegex(RuntimeError,'constructor failure'):
            self.app.run_scene(hardware,item,duration=1)
        self.assertEqual(hardware.writes,0)

    def test_scene_step_failure_stops_audio_and_closes_runtime(self):
        if self.app is None: self.skipTest('real scheduler missing')
        self.add_game('failure'); item=loader.discover(str(self.games))[0]
        hardware=FakeHardware(); FakeRuntime.fail_step=2
        with mock.patch.object(self.app.gc,'mem_free',return_value=1000000,create=True):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError,'step failure'):
                    self.app.run_scene(hardware,item,duration=1)
        self.assertTrue(FakeRuntime.made[-1].closed)
        self.assertGreaterEqual(hardware.stops,1)

    def test_scene_success_drains_and_closes_runtime(self):
        if self.app is None: self.skipTest('real scheduler missing')
        self.add_game('success'); item=loader.discover(str(self.games))[0]
        hardware=FakeHardware()
        with mock.patch.object(self.app.gc,'mem_free',return_value=1000000,create=True):
            with contextlib.redirect_stdout(io.StringIO()):
                result=self.app.run_scene(hardware,item,duration=5)
        self.assertIsNone(result)
        self.assertTrue(FakeRuntime.made[-1].closed)
        self.assertGreater(hardware.writes,0)


if __name__=='__main__':unittest.main(verbosity=2)
