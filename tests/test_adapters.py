import tempfile
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
import numpy as np
from adapters.audio import Capture
from adapters.desktop import InstanceLock, Output


class AudioTests(unittest.TestCase):
    def test_silence_rejected_and_peaks_clipped(self):
        capture = Capture(None, 16000, 1)
        capture.frames = [np.zeros((20, 1), dtype=np.float32)]
        with self.assertRaisesRegex(RuntimeError, 'No audio'):
            capture.snapshot()
        capture.frames = [np.array([[1.3], [-1.4], [0.2]], dtype=np.float32)]
        np.testing.assert_allclose(capture.snapshot(), [1, -1, 0.2])

    def test_callback_caps_memory_and_start_failure_is_closed(self):
        from unittest.mock import MagicMock
        devices = MagicMock()
        devices.lock = threading.Lock()
        devices.resolve.return_value = (None, 'test')
        stream = MagicMock()
        capture = Capture(devices, 10, 1)
        with patch('adapters.audio.sd._terminate'), patch('adapters.audio.sd._initialize'), \
             patch('adapters.audio.sd.InputStream', return_value=stream) as constructor:
            capture.start(lambda: None)
            callback = constructor.call_args.kwargs['callback']
            for _ in range(5):
                callback(np.ones((8, 1), dtype=np.float32), 8, None, None)
            self.assertEqual(capture.samples, 10)
            self.assertEqual(len(capture.snapshot()), 10)
            stream.stop.side_effect = RuntimeError('device removed')
            with self.assertRaises(RuntimeError):
                capture.close()
            stream.close.assert_called_once()

    def test_close_failure_retains_handle_for_retry(self):
        from unittest.mock import MagicMock
        stream = MagicMock()
        stream.close.side_effect = [RuntimeError('native close failed'), None]
        capture = Capture(None, 16000, 1)
        capture.stream = stream
        with self.assertRaisesRegex(RuntimeError, 'native close failed'):
            capture.close()
        self.assertIs(capture.stream, stream)
        capture.close()
        self.assertIsNone(capture.stream)
        self.assertEqual(stream.close.call_count, 2)

    def test_missing_selected_device_falls_back_to_default(self):
        from adapters.audio import AudioDevices
        devices = AudioDevices()
        devices.selected = 'Disconnected AirPods'
        with patch('adapters.audio.sd.query_devices', side_effect=[
            [{'name': 'Built-in', 'max_input_channels': 1}], {'name': 'Built-in'}]):
            self.assertEqual(devices.resolve(), (None, 'Built-in'))


class DesktopTests(unittest.TestCase):
    def test_second_instance_rejected_and_release_allows_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            first = InstanceLock(Path(directory) / 'lock')
            second = InstanceLock(Path(directory) / 'lock')
            try:
                self.assertTrue(first.acquire())
                self.assertFalse(second.acquire())
                first.close()
                self.assertTrue(second.acquire())
            finally:
                first.close()
                second.close()

    def test_untrusted_output_copies_without_key_injection(self):
        output = Output()
        with patch('adapters.desktop.pyperclip.copy') as copy, \
             patch('adapters.desktop.pyautogui.hotkey') as paste, \
             patch('adapters.desktop.AXIsProcessTrusted', return_value=False):
            self.assertIn('Accessibility', output.deliver('hello'))
            copy.assert_called_once_with('hello')
            paste.assert_not_called()

    def test_trusted_output_reports_request_not_confirmation(self):
        with patch('adapters.desktop.pyperclip.copy'), \
             patch('adapters.desktop.pyautogui.hotkey') as paste, \
             patch('adapters.desktop.AXIsProcessTrusted', return_value=True):
            self.assertIn('Paste requested', Output().deliver('hello'))
            paste.assert_called_once_with('command', 'v', _pause=False)

    def test_key_release_preparation_is_cancellable(self):
        cancel = threading.Event()
        cancel.set()
        start = time.monotonic()
        Output(held=lambda: True).prepare(cancel)
        self.assertLess(time.monotonic() - start, 0.1)
