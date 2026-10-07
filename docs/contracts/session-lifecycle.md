# Session lifecycle and adapter contracts — version 1

Implemented 2026-10-07. This is a behavioural contract for a future Python, Swift, Rust, or other implementation. Internal threading primitives and audio arrays are not persistence formats.

## Commands and ownership

One Coordinator serializes commands under a lock and permits one session worker at a time. That worker owns the capture adapter, recognition call, output preparation, and delivery. No native UI objects enter the coordinator. UI events are immutable values with `session_id` (monotonically increasing integer), `state` (stable string), and `message` (display text, not transcript content).

| Input/state | Required result |
|---|---|
| Toggle while idle/error | Allocate new session ID; enter arming before launching worker |
| First nonempty audio callback while arming | Enter recording; callbacks from cancelled/old sessions are ignored |
| Toggle while arming | Cancel pending startup; close a late-created stream |
| Toggle while recording | Enter transcribing; signal worker to stop capture |
| Toggle while transcribing/delivering/cancelling | Ignore; emit busy feedback; never queue another recording |
| Cancel before output commit | Set cancellation and stop flags; suppress all later output for that session |
| Cancel during non-interruptible inference | Show cancelling; wait for worker to drain; do not start overlapping inference |
| Delivery commit already started | Cancellation cannot undo it and is rejected |
| Session ends | Clean up capture; emit idle or actionable error; cancelled sessions return idle |
| Quit | Reject new work, cancel pending output, request cleanup; join worker for up to two seconds |

A blocking native call cannot be forcibly interrupted by Python threads. On quit, an unresponsive daemon worker ends with the process. During normal operation, the coordinator remains busy until the worker drains. Microphone sample watchdogs cannot interrupt a hung native stream constructor; process isolation is a later remedy if observed in practice.

## Adapter shapes

- `capture_factory() → capture`: one capture instance per session.
- `capture.start(ready_callback)`: open microphone, report readiness only after nonempty samples arrive.
- `capture.last_sample_at`: monotonic timestamp for the sample watchdog.
- `capture.close()`: idempotent cleanup; attempt stream close even if stream stop raises.
- `capture.snapshot() → audio`: owned mono float32 samples at configured rate, finite, clipped to [-1, 1]. Reject absent/silent samples. No temporary WAV file is used in the dictation path.
- `recognize(audio) → text`: local Whisper with English and `fp16=False`; error or empty text does not deliver.
- `prepare_delivery(cancelled)`: cancellable waiting for shortcut release and focus-settling delay; no clipboard/paste mutation.
- `deliver(text) → status`: short irreversible output commit, serialized against cancellation. Retain text in memory immediately before attempting output. Always distinguish a paste request from confirmed insertion.
- `emit(event)`: enqueue only. The desktop shell drains events on its main-thread timer; no worker directly mutates Cocoa objects.

Cancellation is defined by the coordinator’s acceptance order, not the physical key timestamp. If the output commit wins the lock, its side effects may happen before cancellation is handled. Do not describe Escape as an undo operation.

## Capture limits and output behaviour

Capture is bounded to `MAX_RECORDING_SECONDS=300` at 16 kHz, one float32 channel: approximately 19.2 MB of sample payload, plus chunks and temporary concatenation/inference allocations. This is not a total process-memory bound. Automatically stop/transcribe at the duration limit. No first sample within five seconds or no samples for three seconds after readiness is an error.

Retain microphone re-enumeration and fallback to system input if a selected device disappears. Microphone picker/refresh actions serialize with lifecycle commands and do not reset PortAudio during active capture. Native removal/permission failures still need physical-device validation beyond the simulated tests.

Output waits up to two seconds for shortcut keys to release, then a cancellable 150 ms settling delay. If keys remain held, copy only and instruct manual paste. If Accessibility is unavailable, also copy only. Otherwise send Command-V without PyAutoGUI’s extra global pause. This reduces one possible timing problem; it does not establish the cause of the earlier failed paste.

The clipboard is overwritten; the destination field is not validated; insertion cannot be confirmed. Those are Stage 2 requirements. Copy Last holds one completed output in memory until quit. Cancelled recognition results do not replace it. Persistent history, export/import, clipboard restoration, and destination checking are not implemented here.

## Conformance evidence

`tests/test_session.py`: lifecycle sequencing, 100 repeated key events, 100 sequential sessions, stop during arming, recording cancellation, cancellation during recognition and output preparation, busy rejection, late result suppression, missing/stalled samples, capture limit, recognition/paste failures, cleanup and shutdown.

`tests/test_adapters.py`: silence rejection, sample clipping, payload cap, close after stop failure, duplicate instance lock, trusted/untrusted output behaviour, cancellable key-release wait.

`tests/test_setup.py`: setup prerequisites and model-load failure. Native GUI startup and duplicate-process rejection were verified on Jim’s Mac. Jim confirmed ordinary dictation pasted and a subsequent Escape-cancelled recording produced no inserted text.

Remaining validation: physical mic unplug/reconnect, native permission revocation, cancelling during a long real inference, other target apps, and measured cancellation latency. Automated scenarios do not substitute for that platform matrix.
