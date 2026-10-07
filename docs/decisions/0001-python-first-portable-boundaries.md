# ADR 0001: Python first, portable contracts from the start

**Date:** 2026-10-07  
**Status:** Direction accepted from user request; detailed architecture proposed.

## Context

WhisperBar is a working personal macOS dictation utility with most logic in one Python file. The intended trajectory is a dependable, potentially affordable paid app. The final commercial stack is undecided. Handy demonstrates a broader Rust/Tauri/React implementation, but it has not been benchmarked against WhisperBar.

## Decision

Develop and evaluate the Python stages in the [PRD](../PRD-robust-whisperbar.md) before selecting the commercial stack. Extract session coordination, recognition, audio, output, storage, and UI boundaries incrementally. Describe contracts with language-neutral data and acceptance fixtures. Use documented, versioned settings/history exports rather than Python-specific serialization.

Documentation and evidence are part of each stage: maintain the development log, setup instructions, contract/schema definitions, measured benchmarks, and migration notes. Keep personal machine paths and installed global packages out of the intended portable build.

## Alternatives deferred

- Full Swift/SwiftUI rewrite: evaluate native integration and delivery through a later spike.
- Rust/Tauri/React rewrite: evaluate Handy’s pattern against actual requirements and maintenance capacity.
- Native shell with separate recognition worker: evaluate if only specific Python boundaries fail.
- Packaged Python as the commercial stack: remains a legitimate outcome if it passes the gates.

## Consequences

Some architecture/documentation effort is added now. A later language change will still require code replacement, but behaviour specifications, datasets, exports, migrations, and acceptance scenarios should survive. Do not introduce remote services or elaborate plugin systems merely to create boundaries.

## Revisit conditions

Evaluate after the Python distribution pilot, or document a hard blocker in a stage experiment. Use measured native reliability, clean installation/update behaviour, latency/resources, support burden, maintenance cost, and user demand. A failed experiment is evidence, not permission for an unplanned rewrite. Record a superseding ADR when the choice changes.

## Evidence

Baseline source commit: `fd4037e21219541d2a8d57d25757e5156c0b0fe9`. User direction dated 2026-10-07. Local Handy snapshot Cargo version: 0.9.8; commit unknown. No current platform policy, pricing research, or cross-stack benchmarks performed.
