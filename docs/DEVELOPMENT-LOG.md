# WhisperBar development log

Record implemented changes separately from proposals. Keep entries newest first. Use repository-relative links and commit identifiers when available.

## 2026-10-07 — Stage 0 isolated setup and baseline

**Status:** Setup implemented and verified on the development Mac; manual record/transcribe/paste smoke test passed on retry. Initial paste failure remains unresolved and must be investigated in the next reliability work.
**Starting commit:** `91a0d10`; implementation commit is discoverable from this entry’s Git history.

Replaced the inherited-package environment with an isolated `.venv`; preserved the prior environment as ignored `.venv-legacy/`. Added direct dependencies, a 44-distribution platform/version-pinned baseline, an idempotent setup script, and a startup preflight. The launcher now uses the project interpreter without fallback. Added actionable model-load failure reporting, inference measurement tooling, five failure-path tests, and updated setup/operation instructions.

Archive review: the older hardening branch contained dependency/setup ideas but omitted scipy, which the current app imports. No archived application implementation was merged. The clean install exposed PyObjC 12.0 as yanked for incorrectly claiming Python 3.9 support; all five PyObjC distributions were changed to 11.1 and revalidated. This establishes the existing Python 3.9 baseline, not the final commercial runtime.

Verified:

- `./scripts/setup.sh`: installed into a fresh environment without system/user site packages; rerun installed corrected PyObjC wheels and passed preflight.
- `.venv/bin/python -m pip check`: no broken requirements; all 44 runtime pins match installed versions.
- Runtime imports: numpy, sounddevice, scipy.io.wavfile, whisper, pyperclip, pyautogui, rumps, and pynput keyboard passed; `site.ENABLE_USER_SITE` is false.
- `.venv/bin/python -m unittest discover -s tests`: five tests passed, covering ready environment, missing package, inherited environment, missing ffmpeg, and injected model-download failure.
- `zsh -n launch.sh scripts/setup.sh` and `git diff --check`: passed.
- Cached small-model CPU inference benchmark: [raw JSON](benchmarks/2026-10-07-silence.json). Model load 0.767 s, first inference 0.618 s, two warm runs 0.419/0.414 s. Synthetic silence produced three output characters each run; direct engine testing bypasses the app’s peak-volume guard. This is not a speech-accuracy result or evidence of hallucination suppression.
- Launched at user request. Log confirms isolated interpreter, MacBook Pro Microphone, and model ready. A 9.048-second recording (144765 samples at 16 kHz, peak 0.18166) produced 111 characters in approximately 1.3 s and attempted paste. User reported that this first attempt did not paste. A retry captured 125205 samples (7.825 s) and produced 107 characters in approximately 0.9 s; user confirmed the retry pasted successfully. An Accessibility trust probe in the unrestricted launch context returned true, so missing Accessibility permission is not established as the cause. No transcript content was copied into this report.

Limitations: no clean second Mac test, no real network-failure integration test (model failure is injected), no latency distribution or recognition corpus, and no new-runtime compatibility validation. This pin set fixes dependency versions but is not a hash-locked build or security audit. ffmpeg and a suitable Python remain system prerequisites; model weights are separate cached/downloaded assets. Detailed recording-state failures remain Stage 1 work.

Rollback: restore the previous code/pin revision and recreate the environment. The former shared environment remains available locally, and `/usr/bin/python3` still has the earlier machine packages; do not redistribute it. No history/schema or login-agent changes occurred. Next: investigate intermittent paste failure while implementing the Stage 1 coordinator and cancellation gates. Basic Stage 0 setup and smoke checks are complete on this Mac; supported-runtime modernization, a clean second-machine test, and larger baseline measurements remain explicit follow-ups.

## 2026-10-07 — Product roadmap documented

**Status:** Documentation created; upgrade stages not implemented.
**Baseline commit:** `fd4037e21219541d2a8d57d25757e5156c0b0fe9`.

Created the [robust-product PRD](PRD-robust-whisperbar.md) and [Python-first decision record](decisions/0001-python-first-portable-boundaries.md). Compared current source with the user-supplied Handy snapshot. Recorded current functionality, proposed stage gates, migration contracts, data portability, and a deferred commercial stack evaluation.

Validation: checked document structure, local documentation links, and separation of proposed work from verified baseline. No runtime behaviour changed in this documentation task. Next: Stage 0 reproducible setup and baseline, followed by Stage 1 lifecycle reliability.

## 2026-10-07 — Local Python environment recovery

**Status:** Local workaround implemented; core imports verified; full app untested.

Problem: `python3 app.py` failed with `ModuleNotFoundError: No module named 'numpy'`. Homebrew `python3` resolved to 3.14.7, while system Python 3.9.6 already had the packages.

Created `.venv` using system Python with `--system-site-packages`; added `.venv/` to `.gitignore`. No packages were installed and no application logic changed. The environment remains dependent on existing machine packages.

Verified NumPy 2.0.2 and imports of sounddevice, scipy.io.wavfile, whisper, pyperclip, and rumps. Checked discoverability, but not runtime imports/behaviour, of pyautogui and pynput. No microphone, hotkey, model inference, paste, or clean-install test was performed.

Local run command: `.venv/bin/python app.py`. Existing `launch.sh` still runs `/usr/bin/python3 app.py`. Neither path is yet a reproducible customer installation. Rollback: stop using the local environment; application source and launcher were unchanged. Stage 0 must replace this workaround with isolated declared dependencies.

## Entry template for future implementation

- Date, stage/requirement, and status: proposed / implemented / verified / released.
- Commit/version and concrete user-visible behaviour changed.
- Modules, contracts, settings/schema changes, and decision links.
- Automated checks: exact commands, results, environment, and evidence location.
- Manual checks: scenarios, applications/devices, results, limitations.
- Performance: hardware, model/engine versions, corpus ID, warm/cold data.
- Privacy/data impact and migration/rollback steps.
- Known failures and next gate; do not mark a stage complete without evidence.
