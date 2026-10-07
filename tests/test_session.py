import threading
import time
import unittest
from core.session import Coordinator, State
from core.shortcut import Chord


def wait_for(predicate):
    end = time.monotonic() + 2
    while not predicate():
        if time.monotonic() > end:
            raise AssertionError('Timed out waiting for session transition')
        time.sleep(0.002)


class FakeCapture:
    def __init__(self, ready=True, start_error=False, gate=None):
        self.last_sample_at = time.monotonic()
        self.ready = ready
        self.start_error = start_error
        self.gate = gate
        self.closed = False

    def start(self, notify):
        if self.gate:
            self.gate.wait(2)
        if self.start_error:
            raise RuntimeError('Mic permission denied')
        if self.ready:
            self.last_sample_at = time.monotonic()
            notify()

    def close(self):
        self.closed = True

    def snapshot(self):
        return ['session-owned audio']


class SessionTests(unittest.TestCase):
    def make(self, capture=None, recognize=None, prepare=None, deliver=None, **kwargs):
        self.events, self.deliveries = [], []
        self.capture = capture or FakeCapture()
        self.coordinator = Coordinator(lambda: self.capture, recognize or (lambda _: 'hello'),
            prepare or (lambda _: None), deliver or (lambda text: self.deliveries.append(text) or 'Paste requested'),
            self.events.append, **kwargs)
        self.addCleanup(self.coordinator.close)
        return self.coordinator

    def record(self, c):
        self.assertTrue(c.toggle())
        wait_for(lambda: c.state == State.RECORDING)

    def finish(self, c):
        wait_for(lambda: c.session is None)

    def test_record_stop_once(self):
        c = self.make()
        self.record(c)
        c.toggle()
        self.finish(c)
        self.assertEqual(self.deliveries, ['hello'])
        self.assertTrue(self.capture.closed)
        self.assertEqual(c.last_text, 'hello')
        self.assertEqual([e.state for e in self.events], [State.ARMING, State.RECORDING, State.TRANSCRIBING, State.DELIVERING, State.IDLE])

    def test_cancel_during_startup_cleans_up_late_stream(self):
        gate = threading.Event()
        c = self.make(FakeCapture(gate=gate))
        c.toggle()
        self.assertEqual(c.state, State.ARMING)
        c.toggle()
        self.assertEqual(c.state, State.CANCELLING)
        gate.set()
        self.finish(c)
        self.assertEqual(self.deliveries, [])
        self.assertEqual(c.state, State.IDLE)

    def test_cancel_recording_does_not_transcribe(self):
        calls = []
        c = self.make(recognize=lambda audio: calls.append(audio) or 'hello')
        self.record(c)
        c.cancel()
        self.finish(c)
        self.assertEqual(calls, [])
        self.assertTrue(self.capture.closed)

    def test_busy_and_cancel_during_inference_suppresses_late_result(self):
        started, finish = threading.Event(), threading.Event()
        def recognize(_):
            started.set()
            finish.wait(2)
            return 'late result'
        c = self.make(recognize=recognize)
        self.record(c)
        c.toggle()
        self.assertTrue(started.wait(2))
        for _ in range(100):
            self.assertFalse(c.toggle())
        c.cancel()
        self.assertFalse(c.toggle())
        finish.set()
        self.finish(c)
        self.assertEqual(self.deliveries, [])
        self.assertIsNone(c.last_text)
        self.assertEqual(c.sequence, 1)

    def test_cancel_during_delivery_preparation(self):
        prepared = threading.Event()
        def prepare(cancel):
            prepared.set()
            cancel.wait(2)
        c = self.make(prepare=prepare)
        self.record(c)
        c.toggle()
        self.assertTrue(prepared.wait(2))
        c.cancel()
        self.finish(c)
        self.assertEqual(self.deliveries, [])
        self.assertIsNone(c.last_text)

    def test_failed_delivery_retains_transcript(self):
        def fail(_):
            raise RuntimeError('clipboard failure')
        c = self.make(deliver=fail)
        self.record(c)
        c.toggle()
        self.finish(c)
        self.assertEqual(c.state, State.ERROR)
        self.assertEqual(c.last_text, 'hello')

    def test_mic_error_cleans_up_and_allows_retry(self):
        c = self.make(FakeCapture(start_error=True))
        c.toggle()
        self.finish(c)
        self.assertTrue(self.capture.closed)
        self.assertEqual(c.state, State.ERROR)
        self.capture.start_error = False
        self.record(c)
        c.toggle()
        self.finish(c)
        self.assertEqual(self.deliveries, ['hello'])

    def test_no_samples_and_device_stall_fail(self):
        for ready in [False, True]:
            with self.subTest(ready=ready):
                c = self.make(FakeCapture(ready=ready), ready_timeout=0.03, stall_timeout=0.03)
                c.toggle()
                self.finish(c)
                self.assertEqual(c.state, State.ERROR)
                self.assertTrue(self.capture.closed)
                self.assertEqual(self.deliveries, [])

    def test_recording_limit_finishes(self):
        c = self.make(max_seconds=0.03)
        c.toggle()
        self.finish(c)
        self.assertEqual(self.deliveries, ['hello'])

    def test_recognition_failure_does_not_deliver(self):
        def fail(_):
            raise RuntimeError('inference failure')
        c = self.make(recognize=fail)
        self.record(c)
        c.toggle()
        self.finish(c)
        self.assertEqual(c.state, State.ERROR)
        self.assertEqual(self.deliveries, [])
        self.assertTrue(self.capture.closed)

    def test_close_suppresses_late_result(self):
        entered, finish = threading.Event(), threading.Event()
        def recognize(_):
            entered.set()
            finish.wait(2)
            return 'late'
        c = self.make(recognize=recognize)
        self.record(c)
        c.toggle()
        self.assertTrue(entered.wait(2))
        closer = threading.Thread(target=c.close)
        closer.start()
        wait_for(lambda: c.closed)
        finish.set()
        closer.join(2)
        self.finish(c)
        self.assertEqual(self.deliveries, [])
        self.assertEqual(c.state, State.CLOSED)
        self.assertFalse(c.toggle())

    def test_100_sessions_have_unique_identity_and_one_delivery_each(self):
        c = self.make()
        for _ in range(100):
            self.record(c)
            c.toggle()
            self.finish(c)
        self.assertEqual(len(self.deliveries), 100)
        self.assertEqual(c.sequence, 100)

    def test_persistent_cleanup_failure_blocks_new_capture_even_when_cancelled(self):
        class UnclosableCapture(FakeCapture):
            def close(self):
                raise RuntimeError('native close failed')
        c = self.make(UnclosableCapture())
        self.record(c)
        c.cancel()
        self.finish(c)
        self.assertEqual(c.state, State.ERROR)
        self.assertTrue(c.restart_required)
        self.assertIs(c.failed_capture, self.capture)
        self.assertFalse(c.toggle())
        self.assertEqual(c.sequence, 1)
        self.assertEqual(self.deliveries, [])

    def test_successful_cleanup_retry_allows_next_session(self):
        class RetryCapture(FakeCapture):
            calls = 0
            def close(self):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError('transient stop error')
                super().close()
        c = self.make(RetryCapture())
        self.record(c)
        c.toggle()
        self.finish(c)
        self.assertEqual(c.state, State.ERROR)
        self.assertFalse(c.restart_required)
        self.record(c)
        c.toggle()
        self.finish(c)
        self.assertEqual(self.deliveries, ['hello'])


class ShortcutTests(unittest.TestCase):
    def test_auto_repeat_and_modifier_variations(self):
        calls = []
        chord = Chord({'alt', 'space'}, lambda: calls.append(1))
        chord.press('alt')
        for _ in range(100):
            chord.press('space')
        chord.press('shift')
        self.assertEqual(len(calls), 1)
        chord.release('space')
        chord.press('space')
        self.assertEqual(len(calls), 2)
        chord.release('space')
        chord.release('alt')
        self.assertFalse(chord.held())
