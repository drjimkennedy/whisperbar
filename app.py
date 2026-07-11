"""WhisperBar — system-wide macOS dictation from the menu bar."""

from __future__ import annotations

import fcntl
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from queue import Empty, Queue
import sys
import threading
import time

import pyautogui
import pyperclip
import rumps
import sounddevice as sd
import whisper
from pynput import keyboard

from config import (
    INPUT_DEVICE,
    MAX_RECORDING_SECONDS,
    PASTE_DELAY_SECONDS,
    SAMPLE_RATE,
    SILENCE_THRESHOLD,
    SHORTCUT_KEY,
    WHISPER_MODEL,
)
from whisperbar_core import AppState, DictationController


APP_DIR = Path(__file__).resolve().parent
LOG_PATH = APP_DIR / "whisperbar.log"
UI_POLL_SECONDS = 0.1


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("whisperbar")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(message)s")
        )
        logger.addHandler(handler)
    return logger


LOGGER = configure_logging()


def acquire_single_instance():
    """Hold a per-user lock for the lifetime of the process."""
    lock_path = Path("/tmp") / f"whisperbar-{os.getuid()}.lock"
    lock_file = lock_path.open("w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        return None
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    return lock_file


def pynput_shortcut(shortcut: str) -> str:
    """Translate the documented shortcut syntax to pynput's HotKey syntax."""
    aliases = {
        "option": "alt",
        "command": "cmd",
        "control": "ctrl",
        "return": "enter",
    }
    special = {"alt", "cmd", "ctrl", "shift", "space", "tab", "enter"}
    converted = []
    for raw_part in shortcut.split("+"):
        part = aliases.get(raw_part.strip().lower(), raw_part.strip().lower())
        if not part:
            raise ValueError("shortcut contains an empty key")
        if part in special:
            converted.append(f"<{part}>")
        elif len(part) == 1:
            converted.append(part)
        else:
            raise ValueError(f"unsupported shortcut key: {raw_part!r}")
    if len(converted) < 2:
        raise ValueError("shortcut must include a modifier and a key")
    return "+".join(converted)


def paste_text(text: str) -> None:
    LOGGER.info("Copying transcript to clipboard (characters=%d)", len(text))
    pyperclip.copy(text)
    time.sleep(PASTE_DELAY_SECONDS)
    LOGGER.info("Sending Command-V to the foreground application")
    pyautogui.hotkey("command", "v")
    LOGGER.info("Paste shortcut sent")


class WhisperBar(rumps.App):
    def __init__(self) -> None:
        super().__init__("⏳", quit_button="Quit WhisperBar")
        self.menu = [
            rumps.MenuItem("Status: starting…"),
            rumps.MenuItem("Last error: none"),
            None,
            rumps.MenuItem(f"Shortcut: {SHORTCUT_KEY}"),
            rumps.MenuItem(f"Model: {WHISPER_MODEL}"),
            rumps.MenuItem(f"Input: {INPUT_DEVICE or 'system default'}"),
        ]
        self._status_item = self.menu["Status: starting…"]
        self._error_item = self.menu["Last error: none"]
        self._events = Queue()
        self._controller = None
        self._controller_lock = threading.Lock()
        self._listener = None
        self._timer = rumps.Timer(self._process_events, UI_POLL_SECONDS)
        self._timer.start()

    def enqueue_state(self, state: AppState, message=None) -> None:
        self._events.put(("state", state, message))

    def enqueue_ready(self, controller, listener) -> None:
        self._events.put(("ready", controller, listener))

    def request_toggle(self) -> None:
        with self._controller_lock:
            controller = self._controller
        if controller is None:
            LOGGER.info("Ignoring hotkey while application is starting")
            return
        controller.toggle()

    def _process_events(self, _timer) -> None:
        while True:
            try:
                event = self._events.get_nowait()
            except Empty:
                break
            kind = event[0]
            if kind == "ready":
                with self._controller_lock:
                    self._controller = event[1]
                    self._listener = event[2]
                self._render_state(AppState.IDLE)
            else:
                self._render_state(event[1], event[2])

    def _render_state(self, state: AppState, message=None) -> None:
        appearances = {
            AppState.STARTING: ("⏳", "Status: starting…"),
            AppState.IDLE: ("🎙", "Status: idle"),
            AppState.RECORDING: ("🔴", "Status: recording…"),
            AppState.TRANSCRIBING: ("⏳", "Status: transcribing…"),
            AppState.ERROR: ("⚠️", "Status: error"),
        }
        self.title, self._status_item.title = appearances[state]
        if message:
            self._error_item.title = f"Last error: {message}"

    def shutdown(self) -> None:
        with self._controller_lock:
            controller = self._controller
        if controller is not None:
            controller.close()
        if self._listener is not None:
            self._listener.stop()


def start_hotkey_listener(app: WhisperBar):
    combination = pynput_shortcut(SHORTCUT_KEY)
    parsed = keyboard.HotKey.parse(combination)
    hotkey = keyboard.HotKey(parsed, app.request_toggle)
    listener = keyboard.Listener(
        on_press=lambda key: hotkey.press(listener.canonical(key)),
        on_release=lambda key: hotkey.release(listener.canonical(key)),
    )
    listener.start()
    return listener


def initialize(app: WhisperBar) -> None:
    try:
        try:
            sd.check_input_settings(
                device=INPUT_DEVICE, samplerate=SAMPLE_RATE, channels=1
            )
            selected_input = sd.query_devices(INPUT_DEVICE, "input")["name"]
            LOGGER.info("Using input device: %s", selected_input)
        except Exception as exc:
            LOGGER.warning("Microphone preflight failed: %s", exc)
            app.enqueue_state(AppState.ERROR, f"Microphone check failed: {exc}")

        LOGGER.info("Loading Whisper model %s", WHISPER_MODEL)
        model = whisper.load_model(WHISPER_MODEL)
        controller = DictationController(
            audio_module=sd,
            model=model,
            paste_text=paste_text,
            state_callback=app.enqueue_state,
            sample_rate=SAMPLE_RATE,
            max_recording_seconds=MAX_RECORDING_SECONDS,
            input_device=INPUT_DEVICE,
            silence_threshold=SILENCE_THRESHOLD,
            logger=LOGGER,
        )
        listener = start_hotkey_listener(app)
        app.enqueue_ready(controller, listener)
        LOGGER.info("WhisperBar ready")
    except Exception as exc:
        LOGGER.exception("WhisperBar initialization failed")
        app.enqueue_state(AppState.ERROR, f"Startup failed: {exc}")


def main() -> int:
    instance_lock = acquire_single_instance()
    if instance_lock is None:
        LOGGER.error("Another WhisperBar instance is already running")
        return 2

    LOGGER.info("Starting WhisperBar with %s", sys.executable)
    app = WhisperBar()
    initializer = threading.Thread(
        target=initialize, args=(app,), name="whisperbar-initialize", daemon=True
    )
    initializer.start()
    try:
        app.run()
    finally:
        app.shutdown()
        instance_lock.close()
        LOGGER.info("WhisperBar stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
