"""Native-copy CALL CONTRACT fixture; this does not execute the C extension.

The recording copier deliberately allocates in tests. Production calls the C
implementation directly; host parity checks routing, ranges and stream policy.
"""
import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import patch
import stream
import test_contracts
import test_timing
from fixtures import ManualTicks, RecordingTransport


class RecordingCopy:
    def __init__(self):
        self.calls = []
        self.fail_at = 0
        self.bad_count = False

    def __call__(self, dst, src, doff, soff, count):
        self.calls.append((len(dst), len(src), doff, soff, count))
        if self.fail_at == len(self.calls):
            raise ValueError('injected copy failure')
        if min(doff, soff, count) < 0 or count > 1048576:
            raise ValueError('copy range')
        if doff + count > len(dst) or soff + count > len(src):
            raise ValueError('copy bounds')
        assert dst is not src, 'stream must use disjoint buffers'
        dst[doff:doff + count] = src[soff:soff + count]
        return count - 2 if self.bad_count else count


class NativeCopyTests(unittest.TestCase):
    def setUp(self):
        self.copy = RecordingCopy()
        self.patch = patch.multiple(stream, NATIVE_COPY=True, _native_copy=self.copy)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def setup_stream(self, capacity=2880):
        self.ticks = ManualTicks()
        self.transport = RecordingTransport(self.ticks)
        self.stream = stream.PcmStream(self.transport, stream.Clock(self.ticks), capacity)
        return self.stream

    def test_all_25_existing_contracts_with_native_copy_injected(self):
        suite = unittest.TestSuite()
        for cls in (test_contracts.StreamContracts, test_contracts.ClockInputContracts,
                    test_timing.TimingTests):
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
        result = unittest.TestResult()
        suite.run(result)
        self.assertEqual(result.testsRun, 25)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.failures, [])
        self.assertGreater(len(self.copy.calls), 0)

    def test_explicit_both_wrap_segments_and_timing(self):
        s = self.setup_stream()
        s.head = 2870
        pcm = memoryview(bytearray((i % 256 for i in range(1500))))
        self.assertEqual(s.enqueue(pcm), 1500)
        self.assertEqual(self.copy.calls, [(2880,1500,2870,0,10), (2880,1500,0,10,1490)])
        self.copy.calls.clear()
        s.pump(3)
        self.assertEqual(self.copy.calls[:2], [(1440,2880,0,2870,10), (1440,2880,10,0,1430)])
        self.assertEqual(self.transport.accepted, pcm[:1064])
        self.assertEqual(s.last_copy_ms, 0)
        self.assertEqual(s.metrics['max_offer_copy_ms'], 0)

    def test_enqueue_second_copy_failure_never_publishes_partial_chunk(self):
        s = self.setup_stream()
        s.head = 2870
        self.copy.fail_at = 2
        with self.assertRaisesRegex(ValueError, 'injected copy failure'):
            s.enqueue(bytes(1500))
        self.assertEqual(s.used, 0)
        self.assertEqual(s.head, 2870)
        self.assertEqual(s.metrics['enqueued_bytes'], 0)
        self.assertEqual(self.transport.accepted, b'')

    def test_native_copy_time_remains_in_existing_metrics(self):
        s = self.setup_stream()
        s.head = 2870
        def delayed_copy(dst, src, doff, soff, count):
            self.ticks.advance(3)
            return self.copy(dst, src, doff, soff, count)
        with patch.object(stream, '_native_copy', delayed_copy):
            s.enqueue(bytes(1500))
            self.assertEqual(s.last_enqueue_ms, 6)
            self.assertEqual(s.metrics['max_enqueue_ms'], 6)
            s.pump(3)
        self.assertEqual(s.last_copy_ms, 6)
        self.assertEqual(s.metrics['max_offer_copy_ms'], 6)
        self.assertEqual(s.last_pump_ms, 6)
        self.assertEqual(s.last_native_ms, 0)

    def test_offer_second_copy_failure_stops_without_native_write(self):
        s = self.setup_stream()
        s.head = 2870
        s.enqueue(bytes(1500))
        self.copy.calls.clear()
        self.copy.fail_at = 2
        with self.assertRaisesRegex(stream.StreamError, 'injected copy failure'):
            s.pump()
        self.assertEqual(s.metrics['write_calls'], 0)
        self.assertEqual(s.metrics['accepted_bytes'], 0)
        self.assertEqual(s.metrics['dropped_bytes'], 1500)
        self.assertEqual(self.transport.stops, 1)

    def test_short_native_copy_count_is_not_accepted(self):
        s = self.setup_stream()
        self.copy.bad_count = True
        with self.assertRaisesRegex(stream.StreamError, 'invalid byte count'):
            s.enqueue(bytes(1500))
        self.assertEqual(s.used, 0)
        self.copy.bad_count = False
        s.enqueue(bytes(1500))
        self.copy.bad_count = True
        with self.assertRaisesRegex(stream.StreamError, 'invalid byte count'):
            s.pump()
        self.assertEqual(s.metrics['accepted_bytes'], 0)

    def test_import_capability_present_and_absent(self):
        path = pathlib.Path(stream.__file__)
        fake = types.ModuleType('_crankfruit_pcm')
        fake.copy_into = self.copy
        for module, expected in ((fake, True), (None, False)):
            spec = importlib.util.spec_from_file_location('isolated_stream', path)
            isolated = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, {'_crankfruit_pcm': module}):
                spec.loader.exec_module(isolated)
            self.assertIs(isolated.NATIVE_COPY, expected)
            if expected:
                self.assertIs(isolated._native_copy, self.copy)


if __name__ == '__main__':
    unittest.main()
