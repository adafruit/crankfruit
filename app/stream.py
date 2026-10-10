"""Bounded foreground PCM queue. No IRQs or fake audio.

The received HDMI writer publishes an ENTIRE VIDEO FRAME on every nonzero
write. Coalesce game chunks before writing: small intermediate tails must stay
here. 180 packets * 4 samples is its source-level maximum bank capacity; offering
1440 bytes is conservative without guessing the live HSTX clock.
"""
try:
    from _crankfruit_pcm import copy_into as _native_copy
except ImportError:
    _native_copy = None

# The board entry can require this capability; fallback is for portable hosts.
# Never catch a copy failure and silently switch implementations mid-stream.
NATIVE_COPY = _native_copy is not None

RATE = 32000
TICK_MASK = (1 << 29) - 1  # supervisor.ticks_ms, not a uint32 game timestamp
MAX_BANK_SAMPLES = 180 * 4
MAX_BANK_BYTES = MAX_BANK_SAMPLES * 2


def ticks_diff(new, old, mask=TICK_MASK):
    half = (mask + 1) // 2
    return ((new - old + half) & mask) - half


class Clock:
    """Unwrap frequent tick observations; reject backwards/ambiguous gaps."""
    def __init__(self, ticks, mask=TICK_MASK):
        self.ticks = ticks
        self.mask = mask
        self.previous = ticks()
        self.elapsed = 0

    def now(self):
        current = self.ticks()
        delta = ticks_diff(current, self.previous, self.mask)
        if delta < 0:
            raise RuntimeError("clock moved backwards or was unobserved for half a wrap")
        self.previous = current
        self.elapsed += delta
        return self.elapsed


class StreamError(RuntimeError):
    pass


class PcmStream:
    """Fixed byte ring + fixed contiguous offer buffer; accepts partial BYTES.

    The native transport copies synchronously. Only its accepted prefix leaves
    our queue. finish() alone permits a final short bank. stop() discards queued
    bytes but never reports drained/physically silent until pending reaches zero.
    audio_pending is a conservative whole-bank SAMPLE count, not a play cursor.
    """
    def __init__(self, transport, clock, capacity=8192, stall_ms=250):
        if capacity < MAX_BANK_BYTES * 2 or capacity % 2 or stall_ms <= 0:
            raise ValueError("even queue capacity >= 2880 and positive stall deadline required")
        self.transport = transport
        self.clock = clock
        self.buffer = bytearray(capacity)
        self.view = memoryview(self.buffer)
        self.offer = bytearray(MAX_BANK_BYTES)
        self.offer_view = memoryview(self.offer)
        self.capacity = capacity
        self.head = 0
        self.used = 0
        self.state = "OPEN"
        self.error = None
        self.stall_ms = stall_ms
        self.last_progress = clock.now()
        self.last_service = self.last_progress
        self.last_pending = 0
        self.started = False
        self.empty_latched = False
        # Preallocated trace storage. Materialize report tuples only after playback.
        self.event_rows = [[0] * 14 for _ in range(8)]
        self.event_count = 0
        self.last_pump_end = self.last_progress
        self.last_pump_phase = 0
        self.last_pump_ms = 0
        self.last_native_ms = 0
        self.last_copy_ms = 0
        self.last_enqueue_ms = 0
        self.last_step_ms = 0
        self.last_mix_ms = 0
        self.last_present_ms = 0
        self.metrics = dict(enqueued_bytes=0, accepted_bytes=0, dropped_bytes=0,
                            write_calls=0, backpressure=0, partial_writes=0,
                            high_water_bytes=0, short_final_offers=0,
                            underrun_observations=0, errors=0, deadline_failures=0,
                            max_service_gap_ms=0, stop_pending_samples=0,
                            max_pump_ms=0, max_native_write_ms=0,
                            max_offer_copy_ms=0, max_enqueue_ms=0,
                            trace_overflow=0)

    @property
    def underrun_events(self):
        # Legacy shape, for reporting only. Do not query in the playback loop.
        return [tuple(row[:4]) for row in self.event_rows[:self.event_count]]

    @property
    def timing_events(self):
        return [tuple(row) for row in self.event_rows[:self.event_count]]

    @property
    def free(self):
        return self.capacity - self.used

    def enqueue(self, pcm):
        before = self.clock.now()
        try:
            return self._enqueue(pcm)
        finally:
            self.last_enqueue_ms = self.clock.now() - before
            self.metrics["max_enqueue_ms"] = max(self.metrics["max_enqueue_ms"], self.last_enqueue_ms)

    def _enqueue(self, pcm):
        if self.state != "OPEN":
            raise StreamError("enqueue after finish/stop")
        if len(pcm) % 2:
            raise ValueError("PCM16 requires even bytes")
        n = min(len(pcm), self.free)
        if n:
            tail = (self.head + self.used) % self.capacity
            first = min(n, self.capacity - tail)
            if NATIVE_COPY:
                if _native_copy(self.buffer, pcm, tail, 0, first) != first:
                    raise StreamError("native PCM copy returned invalid byte count")
                if first < n:
                    if _native_copy(self.buffer, pcm, 0, first, n - first) != n - first:
                        raise StreamError("native PCM copy returned invalid byte count")
            else:
                source = pcm if isinstance(pcm, memoryview) else memoryview(pcm)
                if first == n and n == len(source):
                    self.view[tail:tail + first] = source
                else:
                    self.view[tail:tail + first] = source[:first]
                if first < n:
                    self.view[:n - first] = source[first:n]
            self.used += n
            self.metrics["enqueued_bytes"] += n
            self.metrics["high_water_bytes"] = max(self.metrics["high_water_bytes"], self.used)
        return n

    def finish(self):
        if self.state == "OPEN":
            self.state = "FINISHING"
            self.last_progress = self.clock.now()

    def _pending(self):
        value = self.transport.audio_pending
        if type(value) is not int or value < 0 or value > 2 * MAX_BANK_SAMPLES:
            raise StreamError("invalid audio_pending sample count")
        return value

    def stop(self):
        if self.state in ("STOPPED", "DRAINED"):
            return self.state
        self.metrics["dropped_bytes"] += self.used
        self.used = 0
        self.state = "STOP_PENDING"  # set BEFORE calling a possibly failing driver
        self.transport.audio_stop()
        self.metrics["stop_pending_samples"] = self._pending()
        if self.metrics["stop_pending_samples"] == 0:
            self.state = "STOPPED"
        return self.state

    def poll_stop(self):
        if self.state == "STOP_PENDING":
            self.metrics["stop_pending_samples"] = self._pending()
            if self.metrics["stop_pending_samples"] == 0:
                self.state = "STOPPED"
        return self.state

    def _fail(self, message, deadline=False):
        self.error = message
        self.metrics["errors"] += 1
        if deadline:
            self.metrics["deadline_failures"] += 1
        try:
            self.stop()
        except Exception:
            # Do not overwrite the original failure or claim successful cleanup.
            self.state = "STOP_PENDING"
        raise StreamError(message)

    def pump(self, phase=0):
        """At most two native writes; no busy loop and no blocking waits."""
        if self.state in ("STOP_PENDING", "STOPPED"):
            return self.poll_stop()
        if self.state == "DRAINED":
            return self.state
        now = self.clock.now()
        gap = now - self.last_service
        self.last_service = now
        self.metrics["max_service_gap_ms"] = max(self.metrics["max_service_gap_ms"], gap)
        native_ms = 0
        copy_ms = 0
        try:
            pending = self._pending()
            if pending < self.last_pending:
                self.last_progress = now
            if self.started and pending == 0 and self.state == "OPEN":
                if not self.empty_latched:
                    self.metrics["underrun_observations"] += 1
                    if self.event_count < len(self.event_rows):
                        row = self.event_rows[self.event_count]
                        row[0] = now
                        row[1] = gap
                        row[2] = self.used
                        row[3] = self.last_pending
                        row[4] = phase
                        row[5] = self.last_pump_phase
                        row[6] = self.last_pump_ms
                        row[7] = self.last_native_ms
                        row[8] = self.last_copy_ms
                        row[9] = self.last_enqueue_ms
                        row[10] = self.last_step_ms
                        row[11] = self.last_mix_ms
                        row[12] = self.last_present_ms
                        row[13] = now - self.last_pump_end
                        self.event_count += 1
                    else:
                        self.metrics["trace_overflow"] += 1
                self.empty_latched = True
            elif pending:
                self.empty_latched = False
            for _ in range(2):
                if not self.used or (self.used < MAX_BANK_BYTES and self.state == "OPEN"):
                    break
                # Each native bank holds at most MAX_BANK_SAMPLES. More than
                # that pending means both are occupied; avoid copying an offer
                # merely for a predictably zero-length native acceptance.
                if pending > MAX_BANK_SAMPLES:
                    self.metrics["backpressure"] += 1
                    break
                n = min(self.used, MAX_BANK_BYTES)
                copy_start = self.clock.now()
                first = min(n, self.capacity - self.head)
                if NATIVE_COPY:
                    if _native_copy(self.offer, self.buffer, 0, self.head, first) != first:
                        raise StreamError("native PCM copy returned invalid byte count")
                    if first < n:
                        if _native_copy(self.offer, self.buffer, first, 0, n - first) != n - first:
                            raise StreamError("native PCM copy returned invalid byte count")
                else:
                    self.offer_view[:first] = self.view[self.head:self.head + first]
                    if first < n:
                        self.offer_view[first:n] = self.view[:n - first]
                if n < MAX_BANK_BYTES:
                    self.metrics["short_final_offers"] += 1
                write_view = self.offer_view if n == MAX_BANK_BYTES else self.offer_view[:n]
                write_start = self.clock.now()
                copied = write_start - copy_start
                copy_ms += copied
                self.metrics["max_offer_copy_ms"] = max(self.metrics["max_offer_copy_ms"], copied)
                try:
                    accepted = self.transport.audio_write(write_view, sample_rate=RATE)
                finally:
                    elapsed = self.clock.now() - write_start
                    native_ms += elapsed
                    self.metrics["max_native_write_ms"] = max(self.metrics["max_native_write_ms"], elapsed)
                self.metrics["write_calls"] += 1
                if type(accepted) is not int or accepted < 0 or accepted > n or accepted % 2:
                    raise StreamError("audio_write returned invalid BYTE acceptance")
                if not accepted:
                    self.metrics["backpressure"] += 1
                    break
                if accepted < n:
                    self.metrics["partial_writes"] += 1
                self.head = (self.head + accepted) % self.capacity
                self.used -= accepted
                self.metrics["accepted_bytes"] += accepted
                self.started = True
                self.last_progress = self.clock.now()
            pending = self._pending()
            self.last_pending = pending
            if self.state == "FINISHING" and not self.used and pending == 0:
                self.state = "DRAINED"
            elif (self.used or pending) and self.clock.now() - self.last_progress > self.stall_ms:
                self._fail("PCM feed/drain deadline exceeded", True)
        except StreamError as exc:
            if self.error is not None:
                raise
            self._fail(str(exc))
        except Exception as exc:
            self._fail("HDMI transport failure: " + str(exc))
        finally:
            self.last_pump_end = self.clock.now()
            self.last_pump_ms = self.last_pump_end - now
            self.last_pump_phase = phase
            self.last_native_ms = native_ms
            self.last_copy_ms = copy_ms
            self.metrics["max_pump_ms"] = max(self.metrics["max_pump_ms"], self.last_pump_ms)
        return self.state


def latency_model(hstx_hz, queue_bytes=8192):
    """Conditional source arithmetic, NOT measured latency or live clock discovery.

    Queue residence needs continuous service to have this bound. An underrun,
    clock stall or foreground deadline violation invalidates the model.
    """
    if hstx_hz not in (125000000, 150000000):
        raise ValueError("only the two explicitly audited clock hypotheses are modeled")
    frame_ms = 800 * 625 * 5 * 1000 / hstx_hz
    return dict(assumed_hstx_hz=hstx_hz, frame_ms=frame_ms,
                two_bank_horizon_ms=2 * frame_ms,
                queue_plus_banks_ms=queue_bytes * 1000 / (RATE * 2) + 2 * frame_ms)
