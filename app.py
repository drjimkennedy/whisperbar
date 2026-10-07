"""WhisperBar desktop shell: UI on the main thread, adapters behind a coordinator."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from queue import Empty, Queue
import sys
import threading
from datetime import datetime

from AppKit import NSOpenPanel, NSSavePanel, NSModalResponseOK, NSApplication

import pyperclip
import rumps
import whisper
from pynput import keyboard

from adapters.audio import AudioDevices, Capture, Recognizer
from adapters.desktop import InstanceLock, Output
from core.session import Coordinator, State
from core.shortcut import Chord
from config import SHORTCUT_KEY, SAMPLE_RATE, WHISPER_MODEL, MAX_RECORDING_SECONDS
from storage.settings import Settings, DEFAULTS, data_directory
from storage.history import History

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
    def __init__(self, model, preferences=None, model_id=WHISPER_MODEL, settings_error=None):
        super().__init__('🎙', quit_button=None)
        self.events = Queue()
        self.preferences = preferences
        self.values = dict(preferences.values) if preferences else {**DEFAULTS, 'history_enabled': False}
        self.model_id = model_id
        self.history = None
        self.history_dirty = threading.Event()
        self.startup_warning = settings_error
        self.onboarding_pending = bool(preferences and preferences.first_run)
        if self.onboarding_pending:
            self.values['history_enabled'] = False
        if self.values['history_enabled'] or (data_directory() / 'history.sqlite3').exists():
            try:
                self.history = History(data_directory())
            except Exception:
                log.exception('History unavailable')
                self.startup_warning = 'History unavailable — new text will remain in memory'

        self.devices = AudioDevices()
        self.devices.selected = self.values['microphone']
        self.output = Output()
        self.controller = Coordinator(
            lambda: Capture(self.devices, SAMPLE_RATE, MAX_RECORDING_SECONDS),
            Recognizer(model), self.output.prepare, self.output.deliver, self.events.put,
            max_seconds=MAX_RECORDING_SECONDS, begin_session=self.output.begin,
            save_transcript=self.save_transcript, update_transcript=self.update_transcript,
            sample_rate=SAMPLE_RATE,
        )
        if self.history and self.values['history_enabled']:
            try:
                records = self.history.list()
                self.controller.last_text = records[0]['text'] if records else None
            except Exception:
                self.startup_warning = 'Unable to read saved history — Copy Last starts empty'
        self.status_item = rumps.MenuItem('Status: ' + (self.startup_warning or 'ready'))
        self.history_menu = rumps.MenuItem('Transcript history')
        self.history_toggle = rumps.MenuItem('Keep last 20 transcripts', callback=self.toggle_history)
        self.history_toggle.state = self.values['history_enabled']
        self.model_menu = rumps.MenuItem('Model (next launch)')
        for name in ['tiny', 'base', 'small', 'medium', 'large']:
            item = rumps.MenuItem(name, callback=self.pick_model)
            item.state = name == self.values['model']
            self.model_menu.add(item)
        self.shortcut_item = rumps.MenuItem(f"Shortcut: {self.values['shortcut']}", callback=self.change_shortcut)
        self.mic_menu = rumps.MenuItem('Microphone')
        self.cancel_item = rumps.MenuItem('Cancel dictation (Esc)', callback=self.cancel)
        self.copy_item = rumps.MenuItem('Copy last transcript', callback=self.copy_last)
        self.menu = [self.status_item, self.cancel_item, self.copy_item, self.history_menu,
                     self.history_toggle, None, self.mic_menu, self.shortcut_item, self.model_menu,
                     rumps.MenuItem(f'Active model: {model_id}'), None,
                     rumps.MenuItem('Quit WhisperBar', callback=self.quit_app)]
        self.chord = Chord(parse_shortcut(self.values['shortcut']), self.controller.toggle)
        self.output.held = lambda: self.chord.held()
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.timer = rumps.Timer(self.process_events, 0.05)
        self.rebuild_mics()
        self.rebuild_history()

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
        if self.onboarding_pending:
            self.onboarding_pending = False
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            keep = rumps.alert('Local transcript history',
                'Keep the last 20 completed transcripts on this Mac for recovery after restart? '
                'Raw audio is never saved. Export and delete controls are in the menu.',
                ok='Keep last 20', cancel='No history') == 1
            try:
                if not self.save_preferences(history_enabled=keep):
                    raise RuntimeError('Settings write failed')
                if keep:
                    self.history = History(data_directory())
                self.history_toggle.state = keep
                self.rebuild_history()
                self.status_item.title = 'Status: ready — local history ' + ('on' if keep else 'off')
            except Exception:
                log.exception('History setup failed')
                self.status_item.title = 'Status: history unavailable — new text stays in memory'
            self.listener.start()
        if self.history_dirty.is_set():
            self.history_dirty.clear()
            self.rebuild_history()
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
            selected = None if sender.title == 'System default' else sender.title
            if self.save_preferences(microphone=selected):
                self.devices.selected = selected
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
            self.status_item.title = 'Status: no completed transcript available'
            return
        try:
            pyperclip.copy(text)
            self.status_item.title = 'Status: last transcript copied — paste manually'
        except Exception:
            log.exception('Copy last transcript failed')
            self.status_item.title = 'Status: clipboard unavailable — retry Copy last transcript'

    def save_preferences(self, **changes):
        try:
            if self.preferences is None:
                raise RuntimeError('Settings unavailable; original file preserved')
            self.preferences.save(**changes)
            self.values = dict(self.preferences.values)
            return True
        except Exception:
            log.exception('Unable to save settings')
            self.status_item.title = 'Status: settings not saved — check storage'
            return False

    def idle(self):
        return self.controller.state in (State.IDLE, State.ERROR)

    def save_transcript(self, text, metadata):
        if not self.values['history_enabled']:
            return None
        if self.history is None:
            raise RuntimeError('History unavailable')
        identifier = self.history.add(text, {**metadata, 'model_id': self.model_id})
        self.history_dirty.set()
        return identifier

    def update_transcript(self, identifier, status):
        self.history.update(identifier, status)
        self.history_dirty.set()

    def rebuild_history(self):
        for key in list(self.history_menu.keys()):
            del self.history_menu[key]
        try:
            records = self.history.list() if self.history and self.values['history_enabled'] else []
            for record in records:
                label = datetime.fromisoformat(record['created_at'].replace('Z', '+00:00')).astimezone().strftime('%d %b %H:%M')
                preview = ' '.join(record['text'].split())[:40]
                item = rumps.MenuItem(f"{label} · {preview} [{record['id'][:6]}]")
                item.add(rumps.MenuItem('Copy transcript', callback=lambda _, r=record: self.copy_record(r)))
                item.add(rumps.MenuItem('Delete transcript…', callback=lambda _, r=record: self.delete_record(r)))
                self.history_menu.add(item)
            if not records:
                self.history_menu.add(rumps.MenuItem('No saved transcripts' if self.values['history_enabled'] else 'History is off'))
            self.history_menu.add(rumps.MenuItem('Export history…', callback=self.export_history))
            self.history_menu.add(rumps.MenuItem('Import history…', callback=self.import_history))
            self.history_menu.add(rumps.MenuItem('Delete all history…', callback=self.delete_all))
        except Exception:
            log.exception('Unable to display history')
            self.status_item.title = 'Status: history unavailable — Copy Last still works'

    def copy_record(self, record):
        with self.controller.lock:
            if not self.idle():
                self.status_item.title = 'Status: finish or cancel before copying'
                return
            try:
                pyperclip.copy(record['text'])
                self.status_item.title = 'Status: transcript copied — paste manually'
            except Exception:
                self.status_item.title = 'Status: unable to copy — retry'

    def toggle_history(self, _sender):
        if not self.idle():
            self.status_item.title = 'Status: finish or cancel before changing history'
            return
        enable = not self.values['history_enabled']
        if not enable and rumps.alert('Turn off history?',
                'This deletes stored transcripts on this Mac. Existing exported files are unchanged. '
                'Copy Last will remain in memory until quit.', ok='Turn off and delete', cancel=True) != 1:
            return
        with self.controller.lock:
            if not self.idle():
                return
            try:
                history = self.history or History(data_directory())
                if not enable:
                    history.delete()
                if not self.save_preferences(history_enabled=enable):
                    return
                self.history = history
                self.history_toggle.state = enable
                self.rebuild_history()
            except Exception:
                log.exception('History preference failed')
                self.status_item.title = 'Status: history change incomplete — check storage; saved files may remain'

    def delete_record(self, record):
        if not self.idle() or rumps.alert('Delete this transcript?', 'Exported copies are unchanged.', ok='Delete', cancel=True) != 1:
            return
        with self.controller.lock:
            if not self.idle():
                return
            try:
                self.history.delete(record['id'])
                if self.controller.last_text == record['text']:
                    self.controller.last_text = None
                self.rebuild_history()
            except Exception:
                self.status_item.title = 'Status: deletion failed — transcript remains'

    def delete_all(self, _sender):
        if not self.idle() or not self.history:
            return
        if rumps.alert('Delete all transcript history?', 'This removes saved transcripts and Copy Last. Exported files are unchanged.', ok='Delete all', cancel=True) != 1:
            return
        with self.controller.lock:
            if not self.idle():
                return
            try:
                self.history.delete()
                self.controller.last_text = None
                self.rebuild_history()
            except Exception:
                self.status_item.title = 'Status: deletion failed — check storage'

    def export_history(self, _sender):
        if not self.history or not self.values['history_enabled']:
            self.status_item.title = 'Status: enable history before exporting'
            return
        panel = NSSavePanel.savePanel()
        panel.setNameFieldStringValue_('whisperbar-history.json')
        if panel.runModal() == NSModalResponseOK:
            try:
                self.history.export(panel.URL().path())
                self.status_item.title = 'Status: history exported'
            except Exception:
                log.exception('History export failed')
                self.status_item.title = 'Status: export failed — original history unchanged'

    def import_history(self, _sender):
        if not self.idle() or not self.history or not self.values['history_enabled']:
            self.status_item.title = 'Status: enable history and finish recording before importing'
            return
        panel = NSOpenPanel.openPanel()
        panel.setAllowsMultipleSelection_(False)
        panel.setCanChooseDirectories_(False)
        panel.setAllowedFileTypes_(['json'])
        if panel.runModal() == NSModalResponseOK:
            with self.controller.lock:
                if not self.idle():
                    return
                try:
                    count = self.history.import_file(panel.URL().path())
                    records = self.history.list()
                    self.controller.last_text = records[0]['text'] if records else self.controller.last_text
                    self.rebuild_history()
                    self.status_item.title = f'Status: imported {count}; newest 20 retained'
                except Exception:
                    log.exception('History import failed')
                    self.status_item.title = 'Status: import rejected — original history unchanged'

    def pick_model(self, sender):
        with self.controller.lock:
            if not self.idle():
                return
            if self.save_preferences(model=sender.title):
                for item in self.model_menu.values():
                    item.state = item.title == sender.title
                self.status_item.title = 'Status: restart to load selected model (first use downloads weights)'

    def change_shortcut(self, _sender):
        if not self.idle():
            return
        response = rumps.Window('Example: option+space or ctrl+shift+d', 'Shortcut',
                                default_text=self.values['shortcut'], ok='Save', cancel=True).run()
        if response.clicked:
            try:
                keys = parse_shortcut(response.text)
                with self.controller.lock:
                    if self.idle() and self.save_preferences(shortcut=response.text):
                        self.chord = Chord(keys, self.controller.toggle)
                        self.shortcut_item.title = f'Shortcut: {response.text}'
            except Exception:
                self.status_item.title = 'Status: invalid shortcut — previous setting kept'

    def quit_app(self, _sender):
        self.shutdown()
        rumps.quit_application()

    def shutdown(self):
        self.listener.stop()
        self.timer.stop()
        self.controller.close()

    def start(self):
        if not self.onboarding_pending:
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
        preferences, settings_error = None, None
        model_id = WHISPER_MODEL
        try:
            preferences = Settings(data_directory())
            parse_shortcut(preferences.values['shortcut'])
            if preferences.values['model'] not in whisper.available_models():
                raise ValueError('Unsupported model preference')
            model_id = preferences.values['model']
        except Exception:
            log.exception('Settings unavailable; using defaults without history')
            preferences = None
            settings_error = 'Settings unavailable — defaults active, history off'
        try:
            model = whisper.load_model(model_id)
        except Exception:
            log.exception('Unable to load model')
            print(f"WhisperBar could not load model '{model_id}'. First use requires "
                  'internet and free disk space. Check whisperbar.log, then retry ./launch.sh.',
                  file=sys.stderr)
            return 1
        app = WhisperBar(model, preferences, model_id, settings_error)
        log.info('Model loaded. WhisperBar ready')
        app.start()
        return 0
    finally:
        instance.close()


if __name__ == '__main__':
    sys.exit(main())
