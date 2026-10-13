"""Host tests for optional display scaling. SPDX-License-Identifier: MIT."""
import importlib.util
import json
import pathlib
import random
import tempfile
import types
import unittest
from direct_hardware import load_display_config, select_blit, SCALES
from hardware import HardwareError

KIT = pathlib.Path(__file__).resolve().parent.parent.parent


def reference_module():
    spec = importlib.util.spec_from_file_location('blit_reference', KIT / 'native' / 'blit' / 'reference.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConfigTests(unittest.TestCase):
    def write(self, folder, text):
        path = pathlib.Path(folder) / 'display.json'
        path.write_text(text)
        return str(path)

    def test_valid_and_template(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(load_display_config(self.write(folder, '{"scale": "1.6"}')), {'scale': '1.6'})
            self.assertEqual(load_display_config(self.write(folder, '{"scale": "1"}')), {'scale': '1'})
            self.assertEqual(load_display_config(self.write(folder, '{}')).get('scale', '1'), '1')
        template = KIT / 'tools' / 'display' / 'display-config.json'
        self.assertEqual(load_display_config(str(template)), {'scale': '1.6s'})
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(load_display_config(self.write(folder, '{"scale": "1.6s"}')), {'scale': '1.6s'})

    def test_invalid_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(load_display_config(self.write(folder, '{"scale": "1.6s", "white": "bright"}')),
                             {'scale': '1.6s', 'white': 'bright'})
            for text in ('{"white": "grey"}', '{"white": 2}', '{"scale": "1.5"}', '{"scale": 1.6}', '{"scale": "2"}', '[]',
                         '{"scale": "1.6", "mode": "x"}', ' ' * 1025):
                with self.assertRaises(ValueError, msg=text[:30]):
                    load_display_config(self.write(folder, text))
            with self.assertRaises(OSError) as missing:
                load_display_config(str(pathlib.Path(folder) / 'absent.json'))
            self.assertEqual(missing.exception.args[0], 2)

    def test_startup_loads_display_config_before_hardware(self):
        source = (KIT / 'app' / 'crankfruit.py').read_text()
        self.assertIn("load_display('/display.json')", source)
        self.assertLess(source.index("load_display('/display.json')"), source.index('hardware.initialize()'))


class SelectionTests(unittest.TestCase):
    def test_selects_native_function_and_byte_count(self):
        module = types.SimpleNamespace(blit='one', blit16='scaled')
        self.assertEqual(select_blit(module, '1'), ('one', 12000))
        self.assertEqual(select_blit(module, '1.6'), ('scaled', 38400))
        self.assertEqual(SCALES, ('1', '1.6', '1.6s'))

    def test_old_helper_without_blit16_fails_clearly(self):
        with self.assertRaises(HardwareError) as error:
            select_blit(types.SimpleNamespace(blit='one'), '1.6')
        self.assertIn('updated _crankfruit_blit', str(error.exception))
        with self.assertRaises(HardwareError):
            select_blit(types.SimpleNamespace(blit='one', blit16='scaled'), '1.5')


class ToggleTests(unittest.TestCase):
    def test_b1_toggles_scale_and_clears_edges_for_1x(self):
        import sys
        from direct_hardware import DirectHardware
        fake = types.SimpleNamespace(blit='one', blit16='scaled')
        sys.modules['_crankfruit_blit'] = fake
        try:
            hw = DirectHardware()
            hw.scale = '1.6'
            hw._blit, hw._blit_bytes = 'scaled', 38400
            hw.scan_view = bytearray(b'\xff' * 38400)
            hw._zeros = bytes(38400)
            hw.settings_button(0)
            self.assertEqual((hw.scale, hw._blit, hw._blit_bytes), ('1', 'one', 12000))
            self.assertEqual(hw.scan_view, bytearray(38400))       # old 1.6x edges cleared
            hw.scan_view[:] = b'\x55' * 38400
            hw.settings_button(0)
            self.assertEqual((hw.scale, hw._blit, hw._blit_bytes), ('1.6', 'scaled', 38400))
            self.assertEqual(hw.scan_view, bytearray(b'\x55' * 38400))  # 1.6x rewrites everything
            hw.settings_button(1); hw.settings_button(2)                 # reserved
            self.assertEqual(hw.scale, '1.6')
            sys.modules['_crankfruit_blit'] = types.SimpleNamespace(blit='one')  # old helper
            hw.set_scale('1')
            hw.set_scale('1.6')                                           # logged, no exception
            self.assertEqual((hw.scale, hw._blit), ('1', 'one'))
        finally:
            del sys.modules['_crankfruit_blit']


class TwoBitTests(unittest.TestCase):
    def test_select_blit2_modes(self):
        calls = []
        module = types.SimpleNamespace(blit='one', blit16='scaled',
                                       blit2=lambda src, dst, mode, white: calls.append((mode, white)) or 76800)
        for scale, mode in (('1', 0), ('1.6', 1), ('1.6s', 2)):
            copy, count = select_blit(module, scale, 2)
            self.assertEqual((copy(b'', b''), count), (76800, 76800))
            self.assertEqual(calls[-1], (mode, 2))  # Playdate-like white by default
        select_blit(module, '1.6s', 2, 3)[0](b'', b'')
        self.assertEqual(calls[-1], (2, 3))
        with self.assertRaises(HardwareError):
            select_blit(types.SimpleNamespace(blit='one', blit16='scaled'), '1.6s', 2)  # old helper
        with self.assertRaises(HardwareError):
            select_blit(module, '1.6s', 1)  # smooth needs greys

    def test_configure_selects_2bit_and_b1_cycles_three_modes(self):
        import sys
        from direct_hardware import DirectHardware
        modes = []
        sys.modules['_crankfruit_blit'] = types.SimpleNamespace(
            blit='one', blit16='scaled', blit2=lambda src, dst, mode, white: modes.append((mode, white)) or 76800)
        try:
            hw = DirectHardware()
            hw.configure({'scale': '1.6'})
            self.assertEqual((hw.color_depth, hw.scale, hw.white), (2, '1.6', 2))
            hw.scan_view = bytearray(b'\x55' * 76800)
            seen = []
            for _ in range(4):
                hw.settings_button(0)
                seen.append(hw.scale)
                hw._blit(b'', b'')
            self.assertEqual(seen, ['1.6s', '1', '1.6', '1.6s'])
            self.assertEqual(modes, [(2, 2), (0, 2), (1, 2), (2, 2)])
            hw.configure({'scale': '1', 'white': 'bright'})
            self.assertEqual(hw.white, 3)
            self.assertEqual(hw.scan_view, bytearray(b'\x55' * 76800))  # blit2 rewrites all; no clear
        finally:
            del sys.modules['_crankfruit_blit']

    def test_reference_blit2_smooth_matches_coverage(self):
        ref = reference_module()
        rng = random.Random(11)
        src = bytearray(rng.getrandbits(8) for _ in range(12480))
        dst = bytearray(76800)
        self.assertEqual(ref.blit2(src, dst, 2), 76800)
        playdate = bytearray(76800)
        ref.blit2(src, playdate, 2, 2)
        self.assertTrue(all(((b >> s) & 3) <= 2 for b in playdate[::97] for s in (0, 2, 4, 6)))
        for _ in range(1500):
            x, y = rng.randrange(640), rng.randrange(480)
            level = 0
            if 48 <= y < 432:
                x0, y0, covered = x * 5, (y - 48) * 5, 0
                for sy in range(y0 // 8, (y0 + 4) // 8 + 1):
                    for sx in range(x0 // 8, (x0 + 4) // 8 + 1):
                        if (src[sy * 52 + sx // 8] >> (7 - sx % 8)) & 1:
                            covered += ((min(x0 + 5, sx * 8 + 8) - max(x0, sx * 8)) *
                                        (min(y0 + 5, sy * 8 + 8) - max(y0, sy * 8)))
                level = round(3 * covered / 25)
            self.assertEqual((dst[y * 160 + x // 4] >> (2 * (x % 4))) & 3, level, (x, y))


class SkipUnchangedTests(unittest.TestCase):
    def make(self, with_helper=True):
        from direct_hardware import DirectHardware
        hw = DirectHardware()
        hw.closed = False
        hw.scan_view = bytearray(76800)
        hw._frame = bytearray(12480)
        hw._previous = bytearray(12480)
        hw._changed = reference_module().frame_changed if with_helper else None
        hw._force = True
        hw.skipped_presents = 0
        hw.blits = []
        hw._blit = lambda src, dst: hw.blits.append(bytes(src[:4])) or 76800
        hw._blit_bytes = 76800
        return hw

    def runtime(self, pattern):
        class Runtime:
            def copy_framebuffer_into(self, target, stride=52):
                target[:] = bytes([pattern[0]]) * len(target)
                return 12000
        return Runtime()

    def test_unchanged_frames_skip_the_scaler(self):
        hw = self.make()
        frame = [0]
        rt = self.runtime(frame)
        hw.present(rt)                     # first frame always drawn (forced)
        hw.present(rt); hw.present(rt)     # identical: skipped
        frame[0] = 9
        hw.present(rt)                     # changed: drawn
        hw.present(rt)
        self.assertEqual(len(hw.blits), 2)
        self.assertEqual(hw.skipped_presents, 3)

    def test_mode_switch_forces_a_redraw(self):
        import sys
        hw = self.make()
        rt = self.runtime([5])
        hw.present(rt); hw.present(rt)
        self.assertEqual(len(hw.blits), 1)
        sys.modules['_crankfruit_blit'] = types.SimpleNamespace(
            blit='one', blit16='scaled', blit2=lambda src, dst, mode, white: 76800)
        try:
            hw.color_depth = 2
            hw.set_scale('1.6')
        finally:
            del sys.modules['_crankfruit_blit']
        hw.present(rt)                     # same frame, new mode: drawn once
        hw.present(rt)
        self.assertEqual(hw.skipped_presents, 2)

    def test_old_helper_without_frame_changed_draws_every_frame(self):
        hw = self.make(with_helper=False)
        rt = self.runtime([1])
        for _ in range(3):
            hw.present(rt)
        self.assertEqual((len(hw.blits), hw.skipped_presents), (3, 0))

    def test_scene_end_reports_skips(self):
        source = (KIT / 'app' / 'crankfruit.py').read_text()
        self.assertIn("print('DISPLAY_DONE',scene,'skipped_unchanged_presents',skipped)", source)


class ReferenceTests(unittest.TestCase):
    def test_python_reference_matches_mapping(self):
        ref = reference_module()
        rng = random.Random(7)
        src = bytearray(rng.getrandbits(8) for _ in range(12480))
        dst = bytearray(38400)
        self.assertEqual(ref.blit16(src, dst), 38400)
        for _ in range(4000):
            x, y = rng.randrange(640), rng.randrange(480)
            expect = 0
            if 48 <= y < 432:
                sx, sy = x * 5 // 8, (y - 48) * 5 // 8
                expect = (src[sy * 52 + sx // 8] >> (7 - sx % 8)) & 1
            self.assertEqual((dst[y * 80 + x // 8] >> (x % 8)) & 1, expect)
        self.assertTrue(all(b == 0 for b in dst[:48 * 80]))
        self.assertTrue(all(b == 0 for b in dst[432 * 80:]))


if __name__ == '__main__':
    unittest.main()
