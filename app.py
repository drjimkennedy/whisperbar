"""WhisperBar desktop shell: UI on the main thread, adapters behind a coordinator."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from queue import Empty, Queue
import sys

import pyperclip
import rumps
import whisper
from pynput import keyboard

from adapters.audio import AudioDevices, Capture, Recognizer
from adapters.desktop import InstanceLock, Output
from core.session import Coordinator, State
from core.shortcut import Chord
from config import SHORTCUT_KEY, SAMPLE_RATE, WHISPER_MODEL, MAX_RECORDING_SECONDS

log = logging.getLogger('whisperbar')


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(threadName)s %(message)s',
        handlers=[RotatingFileHandler(Path(__file__).with_name('whisperbar.log'),
                                      maxBytes=1_000_000, backupCount=3),
                  logging.StreamHandler(sys.stdout)],
    )


def parse_shortcut(shortcut):
    aliases = {'option': 'alt', 'command': 'cmd', 'control': 'ctrl', 'return': 'enter'}
    special = {'alt', 'cmd', 'ctrl', 'shift', 'space', 'tab', 'enter'}
    parts = [aliases.get(x.strip().lower(), x.strip().lower()) for x in shortcut.split('+')]
    if len(parts) < 2 or not set(parts) & {'alt', 'cmd', 'ctrl', 'shift'}:
        raise ValueError('Shortcut must include a modifier and a key')
    if any(not p or (p not in special and len(p) != 1) for p in parts):
        raise ValueError('Unsupported shortcut key')
    return keyboard.HotKey.parse('+'.join(f'<{p}>' if p in special else p for p in parts))


class WhisperBar(rumps.App):
    def __init__(self, model):
        super().__init__('🎙', quit_button=None)
        self.events = Queue()
        self.devices = AudioDevices()
        self.output = Output()
        self.controller = Coordinator(
            lambda: Capture(self.devices, SAMPLE_RATE, MAX_RECORDING_SECONDS),
            Recognizer(model), self.output.prepare, self.output.deliver, self.events.put,
            max_seconds=MAX_RECORDING_SECONDS,
        )
        self.status_item = rumps.MenuItem('Status: ready')
        self.mic_menu = rumps.MenuItem('Microphone')
        self.cancel_item = rumps.MenuItem('Cancel dictation (Esc)', callback=self.cancel)
        self.copy_item = rumps.MenuItem('Copy last transcript', callback=self.copy_last)
        self.menu = [self.status_item, self.cancel_item, self.copy_item, None, self.mic_menu,
                     rumps.MenuItem(f'Shortcut: {SHORTCUT_KEY}'),
                     rumps.MenuItem(f'Model: {WHISPER_MODEL}'), None,
                     rumps.MenuItem('Quit WhisperBar', callback=self.quit_app)]
        self.chord = Chord(parse_shortcut(SHORTCUT_KEY), self.controller.toggle)
        self.output.held = self.chord.held
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.timer = rumps.Timer(self.process_events, 0.05)
        self.rebuild_mics()

    def on_press(self, key):
        try:
            if key == keyboard.Key.esc:
                self.controller.cancel()
            else:
                self.chord.press(self.listener.canonical(key))
        except Exception:
            log.exception('Shortcut handler failed')

    def on_release(self, key):
        self.chord.release(self.listener.canonical(key))

    def process_events(self, _timer):
        # All Cocoa mutations happen here or in menu callbacks on the main thread.
        latest = None
        while True:
            try:
                latest = self.events.get_nowait()
            except Empty:
                break
        if latest is not None and latest.session_id == self.controller.sequence:
            icons = {State.IDLE: '🎙', State.ARMING: '⏳', State.RECORDING: '🔴',
                     State.TRANSCRIBING: '⏳', State.DELIVERING: '⏳',
                     State.CANCELLING: '⏳', State.ERROR: '⚠️', State.CLOSED: '🎙'}
            self.title = icons[latest.state]
            self.status_item.title = f'Status: {latest.message}'

    def rebuild_mics(self):
        # Serialize the check and refresh against shortcut commands. Never reset
        # PortAudio while a capture is arming, recording, or being cleaned up.
        with self.controller.lock:
            if self.controller.restart_required:
                self.status_item.title = 'Status: microphone cleanup failed — restart app'
                return
            if self.controller.state not in (State.IDLE, State.ERROR):
                self.status_item.title = 'Status: finish or cancel before changing microphones'
                return
            for key in list(self.mic_menu.keys()):
                del self.mic_menu[key]
            default = rumps.MenuItem('System default', callback=self.pick_mic)
            default.state = self.devices.selected is None
            self.mic_menu.add(default)
            try:
                for name in self.devices.refresh():
                    item = rumps.MenuItem(name, callback=self.pick_mic)
                    item.state = name == self.devices.selected
                    self.mic_menu.add(item)
            except Exception:
                log.exception('Microphone enumeration failed')
                self.status_item.title = 'Status: microphone unavailable — check permissions'
            self.mic_menu.add(rumps.MenuItem('Refresh device list', callback=lambda _: self.rebuild_mics()))

    def pick_mic(self, sender):
        with self.controller.lock:
            if self.controller.restart_required:
                self.status_item.title = 'Status: microphone cleanup failed — restart app'
                return
            if self.controller.state not in (State.IDLE, State.ERROR):
                self.status_item.title = 'Status: finish or cancel before changing microphones'
                return
            self.devices.selected = None if sender.title == 'System default' else sender.title
            self.rebuild_mics()

    def cancel(self, _sender):
        self.controller.cancel()

    def copy_last(self, _sender):
        with self.controller.lock:
            if self.controller.state not in (State.IDLE, State.ERROR):
                self.status_item.title = 'Status: finish or cancel before copying'
                return
            text = self.controller.last_text
        if not text:
            self.status_item.title = 'Status: no completed transcript in this session'
            return
        try:
            pyperclip.copy(text)
            self.status_item.title = 'Status: last transcript copied — paste manually'
        except Exception:
            log.exception('Copy last transcript failed')
            self.status_item.title = 'Status: clipboard unavailable — retry Copy last transcript'

    def quit_app(self, _sender):
        self.shutdown()
        rumps.quit_application()

    def shutdown(self):
        self.listener.stop()
        self.timer.stop()
        self.controller.close()

    def start(self):
        self.listener.start()
        self.timer.start()
        try:
            self.run()
        finally:
            self.shutdown()


def main():
    configure_logging()
    instance = InstanceLock()
    if not instance.acquire():
        print('WhisperBar is already running. Use its menu bar icon.', file=sys.stderr)
        return 2
    try:
        log.info('Starting WhisperBar with %s', sys.executable)
        try:
            model = whisper.load_model(WHISPER_MODEL)
        except Exception:
            log.exception('Unable to load model')
            print(f"WhisperBar could not load model '{WHISPER_MODEL}'. First use requires "
                  'internet and free disk space. Check whisperbar.log, then retry ./launch.sh.',
                  file=sys.stderr)
            return 1
        app = WhisperBar(model)
        log.info('Model loaded. WhisperBar ready')
        app.start()
        return 0
    finally:
        instance.close()


if __name__ == '__main__':
    sys.exit(main())
