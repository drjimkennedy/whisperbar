# WhisperBar — Playbook

System-wide macOS dictation powered by local Whisper. Press a hotkey from any app, speak, press again — transcript pastes back wherever your cursor was.

---

## What It Does

- Menu bar app — lives at `🎙` in the macOS menu bar
- Global hotkey (default: `⌥Space`) works in any app: browser, email, notes, Slack, code editor
- Records audio from your mic, transcribes locally via OpenAI Whisper (no API key, no internet required)
- Auto-pastes result back to wherever focus was

---

## Prerequisites

All already installed on this machine:

| Dependency | Purpose | Installed via |
|---|---|---|
| `openai-whisper` | Transcription engine | pip |
| `sounddevice` | Mic capture | pip |
| `numpy` | Audio array handling | pip |
| `scipy` | WAV file writing | pip |
| `pyperclip` | Clipboard write | pip |
| `pyautogui` | Simulate ⌘V paste | pip |
| `rumps` | macOS menu bar UI | pip |
| `pynput` | Global hotkey listener | pip |
| `ffmpeg` | Audio decode (Whisper dependency) | Homebrew |

---

## Running the App

WhisperBar starts automatically at login (see [Auto-start at Login](#auto-start-at-login) below). The `🎙` icon appears in the menu bar — no terminal needed.

To launch manually from terminal:

```bash
whisperbar
```

(Alias added to `~/.zshrc`. Open a new terminal tab if it's not recognised yet.)

Or directly:

```bash
cd ~/code/whisper
python3 app.py
```

The terminal output confirms the model is loaded:

```
Loading Whisper model 'base'…
Model loaded. Starting WhisperBar…
```

### macOS Permissions (first run only)

Two permissions are required — both must be granted in **System Settings → Privacy & Security**:

| Permission | Section | Purpose |
|---|---|---|
| Microphone | Privacy & Security → Microphone | Audio capture |
| Input Monitoring | Privacy & Security → Input Monitoring | Global hotkey detection |
| Accessibility | Privacy & Security → Accessibility | Simulated ⌘V paste |

> **Note:** The warning `"This process is not trusted! Input event monitoring will not be possible"` means Terminal.app is missing from either Input Monitoring or Accessibility — add it to both and restart.

After granting permissions, quit and relaunch once.

---

## Using It

| Action | What Happens |
|---|---|
| `⌥Space` | Recording starts — icon changes to `🔴` |
| `⌥Space` again | Recording stops — icon changes to `⏳` while transcribing |
| Transcription complete | Text is pasted at cursor — icon returns to `🎙` |

Click the menu bar icon at any time to see current status, shortcut, and model.

---

## Configuration

All settings are in `config.py` — one file, three options:

```python
SHORTCUT_KEY = "option+space"   # change this if ⌥Space conflicts
WHISPER_MODEL = "base"          # tiny / base / small / medium / large
SAMPLE_RATE = 16000             # leave this alone — Whisper expects 16kHz
```

**Shortcut format:** `modifier+key`
- Modifiers: `option`, `cmd`, `ctrl`, `shift`
- Examples: `"cmd+shift+space"`, `"ctrl+option+d"`

**Model tradeoffs:**

| Model | Speed | Accuracy | Use when |
|---|---|---|---|
| `tiny` | ~instant | basic | quick notes, known vocabulary |
| `base` | fast | good | **default — best everyday balance** |
| `small` | 2–3s | better | technical terms, accents |
| `medium` | 5–8s | high | longer dictations where accuracy matters |

Change the model in `config.py`, then restart the app. Model files are cached at `~/.cache/whisper/` — first use of a new model downloads it once.

---

## How It Works

```
⌥Space pressed
    → start_recording() opens sounddevice InputStream at 16kHz
    → audio_callback() appends mic frames to audio_frames[]

⌥Space pressed again
    → recording flag set False, stream closed
    → stop_and_transcribe() runs on a background thread
    → numpy concatenates frames → int16 WAV written to temp file
    → whisper model.transcribe() runs on the WAV
    → text written to clipboard via pyperclip
    → pyautogui simulates ⌘V to paste
    → temp file deleted, icon resets to 🎙
```

The hotkey listener (`pynput`) runs on its own daemon thread. Transcription also runs on a daemon thread so the menu bar UI never blocks.

---

## Troubleshooting

**Hotkey does nothing**
- Check Accessibility permission: System Settings → Privacy & Security → Accessibility → confirm `python3` or `Terminal` is listed and enabled
- Restart the app after granting permission

**Text doesn't paste**
- Accessibility permission is the usual cause — see above
- The 0.15s delay before paste (`time.sleep(0.15)`) gives focus time to return to the previous app; if your machine is slow, bump this to `0.3` in `app.py:72`

**Transcription is slow**
- You're probably on `small` or larger — switch back to `base` in `config.py`
- On Apple Silicon, Whisper runs on CPU by default (`fp16=False` is set intentionally for MPS compatibility)

**`🔴` stays on / app seems stuck**
- A crash during transcription can leave the icon stuck — quit from the menu bar and relaunch
- Check Terminal output for the Python traceback

**`⌥Space` conflict**
- macOS Spotlight sometimes claims `⌥Space` — check System Settings → Keyboard Shortcuts → Spotlight
- Change `SHORTCUT_KEY` in `config.py` to avoid the conflict

---

## Auto-start at Login

WhisperBar is registered as a launchd agent — it starts automatically when you log in, no terminal required.

**Files:**
- `~/code/whisper/launch.sh` — shell wrapper called by launchd
- `~/Library/LaunchAgents/com.drjk.whisperbar.plist` — launchd service definition

**To stop auto-start:**
```bash
launchctl unload ~/Library/LaunchAgents/com.drjk.whisperbar.plist
```

**To re-enable auto-start:**
```bash
launchctl load ~/Library/LaunchAgents/com.drjk.whisperbar.plist
```

**Logs** (if something goes wrong at startup):
```bash
cat ~/code/whisper/whisperbar.log
```

---

## Shell Alias

`whisperbar` is aliased in `~/.zshrc`:

```bash
alias whisperbar="cd ~/code/whisper && python3 app.py"
```

Useful if you ever need to relaunch manually from a terminal (e.g. after a crash or config change).

---

## Files

```
~/code/whisper/
├── app.py              — full app (audio, transcription, menu bar, hotkey)
├── config.py           — shortcut, model, sample rate
├── launch.sh           — shell wrapper for launchd auto-start
├── whisperbar.log      — stdout/stderr from auto-start launches
├── plan.md             — original build plan and decisions log
└── PLAYBOOK.md         — this file

~/Library/LaunchAgents/
└── com.drjk.whisperbar.plist  — launchd service (runs at login)
```
