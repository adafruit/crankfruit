"""Opt-in USB gamepad input for CircuitPython. SPDX-License-Identifier: MIT.

Supports a wired Sony DualShock 4 on the Fruit Jam USB host port. No usb
imports, configuration-file reads or device access on the disabled path.
poll() is rate-limited and holds the last report between reads.
"""
LEFT, RIGHT, UP, DOWN, B, A = 1, 2, 4, 8, 16, 32
HOME = 64  # player-level return to library; never passed to a cartridge
SONY = 0x054c
DS4_PRODUCTS = (0x05c4, 0x09cc)
DS4_ENDPOINT = 0x84
HAT = (UP, UP | RIGHT, RIGHT, DOWN | RIGHT, DOWN, DOWN | LEFT, LEFT, UP | LEFT)
RECONNECT_MS = 1000


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
        if config is None:
            return
        if not isinstance(config, dict) or type(config.get('enabled', False)) is not bool:
            raise ValueError('gamepad enabled must be a boolean in a configuration object')
        if not config.get('enabled', False):
            return
        unknown = [key for key in config if key not in ('enabled', 'kind', 'poll_ms', 'read_timeout_ms', 'stick', 'stick_deadzone')]
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

    def _drop(self, exc):
        self.device = None
        self.bits = 0
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
        return self.bits

    def close(self):
        if not self.closed:
            self.device = None
            self.bits = 0
            self.closed = True
