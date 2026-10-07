# ADR 0003: Portable history and targeted insertion

**Date:** 2026-10-07
**Status:** Implemented; broader native validation pending.

## Decision and reason

Keep up to 20 completed transcripts in SQLite when the user selects persistent history. Keep settings and interchange in strict versioned JSON. Store text before attempting delivery; storage failures preserve in-memory Copy Last and report the failure. Do not persist cancelled results or raw recordings. Keep storage independent of Cocoa, Whisper, and the checkout location. Formats and migration rules are specified in the [data contract](../contracts/history-and-delivery.md).

Capture the native destination at session start and revalidate process, window, field, and selection before setting AXSelectedText. Native objects remain inside the adapter. Automatic insertion never modifies the clipboard. If the target is unsupported or has changed, retain the transcript and offer explicit copying. Report insertion requested because an accepted native setter is not proof of visible output.

## Alternatives and tradeoffs

Clipboard swapping and delayed restoration can race a newer user copy and require preserving multiple native clipboard types. Direct insertion avoids those mutations but supports fewer fields; explicit Copy Last is the compatibility path. A narrowly timed check/set race remains, though the setter addresses the captured field rather than sending a global paste shortcut. Full-document replacement is excluded because it risks unrelated text.

SQLite provides transactional retention/import and stable IDs without a new dependency. JSON exports provide a language-neutral migration route. Version 1 initializes empty databases only; unknown populated schemas remain intact and require an explicit future migration. Settings and history are local private-permission files, not encrypted vaults.

## Validation and rollback

Automated checks cover retention, recovery, imports, schema rejection, privacy wiring, failures, cancellation, and destination identity changes. Jim confirmed TextEdit insertion and saved history after restart, plus earlier Copy Last recovery. First-run native testing found and fixed prompt ordering; selection-range testing found and fixed PyObjC's tuple representation. Native changed-focus, other applications, and save/open panels remain pending.

Export valuable history before rollback and quit the process. Stage 1 ignores these files and preferences and restores its previous clipboard-overwriting delivery. Preserve files for forward recovery; do not rewrite unknown schemas. A later Swift/Rust implementation should retain these formats and acceptance scenarios while replacing platform adapters.
