"""Host sensor fixtures only. SPDX-License-Identifier: MIT."""
import builtins
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from crank_input import CrankInput, load_config


class Sensor:
    def __init__(self):
        self.raw = 0
        self.reads = 0
        self.closes = 0
    @property
    def position(self):
        self.reads += 1
        return self.raw
    @property
    def value(self):
        self.reads += 1
        return self.raw
    def deinit(self):
        self.closes += 1


class CrankTests(unittest.TestCase):
    def setUp(self):
        self.sensor = Sensor()
        self.bus = Sensor()
        self.events = []
        def bus_factory():
            self.events.append('bus')
            return self.bus
        def seesaw(bus, addr, reset):
            self.events.append((bus,addr,reset))
            return 'seesaw-fixture'
        def encoder(device, encoder):
            self.events.append((device,encoder))
            return self.sensor
        self.patch = patch.dict(sys.modules, {
            'board': types.SimpleNamespace(TEST_BUS=bus_factory, VERIFIED_PIN='pin-fixture'),
            'analogio': types.SimpleNamespace(AnalogIn=lambda pin: self.sensor),
            'adafruit_seesaw': types.ModuleType('adafruit_seesaw'),
            'adafruit_seesaw.seesaw': types.SimpleNamespace(Seesaw=seesaw),
            'adafruit_seesaw.rotaryio': types.SimpleNamespace(IncrementalEncoder=encoder),
        })
        self.patch.start()
    def tearDown(self):
        self.patch.stop()
    def encoder(self, **kw):
        config = dict(enabled=True,kind='seesaw',bus_factory='TEST_BUS',address=54,
                      counts_per_revolution=24)
        config.update(kw)
        return CrankInput(config)
    def analog(self, **kw):
        config = dict(enabled=True,kind='analog',pin='VERIFIED_PIN',adc_min=1000,
                      adc_max=61000,deadband=100,travel_degrees=270)
        config.update(kw)
        return CrankInput(config)
    def test_disabled_no_imports_or_io(self):
        with patch.object(builtins, '__import__', side_effect=AssertionError('hardware import')):
            for config in (None,{},dict(enabled=False,kind='analog',pin='NOT_A_PIN')):
                crank = CrankInput(config)
                self.assertEqual(crank.read(), (0,0))
                crank.close()
        self.assertEqual(self.events, [])
    def test_encoder_detents_wrap_and_signed_delta(self):
        crank = self.encoder()
        self.sensor.raw = 100
        self.assertEqual(crank.read(), (0,0))
        self.sensor.raw = 123
        self.assertEqual(crank.read(), (345,345))
        self.sensor.raw = 124
        self.assertEqual(crank.read(), (0,15))
        self.sensor.raw = 123
        self.assertEqual(crank.read(), (345,-15))
        self.assertEqual(self.events[1], (self.bus,54,False))
    def test_encoder_direction_and_more_than_half_turn(self):
        crank = self.encoder(direction=-1,zero_degrees=20)
        crank.read()
        self.sensor.raw = 16
        self.assertEqual(crank.read(), (140,-240))
    def test_signed32_rollover_both_directions(self):
        crank = self.encoder(counts_per_revolution=360)
        self.sensor.raw = 2147483647
        crank.read()
        self.sensor.raw = -2147483648
        self.assertEqual(crank.read(), (1,1))
        self.sensor.raw = 2147483647
        self.assertEqual(crank.read(), (0,-1))
    def test_optional_frame_token_does_not_double_read(self):
        crank = self.encoder()
        crank.read(0)
        self.sensor.raw = 2
        self.assertEqual(crank.read(0), (0,0))
        self.assertEqual(self.sensor.reads, 1)
        self.assertEqual(crank.read(1), (30,30))
        self.sensor.raw = 3
        self.assertEqual(crank.read(1), (30,30))
        self.assertEqual(crank.read(2), (45,15))
        with self.assertRaises(ValueError):
            crank.read(1)
    def test_once_per_admitted_frame_preserves_accounting(self):
        crank = self.encoder()
        crank.read()
        total = 0
        for target in (1,3,2,24,25,-2,0):
            self.sensor.raw = target
            angle, delta = crank.read()
            total += delta
            self.assertAlmostEqual(angle, total % 360)
        self.assertEqual(total, 0)
        self.assertEqual(self.sensor.reads, 8)
    def test_fast_read_delay_uses_direct_seesaw_read(self):
        import struct
        reads = []
        class Device:
            raw = 5
            def read(self, base, register, buffer, delay):
                reads.append((base, register, delay))
                buffer[:] = struct.pack('>i', self.raw)
        device = Device()
        sys.modules['adafruit_seesaw.seesaw'] = types.SimpleNamespace(Seesaw=lambda bus, addr, reset: device)
        crank = self.encoder(counts_per_revolution=20, read_delay_ms=0, encoder=1)
        self.assertEqual(crank.read(), (0, 0))
        device.raw = 7
        self.assertEqual(crank.read(), (36, 36))
        device.raw = -2147483648  # signed32 unpack
        crank.read()
        self.assertEqual(reads[0], (0x11, 0x31, 0))
        self.assertEqual(len(reads), 3)
        self.assertFalse(any(isinstance(e, tuple) and len(e) == 2 for e in self.events))  # no IncrementalEncoder
    def fast_device(self):
        import struct
        class Device:
            raw = 0
            fail = 0  # number of upcoming reads that raise
            def read(self, base, register, buffer, delay):
                if self.fail:
                    self.fail -= 1
                    raise OSError(19)
                buffer[:] = struct.pack('>i', self.raw)
        device = Device()
        sys.modules['adafruit_seesaw.seesaw'] = types.SimpleNamespace(Seesaw=lambda bus, addr, reset: device)
        return device
    def test_fast_read_retry_and_hold_ride_out_glitches(self):
        device = self.fast_device()
        crank = self.encoder(counts_per_revolution=20, read_delay_ms=0)
        crank.read()
        device.raw = 1; device.fail = 1               # first read fails, retry succeeds
        self.assertEqual(crank.read(), (18, 18))
        device.raw = 2; device.fail = 2               # both fail: held, no movement
        self.assertEqual(crank.read(), (18, 0))
        self.assertEqual(crank.read(), (36, 18))      # recovers with the real movement
        metrics = crank.sensor.scene_metrics()
        self.assertEqual(metrics, dict(retries_ok=1, held_frames=1, max_consecutive=1))
        self.assertEqual(crank.sensor.scene_metrics(), dict(retries_ok=0, held_frames=0, max_consecutive=0))
    def test_fast_read_gives_up_after_consecutive_failures(self):
        device = self.fast_device()
        crank = self.encoder(counts_per_revolution=20, read_delay_ms=0)
        crank.read()
        device.fail = 2 * 29
        for _ in range(29):
            self.assertEqual(crank.read()[1], 0)
        device.fail = 2
        with self.assertRaises(OSError):
            crank.read()                              # 30th failed frame: fail closed
    def test_fast_read_first_failure_still_raises(self):
        device = self.fast_device()
        device.fail = 2
        crank = self.encoder(counts_per_revolution=20, read_delay_ms=0)
        with self.assertRaises(OSError):
            crank.read()                              # no baseline to hold yet
    def test_scene_logs_encoder_metrics(self):
        self.assertIn("print('CRANK_DONE',scene,sensor.scene_metrics())",
                      (pathlib.Path(__file__).resolve().parent.parent.parent / 'app' / 'crankfruit.py').read_text())
    def rotary(self, **kw):
        made = []
        class Encoder:
            def __init__(self, a, b, divisor=4):
                made.append((a, b, divisor))
                self.position = 0
                self.closed = False
            def deinit(self):
                self.closed = True
        sys.modules['rotaryio'] = types.SimpleNamespace(IncrementalEncoder=Encoder)
        sys.modules['board'] = types.SimpleNamespace(SDA='gpio20', SCL='gpio21', D6='gpio6', D7='gpio7')
        config = dict(enabled=True, kind='rotaryio', pin_a='SDA', pin_b='SCL', counts_per_revolution=100)
        config.update(kw)
        return CrankInput(config), made
    def test_rotaryio_100_ppr_handwheel(self):
        # measured on the Fruit Jam: 10 clockwise clicks read -10, one turn -100
        crank, made = self.rotary(direction=-1)
        self.assertEqual(made, [('gpio20', 'gpio21', 4)])
        self.assertEqual(crank.kind, 'rotaryio')
        self.assertEqual(crank.read(), (0, 0))
        crank.sensor.position = -10                 # 10 clicks clockwise
        angle, delta = crank.read()
        self.assertAlmostEqual(delta, 36.0)
        self.assertAlmostEqual(angle, 36.0)
        crank.sensor.position = -110                # one more full turn clockwise
        angle, delta = crank.read()
        self.assertAlmostEqual(delta, 360.0)
        self.assertAlmostEqual(angle, 36.0)
        crank.sensor.position = -100                # 10 clicks back
        self.assertAlmostEqual(crank.read()[1], -36.0)
        sensor = crank.sensor
        crank.close()
        self.assertTrue(sensor.closed)              # owned PIO encoder released
    def test_rotaryio_divisor_and_pins(self):
        _, made = self.rotary(pin_a='D6', pin_b='D7', divisor=1, counts_per_revolution=400)
        self.assertEqual(made, [('gpio6', 'gpio7', 1)])
        for bad in (dict(divisor=3), dict(divisor=0), dict(divisor=8), dict(pin_a='6'),
                    dict(counts_per_revolution=None), dict(pin_b=None)):
            with self.assertRaises(ValueError, msg=repr(bad)):
                self.rotary(**bad)
    def test_step_degrees_per_crank(self):
        self.assertEqual(CrankInput(None).step_degrees, 18.0)
        crank, _ = self.rotary(direction=-1, step_degrees=3.6)
        self.assertAlmostEqual(crank.step_degrees, 3.6)
        self.assertEqual(self.rotary()[0].step_degrees, 18.0)
        for bad in (0, 0.5, 91, '5', True, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                self.rotary(step_degrees=bad)
    def test_scenes_take_the_cranks_step(self):
        source = (pathlib.Path(__file__).resolve().parent.parent.parent / 'app' / 'crankfruit.py').read_text()
        self.assertIn("runtime.crank_step = crank.step_degrees", source)
    def test_default_read_delay_keeps_library_encoder(self):
        self.encoder(read_delay_ms=8).read()
        self.assertIn(('seesaw-fixture', 0), self.events)
        for bad in (-1, 9, 0.5):
            with self.assertRaises(ValueError):
                self.encoder(read_delay_ms=bad)
    def test_analog_calibration_clamp_and_direction(self):
        crank = self.analog(zero_degrees=350)
        self.assertEqual(crank.read(), (350,0))
        self.sensor.raw = 31000
        self.assertEqual(crank.read(), (125,135))
        self.sensor.raw = 65535
        self.assertEqual(crank.read(), (260,135))
        self.sensor.raw = 0
        self.assertEqual(crank.read(), (350,-270))
    def test_analog_reverse_and_full_turn_not_shortest_arc(self):
        crank = self.analog(direction=-1,travel_degrees=360)
        crank.read()
        self.sensor.raw = 61000
        self.assertEqual(crank.read(), (0,-360))
    def test_noise_holds_baseline_slow_motion_accumulates(self):
        self.sensor.raw = 30000
        crank = self.analog()
        initial = crank.read()[0]
        for value in (30050,29950,30099,30100):
            self.sensor.raw = value
            self.assertEqual(crank.read(), (initial,0))
        self.sensor.raw = 30101
        angle, delta = crank.read()
        self.assertAlmostEqual(delta, 101*270/60000)
        self.assertAlmostEqual(angle-initial, delta)
    def test_invalid_configuration_before_hardware(self):
        cases = [dict(enabled='yes'), dict(enabled=True,kind='other'),
                 dict(enabled=True,kind='analog',pin='__bad'),
                 dict(enabled=True,kind='seesaw',bus_factory='TEST_BUS',address=None),
                 dict(enabled=True,kind='analog',pin='VERIFIED_PIN',adc_min=2000,adc_max=1000)]
        for config in cases:
            with self.assertRaises(ValueError):
                CrankInput(config)
        self.assertEqual(self.events, [])
    def test_bad_read_does_not_advance_baseline(self):
        crank = self.encoder()
        crank.read()
        self.sensor.raw = None
        with self.assertRaises(ValueError):
            crank.read()
        self.sensor.raw = 1
        self.assertEqual(crank.read(), (15,15))
    def test_cleanup_owned_adc_but_not_shared_i2c(self):
        crank = self.analog()
        crank.close()
        crank.close()
        self.assertEqual(self.sensor.closes, 1)
        with self.assertRaises(RuntimeError):
            crank.read()
        crank = self.encoder()
        crank.close()
        self.assertEqual(self.bus.closes, 0)
    def test_bounded_explicit_json_load(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory)/'crank.json'
            path.write_text('{"enabled":false}')
            self.assertEqual(load_config(path), {'enabled':False})
            for bad in ('[]', '{bad', ' '*4097):
                path.write_text(bad)
                with self.assertRaises(ValueError):
                    load_config(path)


if __name__ == '__main__':
    unittest.main()
