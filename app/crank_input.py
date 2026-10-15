"""Opt-in crank input for CircuitPython. SPDX-License-Identifier: MIT.

No hardware imports, configuration-file reads, buses or pins on the disabled
path. Call read once per admitted game frame, not once per outer-loop spin.
"""


def load_config(path):
    """Explicit optional JSON loader; never called automatically at startup."""
    import json
    with open(path, 'r') as source:
        text = source.read(4097)
    if len(text) > 4096:
        raise ValueError('crank configuration exceeds 4096 characters')
    config = json.loads(text)
    if not isinstance(config, dict):
        raise ValueError('crank configuration must be an object')
    return config


def _integer(config, name, low, high, default=None):
    value = config.get(name, default)
    if type(value) is not int or not low <= value <= high:
        raise ValueError('invalid crank setting: ' + name)
    return value


def _name(config, key):
    value = config.get(key)
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    if (not isinstance(value, str) or not value or value[0] not in letters
            or any(char not in letters + '0123456789_' for char in value)):
        raise ValueError('explicit board name required: ' + key)
    return value


class _EncoderPosition:
    """Seesaw encoder position via Seesaw.read with an explicit delay.

    Same registers as adafruit_seesaw's encoder_position, which always waits
    8ms. On the Fruit Jam with product 4991, a 0ms delay read in ~1ms and matched
    default-delay reads across 3,711 samples including fast turning.
    """
    MAX_FAILED_FRAMES = 30  # ~1s of consecutive failed reads before giving up

    def __init__(self, seesaw, channel, delay):
        import struct
        self.unpack = struct.unpack
        self.seesaw = seesaw
        self.register = 0x30 + channel  # _ENCODER_POSITION
        self.delay = delay
        self.buffer = bytearray(4)
        self.last = None
        self.consecutive = 0
        self.reset_metrics()

    def reset_metrics(self):
        self.retries_ok = 0       # first read failed, immediate retry succeeded
        self.held_frames = 0      # both failed: last position held (no movement)
        self.max_consecutive = 0

    def scene_metrics(self):
        result = dict(retries_ok=self.retries_ok, held_frames=self.held_frames,
                      max_consecutive=self.max_consecutive)
        self.reset_metrics()
        return result

    def _read(self):
        self.seesaw.read(0x11, self.register, self.buffer, self.delay)  # _ENCODER_BASE
        return self.unpack('>i', self.buffer)[0]

    @property
    def position(self):
        # A Fruit Jam game once ended on a single OSError(19) (I2C no answer).
        # Ride out brief bus glitches; a truly missing encoder still fails.
        try:
            value = self._read()
        except OSError:
            try:
                value = self._read()
                self.retries_ok += 1
            except OSError:
                self.consecutive += 1
                self.held_frames += 1
                self.max_consecutive = max(self.max_consecutive, self.consecutive)
                if self.last is None or self.consecutive >= self.MAX_FAILED_FRAMES:
                    raise
                return self.last
        self.consecutive = 0
        self.last = value
        return value


def _step(config, name):
    """Degrees of crank per discrete step (library highlight, Sound Explorer value)."""
    value = config.get(name, 18)
    if type(value) not in (int, float) or not 1 <= value <= 90:
        raise ValueError('invalid crank setting: ' + name + ' (1..90 degrees)')
    return float(value)


class CrankInput:
    def __init__(self, config=None):
        self.closed = False
        self.enabled = False
        self.kind = 'disabled'
        self.angle = 0.0
        self.sensor = None
        self.bus = None
        self.seesaw = None
        self.previous = None
        self.phase = 0
        self.last_frame = None
        self.cached = (0.0, 0.0)
        self.step_degrees = 18.0  # per discrete step; set per crank in /crank.json
        if config is None:
            return
        if not isinstance(config, dict) or type(config.get('enabled', False)) is not bool:
            raise ValueError('crank enabled must be a boolean in a configuration object')
        if not config.get('enabled', False):
            return
        self.kind = config.get('kind')
        self.direction = _integer(config, 'direction', -1, 1, 1)
        if not self.direction:
            raise ValueError('crank direction must be -1 or 1')
        self.zero = _integer(config, 'zero_degrees', 0, 359, 0)
        self.step_degrees = _step(config, 'step_degrees')
        if self.kind == 'seesaw':
            bus_name = _name(config, 'bus_factory')
            address = _integer(config, 'address', 8, 119)
            channel = _integer(config, 'encoder', 0, 3, 0)
            self.counts = _integer(config, 'counts_per_revolution', 1, 1048576)
            # The library's encoder read sleeps 8ms; 0..7 uses a direct read instead.
            delay_ms = _integer(config, 'read_delay_ms', 0, 8, 8)
            # All config validation precedes hardware imports and initialization.
            import board
            from adafruit_seesaw.seesaw import Seesaw
            from adafruit_seesaw.rotaryio import IncrementalEncoder
            factory = getattr(board, bus_name)
            if not callable(factory):
                raise ValueError('configured board bus factory is not callable')
            self.bus = factory()  # board factory is shared; never deinit it here
            self.seesaw = Seesaw(self.bus, addr=address, reset=False)
            if delay_ms == 8:
                self.sensor = IncrementalEncoder(self.seesaw, encoder=channel)
            else:
                self.sensor = _EncoderPosition(self.seesaw, channel, delay_ms / 1000)
        elif self.kind == 'analog':
            pin_name = _name(config, 'pin')
            self.minimum = _integer(config, 'adc_min', 0, 65534)
            self.maximum = _integer(config, 'adc_max', self.minimum + 1, 65535)
            self.deadband = _integer(config, 'deadband', 0, self.maximum - self.minimum - 1, 128)
            self.travel = _integer(config, 'travel_degrees', 1, 360)
            import board
            import analogio
            self.sensor = analogio.AnalogIn(getattr(board, pin_name))
        elif self.kind == 'rotaryio':
            # Quadrature encoder counted by the chip's PIO (no bus transfers).
            # The two pins must be consecutive GPIOs on RP2350, e.g. STEMMA QT
            # SDA/SCL (GPIO20/21) for a 3.3V encoder, or D6/D7.
            pin_a = _name(config, 'pin_a')
            pin_b = _name(config, 'pin_b')
            self.counts = _integer(config, 'counts_per_revolution', 1, 1048576)
            divisor = _integer(config, 'divisor', 1, 4, 4)
            if divisor == 3:
                raise ValueError('rotaryio divisor must be 1, 2 or 4')
            import board
            import rotaryio
            self.sensor = rotaryio.IncrementalEncoder(getattr(board, pin_a), getattr(board, pin_b), divisor=divisor)
        else:
            raise ValueError('crank kind must be seesaw, analog or rotaryio')
        self.enabled = True

    def read(self, frame_id=None):
        """Read once; same optional frame_id returns the held sample unchanged.

        Delta is consumed by the caller exactly once when its game frame runs.
        A skipped/backpressured tick must reuse that token/sample. Do not replay
        the same cached delta into multiple actual frames.
        """
        if self.closed:
            raise RuntimeError('crank input closed')
        if not self.enabled:
            return self.cached
        if frame_id is not None:
            if type(frame_id) is not int or frame_id < 0:
                raise ValueError('frame_id must be a nonnegative integer')
            if frame_id == self.last_frame:
                return self.cached
            if self.last_frame is not None and frame_id < self.last_frame:
                raise ValueError('frame_id must not move backwards')
        if self.kind in ('seesaw', 'rotaryio'):
            raw = self.sensor.position
            if type(raw) is not int or not -(1 << 31) <= raw < (1 << 31):
                raise ValueError('invalid signed32 encoder position')
            steps = 0 if self.previous is None else raw - self.previous
            if steps > 2147483647:
                steps -= 4294967296
            elif steps < -2147483648:
                steps += 4294967296
            steps *= self.direction
            self.phase = (self.phase + steps) % self.counts
            self.angle = (self.zero + self.phase * 360.0 / self.counts) % 360.0
            delta = steps * 360.0 / self.counts
            self.previous = raw
        else:
            raw = self.sensor.value
            if type(raw) is not int or not 0 <= raw <= 65535:
                raise ValueError('invalid analogio 16-bit value')
            value = min(self.maximum, max(self.minimum, raw))
            if self.previous is None:
                delta = 0.0
                self.previous = value
            elif abs(value - self.previous) <= self.deadband:
                value = self.previous
                delta = 0.0
            else:
                delta = (value - self.previous) * self.travel * self.direction / (self.maximum - self.minimum)
                self.previous = value
            # Delta uses physical pot travel, not shortest distance around a ring.
            self.angle = (self.zero + (value - self.minimum) * self.travel * self.direction / (self.maximum - self.minimum)) % 360.0
        self.cached = (self.angle, delta)
        self.last_frame = frame_id
        return self.cached

    def close(self):
        if not self.closed:
            if self.kind in ('analog', 'rotaryio') and self.sensor is not None:
                self.sensor.deinit()  # owned pins (the seesaw I2C bus is shared, not owned)
            self.sensor = self.seesaw = self.bus = None
            self.closed = True
