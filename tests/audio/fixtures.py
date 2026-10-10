"""RECORDING/SIMULATED fixtures only. No hardware modules or device access.

Bank capacities reproduce the audited 625-line packet phase. Clock hypotheses
are test inputs, not discovery of an attached board. Lists/captures in these
fixtures are deliberately not application RAM budgets.
"""
from stream import TICK_MASK


class ManualTicks:
    def __init__(self, start=0):
        self.absolute = start

    def __call__(self):
        return self.absolute & TICK_MASK

    def advance(self, ms):
        self.absolute += ms


class RecordingTransport:
    def __init__(self, ticks, hstx=150000000):
        self.ticks = ticks
        self.hstx = hstx
        self.hz = 60 if hstx == 150000000 else 50
        self.phase = 0
        self.ready = []
        self.active = None
        self.accepted = bytearray()
        self.played = bytearray()
        self.offers = []
        self.capacities = []
        self.stops = 0
        self.discarded = 0
        self.boundary = (ticks.absolute * self.hz) // 1000 + 1
        self.underflows = 0
        self.started = False

    def advance(self):
        while self.ticks.absolute * self.hz >= self.boundary * 1000:
            if self.active is not None:
                self.played.extend(self.active)
            self.active = self.ready.pop(0) if self.ready else None
            if self.active is None and self.started:
                self.underflows += 1
            self.boundary += 1

    @property
    def audio_pending(self):
        self.advance()
        return ((len(self.active) if self.active is not None else 0)
                + sum(len(bank) for bank in self.ready)) // 2

    def audio_write(self, pcm, sample_rate=32000):
        assert sample_rate == 32000 and len(pcm) % 2 == 0
        self.advance()
        if len(self.ready) + (1 if self.active is not None else 0) >= 2:
            return 0
        capacity = 0
        packet_period = (self.hstx // 5) * 4
        for line in range(625):
            self.phase += 32000 * 800
            if line >= 3 and self.phase >= packet_period:
                self.phase -= packet_period
                capacity += 4
        n = min(len(pcm), capacity * 2)
        if n:
            bank = bytes(pcm[:n])
            self.accepted.extend(bank)
            self.ready.append(bank)
            self.offers.append(len(pcm))
            self.capacities.append(capacity)
            self.started = True
        return n

    def audio_stop(self):
        self.advance()
        self.stops += 1
        self.discarded += sum(len(bank) for bank in self.ready)
        self.ready = []


class RecordingDisplay:
    """Real Runtime copies compared to an independently stepped REAL Runtime."""
    def __init__(self, reference=None, transport=None):
        self.reference = reference
        self.transport = transport
        self.frame = bytearray([0xa5] * (52 * 240))
        self.expected = bytearray([0xa5] * (52 * 240))
        self.presentations = 0
        self.dirty_calls = 0
        self.during_audio = 0
        self.changed = 0
        self.previous = None

    def present(self, runtime):
        assert runtime.copy_framebuffer_into(self.frame, stride=52) == 12000
        if self.reference is not None:
            self.reference.copy_framebuffer_into(self.expected, stride=52)
            assert self.frame == self.expected, "actual game frame mismatch"
        for row in range(240):
            assert self.frame[row * 52 + 50] == 0xa5
            assert self.frame[row * 52 + 51] == 0xa5
        if self.previous is not None and self.frame != self.previous:
            self.changed += 1
        self.previous = bytes(self.frame)
        self.dirty_calls += 1  # records the fixture's explicit presentation dirtiness
        self.presentations += 1
        if self.transport is not None and self.transport.audio_pending:
            self.during_audio += 1
        return True
