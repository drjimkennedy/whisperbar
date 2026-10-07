# ADR 0002: One session worker and an explicit output commit

**Date:** 2026-10-07
**Status:** Implemented; extended native validation pending.

## Decision and reason

Replace shared global recording/audio state with a coordinator and one session-scoped worker. Reserve lifecycle state synchronously before launching work. Keep native capture, recognition, desktop output, and UI behind separate modules. Use immutable queued events and main-thread UI updates. The older hardening archive informed locking, log rotation, single-instance behaviour, and direct float-array inference; its controller did not meet the new readiness/cancellation requirements and was not merged wholesale.

Cancellation invalidates output but does not pretend to interrupt a non-interruptible inference library. Block subsequent sessions until that worker drains. Define delivery as a short irreversible commit serialized with cancellation. Wait for shortcut release before reaching that commit. This avoids duplicate/late pastes while acknowledging that a paste already underway cannot be revoked.

Pass clipped float32 audio directly to Whisper rather than writing temporary WAV files. Preserve the existing silence guard and device recovery. Retain one completed transcript in memory immediately before output as a small early slice of Stage 2, providing recovery from paste failure without introducing persistent storage yet.

## Alternatives and tradeoffs

A command-queue event loop or a separate recognition process could provide stricter scheduling or forceful cancellation but adds complexity. The present lock-and-worker design is sufficient for serialized sessions; revisit if real native calls hang or measured cancellation responsiveness fails. Holding the lock through output makes ordering explicit but means cancellation cannot interrupt a stalled clipboard call.

Copy Last and shortcut-release waiting improve usability but do not establish the cause of the earlier missed paste. Focus validation, clipboard preservation, and history remain Stage 2. Native acceptance checks beyond the smoke test remain open.

## Migration and rollback

Carry the [session contracts](../contracts/session-lifecycle.md) and acceptance scenarios into any replacement stack. Map library-specific buffers at adapter boundaries. No persistent user-data schema changed. To roll back, quit this process before launching the previous revision; the old revision has no instance-lock protection. Do not run old and new instances concurrently.
