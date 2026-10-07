# WhisperBar: from personal utility to a dependable macOS product

**Slug:** whisperbar-robust-product-prd
**Created:** 2026-10-07
**Revised:** 2026-10-07 13:11 AEST
**Status:** Proposed

## NOW

- [ ] Complete the remaining platform matrix, including native microphone permission denial; Accessibility denial and manual clipboard recovery now pass.
- [ ] Extend native checks to external displays, switching Spaces, additional target applications, and measured cancellation timing.
- [ ] Confirm the Stage 3 low-input hint under near-zero input before closing its remaining feedback checks.

## Executive Summary

Develop WhisperBar in Python through gated upgrades: reliable operation, recoverable output, clear feedback, improved speech processing, and a distributable pilot. The eventual ambition is an affordable paid macOS dictation app. Pricing, distribution channel, supported hardware, and the final technology stack remain undecided.

The immediate product promise is dependable local dictation: users can tell when recording starts, stop or cancel safely, recover their words, and understand failures. Python remains the implementation choice while these needs are validated. Migration should follow measured limitations or product requirements after the planned Python stages, rather than visual sophistication alone.

Handy is a useful reference: the inspected repository uses a Rust backend with Tauri and React/TypeScript, multiple transcription engines, speech detection, persistent history, and explicit recording coordination. Borrow behaviours and architectural boundaries; do not assume its entire stack is necessary for this product.

Build portability into the work now through versioned data formats, replaceable platform and inference adapters, language-neutral acceptance scenarios, decision records, and an evidence-backed development log. Stage 0 now has a tested isolated development installation and initial inference measurements. Customer packaging, newer-runtime compatibility, and clean-machine distribution remain later validation work.

This document defines the roadmap; Stage 0–3 implementation and remaining verification are tracked in the development log. Jim owns product priorities and the eventual commercial decision; implementation work must record what actually shipped and what was tested.

## 1. Product goal and audience

Serve Mac users who dictate short notes, messages, and working drafts into everyday applications and value local processing, simple setup, and dependable recovery. Jim is the initial operator; the pilot should include people who cannot troubleshoot Python.

The paid-product hypothesis is that convenience, reliability, onboarding, and support can justify an entry-level price even when free tools exist. Validate this with pilot users before selecting a price or building payment infrastructure. No subscription, perpetual licence, account requirement, or App Store commitment is implied.

Proposed first commercial scope: macOS, English dictation, offline transcription after model installation, a menu bar control, visible recording feedback, configurable shortcuts, and transcript recovery. Decide supported macOS versions and Apple Silicon/Intel coverage from testing. Cross-platform support is a possible future benefit of portable boundaries, not an immediate delivery requirement.

## 2. Verified baseline and gaps

The baseline is repository commit `fd4037e21219541d2a8d57d25757e5156c0b0fe9`, inspected on 2026-10-07, plus the uncommitted environment change recorded in the development log.

| Area | Observed implementation | Gap for a dependable product |
|---|---|---|
| Capture | `sounddevice`, mono 16 kHz, device picker, device re-enumeration, peak check | Shared mutable audio state; no explicit arming/processing coordination |
| Recognition | `openai-whisper`, configured `small` model, English, `fp16=False` | No measured benchmark, engine abstraction, model lifecycle UI, or switching UI |
| Controls | `pynput` shortcut; threads started from toggle | Repeated key events and rapid presses can overlap operations; no cancellation |
| Feedback | `rumps` menu bar icons/status and temporary error message | No live microphone level, readiness confirmation, or recoverable error workflow |
| Output | Clipboard overwrite, fixed 150 ms delay, simulated Command-V | No target validation, clipboard preservation, or explicit paste outcome |
| Recovery | Log metadata; temporary WAV deleted after transcription attempt | No transcript archive, retry UI, or last-transcript action |
| Settings | Python constants; selected microphone held in memory | No validated persistent user preferences |
| Installation | Shell launcher invokes `/usr/bin/python3` | Depends on machine-installed packages and external tools |

These are source findings, not reproduced runtime defects. Existing device recovery, silence checks, clipping before WAV conversion, and error logging must be preserved or replaced with verified equivalents.

The README/playbook describe `base` in examples while `config.py` currently selects `small`. Their statements about installed dependencies, aliases, auto-start, and speed are not proof of a clean installation or current performance. Stage 0 reconciles those instructions.

## 3. Required user experience

1. Launch the app and receive actionable setup guidance for missing permissions or models.
2. Choose a microphone and shortcut; retain those choices after restart.
3. Trigger recording. Show “starting microphone” until samples arrive, then a clear recording indicator and level meter.
4. Stop recording once. Show processing feedback while protecting the session from repeated hotkeys.
5. Retain the resulting transcript according to the selected history policy before attempting insertion.
6. Insert into the intended application when the target can be validated. If focus has changed or insertion is unavailable, present a copy action and preserve the result.
7. Cancel recording or pending output with an explicit action. Cancelled work must never paste later.
8. Recover the last completed transcript without repeating the dictation.

Ordinary use must not require a terminal, source editing, or interpreting tracebacks by the pilot stage. Raw dictation remains available unchanged; automatic rewriting is outside the initial paid-product scope.

## 4. Python upgrade stages and exit gates

Proceed in sequence. Each gate requires a dated evidence entry; a failed gate creates a documented issue rather than a silent scope reduction.

| Stage | Deliverables | Exit evidence |
|---|---|---|
| 0 — Reproducible baseline | Declared Python version, dependency manifest and tested resolved versions, isolated environment, explicit launcher, setup/troubleshooting instructions, baseline recordings and metrics | Install in a fresh environment without inherited site packages; import checks; successful record/transcribe/paste smoke test; missing dependency and model-download failure produce understandable errors |
| 1 — Reliable session lifecycle | Single coordinator, repeat-safe shortcut edges, owned audio buffers, guarded transitions, cancellation, single-instance behaviour, deterministic cleanup and main-thread UI updates | Repeated/rapid keys, stop during startup, cancel during inference, mic removal, denied permission, worker error, and second launch all pass; no overlapping capture, duplicate paste, or stale status reset |
| 2 — Recoverable output | Copy-last action, local text history, export/delete controls, safe output adapter, persistent preferences | Transcript remains recoverable after paste failure and restart when persistence is enabled; changed focus prevents automatic paste; user clipboard changes are not overwritten during restoration; schema migration and export/import fixtures pass |
| 3 — Clear feedback and onboarding | Small non-focus-stealing overlay, level meter, arming/recording/processing/error states, setup checks, shortcut and microphone settings | Normal operation needs no terminal; overlay never steals the insertion target; tester can identify muted mic, denied permission, and processing state; keyboard access and supported display configurations verified |
| 4 — Speech quality and performance | Voice activity detection with speech padding, measured model/engine experiments, resource limits, optional idle unloading, optional explicit vocabulary rules | Fixed corpus compared before/after; speech beginnings/endings preserved; no-speech cases produce no invented output in the test corpus; chosen configuration meets agreed latency/quality targets |
| 5 — Python distribution pilot | Repeatable app packaging experiment, bundled runtime/dependency strategy, model acquisition UI, installation/update/uninstall design, pilot support guide | Non-developer installs on a clean supported Mac without Python/Homebrew setup; model download interruption recovers; offline operation works after setup; update preserves settings/history and recovery is documented |
| 6 — Product and stack decision | Measured stack scorecard, pilot feedback, support burden, pricing research, focused migration spike if justified | Written decision to ship Python, extend a specific experiment, migrate a component, or migrate the shell; commercial release gates separately satisfied |

Hold-to-talk can follow reliable toggle operation during Stage 3 if pilot demand supports it. Live transcription, cloud cleanup, multiple languages, automation APIs, extensive vocabulary correction, and cross-platform UI are later candidates, not prerequisites for these gates.

Exhausting the Python stages means completing each experiment or documenting why its gate cannot be met at acceptable effort. A proven hard blocker can stop an experiment; do not spend indefinitely to preserve a language choice. A full rewrite still needs an explicit decision record.

## 5. Architecture that survives a stack change

Use a small application core with explicit input commands and output events. Keep operating-system calls, GUI types, audio-library buffers, and inference objects out of the domain contracts. These boundaries can be Python protocols and plain data structures initially; they do not require services, a network API, or a plugin framework.

| Boundary | Responsibility | Portable contract |
|---|---|---|
| Session coordinator | Serialize commands, own state and session identity | Start/Stop/Cancel commands; state and completion events |
| Audio adapter | Device enumeration, capture, levels, sample conversion | Device descriptors; audio frames with sample rate, channel count, timestamps |
| Recognition adapter | Load/unload model, transcribe, report errors/capabilities | Audio asset + options → transcript + engine/model metadata + timings |
| Output adapter | Target snapshot, validation, copy/insertion, clipboard handling | Target token + text → structured outcome with assurance level |
| History repository | Persist, retrieve, delete, export and migrate records | Versioned transcript/settings records |
| Desktop shell | Menu bar, overlay, settings, onboarding | Dispatch commands and render events; no inference or storage logic |
| Diagnostics | Collect timings and redacted failure metadata | Versioned diagnostic events with session IDs |

Recommended lifecycle: `idle → arming → recording → transcribing → delivering → idle`. Errors and cancellation have explicit terminal outcomes and cleanup. State is owned by one coordinator, not independent UI and worker flags. UI updates execute through the UI framework’s supported thread mechanism.

Each session has a unique ID and its own audio snapshot. Late worker results and timers must match the active session before changing state or output. In Stage 1, triggers received while busy are ignored with visible feedback rather than queued. A future queue requires its own defined semantics and tests.

Cancellation invalidates delivery immediately. If the inference library cannot interrupt execution safely, let it finish without delivering its result and block new inference until that worker drains. Never advertise instant compute cancellation without verifying it. Shut down streams and temporary files on every handled error path; clean abandoned app-owned temporary files on next startup.

Proposed modules: `core/`, `adapters/audio/`, `adapters/transcription/`, `adapters/macos/`, `storage/`, `ui/`, and `tests/contracts/`. Extract incrementally from `app.py` while preserving working behaviour. Keep the launch entry point thin.

## 6. Data, privacy, and output behaviour

Local transcription is the default. No audio, transcript, or diagnostics leave the machine automatically. Downloads for models/updates are disclosed network actions. Optional future remote processing must be separately enabled and clearly identify what is sent.

Proposed history defaults: retain the last 20 completed transcripts locally; raw recording retention off. Explain the text-history default during onboarding and provide a no-history mode. In no-history mode, Copy Last exists only in memory until quit. Do not persist cancelled sessions. Persistence failures must be visible and must not discard the in-memory completed transcript.

History deletion removes app-managed records and associated recordings; do not promise forensic erasure or removal from system backups. Diagnostic logs exclude transcript text and audio by default, rotate to a bounded size, and expose a user-reviewed export.

Use SQLite for local history and documented JSON/JSONL exports for portability. Avoid Python pickle, executable configuration files, and library-specific serialized objects as migration formats. Settings use versioned JSON; credentials, if ever needed, belong behind an operating-system credential adapter.

Minimum transcript export fields: `schema_version`, `id`, `created_at` (UTC ISO 8601), `text`, `language`, `engine_id`, `model_id`, `duration_ms`, `transcription_ms`, and `delivery_status`. Optional audio uses a relative asset reference plus format/checksum metadata, never a machine-specific absolute path. Exports omit raw audio unless explicitly requested. Stable identifiers are independent of engine package names and UI labels.

Every schema change has a migration, representative fixture, and backup/recovery procedure. Export/import must preserve text and identifiers, reject unsupported versions clearly, and define duplicate-ID handling. Test against malformed files without executing their contents.

Capture the destination application/window when recording begins and revalidate immediately before insertion. Application identity alone does not guarantee the same text field. Where field identity cannot be established, document that limitation, default to a conservative delivery policy, and offer explicit copy/manual paste. Do not silently redirect output to a newly focused application.

Distinguish “copy complete,” “paste requested,” and “insertion confirmed”; simulated Command-V alone is not confirmation. Clipboard preservation must not overwrite a newer user copy, including non-text content. If full restoration cannot be supported reliably, make the supported behaviour explicit and retain the transcript for manual recovery.

## 7. Quality targets and verification

These are proposed targets, not measured claims. Stage 0 records a named reference Mac, OS, engine/model version, microphone, and warm/cold conditions. Jim accepts or adjusts the target values after baseline measurement, with reasons retained in the decision log.

| Measure | Proposed gate |
|---|---|
| Reliability | 100 consecutive scripted/manual sessions with zero hangs, duplicate deliveries, or missing recoverable completed transcripts under enabled history |
| Recording readiness | Warm p95 trigger-to-first-sample ≤500 ms on reference hardware; indicator remains honest if slower |
| Transcription | Warm p95 stop-to-text ≤3 seconds for 10-second clips on selected reference configuration |
| Cancellation | UI acknowledges within 250 ms; zero post-cancel deliveries, including late worker results |
| Recognition quality | Compare word error rate and critical name/term accuracy on at least 30 consented clips; no >1 percentage-point WER regression without an explicit tradeoff decision |
| Resources | Record idle/peak memory, cold load time, package/model sizes, and inference CPU/GPU use; set numeric budgets after baseline |
| Recovery | Every deliberate paste failure leaves text accessible under the chosen retention policy |
| Installation | Fresh supported Mac can reach first successful dictation using only shipped instructions and app UI |

Corpus should cover Jim’s accent, short messages, technical names, silence, fan/background noise, pauses, and more than one microphone where available. Keep corpus consent and distribution rights clear; use synthetic/non-sensitive fixtures in the repository. No accuracy or speed marketing claim should be inferred from a small internal corpus.

Automate state transitions, repeated events, late results, contract tests, schema migrations, and failure injection. Use manual macOS checks for permissions, focus, input monitoring, app activation, microphone changes, and clipboard interactions. Exercise Notes, a browser text field, an editor, and at least one messaging application; record exact versions and observed outcomes. Report unsupported secure fields rather than claiming universal text insertion.

## 8. Commercial readiness and stack evaluation

Treat an affordable paid app as an outcome to validate. Before charging, define the supported hardware/OS matrix, installation route, software/model redistribution rights, privacy wording, update and rollback behaviour, purchase/recovery experience, support process, and ongoing cost assumptions. Verify current Apple distribution and signing requirements with official sources at that time. This PRD does not settle App Store feasibility or current platform rules.

| Candidate | Role in the later evaluation | Evidence still needed |
|---|---|---|
| Packaged Python with a macOS shell | Continue the working implementation with minimal core replacement | Clean-machine package behaviour, dependency size, native integration, updates, support burden |
| Swift/SwiftUI with native macOS adapters | Candidate for a Mac-focused product | Prototype hotkeys, overlay, insertion, model binding and migrations; development/maintenance effort |
| Rust + Tauri + React/TypeScript | Handy’s observed architecture; candidate if web UI reuse or additional platforms matter | macOS integration quality, bundle/runtime cost, build complexity, team familiarity and engine bindings |
| Hybrid native shell plus isolated recognition component | Replace only boundaries proven inadequate | IPC/process lifecycle, signing/package complexity, failure recovery and resource overhead |

Handy’s inspected source uses `transcribe-cpp` for Whisper-family inference with a macOS Metal feature, `transcribe-rs` for ONNX engines, `cpal` for capture, speech detection, SQLite history, and a React overlay. It also includes a beta clipboard read-receipt mechanism. These are source observations, not performance measurements or proof that the same choices suit WhisperBar.

After Stage 5, score viable candidates 1–5 using observed evidence: reliability/native integration 30%, reproducible distribution and updates 25%, performance/resource use 20%, maintenance and migration cost 15%, and future platform reach 10%. Mark unknowns explicitly. Pilot results can change the weights through a recorded decision.

Migration triggers include an unmet distribution gate, persistent native integration failures, unacceptable measured resource use, or repeated adapter workarounds with disproportionate support cost. Carry forward acceptance fixtures, data formats, user workflows, and decision history. Reimplement adapters behind the same contracts; migrate existing settings/history with backup and rollback. Do not assume Python implementation code itself is portable to Rust or Swift.

Pricing discovery belongs in the pilot: understand which problems users would pay to avoid, willingness to pay, preferred purchase model, and likely support volume. No price or commercial viability is asserted here.

## 9. Documentation and delivery discipline

Every stage must leave a usable handoff, not just working code. Maintain:

- This PRD for scope, requirements, gates, and unresolved product decisions.
- [Development log](DEVELOPMENT-LOG.md) for dated implemented changes, tests, limitations, and next steps.
- [Decision records](decisions/0001-python-first-portable-boundaries.md) for architecture choices, alternatives, evidence, and revisit triggers.
- `README.md` for verified setup and use; `PLAYBOOK.md` for operational troubleshooting, updated when behaviour changes.
- Contract/schema documentation and fixtures alongside their first implementation; benchmark reports with environment and corpus identifiers.

A stage handoff identifies the commit, requirement IDs or section references addressed, changed modules, commands/results, manual test evidence, data migration effects, known failures, rollback steps, and next gate. Label status as proposed, implemented, verified, or released. Never infer deployment or testing from code presence.

Use repository-relative paths in documentation and avoid personal home paths in launchers, settings, exports, and build definitions. Do not commit downloaded models, virtual environments, user history, recordings, or credentials. Capture dependency versions and system prerequisites so a different developer or agent can reproduce the work.

Jim owns scope and commercial choices. The implementing developer/agent owns evidence and handoff completeness. A future agent reads this PRD, the latest log, relevant decisions, and repository instructions before changing behaviour.

## AI Appendix

### Source inventory and evidence boundaries

- [Current application](../app.py), [configuration](../config.py), [launcher](../launch.sh), [README](../README.md), and [playbook](../PLAYBOOK.md), inspected 2026-10-07.
- Original `plan.md` is local historical context and currently ignored by Git; this PRD stands alone and must not depend on distributing that file.
- Handy reference snapshot was supplied locally at `/Users/jimkennedy/Downloads/Handy-main`. Its Cargo manifest reports `0.9.8`; no commit provenance was verified. This absolute path records source provenance only and is not a build/runtime dependency.
- Handy source locations: `src-tauri/src/transcription_coordinator.rs`, `managers/audio.rs`, `managers/history.rs`, `managers/transcription.rs`, `audio_toolkit/text.rs`, `paste_tx/macos.rs`, `settings.rs`, `src/overlay/RecordingOverlay.tsx`, and `src-tauri/Cargo.toml`.
- Handy was inspected, not built, executed, or benchmarked. No current external pricing, Apple policy, or competitive-market research was performed. Stack alternatives are hypotheses for later evaluation.
- Use Handy as design evidence. If implementation code/assets are reused later, record provenance and review the applicable licence/branding terms for the exact copied material.

### Environment repair already performed

The reported error was `ModuleNotFoundError: No module named 'numpy'`. `python3` resolved to Homebrew Python 3.14.7; `/usr/bin/python3` was Python 3.9.6 with the app packages discoverable. A local `.venv` was created using `/usr/bin/python3 -m venv --system-site-packages .venv`, and `.venv/` was added to `.gitignore`.

Core imports verified: NumPy 2.0.2, sounddevice, scipy.io.wavfile, whisper, pyperclip, and rumps. `pyautogui` and `pynput` module availability was checked, but their runtime behaviour and full dictation were not validated. No fresh package installation was needed. This environment inherits machine packages and is explicitly not the intended portable setup. `launch.sh` still invokes system Python.

### Assumptions and open decisions

“Apple” in the request is interpreted as “app,” with macOS as the first product platform because that is the current implementation. Pricing is entry-level in intent; amount/currency and licence model remain open. Python stages are the agreed direction, while their detailed acceptance targets are proposed here.

Open decisions: supported OS/hardware; initial distribution route; confirmed latency/resource budgets; history default acceptance; maximum recording duration and memory cap; commercial engine/model rights; commercial differentiation and price. Stage 0 measures capture growth and Stage 1 must set a documented recording cap before unbounded sessions are allowed. Stage 4 may revise the cap based on evidence.

### Update instructions and change history

2026-10-07: Created the Python-first product roadmap, measurable stage gates, migration boundaries, data rules, and baseline record. No upgrade-stage implementation is claimed.

When revising, preserve the original creation date, update Revised/status, distinguish evidence from proposals, recompute the NOW items, and append a dated note for changed scope or decisions. Preserve superseded targets and their rationale in decision records rather than silently rewriting history.

2026-10-07 11:19 AEST: Stage 0 isolated setup, preflight, dependency pins, failure checks, and baseline measurement implemented. Manual paste succeeded on retry after an initial failure; retain that failure as an unresolved reliability issue. Historical environment-repair notes above describe the earlier state, now superseded by the isolated installation.

2026-10-07: Stage 1 coordinator, adapters, cancellation, repeat protection, instance locking, limits, and paste feedback implemented. Twenty-four tests plus native startup, duplicate launch, and user-confirmed dictation/Escape cancellation passed. Extended native failure checks remain open; see the development log and lifecycle contract. In-memory Copy Last was brought forward from Stage 2; persistent history and safer destination handling remain planned.

2026-10-07: Additional Stage 1 validation passed: actual cached-model inference cancellation, native AirPods removal detection, and subsequent Mac microphone dictation without restart. Fixed uncertain stream cleanup to retain/retry its handle and block new capture after persistent failure. Twenty-eight automated tests pass. Native permission revocation and broader application coverage remain open.

2026-10-07: Native Accessibility-denial test passed: trust became false, transcription completed without automatic paste, and production output routing selected copy-only. Original permissions were restored and native trust returned true. Jim confirmed manual clipboard recovery; microphone permission revocation is a separate untested case.

2026-10-07: At Jim’s request, implemented Stage 2 while carrying forward incomplete Stage 1 native checks explicitly. Added optional last-20 SQLite history, versioned JSON interchange/preferences, deletion, and direct target-validated insertion that leaves the clipboard untouched. Jim selected Keep last 20 and confirmed TextEdit automatic insertion plus history visible after restart; earlier Copy Last fallback also passed. Fixed first-run UI ordering and PyObjC tuple selection-range handling during native checks. Wider native validation remains open; see the data contract and ADR 0003.

2026-10-07 12:24 AEST: Stage 2 accepted on the current Mac. Jim confirmed switching away from TextEdit prevented automatic insertion, Copy Last recovered the sentence, the export dialog saved a JSON file, and importing that file produced no duplicate records. Stage 3 can begin; wider compatibility and the carried-forward Stage 1 checks remain explicit release work.

2026-10-07 13:03 AEST: Stage 3 implemented: nonactivating click-through status panel, live RMS meter, elapsed recording time, quiet-input guidance, background model import/loading, in-app retry, and setup/permission reporting. Fifty-six tests passed. Jim confirmed panel/meter/processing/insertion in ordinary TextEdit on the MacBook display, cancellation with no output, setup dialog keyboard dismissal, and insertion with the panel visible in full-screen TextEdit. A quiet pause did not establish the low-input hint because actual signal level is unconfirmed. External displays, switching Spaces, and wider platform/failure checks remain open; see the feedback contract and development log.

2026-10-07 13:11 AEST: Refined the input hint after native testing. The initial near-zero threshold did not trigger during room-noise pauses; an increased threshold warned during quieter speech and was rejected. Final behaviour checks near-silent RMS input with brief-spike protection and says “Very little audio”. It is not speech detection and does not stop recording. Temporary level-only diagnostics were removed; the final 59 automated tests pass. Native muted-input validation remains open; the actual hint surface was observed during calibration.
