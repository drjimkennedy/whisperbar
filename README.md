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

### Python packages

```bash
pip install sounddevice numpy scipy openai-whisper pyperclip pyautogui rumps pynput
```

### System (Homebrew)

```bash
brew install ffmpeg
```

### macOS permissions

Go to **System Settings → Privacy & Security** and grant:

- **Microphone** — audio capture
- **Input Monitoring** — global hotkey from any app
- **Accessibility** — simulated ⌘V paste

> **First-run gotcha:** if you see *"This process is not trusted — input event monitoring will not be possible"*, add Terminal (or `python3`) to both Input Monitoring and Accessibility, quit, and relaunch.

---

## Run it

```bash
python3 app.py
```

The `🎙` icon appears in your menu bar. Press `⌥Space` to start recording, press again to transcribe and paste.

---

## Configuration

Edit `config.py` — three settings, nothing else needs touching:

```python
SHORTCUT_KEY = "option+space"   # change if it conflicts
WHISPER_MODEL = "base"          # tiny / base / small / medium / large
SAMPLE_RATE = 16000             # what Whisper expects — leave this alone
```

`WHISPER_MODEL` is the speed-vs-accuracy dial. `base` is the sweet spot for most people — feels near-instant and accurate enough for normal speech.

---

## Auto-start at login

So the icon is just always there — no terminal, no ritual.

1. Edit `launch.sh` if needed (it uses `$(dirname "$0")` so it works from any location)
2. Create a launchd agent:

```bash
cat > ~/Library/LaunchAgents/com.drjk.whisperbar.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.drjk.whisperbar</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>/path/to/whisperbar/launch.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/whisperbar.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/whisperbar.log</string>
</dict>
</plist>
EOF
```

Replace `/path/to/whisperbar/` with the actual path, then load it:

```bash
launchctl load ~/Library/LaunchAgents/com.drjk.whisperbar.plist
```

---

## The PRD

The full spec that Claude used to build this — architecture, decision log, component breakdown — is at **[drjimkennedy.com/resources/whisperbar](https://drjimkennedy.com/resources/whisperbar)**.

Built with Claude using the 90/500 Method: your judgment writes the spec, Claude's knowledge of code executes it.

---

## Extending it

These were deliberately left out — each slots in without changing the signal chain:

- **Push-to-talk mode** — a config flag branching in `toggle()`
- **Multi-language** — remove the hard-pinned `language="en"` in `config.py`
- **Model picker in the menu** — the menu already shows the model; making it selectable is UI-only
- **Floating waveform window** — an optional second UI surface; the signal chain is untouched

---

MIT License
