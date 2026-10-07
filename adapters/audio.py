"""PortAudio capture and local Whisper adapters; never touch the UI."""
import logging
import threading
import time
import numpy as np
import sounddevice as sd

log = logging.getLogger('whisperbar')


class AudioDevices:
    def __init__(self):
        self.lock = threading.Lock()
        self.selected = None

    def refresh(self):
        # Caller must keep this off the active recording path.
        with self.lock:
            sd._terminate()
            sd._initialize()
            return list(dict.fromkeys(d['name'] for d in sd.query_devices() if d['max_input_channels'] > 0))

    def resolve(self):
        if self.selected:
            for index, device in enumerate(sd.query_devices()):
                if device['name'] == self.selected and device['max_input_channels'] > 0:
                    return index, self.selected
            log.warning('Selected microphone unavailable — using system default')
        return None, sd.query_devices(kind='input')['name']


class Capture:
    def __init__(self, devices, sample_rate, max_seconds):
        self.devices = devices
        self.sample_rate = sample_rate
        self.limit = sample_rate * max_seconds
        self.frames = []
        self.samples = 0
        self.stream = None
        self.lock = threading.Lock()
        self.last_sample_at = 0
        self.accepting = False

    def start(self, ready):
        with self.devices.lock:
            sd._terminate()
            sd._initialize()
            index, name = self.devices.resolve()
            self.accepting = True

            def callback(indata, _frames, _time, status):
                if status:
                    log.warning('Audio callback: %s', status)
                first = False
                with self.lock:
                    if not self.accepting:
                        return
                    if len(indata) == 0:
                        return
                    first = self.last_sample_at == 0
                    self.last_sample_at = time.monotonic()
                    remaining = self.limit - self.samples
                    if remaining > 0:
                        frame = indata[:remaining].copy()
                        self.frames.append(frame)
                        self.samples += len(frame)
                if first:
                    ready()

            self.stream = sd.InputStream(samplerate=self.sample_rate, channels=1,
                                         dtype='float32', device=index, callback=callback)
            self.stream.start()
            log.info('Microphone stream started (device=%s)', name)

    def close(self):
        with self.lock:
            self.accepting = False
        stream = self.stream
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
                # Retain the handle if native close raises, so cleanup can retry.
                self.stream = None

    def snapshot(self):
        with self.lock:
            if not self.frames:
                raise RuntimeError('No audio captured — check microphone')
            audio = np.concatenate(self.frames).reshape(-1).astype(np.float32)
            self.frames.clear()
        peak = float(np.abs(audio).max())
        log.info('Recording captured (samples=%d, peak=%.5f)', len(audio), peak)
        if not np.isfinite(audio).all():
            raise RuntimeError('Invalid microphone samples — retry')
        if peak < 0.001:
            raise RuntimeError('No audio captured — check mute and microphone')
        return np.clip(audio, -1.0, 1.0)


class Recognizer:
    def __init__(self, model):
        self.model = model

    def __call__(self, audio):
        start = time.monotonic()
        text = self.model.transcribe(audio, language='en', fp16=False)['text'].strip()
        log.info('Transcribed %d characters in %.2fs', len(text), time.monotonic() - start)
        return text
