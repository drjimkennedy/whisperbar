"""
WhisperBar — system-wide dictation via menu bar.

Shortcut: Option+Space (configurable via SHORTCUT in config.py)
- Press once to start recording (icon turns red)
- Press again to stop, transcribe, and paste
"""

import threading
import tempfile
import logging
import os
import sys
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

# ── Logging ────────────────────────────────────────────────────────────────────
# Every recording logs device, sample count, and peak level to whisperbar.log —
# when dictation fails, the log says whether the mic was silent, missing, or
# the transcript was empty, without needing to reproduce the problem.

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisperbar.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(threadName)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("whisperbar")

# ── State ─────────────────────────────────────────────────────────────────────

recording = False
audio_frames = []
stream = None
model = None
selected_mic = None  # None = follow system default; else a device name string

# ── Audio ──────────────────────────────────────────────────────────────────────

def audio_callback(indata, frames, time_info, status):
    if recording:
        audio_frames.append(indata.copy())


def reset_portaudio():
    """Force PortAudio to re-enumerate audio devices.

    macOS gotcha: PortAudio caches the device list when it first initializes.
    If the default input changes after startup (AirPods/Continuity mic connect,
    another app grabs the mic), the stale handle either records pure silence
    (peak=0.0) or fails to open with PaErrorCode -9986. Terminating and
    re-initializing right before each recording picks up the current device.
    """
    sd._terminate()
    sd._initialize()


def list_input_devices():
    """Names of all devices that can record, in PortAudio order (deduped)."""
    names = []
    for dev in sd.query_devices():
        if dev["max_input_channels"] > 0 and dev["name"] not in names:
            names.append(dev["name"])
    return names


def resolve_input_device():
    """Return (device_index_or_None, device_name) honoring the mic picker.

    None index = PortAudio default (follows the macOS system input). If the
    picked mic isn't currently connected (AirPods in the case, iPhone out of
    range), fall back to the system default rather than failing.
    """
    if selected_mic:
        for idx, dev in enumerate(sd.query_devices()):
            if dev["name"] == selected_mic and dev["max_input_channels"] > 0:
                return idx, dev["name"]
        log.warning("Picked mic '%s' not connected — using system default", selected_mic)
    return None, sd.query_devices(kind="input")["name"]


def start_recording(app_ref):
    global recording, audio_frames, stream
    audio_frames = []
    try:
        reset_portaudio()
        device_index, device_name = resolve_input_device()
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, callback=audio_callback, device=device_index
        )
        stream.start()
        recording = True
        app_ref.set_recording(device_name)
        log.info("Recording started (device=%s)", device_name)
    except Exception:
        recording = False
        stream = None
        log.exception("Unable to start recording")
        app_ref.set_error("mic unavailable — try again")


def stop_and_transcribe(app_ref):
    global recording, stream
    recording = False
    if stream:
        try:
            stream.stop()
            stream.close()
        except Exception:
            log.exception("Error closing stream")
        stream = None

    if not audio_frames:
        log.warning("Recording stopped with no audio frames")
        app_ref.set_idle()
        return

    app_ref.title = "⏳"

    audio_data = np.concatenate(audio_frames, axis=0)
    peak = float(np.abs(audio_data).max())
    log.info("Recording stopped (samples=%d, peak=%.5f)", len(audio_data), peak)

    # Silence guard: if the mic delivered only zeros (stale device), tell the
    # user instead of silently pasting nothing.
    if peak < 0.001:
        log.warning("Recording was silent — input device likely stale or muted")
        app_ref.set_error("no audio captured — check mic")
        return

    # Clip before int16 conversion — peaks above 1.0 (seen on AirPods) would
    # otherwise wrap around and inject loud negative spikes into the WAV
    audio_data = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name
    wav.write(tmp_path, SAMPLE_RATE, audio_data)

    try:
        t0 = time.time()
        result = model.transcribe(tmp_path, language="en", fp16=False)
        text = result["text"].strip()
        if text:
            log.info("Transcribed %d chars in %.1fs — pasting", len(text), time.time() - t0)
            pyperclip.copy(text)
            time.sleep(0.15)  # brief pause so focus returns to original app
            pyautogui.hotkey("command", "v")
            app_ref.set_idle()
        else:
            log.warning("Transcription completed with no detected speech")
            app_ref.set_error("no speech detected")
    except Exception:
        log.exception("Transcription failed")
        app_ref.set_error("transcription failed")
    finally:
        os.unlink(tmp_path)


# ── Menu bar app ───────────────────────────────────────────────────────────────

class WhisperBar(rumps.App):
    def __init__(self):
        super().__init__("🎙", quit_button="Quit WhisperBar")
        self._mic_menu = rumps.MenuItem("Microphone")
        self.menu = [
            rumps.MenuItem("Status: idle"),
            None,  # separator
            self._mic_menu,
            rumps.MenuItem(f"Shortcut: {SHORTCUT_KEY}"),
            rumps.MenuItem(f"Model: {WHISPER_MODEL}"),
        ]
        self._status_item = self.menu["Status: idle"]
        self.rebuild_mic_menu()

    def rebuild_mic_menu(self):
        """Populate the Microphone submenu with currently available inputs.

        AirPods / iPhone Continuity mics only appear here while connected —
        the Refresh item re-scans after connecting them.
        """
        for key in list(self._mic_menu.keys()):
            del self._mic_menu[key]

        default_item = rumps.MenuItem("System default", callback=self.pick_mic)
        default_item.state = selected_mic is None
        self._mic_menu.add(default_item)

        try:
            reset_portaudio()
            for name in list_input_devices():
                item = rumps.MenuItem(name, callback=self.pick_mic)
                item.state = name == selected_mic
                self._mic_menu.add(item)
        except Exception:
            log.exception("Could not list input devices")

        self._mic_menu.add(rumps.MenuItem("Refresh device list", callback=self.refresh_mics))

    def pick_mic(self, sender):
        global selected_mic
        selected_mic = None if sender.title == "System default" else sender.title
        for item in self._mic_menu.values():
            if item.title != "Refresh device list":
                item.state = item.title == sender.title
        log.info("Microphone picked: %s", sender.title)

    def refresh_mics(self, _sender):
        self.rebuild_mic_menu()
        log.info("Device list refreshed: %s", ", ".join(list_input_devices()))

    def set_idle(self):
        self.title = "🎙"
        self._status_item.title = "Status: idle"

    def set_recording(self, device_name=None):
        self.title = "🔴"
        suffix = f" ({device_name})" if device_name else ""
        self._status_item.title = f"Status: recording…{suffix}"

    def set_error(self, message):
        """Show an error in the menu bar briefly, then return to idle."""
        self.title = "⚠️"
        self._status_item.title = f"Status: {message}"
        threading.Timer(3.0, self.set_idle).start()

    def toggle(self):
        global recording
        if not recording:
            # start_recording sets the icon itself — only after the stream
            # actually opens, so a failed mic never shows a false red icon
            threading.Thread(target=start_recording, args=(self,), daemon=True).start()
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
        try:
            pressed.add(k)
            if trigger_key in pressed and required_modifiers.issubset(pressed):
                app_ref.toggle()
        except Exception:
            # never let an error kill the listener — the hotkey must survive
            log.exception("Hotkey handler error")

    def on_release(k):
        pressed.discard(k)

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Starting WhisperBar with %s", sys.executable)
    try:
        device_name = sd.query_devices(kind="input")["name"]
        log.info("Using input device: %s", device_name)
    except Exception:
        log.exception("No input device found at startup")
    log.info("Loading Whisper model '%s'…", WHISPER_MODEL)
    try:
        model = whisper.load_model(WHISPER_MODEL)
    except Exception:
        log.exception("Unable to load Whisper model '%s'", WHISPER_MODEL)
        print(
            f"WhisperBar could not load model '{WHISPER_MODEL}'. "
            "First use requires an internet connection and free disk space. "
            "Check the connection, available storage, and whisperbar.log, then retry ./launch.sh.",
            file=sys.stderr,
        )
        sys.exit(1)
    log.info("Model loaded. WhisperBar ready")

    app = WhisperBar()

    hotkey_thread = threading.Thread(target=start_hotkey_listener, args=(app,), daemon=True)
    hotkey_thread.start()

    app.run()
