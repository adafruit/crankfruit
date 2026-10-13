"""Host USB fixtures only. SPDX-License-Identifier: MIT."""
import json
import pathlib
import sys
import tempfile
import unittest
from gamepad_input import (GamepadInput, decode_ds4, load_config, stick_angle, angle_change,
                           LEFT, RIGHT, UP, DOWN, A, B, HOME)


def report(hat=8, face=0, misc=0, x=128, y=128):
    data = bytearray(64)
    data[0] = 1
    data[1], data[2] = x, y
    data[5] = (face & 0xf0) | hat
    data[6] = misc
    return data


class USBError(Exception):
    pass


class USBTimeoutError(USBError):
    pass


class Device:
    def __init__(self, product=0x05c4):
        self.idVendor = 0x054c
        self.idProduct = product
        self.reports = []
        self.reads = 0
        self.configured = 0
        self.detached = 0
        self.kernel_active = True
        self.fail = None
    def set_configuration(self):
        self.configured += 1
    def is_kernel_driver_active(self, interface):
        return self.kernel_active
    def detach_kernel_driver(self, interface):
        self.detached += 1
        self.kernel_active = False
    def read(self, endpoint, buffer, timeout):
        assert endpoint == 0x84 and 2 <= timeout <= 5
        self.reads += 1
        if self.fail is not None:
            raise self.fail
        if not self.reports:
            raise USBTimeoutError('timeout')
        data = self.reports.pop(0)
        buffer[:len(data)] = data
        return len(data)


class USBCore:
    USBError = USBError
    USBTimeoutError = USBTimeoutError
    def __init__(self, device=None):
        self.device = device
        self.finds = 0
    def find(self, idVendor):
        assert idVendor == 0x054c
        self.finds += 1
        return self.device


def enabled(core, **extra):
    config = dict(enabled=True, kind='ds4')
    config.update(extra)
    return GamepadInput(config, usb_core=core)


class DecodeTests(unittest.TestCase):
    def test_idle_and_short_or_unknown_reports(self):
        self.assertEqual(decode_ds4(report()), 0)
        self.assertEqual(decode_ds4(bytearray(7)), 0)
        bad = report(hat=0)
        bad[0] = 0x11  # bluetooth-style report id is not decoded
        self.assertEqual(decode_ds4(bad), 0)

    def test_hat_all_eight_directions(self):
        expected = (UP, UP | RIGHT, RIGHT, DOWN | RIGHT, DOWN, DOWN | LEFT, LEFT, UP | LEFT)
        for hat, bits in enumerate(expected):
            self.assertEqual(decode_ds4(report(hat=hat)), bits, hat)
        for hat in range(8, 16):
            self.assertEqual(decode_ds4(report(hat=hat)), 0)

    def test_captured_board_reports(self):
        # bytes 5..7 recorded from the Fruit Jam capture on 2026-10-09
        for raw, bits in (('00007c', UP), ('040004', DOWN), ('060044', LEFT), ('020060', RIGHT),
                          ('280088', A), ('480048', B), ('1800b4', 0), ('8800c4', 0),
                          ('08010c', 0), ('08105c', 0), ('0820b0', HOME), ('080065', 0), ('080026', 0)):
            data = report()
            data[5:8] = bytes.fromhex(raw)
            self.assertEqual(decode_ds4(data), bits, raw)

    def test_mapping_cross_circle_options(self):
        self.assertEqual(decode_ds4(report(face=0x20)), A)
        self.assertEqual(decode_ds4(report(face=0x40)), B)
        self.assertEqual(decode_ds4(report(face=0x10 | 0x80)), 0)  # square/triangle unused
        self.assertEqual(decode_ds4(report(misc=0x20)), HOME)
        self.assertEqual(decode_ds4(report(misc=0xdf)), 0)  # other shoulder/system buttons unused
        self.assertEqual(decode_ds4(report(hat=2, face=0x60, misc=0x20)), RIGHT | A | B | HOME)

    def test_stick_deadzone_and_disable(self):
        self.assertEqual(decode_ds4(report(x=64, y=191)), 0)
        self.assertEqual(decode_ds4(report(x=63, y=192)), LEFT | DOWN)
        self.assertEqual(decode_ds4(report(x=255, y=0)), RIGHT | UP)
        self.assertEqual(decode_ds4(report(x=0, y=0), stick=False), 0)
        self.assertEqual(decode_ds4(report(x=100), deadzone=20), LEFT)
        self.assertEqual(decode_ds4(report(hat=0, y=255)), UP | DOWN)  # d-pad and stick combine


class ConfigTests(unittest.TestCase):
    def test_disabled_paths_touch_nothing(self):
        before = set(sys.modules)
        for config in (None, {}, {'enabled': False}):
            pad = GamepadInput(config)
            self.assertFalse(pad.enabled)
            self.assertEqual(pad.kind, 'disabled')
            self.assertEqual(pad.poll(0), 0)
        self.assertNotIn('usb', set(sys.modules) - before)
        self.assertNotIn('usb.core', set(sys.modules) - before)

    def test_invalid_settings_rejected(self):
        for config in ({'enabled': 'yes'}, [], {'enabled': True}, {'enabled': True, 'kind': 'xbox'},
                       {'enabled': True, 'kind': 'ds4', 'poll_ms': 7},
                       {'enabled': True, 'kind': 'ds4', 'poll_ms': 101},
                       {'enabled': True, 'kind': 'ds4', 'poll_ms': 25.0},
                       {'enabled': True, 'kind': 'ds4', 'read_timeout_ms': 1},
                       {'enabled': True, 'kind': 'ds4', 'stick': 1},
                       {'enabled': True, 'kind': 'ds4', 'stick_deadzone': 121},
                       {'enabled': True, 'kind': 'ds4', 'typo': 1}):
            with self.assertRaises(ValueError, msg=repr(config)):
                GamepadInput(config, usb_core=USBCore())

    def test_load_config_bounds_and_shipped_template(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / 'gamepad.json'
            path.write_text('{"enabled": true, "kind": "ds4"}')
            self.assertEqual(load_config(str(path)), {'enabled': True, 'kind': 'ds4'})
            path.write_text('[]')
            with self.assertRaises(ValueError):
                load_config(str(path))
            path.write_text(' ' * 4097)
            with self.assertRaises(ValueError):
                load_config(str(path))
            with self.assertRaises(OSError) as missing:
                load_config(str(pathlib.Path(folder) / 'absent.json'))
            self.assertEqual(missing.exception.args[0], 2)
        template = json.loads((pathlib.Path(__file__).parent / 'gamepad-config.json').read_text())
        self.assertTrue(GamepadInput(template, usb_core=USBCore()).enabled)

    def test_tool_copy_matches_app(self):
        here = pathlib.Path(__file__).resolve().parent
        app = here.parent.parent / 'app' / 'gamepad_input.py'
        self.assertEqual((here / 'gamepad_input.py').read_bytes(), app.read_bytes())


class PollTests(unittest.TestCase):
    def test_connect_detaches_and_reads_once_per_interval(self):
        device = Device()
        core = USBCore(device)
        pad = enabled(core)
        self.assertEqual(pad.poll(0), 0)  # first poll connects, no read yet
        self.assertEqual((device.configured, device.detached, pad.metrics['connects']), (1, 1, 1))
        device.reports = [report(hat=6, face=0x20)]
        self.assertEqual(pad.poll(25), LEFT | A)
        for now in range(26, 50):
            self.assertEqual(pad.poll(now), LEFT | A)  # held between polls
        self.assertEqual(device.reads, 1)
        device.reports = [report()]
        self.assertEqual(pad.poll(50), 0)
        self.assertEqual(device.reads, 2)

    def test_timeout_keeps_held_state(self):
        device = Device()
        pad = enabled(USBCore(device), poll_ms=8)
        pad.poll(0)
        device.reports = [report(face=0x40)]
        self.assertEqual(pad.poll(8), B)
        self.assertEqual(pad.poll(16), B)  # timeout: no fresh report
        self.assertEqual(pad.metrics['timeouts'], 1)

    def test_absent_device_retries_once_per_second(self):
        core = USBCore(None)
        pad = enabled(core)
        for now in range(0, 3000, 25):
            self.assertEqual(pad.poll(now), 0)
        self.assertEqual(core.finds, 3)

    def test_wrong_sony_product_ignored(self):
        device = Device(product=0x0268)  # PS3 controller
        pad = enabled(USBCore(device))
        self.assertEqual(pad.poll(0), 0)
        self.assertIsNone(pad.device)
        self.assertEqual(device.configured, 0)

    def test_second_generation_ds4_accepted_without_kernel_driver_api(self):
        device = Device(product=0x09cc)
        def unsupported(interface):
            raise NotImplementedError
        device.is_kernel_driver_active = unsupported
        pad = enabled(USBCore(device))
        pad.poll(0)
        self.assertIs(pad.device, device)

    def test_unplug_releases_buttons_and_reconnects(self):
        device = Device()
        core = USBCore(device)
        pad = enabled(core)
        pad.poll(0)
        device.reports = [report(hat=2)]
        self.assertEqual(pad.poll(25), RIGHT)
        device.fail = USBError('no device')
        self.assertEqual(pad.poll(50), 0)
        self.assertIsNone(pad.device)
        self.assertEqual(pad.metrics['disconnects'], 1)
        self.assertEqual(pad.poll(75), 0)  # no immediate retry storm
        self.assertEqual(core.finds, 1)
        device.fail = None
        self.assertEqual(pad.poll(1050), 0)  # reconnects
        self.assertEqual(core.finds, 2)
        device.reports = [report(hat=4)]
        self.assertEqual(pad.poll(1075), DOWN)

    def test_connect_error_is_retried_later(self):
        device = Device()
        def broken():
            raise USBError('stall')
        device.set_configuration = broken
        core = USBCore(device)
        pad = enabled(core)
        self.assertEqual(pad.poll(0), 0)
        self.assertIsNone(pad.device)
        self.assertEqual(pad.poll(500), 0)
        self.assertEqual(core.finds, 1)

    def test_close_idempotent_and_rejects_polls(self):
        pad = enabled(USBCore(Device()))
        pad.close()
        pad.close()
        with self.assertRaises(RuntimeError):
            pad.poll(0)


def stick_report(angle=None, radius=120):
    """Report with the right stick pushed toward a Playdate-convention angle."""
    import math
    data = report()
    if angle is None:
        data[3], data[4] = 128, 128
    else:
        rad = math.radians(angle)
        data[3] = round(128 + radius * math.sin(rad))
        data[4] = round(128 - radius * math.cos(rad))
    return data


class StickCrankTests(unittest.TestCase):
    def crank_pad(self, **extra):
        device = Device()
        pad = enabled(USBCore(device), poll_ms=8, crank=True, **extra)
        pad.poll(0)  # connect
        return pad, device

    def feed(self, pad, device, now, data):
        device.reports = [data]
        pad.poll(now)

    def test_angle_convention_and_wrap(self):
        self.assertAlmostEqual(stick_angle(128, 0), 0.0)       # up
        self.assertAlmostEqual(stick_angle(255, 128), 90.0)    # right: clockwise positive
        self.assertAlmostEqual(stick_angle(128, 255), 180.0)   # down
        self.assertAlmostEqual(stick_angle(1, 128), 270.0)     # left
        self.assertAlmostEqual(angle_change(10, 350), 20.0)
        self.assertAlmostEqual(angle_change(350, 10), -20.0)
        self.assertAlmostEqual(angle_change(180, 0), 180.0)

    def test_disabled_by_default_and_config(self):
        self.assertIsNone(enabled(USBCore(Device())).crank)
        self.assertIsNone(GamepadInput({'enabled': False, 'crank': True}).crank)
        for bad in ({'crank': 1}, {'crank_engage': 39}, {'crank_engage': 128}):
            with self.assertRaises(ValueError, msg=repr(bad)):
                enabled(USBCore(Device()), **bad)
        crank = enabled(USBCore(Device()), crank=True).crank
        self.assertEqual((crank.kind, crank.enabled), ('ds4_right_stick', True))

    def test_clockwise_rotation_accumulates_once_per_read(self):
        pad, device = self.crank_pad()
        crank = pad.crank
        now = 8
        for angle in (0, 15, 30, 45):
            self.feed(pad, device, now, stick_report(angle))
            now += 8
        angle, delta = crank.read()  # first read in a scene: baseline only
        self.assertAlmostEqual(angle, 45.0, delta=1.0)
        self.assertEqual(delta, 0.0)
        for target in (60, 75, 90):
            self.feed(pad, device, now, stick_report(target))
            now += 8
        angle, delta = crank.read()
        self.assertAlmostEqual(angle, 90.0, delta=1.0)
        self.assertAlmostEqual(delta, 45.0, delta=1.0)
        self.assertEqual(crank.read()[1], 0.0)  # consumed exactly once

    def test_counterclockwise_across_zero_is_negative(self):
        pad, device = self.crank_pad()
        self.feed(pad, device, 8, stick_report(20))
        pad.crank.read()
        for i, target in enumerate((10, 0, 350, 340)):
            self.feed(pad, device, 16 + 8 * i, stick_report(target))
        angle, delta = pad.crank.read()
        self.assertAlmostEqual(angle, 320.0, delta=1.0)  # virtual angle: 0 - 40
        self.assertAlmostEqual(delta, -40.0, delta=1.0)

    def test_full_turns_accumulate_beyond_360(self):
        pad, device = self.crank_pad()
        self.feed(pad, device, 8, stick_report(0))
        pad.crank.read()
        now = 16
        total = 0.0
        for step in range(1, 25):  # 24 steps of 30 degrees = two turns
            self.feed(pad, device, now, stick_report(step * 30 % 360))
            now += 8
            if step % 4 == 0:
                total += pad.crank.read()[1]  # game reads stay under the stale limit
        self.assertAlmostEqual(total, 720.0, delta=2.0)
        self.assertAlmostEqual(pad.crank_angle % 360.0, 0.0, delta=1.0)

    def test_release_holds_angle_and_reengage_adds_no_movement(self):
        pad, device = self.crank_pad()
        self.feed(pad, device, 8, stick_report(90))
        self.feed(pad, device, 16, stick_report(120))
        pad.crank.read()
        self.assertAlmostEqual(pad.crank_angle, 30.0, delta=1.0)
        self.feed(pad, device, 24, stick_report(None))      # centred: released
        self.assertAlmostEqual(pad.crank.read()[0], 30.0, delta=1.0)
        self.feed(pad, device, 32, stick_report(270))       # re-engaged elsewhere
        angle, delta = pad.crank.read()
        self.assertAlmostEqual(angle, 30.0, delta=1.0)      # virtual crank does not jump
        self.assertEqual(delta, 0.0)
        self.feed(pad, device, 40, stick_report(300))
        self.assertAlmostEqual(pad.crank.read()[1], 30.0, delta=1.0)

    def test_scale_slows_movement_and_angle_together(self):
        pad, device = self.crank_pad(crank_scale=50)
        self.feed(pad, device, 8, stick_report(0))
        pad.crank.read()
        for i, target in enumerate((30, 60, 90)):
            self.feed(pad, device, 16 + 8 * i, stick_report(target))
        angle, delta = pad.crank.read()
        self.assertAlmostEqual(delta, 45.0, delta=1.0)
        self.assertAlmostEqual(angle, 45.0, delta=1.0)
        for bad in (9, 201, 0.5):
            with self.assertRaises(ValueError):
                enabled(USBCore(Device()), crank=True, crank_scale=bad)

    def test_hysteresis_keeps_engaged_between_thresholds(self):
        pad, device = self.crank_pad()
        self.feed(pad, device, 8, stick_report(0, radius=70))   # below engage 80
        self.assertFalse(pad.crank_engaged)
        self.feed(pad, device, 16, stick_report(0, radius=90))
        self.assertTrue(pad.crank_engaged)
        self.feed(pad, device, 24, stick_report(30, radius=65))  # above release 60
        self.assertTrue(pad.crank_engaged)
        self.assertAlmostEqual(pad.crank_pending, 30.0, delta=1.5)
        self.feed(pad, device, 32, stick_report(60, radius=50))
        self.assertFalse(pad.crank_engaged)

    def test_movement_outside_a_game_is_dropped(self):
        pad, device = self.crank_pad()
        self.feed(pad, device, 8, stick_report(0))
        pad.crank.read()
        now = 16
        for target in range(10, 360, 10):  # library: polled, no game reading
            self.feed(pad, device, now, stick_report(target))
            now += 25
        angle, delta = pad.crank.read()
        self.assertAlmostEqual(angle, 350.0, delta=1.0)
        self.assertEqual(delta, 0.0)

    def test_unplug_clears_crank_state(self):
        pad, device = self.crank_pad()
        self.feed(pad, device, 8, stick_report(0))
        pad.crank.read()
        self.feed(pad, device, 16, stick_report(40))
        device.fail = USBError('gone')
        pad.poll(24)
        self.assertEqual(pad.crank.read()[1], 0.0)
        self.assertFalse(pad.crank_engaged)

    def test_left_stick_and_buttons_unaffected(self):
        pad, device = self.crank_pad()
        data = stick_report(90)
        data[5] = 0x20 | 6  # cross + d-pad left
        self.feed(pad, device, 8, data)
        self.assertEqual(pad.bits, LEFT | A)


class PlayerIntegrationTests(unittest.TestCase):
    def test_stick_crank_wiring(self):
        app = pathlib.Path(__file__).resolve().parent.parent.parent / 'app'
        source = (app / 'crankfruit.py').read_text()
        self.assertIn('crank=hardware.gamepad.crank', source)
        self.assertIn('hardware crank takes priority', source)

    """Source-level checks: player bits are masked and Options routes home."""
    def test_scene_loop_masks_home_and_routes(self):
        app = pathlib.Path(__file__).resolve().parent.parent.parent / 'app'
        source = (app / 'crankfruit.py').read_text()
        self.assertIn('player.tick(active & 63)', source)
        self.assertIn("if active & 64: route = 'library'", source)
        self.assertIn("load_gamepad_config('/gamepad.json')", source)
        hardware = (app / 'hardware.py').read_text()
        self.assertIn('pad = self.gamepad.poll(now)', hardware)
        self.assertIn('bits |= pad', hardware)
        self.assertIn('self.gamepad.record_poll(self.clock.now() - now)', hardware)

    def test_hardware_read_buttons_merges_gamepad(self):
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / 'app'))
        try:
            from hardware import Hardware
            from player import Debounce
        finally:
            sys.path.pop(0)

        class Clock:
            t = 0
            def now(self):
                return self.t

        class Pin:
            def __init__(self, pressed):
                self.value = not pressed

        class Pad:
            bits = A | HOME
            device = None  # enabled but not connected: onboard buttons still play
            recorded = []
            def poll(self, now):
                hw.clock.t += 5  # a slow poll, measured by the caller
                return self.bits
            def record_poll(self, spent):
                self.recorded.append(spent)

        hw = Hardware()
        hw.clock = Clock()
        hw.debounce = Debounce(hw.clock)
        hw.buttons = [Pin(True), Pin(False), Pin(False)]
        self.assertEqual(hw.read_buttons(), 0)  # onboard debounce pending; no pad yet
        hw.clock.t = 20
        self.assertEqual(hw.read_buttons(), LEFT)
        hw.gamepad = Pad()
        self.assertEqual(hw.read_buttons(), LEFT | A | HOME)
        self.assertEqual(hw.gamepad.recorded, [5])

    def test_connected_gamepad_turns_onboard_buttons_into_settings(self):
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / 'app'))
        try:
            from hardware import Hardware
            from player import Debounce
        finally:
            sys.path.pop(0)

        class Clock:
            t = 0
            def now(self):
                return self.t

        class Pin:
            def __init__(self):
                self.value = True  # released (pull-up)

        class Pad:
            bits = RIGHT
            device = object()  # connected
            def poll(self, now):
                return self.bits
            def record_poll(self, spent):
                pass

        presses = []
        hw = Hardware()
        hw.settings_button = presses.append
        hw.clock = Clock()
        hw.debounce = Debounce(hw.clock)
        hw.buttons = [Pin(), Pin(), Pin()]
        hw.gamepad = Pad()
        self.assertEqual(hw.read_buttons(), RIGHT)
        hw.buttons[0].value = False                  # press B1
        hw.clock.t = 20; hw.read_buttons()           # change seen, still debouncing
        self.assertEqual(presses, [])
        hw.clock.t = 40
        self.assertEqual(hw.read_buttons(), RIGHT)   # stable: B1 is not LEFT any more
        self.assertEqual(presses, [0])
        hw.clock.t = 60
        hw.read_buttons()                            # held: no repeat
        self.assertEqual(presses, [0])
        hw.buttons[0].value = True; hw.buttons[2].value = False  # release B1, press B3
        hw.clock.t = 80; hw.read_buttons()
        hw.clock.t = 100
        self.assertEqual(hw.read_buttons(), RIGHT)   # B3 is not A any more
        self.assertEqual(presses, [0, 2])
        hw.gamepad.device = None                     # unplugged: B3 plays again
        hw.clock.t = 120
        self.assertEqual(hw.read_buttons(), RIGHT | A)
        self.assertEqual(presses, [0, 2])


class PollTimingTests(unittest.TestCase):
    def test_record_poll_and_per_scene_reset(self):
        pad = enabled(USBCore(Device()))
        for spent in (0, 1, 3, 4, 9, 2):
            pad.record_poll(spent)
        first = pad.scene_metrics()
        self.assertEqual((first['max_poll_ms'], first['slow_polls']), (9, 2))
        self.assertIn('reports', first)
        second = pad.scene_metrics()
        self.assertEqual((second['max_poll_ms'], second['slow_polls']), (0, 0))

    def test_scene_loop_prints_gamepad_metrics(self):
        app = pathlib.Path(__file__).resolve().parent.parent.parent / 'app'
        source = (app / 'crankfruit.py').read_text()
        self.assertIn("print('GAMEPAD_DONE',scene,gamepad.scene_metrics())", source)


if __name__ == '__main__':
    unittest.main()
