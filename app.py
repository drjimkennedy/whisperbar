"""
WhisperBar — system-wide dictation via menu bar.

Shortcut: Option+Space (configurable via SHORTCUT in config.py)
- Press once to start recording (icon turns red)
- Press again to stop, transcribe, and paste
"""

import threading
import tempfile
import os
import time
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import whisper
import pyperclip
import pyautogui
import rumps
from pynput import keyboard

from config import SHORTCUT_KEY, SAMPLE_RATE, WHISPER_MODEL

# ── State ─────────────────────────────────────────────────────────────────────

recording = False
audio_frames = []
stream = None
model = None

# ── Audio ──────────────────────────────────────────────────────────────────────

def audio_callback(indata, frames, time_info, status):
    if recording:
        audio_frames.append(indata.copy())


def start_recording():
    global recording, audio_frames, stream
    audio_frames = []
    recording = True
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=audio_callback)
    stream.start()


def stop_and_transcribe(app_ref):
    global recording, stream
    recording = False
    if stream:
        stream.stop()
        stream.close()
        stream = None

    if not audio_frames:
        app_ref.set_idle()
        return

    app_ref.title = "⏳"

    audio_data = np.concatenate(audio_frames, axis=0)
    audio_data = (audio_data * 32767).astype(np.int16)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name
    wav.write(tmp_path, SAMPLE_RATE, audio_data)

    try:
        result = model.transcribe(tmp_path, language="en", fp16=False)
        text = result["text"].strip()
        if text:
            pyperclip.copy(text)
            time.sleep(0.15)  # brief pause so focus returns to original app
            pyautogui.hotkey("command", "v")
    finally:
        os.unlink(tmp_path)
        app_ref.set_idle()


# ── Menu bar app ───────────────────────────────────────────────────────────────

class WhisperBar(rumps.App):
    def __init__(self):
        super().__init__("🎙", quit_button="Quit WhisperBar")
        self.menu = [
            rumps.MenuItem("Status: idle"),
            None,  # separator
            rumps.MenuItem(f"Shortcut: {SHORTCUT_KEY}"),
            rumps.MenuItem(f"Model: {WHISPER_MODEL}"),
        ]
        self._status_item = self.menu["Status: idle"]

    def set_idle(self):
        self.title = "🎙"
        self._status_item.title = "Status: idle"

    def set_recording(self):
        self.title = "🔴"
        self._status_item.title = "Status: recording…"

    def toggle(self):
        global recording
        if not recording:
            self.set_recording()
            start_recording()
        else:
            threading.Thread(target=stop_and_transcribe, args=(self,), daemon=True).start()


# ── Hotkey listener ────────────────────────────────────────────────────────────

def parse_shortcut(shortcut_str):
    """Parse 'option+space' into pynput Key combination."""
    parts = [p.strip().lower() for p in shortcut_str.split("+")]
    modifiers = set()
    key = None
    modifier_map = {
        "option": keyboard.Key.alt,
        "alt": keyboard.Key.alt,
        "cmd": keyboard.Key.cmd,
        "command": keyboard.Key.cmd,
        "ctrl": keyboard.Key.ctrl,
        "control": keyboard.Key.ctrl,
        "shift": keyboard.Key.shift,
    }
    key_map = {
        "space": keyboard.Key.space,
        "tab": keyboard.Key.tab,
        "return": keyboard.Key.enter,
        "enter": keyboard.Key.enter,
    }
    for part in parts:
        if part in modifier_map:
            modifiers.add(modifier_map[part])
        elif part in key_map:
            key = key_map[part]
        else:
            key = keyboard.KeyCode.from_char(part)
    return modifiers, key


def start_hotkey_listener(app_ref):
    required_modifiers, trigger_key = parse_shortcut(SHORTCUT_KEY)
    pressed = set()

    def on_press(k):
        pressed.add(k)
        if trigger_key in pressed and required_modifiers.issubset(pressed):
            app_ref.toggle()

    def on_release(k):
        pressed.discard(k)

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Loading Whisper model '{WHISPER_MODEL}'…")
    model = whisper.load_model(WHISPER_MODEL)
    print("Model loaded. Starting WhisperBar…")

    app = WhisperBar()

    hotkey_thread = threading.Thread(target=start_hotkey_listener, args=(app,), daemon=True)
    hotkey_thread.start()

    app.run()
