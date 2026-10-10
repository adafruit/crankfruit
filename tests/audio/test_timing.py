"""Deterministic transport fixtures, not physical HDMI/audio qualification."""
import unittest
import baseline_stream
from stream import Clock, PcmStream, StreamError, TICK_MASK
from fixtures import ManualTicks, RecordingTransport


class TimingTests(unittest.TestCase):
    def test_native_time_and_entry_vs_exit_gap(self):
        ticks = ManualTicks()
        transport = RecordingTransport(ticks)
        stream = PcmStream(transport, Clock(ticks))
        original_write = transport.audio_write
        seen = []
        def delayed_write(pcm, sample_rate):
            seen.append(pcm is stream.offer_view)
            ticks.advance(7)
            return original_write(pcm, sample_rate)
        transport.audio_write = delayed_write
        stream.enqueue(memoryview(bytearray(4266)))
        stream.pump(3)
        self.assertEqual(stream.last_native_ms, 14)
        self.assertEqual(stream.last_pump_ms, 14)
        self.assertEqual(stream.metrics['max_native_write_ms'], 7)
        self.assertEqual(seen, [True, True])
        ticks.advance(70)
        stream.pump(4)
        row = stream.timing_events[0]
        self.assertEqual(row[0:2], (84, 84))
        self.assertEqual(row[4:9], (4, 3, 14, 14, 0))
        self.assertEqual(row[13], 70)
        self.assertEqual(stream.underrun_events[0], row[:4])
        # Empty/backpressured pumps must not inherit the last write duration.
        stream.pump(6)
        self.assertEqual(stream.last_native_ms, 0)

    def test_failure_native_duration_recorded_original_error_preserved(self):
        ticks = ManualTicks()
        transport = RecordingTransport(ticks)
        stream = PcmStream(transport, Clock(ticks))
        def broken(pcm, sample_rate):
            ticks.advance(9)
            raise OSError('timed failure')
        transport.audio_write = broken
        stream.enqueue(bytes(3000))
        with self.assertRaisesRegex(StreamError, 'timed failure'):
            stream.pump(3)
        self.assertEqual(stream.metrics['max_native_write_ms'], 9)
        self.assertEqual(stream.last_native_ms, 9)
        self.assertEqual(stream.last_pump_ms, 9)
        self.assertEqual(transport.stops, 1)

    def test_trace_storage_is_bounded_and_preallocated(self):
        ticks = ManualTicks()
        transport = RecordingTransport(ticks)
        stream = PcmStream(transport, Clock(ticks))
        rows = list(stream.event_rows)
        for _ in range(12):
            stream.enqueue(bytes(4266))
            stream.pump(3)
            ticks.advance(70)
            stream.pump(4)
        self.assertEqual(stream.event_count, 8)
        self.assertGreater(stream.metrics['trace_overflow'], 0)
        self.assertTrue(all(a is b for a, b in zip(rows, stream.event_rows)))

    def test_baseline_exact_bytes_offers_states_through_wrap_and_partial(self):
        data = bytes((i * 19) % 256 for i in range(24000))
        for hstx in (125000000, 150000000):
            results = []
            for cls in (baseline_stream.PcmStream, PcmStream):
                ticks = ManualTicks(TICK_MASK - 99)
                transport = RecordingTransport(ticks, hstx)
                stream = cls(transport, Clock(ticks), capacity=2880)
                offset = 0
                trace = []
                for index in range(5000):
                    if offset < len(data):
                        view = memoryview(data)[offset:offset + 2134]
                        offset += stream.enqueue(view)
                    else:
                        stream.finish()
                    stream.pump()
                    trace.append((stream.state, stream.head, stream.used, stream.last_pending))
                    if stream.state == 'DRAINED':
                        break
                    ticks.advance((1, 2, 5, 3)[index % 4])
                self.assertEqual(stream.state, 'DRAINED')
                self.assertEqual(transport.played, data)
                results.append((transport.accepted, transport.played, transport.offers, trace))
            self.assertEqual(results[0], results[1])


if __name__ == '__main__':
    unittest.main()
