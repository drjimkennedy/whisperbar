"""Thread-safe recording and transcription state for WhisperBar."""

from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import Callable, List, Optional

import numpy as np


class AppState(str, Enum):
    STARTING = "starting"
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    ERROR = "error"


StateCallback = Callable[[AppState, Optional[str]], None]


class DictationController:
    """Owns the audio stream and allows at most one operation at a time."""

    def __init__(
        self,
        *,
        audio_module,
        model,
        paste_text: Callable[[str], None],
        state_callback: StateCallback,
        sample_rate: int = 16_000,
        max_recording_seconds: int = 300,
        language: Optional[str] = "en",
        logger: Optional[logging.Logger] = None,
        thread_factory=threading.Thread,
    ) -> None:
        self._audio = audio_module
        self._model = model
        self._paste_text = paste_text
        self._state_callback = state_callback
        self._sample_rate = sample_rate
        self._max_samples = sample_rate * max_recording_seconds
        self._language = language
        self._logger = logger or logging.getLogger(__name__)
        self._thread_factory = thread_factory

        self._lock = threading.RLock()
        self._state = AppState.IDLE
        self._frames: List[np.ndarray] = []
        self._stream = None
        self._captured_samples = 0
        self._limit_reported = False

    @property
    def state(self) -> AppState:
        with self._lock:
            return self._state

    def toggle(self) -> bool:
        """Start/stop recording. Return False when the request is ignored."""
        with self._lock:
            current = self._state
            if current in (AppState.IDLE, AppState.ERROR):
                self._state = AppState.STARTING
            elif current == AppState.RECORDING:
                self._state = AppState.TRANSCRIBING
            else:
                self._logger.info("Ignoring hotkey while state=%s", current.value)
                return False

        if current in (AppState.IDLE, AppState.ERROR):
            self._start_recording()
        else:
            self._stop_and_launch_transcription()
        return True

    def close(self) -> None:
        """Release the input stream during application shutdown."""
        with self._lock:
            stream = self._stream
            self._stream = None
            self._frames = []
            self._captured_samples = 0
            self._state = AppState.IDLE
        if stream is not None:
            self._close_stream(stream)

    def _set_state(self, state: AppState, message: Optional[str] = None) -> None:
        with self._lock:
            self._state = state
        self._state_callback(state, message)

    def _audio_callback(self, indata, _frames, _time_info, status) -> None:
        if status:
            self._logger.warning("Audio callback status: %s", status)
        with self._lock:
            if self._state == AppState.RECORDING:
                remaining = self._max_samples - self._captured_samples
                if remaining > 0:
                    frame = indata[:remaining].copy()
                    self._frames.append(frame)
                    self._captured_samples += len(frame)
                elif not self._limit_reported:
                    self._logger.warning("Maximum recording length reached")
                    self._limit_reported = True

    def _start_recording(self) -> None:
        try:
            stream = self._audio.InputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype="float32",
                callback=self._audio_callback,
            )
            with self._lock:
                self._frames = []
                self._captured_samples = 0
                self._limit_reported = False
                self._stream = stream
                self._state = AppState.RECORDING
            stream.start()
        except Exception as exc:
            self._logger.exception("Unable to start recording")
            with self._lock:
                failed_stream = self._stream
                self._stream = None
                self._frames = []
                self._captured_samples = 0
            if failed_stream is not None:
                self._close_stream(failed_stream)
            self._set_state(AppState.ERROR, f"Microphone unavailable: {exc}")
            return
        self._state_callback(AppState.RECORDING, None)

    def _stop_and_launch_transcription(self) -> None:
        with self._lock:
            stream = self._stream
            self._stream = None

        try:
            if stream is not None:
                stream.stop()
                stream.close()
        except Exception as exc:
            self._logger.exception("Unable to stop recording")
            self._set_state(AppState.ERROR, f"Microphone error: {exc}")
            return

        with self._lock:
            captured_frames = self._frames
            self._frames = []

        if not captured_frames:
            self._set_state(AppState.ERROR, "No audio was captured")
            return

        self._state_callback(AppState.TRANSCRIBING, None)
        worker = self._thread_factory(
            target=self._transcribe,
            args=(captured_frames,),
            name="whisperbar-transcribe",
            daemon=True,
        )
        worker.start()

    def _transcribe(self, frames: List[np.ndarray]) -> None:
        try:
            # Whisper accepts a mono float32 array directly. This avoids a
            # temporary WAV file and removes ffmpeg from the recording path.
            audio = np.concatenate(frames, axis=0).reshape(-1).astype(np.float32)
            options = {"fp16": False, "verbose": False}
            if self._language:
                options["language"] = self._language
            result = self._model.transcribe(audio, **options)
            text = result.get("text", "").strip()
            if text:
                self._paste_text(text)
            self._set_state(AppState.IDLE)
        except Exception as exc:
            self._logger.exception("Transcription or paste failed")
            self._set_state(AppState.ERROR, f"Transcription failed: {exc}")

    def _close_stream(self, stream) -> None:
        try:
            stream.stop()
        except Exception:
            self._logger.debug("Stream stop failed during cleanup", exc_info=True)
        try:
            stream.close()
        except Exception:
            self._logger.debug("Stream close failed during cleanup", exc_info=True)
