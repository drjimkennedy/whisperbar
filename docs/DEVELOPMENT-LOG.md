# WhisperBar development log

Record implemented changes separately from proposals. Keep entries newest first. Use repository-relative links and commit identifiers when available.

## 2026-10-07 — Stage 2 native acceptance follow-up

**Status:** Stage 2 accepted on the current Mac. Changed-focus protection, manual recovery, native export, and native import without duplicates passed.
**Implementation commit:** `2482c0d`.

Jim started dictation in TextEdit, switched applications, and stopped with the other application active. He confirmed that no text appeared automatically. He then confirmed Copy Last recovered the sentence in TextEdit and the native Export history dialog saved `WhisperBar-history-test.json` in Downloads. Jim then confirmed importing that same file through the native open dialog succeeded without duplicate entries. This completes the agreed Stage 2 native sign-off, alongside earlier TextEdit insertion and restart recovery and 49 passing automated tests. Broader app/OS coverage and outstanding Stage 1 microphone-permission and native cancellation-timing checks remain release work; this is not universal compatibility certification. No transcript text is included here. The exported file is a separate user-controlled copy and is not removed by history deletion.

## 2026-10-07 — Stage 2 recoverable output and preferences

**Status:** Implemented; TextEdit insertion, Copy Last recovery, first-run choice, and history after restart verified by Jim. Extended native checks remain open.
**Starting commit:** `ac96168`.

Added independent storage modules with SQLite version 1, newest-20 retention, strict JSON export/import, atomic versioned preferences, and unknown-schema preservation. Menu controls cover copying/deleting records, deleting all, import/export, history opt-out, persistent microphone/shortcut, and next-launch model. Completed text is retained before delivery; cancellation excludes persistence, and storage failure preserves memory recovery. No raw audio is retained. User data lives outside the checkout under Application Support; export files contain transcript text.

Added a macOS destination adapter and structured delivery outcomes. Capture process/window/field/selection at session start, revalidate before targeted AXSelectedText insertion, and retain text for explicit Copy Last when unsupported or changed. Automatic output leaves the clipboard untouched. This intentionally replaces Stage 1 automatic copy-and-Command-V, including automatic clipboard population when permission is denied. See [ADR 0003](decisions/0003-portable-history-and-targeted-insertion.md) and the [portable data contract](contracts/history-and-delivery.md).

Native testing found the first-run privacy prompt was issued before the menu-bar event loop; moved it to the first UI timer tick before enabling shortcuts. Jim selected Keep last 20, and saved preferences confirmed that choice. The initial TextEdit session required Copy Last, which Jim confirmed recovered the text. Investigation found that PyObjC returns a plain tuple for AX selection ranges; corrected handling and added a regression test. Restarted the app with the fix. Jim then confirmed both automatic TextEdit insertion and the earlier transcript visible in history after restart. Transcript contents were not copied into this log.

Validation: `.venv/bin/python -m unittest discover -s tests` covers 49 cases, including history restart/retention, import idempotence and rollback, schema protection, live-data export overwrite prevention, settings atomic failure, no-history wiring, save-before-delivery, cancellation exclusion, destination changes, and deferred onboarding. Final run results are recorded with this commit. No runtime dependency changes were needed.

Limits: native changed-focus testing, native import/export panels, additional destination apps, microphone-permission denial, and measured native cancellation latency remain pending. Unit tests do not close those gates. Stage 2 proceeded at Jim's request with remaining Stage 1 checks carried forward. Rollback: export valuable text, quit the app, restore the prior code/environment; Stage 1 does not consume these settings/history files and overwrites the clipboard. Preserve files for forward recovery.

## 2026-10-07 — Stage 1 native-validation follow-up

**Status:** Cleanup fix implemented and 28 automated tests passed; native AirPods disconnect and recovery to the Mac microphone passed. Native Accessibility denial was verified and original access restored; manual Command-V recovery also passed. Additional target-app checks remain pending.
**Starting commit:** `2e07f7e`.

Inspection found that `Capture.close()` dropped its stream handle before confirming native close succeeded. A repeated close failure could therefore be followed by another recording, and cancellation could hide the cleanup error. Retain the handle until successful close, retry in final cleanup, and block recording/device refresh with a restart-required error if cleanup remains uncertain. Added regression checks for close retry, persistent failure during cancellation, and selected-device fallback.

Ran real cached Whisper `small` CPU inference on 120 seconds of synthetic silence through the coordinator. Cancellation occurred while inference was active; the call returned in 0.055 ms, processing drained after 1.781 seconds total, new recording was rejected during the drain, and no delivery or retained transcript occurred. [Raw evidence](benchmarks/2026-10-07-inference-cancellation.json). These are one-run coordinator measurements, not native key/UI latency, accuracy, or p95 claims. The reproducible script neither records microphones nor touches clipboard/output.

Validation: 28 unit tests passed, including the four new cleanup/fallback regressions. Restarted the idle app with the fix for the user-assisted AirPods test. The first AirPods attempt captured 148560 samples (~9.285 s) and produced seven characters; Jim reported partial output. The connected-AirPods retry captured 171680 samples (~10.730 s), produced 77 characters in 0.76 s, and Jim confirmed the complete sentence arrived. Normal AirPods dictation is therefore verified on retry; the first partial result remains unexplained. This does not establish a passing disconnect gate. During the disconnect test, the app reported “Microphone stopped sending audio — reconnect and retry” at 11:39:03 AEST and did not transcribe/deliver the interrupted session. The next session used MacBook Pro Microphone, captured 112290 samples (~7.018 s), produced 60 characters in 0.68 s, and requested paste. Jim’s follow-up dictation confirmed that the system-default Mac microphone output came through. No app restart was needed after the disconnect error. For the subsequent authorized permission test, macOS Device Control and Data Access was temporarily disabled for zsh, which did not change trust, and immediately restored. Disabling Terminal changed the native Accessibility probe to false. Both entries were restored to their original on state, and the probe returned true again. Codex Computer Use access remained on. No lasting permission change was made.

Rollback: quit and restore the prior commit; no dependency or data-schema change. Permission evidence: with real native Accessibility denial and clipboard/key actions replaced by spies, the production output handler requested a copy and no paste; see [raw evidence](benchmarks/2026-10-07-permission-denied.json). Independently, the live app captured 90975 samples (~5.686 s), transcribed 62 characters in 0.87 s, and Jim confirmed nothing pasted automatically. Jim confirmed Command-V recovered the dictated sentence. Original permission restoration was verified with both the Settings UI and a native trust probe. Additional target applications and native microphone-permission revocation remain untested; do not equate Accessibility denial with microphone denial.

## 2026-10-07 — Stage 1 session reliability

**Status:** Implemented; 24 automated tests and native startup/duplicate-launch/dictation/cancellation smoke checks passed. Extended physical-device and permission checks remain open.
**Starting commit:** `95c49a3`; implementation commit is available from this entry’s history.

Extracted a platform-independent session coordinator and shortcut latch into `core/`; moved capture/recognition and macOS output/instance locking into `adapters/`; reduced `app.py` to the desktop shell and startup. Added explicit arming, recording, transcribing, delivering, cancelling, error, and closed states. Session IDs and cancellation flags prevent old callbacks/results from delivering or changing a later session. UI mutations now occur on the main thread through queued events.

Added Escape/menu cancellation, repeat-safe shortcuts, rejection of triggers while busy, 300-second capture limit, sample-readiness/stall watchdogs, single-instance locking, bounded rotating logs, and safe microphone refresh gating. Kept device fallback, silence detection, and sample clipping. Direct float-array transcription eliminates app-created temporary WAV files. Added cancellable shortcut-release waiting before output, Accessibility-aware copy-only fallback, honest paste-request status, and in-memory Copy Last recovery. No persistent history or clipboard restoration yet.

Verification:

- `.venv/bin/python -m unittest discover -s tests`: 24 tests passed, including 100 simulated sequential sessions and 100 repeated key-downs, startup/inference/delivery-preparation cancellation, late results, capture failure/stall/limit, output failure recovery, cleanup, and instance lock behaviour.
- `.venv/bin/python -m pip check`: no broken requirements. `git diff --check`: passed.
- Parsed all changed Python sources without writing bytecode. A separate `compileall` attempt could not write macOS’s cache inside the sandbox; its permission request was cancelled. No claim is made that that command completed; imports, test execution, and parsing provide the syntax evidence.
- Restarted the idle old process and launched the new app through `./launch.sh`. Model and UI initialized. A second actual launch exited with code 2 and an already-running message, without loading a duplicate model.
- Normal live session captured 121995 samples (~7.625 s), transcribed 95 characters in 0.91 s, and requested paste. Jim confirmed that this first dictation pasted and the next recording, cancelled with Escape, did not paste. Transcript content is not retained in this log.

Known limits: initial Stage 0 paste failure is not conclusively diagnosed. No destination-field validation or insertion receipt; output status intentionally says requested. No raw audio/transcript history on disk. Native mic removal, permission revocation, multiple target apps, and long-running inference cancellation still need manual validation. Cancellation cannot undo committed output or forcibly interrupt a blocking native call. The full Stage 1 platform gate remains open for these checks.

Contracts and rationale: [lifecycle contract](contracts/session-lifecycle.md), [ADR 0002](decisions/0002-session-coordinator.md). Rollback: quit the new process and restore the previous revision; do not run an older unprotected instance alongside it. No package or persisted-data migration required. Next: finish the remaining native failure checks before closing Stage 1, then Stage 2 persistent recovery and safer delivery.

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
