"""Opt-in real-inference cancellation check. No microphone, clipboard, or downloads.

Uses synthetic silence and a cached model; not a speech-accuracy benchmark.
Run: .venv/bin/python scripts/check_inference_cancellation.py
"""
import json
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import whisper
from core.session import Coordinator, State


class SyntheticCapture:
    def start(self, ready):
        self.last_sample_at = time.monotonic()
        ready()

    def close(self):
        pass

    def snapshot(self):
        return np.zeros(16000 * 120, dtype=np.float32)


def main():
    model_path = Path.home() / '.cache/whisper/small.pt'
    if not model_path.is_file():
        raise SystemExit('Cached small.pt missing; no download attempted.')
    model = whisper.load_model(str(model_path), device='cpu')
    entered, finished = threading.Event(), threading.Event()
    timings, events, deliveries = {}, [], []

    def recognize(audio):
        timings['inference_start'] = time.monotonic()
        entered.set()
        result = model.transcribe(audio, language='en', fp16=False)['text']
        timings['inference_end'] = time.monotonic()
        finished.set()
        # The real result is returned to the coordinator, which must discard it.
        return result

    c = Coordinator(SyntheticCapture, recognize, lambda _: None,
                    lambda text: deliveries.append(text), events.append)
    try:
        c.toggle()
        deadline = time.monotonic() + 10
        while c.state != State.RECORDING:
            if time.monotonic() > deadline:
                raise RuntimeError('Synthetic capture did not become ready')
            time.sleep(0.005)
        c.toggle()
        if not entered.wait(10):
            raise RuntimeError('Inference did not start')
        time.sleep(0.1)  # Allow the actual inference call to enter its compute path.
        active_at_cancel = not finished.is_set()
        cancel_start = time.monotonic()
        accepted = c.cancel()
        cancel_ms = (time.monotonic() - cancel_start) * 1000
        busy_rejected = not c.toggle()
        worker = c.worker
        worker.join(60)
        if worker.is_alive():
            raise RuntimeError('Inference did not drain within 60 seconds')
        passed = (active_at_cancel and accepted and busy_rejected and finished.is_set()
                  and not deliveries and c.last_text is None and c.state == State.IDLE)
        report = {
            'schema_version': 1, 'fixture': '120 seconds synthetic silence',
            'model': 'small', 'device': 'cpu', 'actual_inference_ran': finished.is_set(),
            'inference_active_when_cancelled': active_at_cancel,
            'cancel_accepted': accepted, 'cancel_call_ms': round(cancel_ms, 3),
            'new_session_rejected_while_draining': busy_rejected,
            'inference_seconds': round(timings['inference_end'] - timings['inference_start'], 3),
            'delivery_count': len(deliveries), 'retained_transcript': c.last_text is not None,
            'final_state': c.state.value, 'passed': passed,
            'scope': 'Real cached-model compute with synthetic capture and spy output; no native Escape, physical mic, paste, or accuracy check.',
        }
        print(json.dumps(report, indent=2))
        return 0 if passed else 1
    finally:
        c.close()


if __name__ == '__main__':
    sys.exit(main())
