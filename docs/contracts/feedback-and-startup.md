# Feedback and startup contracts — version 1

Implemented during Stage 3 on 2026-10-07. The development log records native verification separately from implementation.

## Startup

Construct the menu shell before importing Whisper/Torch or loading model weights. The first UI timer starts one background loader. While loading, show an indeterminate loading message in the menu and panel; do not invent percentages or accept a recording. A failed load keeps the app open with Retry model loading and setup guidance. Successful retry installs the recognizer and enables the shortcut. Results arriving after shutdown do not re-open UI or enable recording.

The first-run history choice still precedes shortcut activation. Model loading starts after that choice. This is a development checkout: dependencies and Python are still installed through the setup script, and the launcher performs environment checks before the shell can start. Customer packaging is Stage 5. Ordinary recording, recovery, settings, and model retry use the menu and panel without terminal interaction.

## Feedback ownership

`core/feedback.py` maps lifecycle states and scalar meter samples to text, visibility, and level values. It has no Cocoa dependency. `ui/overlay.py` renders that presentation exclusively on the main thread. Audio callbacks publish only their latest RMS value and monotonic timestamp through a lock-protected tuple; they never call Cocoa or accumulate a telemetry queue. These readings are transient and are not written to history or logs.

The panel is a borderless nonactivating NSPanel, cannot become key/main, and ignores mouse events. It is shown without app activation. It occupies the bottom of the active screen's visible frame and participates in Spaces/full-screen auxiliary display. It does not expose actions that require clicking; the hotkey and Escape remain the primary keyboard commands, with recovery and settings in the menu. Explicit setup and first-run dialogs may activate the app because they require a user response. Native focus/display/accessibility checks remain necessary.

## States and timing

Starting, recording, transcribing, inserting, and cancelling have distinct text. Recording begins only after the coordinator reports first samples. The panel and menu show elapsed recording time; repeated busy events do not restart the clock. The level bar maps RMS amplitude from −60 to 0 dBFS into 0–1, clamped and finite, and zeros readings older than 500 ms. It indicates input activity, not calibrated loudness or speech recognition quality.

After three seconds without sustained input above −60 dBFS (RMS 0.001), display “Very little audio — check mute or selected microphone.” Above-threshold input must last 200 ms to clear/reset the hint, so brief taps do not suppress it. Sample gaps longer than 500 ms cannot count as sustained activity. This does not assert that the microphone is muted or permission is denied. Sustained input resumes the normal shortcut hint. The hint never stops or discards recording; existing silence validation and first-sample/stalled-audio watchdogs remain unchanged. Only near-silent input should trigger this advisory; background noise during a pause can prevent it. This is not speech detection.

Processing feedback is indeterminate. Cancellation states that processing may still need to finish. Completion/recovery feedback lasts five seconds; recording errors last ten seconds. The menu retains the last result after the panel disappears. Model loading/failure stays visible until ready/retried or quit. No transcript text is shown in the panel.

## Setup and permission reporting

Setup and permissions reports model readiness, resolved input, global input-monitoring trust, Accessibility trust, microphone authorization, and current shortcut. Read-only AVFoundation authorization uses the installed system framework through the existing PyObjC bridge, without a new package or permission prompt. Unknown status remains unknown. Denied/restricted microphone authorization produces an actionable capture error before opening the stream. PortAudio failures suggest checking permission and input; they do not claim a specific cause.

Permissions belong to the launch context, often Terminal in this development build. Sandboxed diagnostic processes can report different authorization from the running app, so only the actual app's results establish native acceptance. The setup report never toggles permissions. No persistent-data schema changes are introduced in this stage.

## Acceptance

Automated coverage includes deferred model startup, shortcut gating, failed-load retry, late completion after quit, stale sessions, elapsed-time stability, quiet-input hints, stale/invalid levels, and denial before stream creation. Native validation must check visible loading/recording/processing, level response, target preservation with the panel shown, silence guidance, Escape cancellation, setup dialog keyboard use, and the supported display/Spaces configurations. Do not mark these native gates passed from unit tests alone.
