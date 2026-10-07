"""Measure cached-model inference without recording audio, pasting, or downloading."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import time

import numpy as np
import whisper


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, help="Consented local audio file; otherwise use 10 seconds of silence")
    parser.add_argument("--model", type=Path, default=Path.home() / ".cache/whisper/small.pt")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    if not args.model.is_file():
        parser.error("Cached model missing. Download through normal app startup before benchmarking.")
    if args.runs < 2:
        parser.error("Use at least two runs to separate first inference from warm inference.")
    audio = whisper.load_audio(str(args.audio)) if args.audio else np.zeros(160_000, dtype=np.float32)
    t0 = time.perf_counter()
    model = whisper.load_model(str(args.model), device="cpu")
    load_seconds = time.perf_counter() - t0
    times, counts = [], []
    for _ in range(args.runs):
        t0 = time.perf_counter()
        result = model.transcribe(audio, language="en", fp16=False)
        times.append(round(time.perf_counter() - t0, 3))
        counts.append(len(result["text"].strip()))
    print(json.dumps({
        "schema_version": 1,
        "fixture": "provided-audio" if args.audio else "synthetic-silence-10s",
        "audio_sha256": hashlib.sha256(audio.tobytes()).hexdigest(),
        "audio_seconds": len(audio) / 16000,
        "model_file": args.model.name,
        "model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
        "python": platform.python_version(), "macos": platform.mac_ver()[0],
        "architecture": platform.machine(), "device": "cpu", "fp16": False,
        "whisper": importlib.metadata.version("openai-whisper"),
        "torch": importlib.metadata.version("torch"),
        "model_load_seconds": round(load_seconds, 3),
        "inference_seconds": times,
        "warm_median_seconds": statistics.median(times[1:]),
        "output_characters": counts,
        "scope": "Inference only; no microphone, hotkey, insertion, accuracy, or p95 validation. Model load may use OS disk cache.",
    }, indent=2))


if __name__ == "__main__":
    main()
