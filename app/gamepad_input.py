"""Opt-in USB gamepad input for CircuitPython. SPDX-License-Identifier: MIT.

Supports a wired Sony DualShock 4 on the Fruit Jam USB host port. No usb
imports, configuration-file reads or device access on the disabled path.
poll() is rate-limited and holds the last report between reads.
Optional "crank": the right stick's direction becomes a Playdate-style crank.
"""
import math

LEFT, RIGHT, UP, DOWN, B, A = 1, 2, 4, 8, 16, 32
HOME = 64  # player-level return to library; never passed to a cartridge
SONY = 0x054c
DS4_PRODUCTS = (0x05c4, 0x09cc)
DS4_ENDPOINT = 0x84
HAT = (UP, UP | RIGHT, RIGHT, DOWN | RIGHT, DOWN, DOWN | LEFT, LEFT, UP | LEFT)
RECONNECT_MS = 1000
CRANK_HYSTERESIS = 20  # stick radius units between engage and release
CRANK_STALE_MS = 250   # movement older than this (no game reading it) is dropped
SLOW_POLL_MS = 4


def load_config(path):
    """Explicit optional JSON loader; never called automatically at startup."""
    import json
    with open(path, 'r') as source:
        text = source.read(4097)
    if len(text) > 4096:
        raise ValueError('gamepad configuration exceeds 4096 characters')
    config = json.loads(text)
    if not isinstance(config, dict):
        raise ValueError('gamepad configuration must be an object')
    return config


def _integer(config, name, low, high, default):
    value = config.get(name, default)
    if type(value) is not int or not low <= value <= high:
        raise ValueError('invalid gamepad setting: ' + name)
    return value


def decode_ds4(report, stick=True, deadzone=64):
    """USB input report 0x01 to player bits. Short/unknown reports read as idle."""
    if len(report) < 8 or report[0] != 1:
        return 0
    hat = report[5] & 15
    bits = HAT[hat] if hat < 8 else 0
    if stick:
        x, y = report[1], report[2]
        if x < 128 - deadzone: bits |= LEFT
        elif x > 127 + deadzone: bits |= RIGHT
        if y < 128 - deadzone: bits |= UP
        elif y > 127 + deadzone: bits |= DOWN
    if report[5] & 0x20: bits |= A     # cross
    if report[5] & 0x40: bits |= B     # circle
    if report[6] & 0x20: bits |= HOME  # options
    return bits


def stick_angle(x, y):
    """Playdate crank convention: 0 = up, increasing clockwise, in [0, 360)."""
    return math.degrees(math.atan2(x - 128, 128 - y)) % 360.0


def angle_change(new, old):
    """Shortest signed rotation from old to new, in (-180, 180]."""
    change = (new - old) % 360.0
    return change - 360.0 if change > 180.0 else change


class StickCrank:
    """Right-stick crank with the same read()/close() surface as CrankInput."""
    kind = 'ds4_right_stick'
    enabled = True

    @property
    def step_degrees(self):
        return self.pad.crank_step  # degrees per library/Sound Explorer step

    def __init__(self, pad):
        self.pad = pad
        self.read_at = None

    def read(self, frame_id=None):
        pad = self.pad
        now = pad.last_poll
        stale = self.read_at is None or now is None or now - self.read_at > CRANK_STALE_MS
        self.read_at = now
        delta = 0.0 if stale else pad.crank_pending
        pad.crank_pending = 0.0
        return pad.crank_angle, delta

    def close(self):
        self.pad = None


class GamepadInput:
    def __init__(self, config=None, usb_core=None):
        self.closed = False
        self.enabled = False
        self.kind = 'disabled'
        self.device = None
        self.bits = 0
        self.last_poll = None
        self.next_connect = 0
        self.metrics = dict(connects=0, disconnects=0, reports=0, timeouts=0)
        self.max_poll_ms = 0   # per scene; see scene_metrics()
        self.slow_polls = 0    # polls taking SLOW_POLL_MS or longer, per scene
        self.crank = None
        self.crank_angle = 0.0   # virtual crank: advances by scaled stick rotation
        self.crank_pending = 0.0
        self.crank_engaged = False
        self.stick_last = 0.0
        if config is None:
            return
        if not isinstance(config, dict) or type(config.get('enabled', False)) is not bool:
            raise ValueError('gamepad enabled must be a boolean in a configuration object')
        if not config.get('enabled', False):
            return
        unknown = [key for key in config if key not in ('enabled', 'kind', 'poll_ms', 'read_timeout_ms', 'stick', 'stick_deadzone',
                                                        'crank', 'crank_engage', 'crank_scale',
                                                        'crank_step_degrees')]
        if unknown:
            raise ValueError('unknown gamepad setting: ' + unknown[0])
        self.kind = config.get('kind')
        if self.kind != 'ds4':
            raise ValueError('gamepad kind must be ds4')
        self.poll_ms = _integer(config, 'poll_ms', 8, 100, 25)
        self.read_timeout_ms = _integer(config, 'read_timeout_ms', 2, 5, 2)
        self.stick = config.get('stick', True)
        if type(self.stick) is not bool:
            raise ValueError('invalid gamepad setting: stick')
        self.deadzone = _integer(config, 'stick_deadzone', 16, 120, 64)
        crank = config.get('crank', False)
        if type(crank) is not bool:
            raise ValueError('invalid gamepad setting: crank')
        self.crank_engage = _integer(config, 'crank_engage', 40, 127, 80)
        self.crank_scale = _integer(config, 'crank_scale', 10, 200, 100) / 100  # percent
        step = config.get('crank_step_degrees', 18)
        if type(step) not in (int, float) or not 1 <= step <= 90:
            raise ValueError('invalid gamepad setting: crank_step_degrees (1..90 degrees)')
        self.crank_step = float(step)
        if crank:
            self.crank = StickCrank(self)
        if usb_core is None:
            import usb.core as usb_core
        self.usb = usb_core
        self.report = bytearray(64)
        self.enabled = True

    def _connect(self, now):
        self.next_connect = now + RECONNECT_MS
        device = self.usb.find(idVendor=SONY)
        if device is None or device.idProduct not in DS4_PRODUCTS:
            return
        device.set_configuration()
        try:
            if device.is_kernel_driver_active(0):
                device.detach_kernel_driver(0)
        except NotImplementedError:
            pass
        self.device = device
        self.metrics['connects'] += 1
        print('GAMEPAD connected', hex(device.idVendor), hex(device.idProduct))

    def _update_crank(self, report):
        dx, dy = report[3] - 128, report[4] - 128
        radius2 = dx * dx + dy * dy
        limit = self.crank_engage if not self.crank_engaged else self.crank_engage - CRANK_HYSTERESIS
        if radius2 < limit * limit:
            self.crank_engaged = False  # released: hold the last angle, no movement
            return
        angle = stick_angle(report[3], report[4])
        if self.crank_engaged:
            change = angle_change(angle, self.stick_last) * self.crank_scale
            self.crank_pending += change
            self.crank_angle = (self.crank_angle + change) % 360.0
        self.stick_last = angle  # re-engaging elsewhere adds no movement
        self.crank_engaged = True

    def _drop(self, exc):
        self.device = None
        self.bits = 0
        self.crank_engaged = False
        self.crank_pending = 0.0
        self.metrics['disconnects'] += 1
        print('GAMEPAD disconnected', repr(exc))

    def poll(self, now):
        """Return held player bits; touch USB at most once per poll_ms."""
        if self.closed:
            raise RuntimeError('gamepad input closed')
        if not self.enabled:
            return 0
        if self.last_poll is not None and now - self.last_poll < self.poll_ms:
            return self.bits
        self.last_poll = now
        if self.device is None:
            if now < self.next_connect:
                return 0
            try:
                self._connect(now)
            except self.usb.USBError as exc:
                print('GAMEPAD connect failed', repr(exc))
                self.device = None
            return 0
        try:
            self.device.read(DS4_ENDPOINT, self.report, timeout=self.read_timeout_ms)
        except self.usb.USBTimeoutError:
            self.metrics['timeouts'] += 1  # no fresh report: keep held state
            return self.bits
        except self.usb.USBError as exc:
            self._drop(exc)
            self.next_connect = now + RECONNECT_MS
            return 0
        self.metrics['reports'] += 1
        self.bits = decode_ds4(self.report, self.stick, self.deadzone)
        if self.crank is not None and len(self.report) >= 8 and self.report[0] == 1:
            self._update_crank(self.report)
        return self.bits

    def record_poll(self, spent_ms):
        """Caller-measured poll duration; kept cheap for every outer-loop spin."""
        if spent_ms > self.max_poll_ms:
            self.max_poll_ms = spent_ms
        if spent_ms >= SLOW_POLL_MS:
            self.slow_polls += 1

    def scene_metrics(self):
        """Return cumulative counters plus per-scene poll timing, then reset the latter."""
        result = dict(self.metrics, max_poll_ms=self.max_poll_ms, slow_polls=self.slow_polls)
        self.max_poll_ms = 0
        self.slow_polls = 0
        return result

    def close(self):
        if not self.closed:
            self.device = None
            self.bits = 0
            self.crank_pending = 0.0
            self.closed = True
