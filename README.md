# WhisperBar

Free, private, offline Mac dictation with recoverable transcripts.

Press a hotkey from anywhere — browser, email, Slack, Notes — speak, press again. The transcript inserts into supported, unchanged text fields; Copy Last recovers it elsewhere. No API key. No internet. Runs locally via [OpenAI Whisper](https://github.com/openai/whisper).

**[Watch the build video →](https://youtu.be/hyL6X3hODlE)**  
**[Full PRD and walkthrough →](https://drjimkennedy.com/resources/whisperbar)**

---

## How it works

```
⌥Space → Mic → Buffer → Whisper (on-device) → History → Verified text field
```

A menu-bar icon (`🎙`) and a small floating panel show what is happening. Recording includes elapsed time and a live input meter. The panel lets clicks pass through and does not take keyboard focus. One hotkey starts and stops recording; Escape cancels.

---

## Prerequisites

### Reproducible development setup

The current tested baseline is **macOS arm64 with CPython 3.9.6**. This preserves the existing app for measurement; it is not the final customer runtime or a supported-platform promise. Python/runtime modernization remains an explicit follow-up before commercial packaging.

Install `ffmpeg` if needed, then run the setup script:

```bash
brew install ffmpeg
./scripts/setup.sh
```

Setup uses `/usr/bin/python3` by default. If that is not Python 3.9, provide an appropriate interpreter:

```bash
WHISPERBAR_PYTHON=/path/to/python3.9 ./scripts/setup.sh
```

The script creates an isolated `.venv`, installs the complete version-pinned [baseline dependencies](requirements/macos-arm64-py39.txt), and checks dependencies and prerequisites. Downloads need internet access. It refuses an existing environment that inherits machine packages; preserve that environment elsewhere before setup. Never copy a virtual environment between machines—recreate it.

`requirements.txt` documents direct dependencies. The platform-specific file also pins transitive dependencies; neither file is a hash-verified artifact lock. Installed system tools and model files remain separate prerequisites.

### macOS permissions

Go to **System Settings → Privacy & Security** and grant:

- **Microphone** — audio capture
- **Input Monitoring** — global hotkey from any app
- **Accessibility** — verify the destination and insert text

> **First-run gotcha:** if you see *"This process is not trusted — input event monitoring will not be possible"*, add Terminal (or `python3`) to both Input Monitoring and Accessibility, quit, and relaunch.

---

## Run it

```bash
./launch.sh
```

The `🎙` icon appears in your menu bar. Press `⌥Space` to start recording, press again to transcribe and request a paste. Press **Escape** or choose **Cancel dictation** to cancel before delivery begins. If insertion fails, use **Copy last transcript** from the menu. On first run, choose **Keep last 20** or **No history**. Keeping history restores transcripts after restart; No history keeps Copy Last only until quit. Automatic insertion leaves your clipboard untouched; explicit Copy Last replaces it.

Recording starts visibly when audio samples arrive and stops automatically after five minutes. Repeated key events and processing-time presses cannot create overlapping sessions. A second launch exits without opening a duplicate app. See the [session contracts](docs/contracts/session-lifecycle.md) for behaviour and test coverage.

The menu appears before model loading finishes. Loading and processing have visible feedback; a model failure leaves **Retry model loading** available in the menu. **Setup and permissions…** reports the selected input and access status. Three seconds of very low input shows a mute/microphone hint; this is an activity check, not a diagnosis. See the [feedback contract](docs/contracts/feedback-and-startup.md) for timing and native verification requirements.

---

## Configuration

Choose microphone, shortcut, and next-launch model in the menu; these preferences persist. `config.py` supplies defaults and capture settings:

```python
SHORTCUT_KEY = "option+space"   # change if it conflicts
WHISPER_MODEL = "small"         # tiny / base / small / medium / large
SAMPLE_RATE = 16000             # what Whisper expects — leave this alone
```

`WHISPER_MODEL` controls the speed/accuracy tradeoff. The current configuration is `small`; compare models on your own recordings before changing it.

---

## Transcript history

The history menu offers Copy, Delete, Delete All, and portable JSON export/import. Disabling history asks to delete stored records. Local settings and SQLite text history live in `~/Library/Application Support/WhisperBar/`; raw recordings are not retained. Exports contain transcript text and remain wherever you save them. See the [history and delivery contract](docs/contracts/history-and-delivery.md) for formats, privacy, and compatibility limits.

## Auto-start at login

So the icon is just always there — no terminal, no ritual.

1. Complete setup first. `launch.sh` resolves its own location and runs the project’s isolated `.venv`.
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

The next product phase is defined in the [robust-app PRD](docs/PRD-robust-whisperbar.md): staged Python upgrades, acceptance gates, and a later commercial technology-stack decision. Track implementation evidence in the [development log](docs/DEVELOPMENT-LOG.md) and architecture choices in the [decision record](docs/decisions/0001-python-first-portable-boundaries.md).

The full spec that Claude used to build this — architecture, decision log, component breakdown — is at **[drjimkennedy.com/resources/whisperbar](https://drjimkennedy.com/resources/whisperbar)**.

Built with Claude using the 90/500 Method: your judgment writes the spec, Claude's knowledge of code executes it.

---

## Extending it

These were deliberately left out — each slots in without changing the signal chain:

- **Push-to-talk mode** — a config flag branching in `toggle()`
- **Multi-language** — remove the hard-pinned `language="en"` in `config.py`
- **Waveform visualization** — the current floating panel has an input level bar rather than a waveform

---

MIT License
