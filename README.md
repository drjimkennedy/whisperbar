# WhisperBar

Free, private, offline Mac dictation that works in any app.

Press a hotkey from anywhere — browser, email, Slack, Notes — speak, press again. The transcript pastes back wherever your cursor was. No API key. No internet. Runs locally via [OpenAI Whisper](https://github.com/openai/whisper).

**[Watch the build video →](https://youtu.be/hyL6X3hODlE)**  
**[Full PRD and walkthrough →](https://drjimkennedy.com/resources/whisperbar)**

---

## How it works

```
⌥Space → Mic → Buffer → Whisper (on-device) → Clipboard → ⌘V → Cursor
```

A menu-bar icon (`🎙`) shows you what's happening. One hotkey starts and stops recording. That's the entire interface.

---

## Prerequisites

### Python environment

```bash
/usr/bin/python3 -m venv .venv
.venv/bin/python3 -m pip install --upgrade pip
.venv/bin/python3 -m pip install -r requirements.txt
```

### Optional Whisper command-line tooling

```bash
brew install ffmpeg
```

WhisperBar passes in-memory audio directly to Whisper and does not require
`ffmpeg` for normal dictation. It is useful if you also use Whisper's CLI with
audio files.

### macOS permissions

Go to **System Settings → Privacy & Security** and grant:

- **Microphone** — audio capture
- **Input Monitoring** — global hotkey from any app
- **Accessibility** — simulated ⌘V paste

> **First-run gotcha:** if you see *"This process is not trusted — input event monitoring will not be possible"*, add Terminal (or `python3`) to both Input Monitoring and Accessibility, quit, and relaunch.

---

## Run it

```bash
./launch.sh
```

The `🎙` icon appears in your menu bar. Press `⌥Space` to start recording, press again to transcribe and paste.

---

## Configuration

Edit `config.py` — seven settings, nothing else needs touching:

```python
SHORTCUT_KEY = "option+space"   # change if it conflicts
WHISPER_MODEL = "base"          # tiny / base / small / medium / large
SAMPLE_RATE = 16000             # what Whisper expects — leave this alone
INPUT_DEVICE = None              # use macOS default, or an exact input-device name
MAX_RECORDING_SECONDS = 300     # prevents unbounded memory use
PASTE_DELAY_SECONDS = 0.35      # wait before simulated ⌘V
SILENCE_THRESHOLD = 0.001       # flags a silent/wrong microphone
```

`WHISPER_MODEL` is the speed-vs-accuracy dial. `base` is the sweet spot for most people — feels near-instant and accurate enough for normal speech.

---

## Auto-start at login

So the icon is just always there — no terminal, no ritual.

The repository includes a crash-recovering launchd definition at
`launchd/com.drjk.whisperbar.plist`. It restarts unexpected failures but still
allows a normal **Quit WhisperBar** to remain stopped.

1. If this repository is somewhere other than `/Users/jimkennedy/code/whisper`,
   update the paths in the plist.
2. Install and start it:

```bash
cp launchd/com.drjk.whisperbar.plist ~/Library/LaunchAgents/
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.drjk.whisperbar.plist 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.drjk.whisperbar.plist
```

Logs are written to `whisperbar.log` and automatically rotated.

---

## The PRD

The full spec that Claude used to build this — architecture, decision log, component breakdown — is at **[drjimkennedy.com/resources/whisperbar](https://drjimkennedy.com/resources/whisperbar)**.

Built with Claude using the 90/500 Method: your judgment writes the spec, Claude's knowledge of code executes it.

---

## Extending it

The application now uses guarded `starting`, `idle`, `recording`,
`transcribing`, and `error` states. Repeated hotkeys cannot start overlapping
recordings or Whisper jobs. Audio is passed directly to Whisper as a NumPy
array, so transcription does not depend on a temporary WAV file or `ffmpeg`.

Run the test suite with:

```bash
.venv/bin/python3 -m unittest discover -s tests -v
```

Possible extensions:

- **Push-to-talk mode** — a config flag branching in `toggle()`
- **Multi-language** — remove the hard-pinned `language="en"` in `config.py`
- **Model picker in the menu** — the menu already shows the model; making it selectable is UI-only
- **Floating waveform window** — an optional second UI surface; the signal chain is untouched

---

MIT License
