# WhisperBar development log

Record implemented changes separately from proposals. Keep entries newest first. Use repository-relative links and commit identifiers when available.

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
