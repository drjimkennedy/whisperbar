# ADR 0004: Nonactivating feedback and background model loading

**Date:** 2026-10-07
**Status:** Implemented; native acceptance recorded in the development log.

## Decision and reason

Keep lifecycle-to-presentation logic in `core/feedback.py` and native rendering in `ui/overlay.py`. Show a small click-through panel that cannot become key or main, using a nonactivating NSPanel. Do not activate the application for ordinary feedback. Existing shortcuts and menu actions remain the interaction surface, so the panel does not compete with the captured text destination.

Use a latest-value RMS meter with a timestamp, without buffering telemetry or exposing transcript contents. Show elapsed recording time, a quiet-input hint, distinct processing/cancellation states, and timed completion/error messages. Keep the last result in the menu. The meter reports activity; it cannot diagnose mute, device failure, permission, or speech accuracy by itself.

Create the menu first and import/load Whisper on one daemon worker. Queue its result to the main thread, gate recording until ready, keep failures visible, and permit a retry without relaunching. Loading remains indeterminate because the current recognition adapter does not provide a reliable unified import/download/load progress estimate. Ignore loader results after shutdown.

## Alternatives and tradeoffs

A clickable floating panel risks target activation; keyboard commands and the menu are adequate for this stage. A waveform requires more UI work without improving the immediate input-presence check. Background threads preserve UI responsiveness but cannot force-cancel a native model load; quitting ends the process. Process isolation remains an option if measured native hangs justify it.

Use read-only AVFoundation authorization through the installed system framework and existing PyObjC bridge. No new package or data schema is needed. Permission results depend on the actual launching process; a sandboxed diagnostic is not a substitute for the running app's report. Explicit setup/onboarding dialogs may activate because they require input; ordinary status panels may not.

## Portability and rollback

The [feedback contract](../contracts/feedback-and-startup.md) defines the states, timings, meter semantics, startup gating, and acceptance scenarios for any future shell. Replace the Cocoa panel and permission adapter when migrating; retain presentation tests and storage formats. Rollback requires quitting and restoring the previous code, with unchanged dependencies and data schemas. Stage 2 retains history/insertion but lacks the new feedback and retry UI.
