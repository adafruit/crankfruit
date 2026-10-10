"""Host scheduling/hardware-initialization RECORDING FIXTURES, not HW proof.

Real game/Runtime validation lives in real_cp.py. There is no fake Python game.
"""
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

from stream import Clock, PcmStream, StreamError, MAX_BANK_BYTES, TICK_MASK, latency_model
from player import map_buttons, Debounce
from fixtures import ManualTicks, RecordingTransport


class StreamContracts(unittest.TestCase):
    def setup_stream(self, capacity=8192, hstx=150000000):
        self.ticks = ManualTicks()
        self.clock = Clock(self.ticks)
        self.transport = RecordingTransport(self.ticks, hstx)
        self.stream = PcmStream(self.transport, self.clock, capacity=capacity)
        return self.stream

    def drain(self):
        self.stream.finish()
        for _ in range(2000):
            if self.stream.pump() == "DRAINED":
                break
            self.ticks.advance(1)
        self.assertEqual(self.stream.state, "DRAINED")

    def test_small_intermediate_tail_is_held(self):
        s = self.setup_stream()
        s.enqueue(bytes(2132))
        s.pump()
        self.assertEqual(len(self.transport.offers), 1)
        self.assertEqual(s.used, 1068)
        self.ticks.advance(20)
        s.pump()
        self.assertEqual(len(self.transport.offers), 1)
        s.enqueue(bytes(2134))
        s.pump()
        self.assertTrue(all(n >= 1440 for n in self.transport.offers))
        self.drain()
        self.assertEqual(len(self.transport.played), 4266)

    def test_partial_enqueue_ring_wrap_and_conservation(self):
        s = self.setup_stream(capacity=2880)
        original = bytes((i * 19) % 256 for i in range(20000))
        offset = 0
        partial = 0
        for _ in range(3000):
            if offset < len(original):
                chunk = original[offset:offset + 2134]
                n = s.enqueue(chunk)
                partial += n < len(chunk)
                offset += n
            else:
                s.finish()
            if s.pump() == "DRAINED":
                break
            self.ticks.advance(1)
        self.assertGreater(partial, 0)
        self.assertEqual(s.state, "DRAINED")
        self.assertEqual(self.transport.played, original)
        self.assertEqual(s.metrics["accepted_bytes"], len(original))
        self.assertLessEqual(s.metrics["high_water_bytes"], 2880)

    def test_two_bank_backpressure_does_not_consume(self):
        s = self.setup_stream()
        s.enqueue(bytes(8000))
        s.pump()
        before = s.used
        s.pump()
        self.assertEqual(s.used, before)
        self.assertGreater(s.metrics["backpressure"], 0)

    def test_final_short_tail_and_conservative_pending(self):
        s = self.setup_stream()
        s.enqueue(b"\x01\x02" * 17)
        s.pump()
        self.assertEqual(s.metrics["accepted_bytes"], 0)
        s.finish()
        s.pump()
        self.assertEqual(s.used, 0)
        self.assertEqual(s.state, "FINISHING")
        self.ticks.advance(17)
        s.pump()
        self.assertEqual(self.transport.audio_pending, 17)  # whole active bank
        self.ticks.advance(15)
        self.assertEqual(self.transport.audio_pending, 17)
        self.ticks.advance(2)
        self.assertEqual(s.pump(), "DRAINED")
        self.assertEqual(len(self.transport.played), 34)

    def test_stop_preserves_active_tail_and_drops_ready(self):
        s = self.setup_stream()
        s.enqueue(bytes(8000))
        s.pump()
        self.ticks.advance(17)
        self.assertEqual(s.stop(), "STOP_PENDING")
        self.assertEqual(s.metrics["stop_pending_samples"], 532)
        self.assertGreater(s.metrics["dropped_bytes"], 0)
        self.assertGreater(self.transport.discarded, 0)
        self.assertNotEqual(s.state, "DRAINED")
        self.ticks.advance(17)
        self.assertEqual(s.poll_stop(), "STOPPED")
        self.assertEqual(len(self.transport.played), 1064)
        self.assertEqual(s.stop(), "STOPPED")

    def test_ready_only_stop_can_complete(self):
        s = self.setup_stream()
        s.enqueue(bytes(3000))
        s.pump()
        self.assertEqual(s.stop(), "STOPPED")
        self.assertEqual(self.transport.played, b"")

    def test_stalled_feed_deadline(self):
        s = self.setup_stream()
        self.transport.audio_write = lambda *a, **k: 0
        s.enqueue(bytes(3000))
        s.pump()
        self.ticks.advance(251)
        with self.assertRaisesRegex(StreamError, "deadline"):
            s.pump()
        self.assertEqual(s.metrics["deadline_failures"], 1)
        self.assertEqual(s.metrics["errors"], 1)
        self.assertEqual(s.metrics["accepted_bytes"], 0)
        self.assertIsNotNone(s.error)

    def test_stalled_drain_keeps_pending_distinction(self):
        s = self.setup_stream()
        s.enqueue(bytes(3000))
        s.pump()
        self.ticks.advance(17)
        self.transport.advance()
        self.transport.advance = lambda: None  # NEGATIVE CONTROL: stuck DMA frame
        s.finish()
        self.ticks.advance(251)
        with self.assertRaisesRegex(StreamError, "deadline"):
            s.pump()
        self.assertEqual(s.state, "STOP_PENDING")
        self.assertGreater(s.metrics["stop_pending_samples"], 0)
        self.assertIsNotNone(s.error)

    def test_invalid_acceptance_fails_without_byte_advance(self):
        for value in (-2, 1, 1442, True, None, 1.0):
            with self.subTest(value=value):
                s = self.setup_stream()
                s.enqueue(bytes(3000))
                self.transport.audio_write = lambda *a, **k: value
                with self.assertRaisesRegex(StreamError, "acceptance"):
                    s.pump()
                self.assertEqual(s.metrics["accepted_bytes"], 0)
                self.assertEqual(s.metrics["dropped_bytes"], 3000)

    def test_invalid_pending_is_not_reported_as_silence(self):
        for value in (-1, 1441, True, None, 0.0):
            with self.subTest(value=value):
                s = self.setup_stream()
                s.transport = types.SimpleNamespace(audio_pending=value, audio_stop=lambda: None)
                s.enqueue(bytes(3000))
                with self.assertRaisesRegex(StreamError, "audio_pending"):
                    s.pump()
                self.assertEqual(s.state, "STOP_PENDING")
                self.assertEqual(s.metrics["accepted_bytes"], 0)

    def test_driver_exception_stops_and_preserves_error(self):
        s = self.setup_stream()
        def broken(*a, **k):
            raise OSError("injected hardware failure")
        self.transport.audio_write = broken
        s.enqueue(bytes(3000))
        with self.assertRaisesRegex(StreamError, "injected hardware"):
            s.pump()
        self.assertEqual(self.transport.stops, 1)

    def test_broken_stop_retains_unknown_pending(self):
        s = self.setup_stream()
        def broken():
            raise OSError("stop unavailable")
        self.transport.audio_stop = broken
        self.transport.audio_write = lambda *a, **k: -1
        s.enqueue(bytes(3000))
        with self.assertRaises(StreamError):
            s.pump()
        self.assertEqual(s.state, "STOP_PENDING")
        self.assertIn("acceptance", s.error)

    def test_underrun_is_observation_not_fps_claim(self):
        s = self.setup_stream()
        s.enqueue(bytes(4266))
        s.pump()
        self.ticks.advance(70)
        s.pump()
        self.assertEqual(s.metrics["underrun_observations"], 1)
        self.assertEqual(s.metrics["max_service_gap_ms"], 70)

    def test_empty_finish_and_invalid_reuse(self):
        s = self.setup_stream()
        s.finish()
        self.assertEqual(s.pump(), "DRAINED")
        with self.assertRaises(StreamError):
            s.enqueue(bytes(2))
        self.assertEqual(s.stop(), "DRAINED")

    def test_pcm_alignment_and_capacity_validation(self):
        s = self.setup_stream()
        with self.assertRaises(ValueError):
            s.enqueue(b"x")
        for capacity in (1, 2878, 2881):
            with self.assertRaises(ValueError):
                PcmStream(self.transport, self.clock, capacity)

    def test_source_packet_phase_models(self):
        for hstx, expected in ((125000000, [640] * 3), (150000000, [532, 532, 536])):
            self.setup_stream(hstx=hstx)
            for _ in range(3):
                self.transport.audio_write(bytes(1440))
                self.ticks.advance(40)
            self.assertEqual(self.transport.capacities, expected)

    def test_bank_limit_models_are_conditional(self):
        self.assertEqual(latency_model(125000000)["two_bank_horizon_ms"], 40)
        self.assertAlmostEqual(latency_model(150000000)["queue_plus_banks_ms"], 161.333333333)
        with self.assertRaises(ValueError):
            latency_model(0)


class ClockInputContracts(unittest.TestCase):
    def test_tick_wrap_is_monotonic(self):
        ticks = ManualTicks(TICK_MASK - 3)
        clock = Clock(ticks)
        ticks.advance(10)
        self.assertEqual(clock.now(), 10)
        ticks.advance(100)
        self.assertEqual(clock.now(), 110)

    def test_backwards_clock_is_not_silently_elapsed(self):
        ticks = ManualTicks(100)
        clock = Clock(ticks)
        ticks.advance(-1)
        with self.assertRaisesRegex(RuntimeError, "clock"):
            clock.now()

    def test_all_button_combinations(self):
        self.assertEqual([map_buttons(i & 1, i & 2, i & 4) for i in range(8)],
                         [0, 1, 2, 16, 32, 33, 34, 48])

    def test_bounce_and_chord_direction_suppression(self):
        ticks = ManualTicks()
        debounce = Debounce(Clock(ticks))
        self.assertEqual(debounce.update(1), 0)
        ticks.advance(5)
        self.assertEqual(debounce.update(0), 0)
        ticks.advance(5)
        self.assertEqual(debounce.update(3), 0)
        ticks.advance(15)
        self.assertEqual(debounce.update(3), 16)


if __name__ == "__main__":
    unittest.main()
