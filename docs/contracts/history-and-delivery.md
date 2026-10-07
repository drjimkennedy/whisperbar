# History, settings, and delivery contracts — version 1

Implemented in Stage 2 on 2026-10-07. Native validation results belong in the development log; this contract does not claim universal application compatibility.

## Local data and privacy

Production data lives in `~/Library/Application Support/WhisperBar/`, independent of the checkout. `WHISPERBAR_DATA_DIR` can override it for isolated tests. The app creates its data directory with mode 0700 and new database/settings files with mode 0600. This is ordinary local storage, not application-level encryption.

The first-run choice is shown from the running main-thread UI, after the menu bar is initialized. Keep last 20 enables persistent text history; No history keeps only Copy Last in memory. Raw recordings and transcript contents are not written to diagnostic logs. Cancelled results are not persisted. Completed text is retained in memory and, when enabled, committed to history before delivery is attempted. A storage failure must report that history is unavailable while preserving Copy Last.

Turning history off deletes the app's stored records after an explicit confirmation. Individual deletion and Delete All are also available. Deletion does not erase separately exported files, system backups, or every forensic trace. Imported records are subject to the same newest-20 retention policy.

## SQLite schema and migration

`history.sqlite3` uses SQLite `user_version=1`. The `transcripts` table contains the fields below, excluding `schema_version`, which is added to each exported record. IDs are UUID strings and the primary key. Each operation opens its own connection, uses a transaction and parameterized SQL, then closes the connection.

An empty unversioned database migrates transactionally to version 1. A populated unversioned database or unknown newer schema is rejected without replacing its data. There is no previously shipped populated history schema to migrate. Future migrations must first provide backup/recovery instructions and fixtures covering existing records. Do not invent a conversion for an unknown database.

## JSON interchange

Export envelope: `{"schema_version": 1, "transcripts": [...]}`. Each record contains exactly:

| Field | Meaning |
|---|---|
| `schema_version` | Integer 1 |
| `id` | Canonical UUID, stable across export/import |
| `created_at` | UTC ISO 8601 timestamp ending in Z |
| `text` | Completed Unicode transcript |
| `language` | Recognition language, currently en |
| `engine_id` | Stable recognition adapter identifier, currently openai-whisper |
| `model_id` | Model used for this record, independent of the next-launch preference |
| `duration_ms` | Audio duration in milliseconds, or null if unavailable |
| `transcription_ms` | Measured recognition duration, or null if unavailable |
| `delivery_status` | retained, insert_requested, manual_copy_required, or failed |

Import is limited to 5 MB and 20 records, validates all records before mutation, and rejects unsupported versions, unknown fields, invalid timestamps/types/statuses, duplicate IDs in a file, or conflicting existing IDs. An identical existing record is skipped, making repeat imports idempotent. A conflict rolls back the whole import. Merge retains the newest 20 by timestamp, with ID as a deterministic tie-breaker. Import/export preserves text and IDs and never executes file contents.

Export uses a private temporary file, flush/fsync, and atomic replacement. It cannot replace the app's database or settings file. Existing data remains intact if validation fails. Export filenames and destinations are chosen through a native save panel; exported text is user data, not a diagnostic artifact.

## Preferences

`settings.json` has schema version 1 and the fields `history_enabled`, `microphone` (name or null for system default), `shortcut`, and `model`. Writes use the same atomic file mechanism. Invalid/future settings are not overwritten: startup uses safe defaults with history off and an error status. Microphone and shortcut changes apply when idle; the model choice applies after restart. No-history mode does not restore old text from a database even if a leftover database exists.

## Conservative automatic insertion

The macOS adapter captures an opaque target at the start of a session: process, window, editable field, and selection range. None of these native objects enter SQLite or JSON. At completion, the adapter verifies permission, field capability, and all target components again. Secure, unknown, unsupported, or changed fields require explicit Copy Last.

When supported, `AXSelectedText` inserts into the captured field directly. Automatic delivery never writes or restores the clipboard, so text, images, files, or a newer user copy remain unchanged. Explicit Copy Last or Copy Transcript intentionally replaces the clipboard. This replaces Stage 1's automatic copy-and-Command-V behaviour, including its copy-only permission fallback: under Stage 2, denied permission retains text and asks for explicit Copy Last.

An accepted accessibility setter is reported as **insertion requested**, not confirmed insertion. There remains a narrow native check/set race, but the setter addresses the captured field rather than redirecting a global paste to a different application. No unsupported full-document replacement or simulated Return is used. A full-stack field change or a manual-copy fallback is a supported outcome, not proof that insertion worked.

## Tests and remaining validation

Automated checks cover persistence/restart, newest-20 retention, exact export/import, conflicts, initial schema creation, unknown schema preservation, deletion, atomic settings failures, no-history wiring, cancellation exclusion, storage failure recovery, target identity changes, permission denial, and the native tuple representation of selection ranges. Desktop startup tests ensure the privacy prompt is deferred until the UI timer runs.

Native checks must additionally verify first-run choice, supported-field insertion, Copy Last fallback, changed-focus behaviour, history recovery after a real process restart, and save/open panels. See the development log for which have actually passed. Wider application/OS coverage remains a release gate.
