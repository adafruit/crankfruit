"""Experimental combined game scheduler; all Lua/mixing stays foreground.

Dependency-injected transport/display/clock does NOT substitute the Runtime.
Production entry imports the built-in crankjam module or fails explicitly.
"""
from stream import RATE, PcmStream

LEFT, RIGHT, B, A = 1, 2, 16, 32
MAX_GAME_MS = 0x7fffffff  # conservative until the 32-bit binding conversion is fixed


def map_buttons(b1, b2, b3):
    # Chord wins over directions. A remains independently available.
    return (B if b1 and b2 else (LEFT if b1 else 0) | (RIGHT if b2 else 0)) | (A if b3 else 0)


class Debounce:
    def __init__(self, clock, delay_ms=15):
        self.clock = clock
        self.delay_ms = delay_ms
        self.raw = 0
        self.stable = 0
        self.changed_at = clock.now()

    def update(self, raw):
        now = self.clock.now()
        if raw != self.raw:
            self.raw = raw
            self.changed_at = now
        if now - self.changed_at >= self.delay_ms:
            self.stable = raw
        return map_buttons(self.stable & 1, self.stable & 2, self.stable & 4)


class GamePlayer:
    """Two- or three-update prefill, fixed buffers, no catch-up burst.

    Game time starts at 0,33ms (optionally 66ms); after prefill it runs one or
    two ticks ahead of wall time. This is explicit latency, not performance. A late
    step generates one chunk only, counts skipped wall deadlines, and does not
    lose bytes previously mixed. Severe (>100ms) lateness fails closed.
    """
    def __init__(self, runtime, display, transport, clock, present_every=2, prefill_frames=2, crank=None):
        self.runtime = runtime
        self.display = display
        self.clock = clock
        self.crank = crank
        self.hz = runtime.refresh_rate()
        if self.hz != 30:
            raise ValueError("combined player currently requires a 30 Hz game")
        if present_every < 1:
            raise ValueError("present_every must be positive")
        self.present_every = present_every
        if type(prefill_frames) is not int or prefill_frames not in (2, 3):
            raise ValueError("prefill_frames must be 2 or 3")
        self.prefill_frames = prefill_frames
        self.lead_ms = (prefill_frames - 1) * 1000 // self.hz
        self.small = bytearray((RATE // self.hz) * 2)
        self.large = bytearray(((RATE + self.hz - 1) // self.hz) * 2)
        self.small_view = memoryview(self.small)
        self.large_view = memoryview(self.large)
        self.sample_phase = 0
        self.stream = PcmStream(transport, clock)
        self.origin = clock.now()
        self.next_tick = 1
        self.next_due = self.origin + 1000 // self.hz
        self.started = False
        self.finished = False
        self.error = None
        self.metrics = dict(frames=0, mixed_samples=0, presentations=0,
                            late_frames=0, missed_deadlines=0, queue_backpressure=0,
                            max_lateness_ms=0, max_step_ms=0, max_mix_ms=0,
                            max_present_ms=0, max_tick_ms=0, errors=0,
                            deadline_failures=0, primed_frames=0)

    def _frame(self, buttons, elapsed, angle=0.0, delta=0.0, present=True):
        if elapsed > MAX_GAME_MS:
            raise RuntimeError("game elapsed time reached conservative 32-bit binding limit; restart required")
        before = self.clock.now()
        self.runtime.step(buttons, angle, delta, elapsed)
        after = self.clock.now()
        self.stream.last_step_ms = after - before
        self.metrics["max_step_ms"] = max(self.metrics["max_step_ms"], after - before)
        if self.started:
            self.stream.pump(3)  # after Lua step, before mixer
        self.sample_phase += RATE
        count = self.sample_phase // self.hz
        self.sample_phase %= self.hz
        pcm = self.small_view if count == RATE // self.hz else self.large_view
        mix_started = self.clock.now()
        written = self.runtime.audio_into(pcm, rate=RATE)
        if written != len(pcm):
            raise RuntimeError("Runtime.audio_into byte count mismatch")
        self.stream.last_mix_ms = self.clock.now() - mix_started
        self.metrics["max_mix_ms"] = max(self.metrics["max_mix_ms"], self.stream.last_mix_ms)
        if self.stream.enqueue(pcm) != len(pcm):
            raise RuntimeError("internal admission error: mixed PCM would be lost")
        self.metrics["frames"] += 1
        self.metrics["mixed_samples"] += count
        if self.started:
            self.stream.pump(4)  # after mixing/enqueue, before presentation
        self.stream.last_present_ms = 0
        if present and self.metrics["frames"] % self.present_every == 0:
            before = self.clock.now()
            if self.display.present(self.runtime):
                self.metrics["presentations"] += 1
            self.stream.last_present_ms = self.clock.now() - before
            self.metrics["max_present_ms"] = max(self.metrics["max_present_ms"], self.stream.last_present_ms)
        if self.started:
            self.stream.pump(5)  # after optional presentation

    def start(self, buttons=0):
        if self.started or self.finished:
            raise RuntimeError("player already started/finished")
        try:
            for frame in range(self.prefill_frames):
                self._frame(buttons, frame * 1000 // self.hz,
                            present=frame == self.prefill_frames - 1)
            self.metrics["primed_frames"] = self.prefill_frames
            self.started = True
            # Precomputation precedes playback; do not charge it against first deadline.
            self.origin = self.clock.now()
            self.next_due = self.origin + 1000 // self.hz
            self.stream.pump(1)
        except Exception as exc:
            self._failure(exc)

    def _failure(self, exc):
        self.error = str(exc)
        self.metrics["errors"] += 1
        self.finished = True
        try:
            self.stream.stop()
        finally:
            raise exc

    def tick(self, buttons=0, angle=0.0, delta=0.0):
        if not self.started:
            raise RuntimeError("start player before ticking")
        if self.finished:
            return self.stream.pump(7)
        before = self.clock.now()
        try:
            self.stream.pump(2)
            now = self.clock.now()
            if now >= self.next_due:
                late = now - self.next_due
                self.metrics["max_lateness_ms"] = max(self.metrics["max_lateness_ms"], late)
                if late > 2:
                    self.metrics["late_frames"] += 1
                if late > 100:
                    self.metrics["deadline_failures"] += 1
                    raise RuntimeError("game scheduling deadline exceeded (100ms)")
                if self.stream.free < len(self.large):
                    self.metrics["queue_backpressure"] += 1
                    return self.stream.state  # leave both game and PCM unadvanced
                # Sample optional hardware exactly once per admitted update.
                # Reading it on every foreground loop would consume encoder
                # deltas before a frame actually reaches the game.
                if self.crank is not None:
                    angle, delta = self.crank.read()
                elapsed = now - self.origin + self.lead_ms
                self._frame(buttons, elapsed, angle, delta)
                due_index = ((now - self.origin) * self.hz) // 1000 + 1
                self.metrics["missed_deadlines"] += max(0, due_index - self.next_tick - 1)
                self.next_tick = max(self.next_tick + 1, due_index)
                self.next_due = self.origin + (self.next_tick * 1000) // self.hz
            self.stream.pump(6)
            return self.stream.state
        except Exception as exc:
            self._failure(exc)
        finally:
            self.metrics["max_tick_ms"] = max(self.metrics["max_tick_ms"], self.clock.now() - before)

    def finish(self):
        """Graceful drain: includes the one final short bank, never audio_stop."""
        self.finished = True
        self.stream.finish()

    def stop(self):
        """Abort, not graceful drain. Accepted active-bank tail can still play."""
        self.finished = True
        return self.stream.stop()

    def close_runtime(self):
        # Native audio already copied its data. Safe even if STOP_PENDING.
        self.runtime.close()


TONE_SOURCE = b'''local p=playdate
local s=p.sound.synth.new(p.sound.kWaveSine)
s:setVolume(0.35); s:setADSR(0.01,0.01,0.8,0.02)
s:playNote(440,0.8,0.25)
function p.update()
 p.graphics.clear(p.graphics.kColorBlack)
 p.graphics.setColor(p.graphics.kColorWhite)
 p.graphics.drawText("ISOLATED 440 HZ TONE",40,100)
 p.graphics.drawText("IMAGE HELD DURING AUDIO",40,120)
end'''


class IsolatedTone:
    """Render/mix once BEFORE playback. This is deliberately NOT game mode."""
    def __init__(self, runtime_class, display, transport, clock):
        runtime = runtime_class(TONE_SOURCE, heap_cap=65536)
        try:
            runtime.step(0, 0.0, 0.0, 0)
            display.present(runtime)
            self.pcm = bytearray(32000)  # half-second, below binding's 65536-byte cap
            if runtime.audio_into(self.pcm, rate=RATE) != len(self.pcm):
                raise RuntimeError("tone mix byte count mismatch")
        finally:
            runtime.close()
        self.view = memoryview(self.pcm)
        self.offset = 0
        self.stream = PcmStream(transport, clock)

    def tick(self):
        if self.offset < len(self.pcm):
            count = min(1440, len(self.pcm) - self.offset)
            self.offset += self.stream.enqueue(self.view[self.offset:self.offset + count])
        if self.offset == len(self.pcm):
            self.stream.finish()
        return self.stream.pump()
