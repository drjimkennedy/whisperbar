# WhisperBar operations playbook

Updated 2026-10-07 for the Stage 1 session coordinator. The upgrade [PRD](docs/PRD-robust-whisperbar.md) describes proposed work; the [development log](docs/DEVELOPMENT-LOG.md) records delivered changes and verification.

## Setup and launch

From the checkout, run `./scripts/setup.sh`, then `./launch.sh`. Setup currently targets macOS arm64 / Python 3.9 and requires ffmpeg on PATH. See the [README](README.md) for prerequisites and interpreter selection. The launcher runs only the project environment and never silently falls back to another Python.

The model is `small` in `config.py`, with English recognition and 16 kHz mono capture. First model use downloads weights; subsequent local use uses the model cache. The menu bar icon appears after model loading. Stage 3 will improve startup feedback.

If upgrading from the earlier shared environment, the original local environment has been preserved as `.venv-legacy/`. The new `.venv` is isolated. Do not move or distribute virtual environments; recreate them through setup. Launch the old app with `/usr/bin/python3 app.py` only as a local emergency fallback if those machine packages still exist, not as portable installation guidance.

## Everyday operation

- Option+Space starts recording; press again to stop and transcribe. Repeated key-down events do not toggle again. A second press during microphone startup cancels that attempt. Presses during processing are ignored.
- Menu bar: microphone icon is idle, red appears after actual audio samples arrive, hourglass is starting/processing/cancelling, warning is an error. Open the menu for the full status.
- Microphone menu selects an input; Refresh device list re-enumerates devices. Selection does not yet persist across restarts.
- Output overwrites the clipboard and attempts Command-V into the active field. Focus validation and history are planned, not implemented.
- Escape or Cancel dictation cancels recording or suppresses pending output. Inference may finish internally before a new session can start. Cancellation cannot undo a paste once delivery has begun. Escape is not swallowed and may also affect the focused application.
- Copy last transcript recovers the most recent completed output from memory, including a failed paste. It is lost when the app quits; no persistent history exists yet.
- Recording automatically stops at 300 seconds. Silent, missing, invalid, or stalled audio reports an error. Microphone selection/refresh is blocked during active work.
- Configuration changes in `config.py` require restart. A second launch exits with a message instead of creating another instance.

## Permissions and troubleshooting

Grant the launching app/interpreter the applicable Microphone, Input Monitoring, and Accessibility permissions in macOS settings. Restart after changing permissions. Actual behaviour must be manually tested on each supported macOS/runtime combination.

| Symptom | Action |
|---|---|
| Missing environment/package | Run `./scripts/setup.sh`; start with `./launch.sh`, not bare `python3` |
| Setup rejects interpreter/platform | Supply the tested Python 3.9 interpreter; other platforms/runtimes need a separate compatibility evaluation |
| Missing ffmpeg | Install `brew install ffmpeg`; ensure its executable is on PATH |
| Model load/download fails | Check connection and disk space, inspect `whisperbar.log`, retry launcher; this is distinct from package setup |
| No microphone audio | Check permissions, selected/default input and mute status; refresh device list |
| Shortcut does nothing | Check input/accessibility permissions and shortcut conflicts |
| Text does not paste | Use Copy last transcript and paste manually. Check Accessibility and focus; persistent history and destination validation remain planned |
| App appears stuck | Use Cancel dictation and wait for inference to drain; inspect `whisperbar.log` if it does not recover |

The current runtime logs are in `whisperbar.log` beside `app.py`. Logs rotate at approximately 1 MB with three backups; transcript text and raw audio are not logged by this app. Do not distribute logs without reviewing them.

## Verification and baseline measurement

```bash
.venv/bin/python -m pip check
.venv/bin/python scripts/check_environment.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/benchmark.py
```

The benchmark defaults to ten seconds of synthetic silence and reads the cached `small.pt`; it does not download a model, open a microphone, or paste. This measures inference plumbing, not speech accuracy or full dictation latency. For a consented recording:

```bash
.venv/bin/python scripts/benchmark.py --audio /path/to/sample.wav --runs 5
```

The JSON includes decoded-audio and model checksums, inference times, environment versions, and output character counts; it excludes transcript text and full audio paths. First inference is separate from warm runs. Model-load timing is not a cold disk-cache measurement. Record hardware identity alongside results. Do not claim p95 from these small runs.

Manual smoke test: quit any running copy, launch, focus a non-sensitive Notes document, dictate one sentence, stop, verify one correct paste and return to idle. Record microphone, permissions, hardware/OS, and outcome. Stage 0 passed on retry. For Stage 1, also cancel a second recording with Escape and verify it produces no text. The initial Stage 0 failed paste is not considered conclusively fixed.

## Login startup and recovery

The README includes a launchd example. This checkout does not prove that a login agent or shell alias is currently installed. Configure login startup only after a manual launch works. Its command should call this checkout’s `launch.sh`, which uses `.venv`.

Dependency changes require updating both direct and full baseline pins, a fresh isolated install, `pip check`, imports, and the relevant manual smoke test. Preserve prior pin files in Git and record migrations in the development log. To roll back code, use a known Git revision and recreate its environment; do not assume a newer environment is compatible.
