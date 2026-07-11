import unittest

import numpy as np

from whisperbar_core import AppState, DictationController


class ImmediateThread:
    def __init__(self, *, target, args, **_kwargs):
        self.target = target
        self.args = args

    def start(self):
        self.target(*self.args)


class FakeStream:
    def __init__(self, callback, fail_start=False):
        self.callback = callback
        self.fail_start = fail_start
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self):
        if self.fail_start:
            raise RuntimeError("no input device")
        self.started = True

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True

    def feed(self, values):
        data = np.asarray(values, dtype=np.float32).reshape(-1, 1)
        self.callback(data, len(data), None, None)


class FakeAudio:
    def __init__(self, fail_start=False):
        self.fail_start = fail_start
        self.streams = []

    def InputStream(self, *, callback, **_kwargs):
        stream = FakeStream(callback, self.fail_start)
        self.streams.append(stream)
        return stream


class FakeModel:
    def __init__(self, text="hello", error=None):
        self.text = text
        self.error = error
        self.calls = []

    def transcribe(self, audio, **options):
        self.calls.append((audio, options))
        if self.error:
            raise self.error
        return {"text": self.text}


class DeferredThread(ImmediateThread):
    instances = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__class__.instances.append(self)

    def start(self):
        pass


class ControllerTests(unittest.TestCase):
    def make_controller(self, **overrides):
        self.audio = overrides.pop("audio_module", FakeAudio())
        self.model = overrides.pop("model", FakeModel())
        self.pasted = []
        self.states = []
        return DictationController(
            audio_module=self.audio,
            model=self.model,
            paste_text=self.pasted.append,
            state_callback=lambda state, message: self.states.append((state, message)),
            thread_factory=overrides.pop("thread_factory", ImmediateThread),
            **overrides,
        )

    def test_record_stop_transcribe_and_paste(self):
        controller = self.make_controller()

        self.assertTrue(controller.toggle())
        self.audio.streams[0].feed([0.25, -0.25])
        self.assertTrue(controller.toggle())

        self.assertEqual(controller.state, AppState.IDLE)
        self.assertEqual(self.pasted, ["hello"])
        np.testing.assert_array_equal(
            self.model.calls[0][0], np.array([0.25, -0.25], dtype=np.float32)
        )
        self.assertEqual(
            self.model.calls[0][1],
            {"language": "en", "fp16": False, "verbose": False},
        )
        self.assertTrue(self.audio.streams[0].closed)

    def test_hotkey_is_ignored_during_transcription(self):
        DeferredThread.instances = []
        controller = self.make_controller(thread_factory=DeferredThread)
        controller.toggle()
        self.audio.streams[0].feed([0.1])
        controller.toggle()

        self.assertEqual(controller.state, AppState.TRANSCRIBING)
        self.assertFalse(controller.toggle())
        self.assertEqual(len(self.audio.streams), 1)

        DeferredThread.instances[0].target(*DeferredThread.instances[0].args)
        self.assertEqual(controller.state, AppState.IDLE)

    def test_microphone_failure_becomes_visible_error(self):
        controller = self.make_controller(audio_module=FakeAudio(fail_start=True))

        controller.toggle()

        self.assertEqual(controller.state, AppState.ERROR)
        self.assertIn("Microphone unavailable", self.states[-1][1])
        self.assertTrue(self.audio.streams[0].closed)

    def test_transcription_failure_becomes_visible_error(self):
        controller = self.make_controller(model=FakeModel(error=RuntimeError("bad model")))
        controller.toggle()
        self.audio.streams[0].feed([0.1])

        controller.toggle()

        self.assertEqual(controller.state, AppState.ERROR)
        self.assertIn("bad model", self.states[-1][1])

    def test_empty_recording_does_not_call_model(self):
        controller = self.make_controller()
        controller.toggle()

        controller.toggle()

        self.assertEqual(controller.state, AppState.ERROR)
        self.assertEqual(self.model.calls, [])

    def test_recording_buffer_is_bounded(self):
        controller = self.make_controller(sample_rate=2, max_recording_seconds=1)
        controller.toggle()
        self.audio.streams[0].feed([0.1, 0.2, 0.3, 0.4])

        controller.toggle()

        np.testing.assert_array_equal(
            self.model.calls[0][0], np.array([0.1, 0.2], dtype=np.float32)
        )

    def test_silent_recording_reports_microphone_problem(self):
        controller = self.make_controller()
        controller.toggle()
        self.audio.streams[0].feed([0.0, 0.0])

        controller.toggle()

        self.assertEqual(controller.state, AppState.ERROR)
        self.assertIn("No audible input", self.states[-1][1])
        self.assertEqual(self.model.calls, [])


if __name__ == "__main__":
    unittest.main()
