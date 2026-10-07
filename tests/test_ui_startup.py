"""Desktop-shell wiring tests with no Cocoa windows or input hooks."""
import importlib.util
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch
from storage.settings import Settings
from storage.history import History


class Menu(dict):
    def __init__(self, title, callback=None):
        super().__init__()
        self.title, self.callback, self.state = title, callback, False
    def add(self, item):
        self[item.title] = item


class Shell:
    def __init__(self, *_args, **_kwargs):
        pass


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        fake_rumps = types.SimpleNamespace(App=Shell, MenuItem=Menu, Timer=MagicMock(),
                                           alert=MagicMock(return_value=1))
        spec = importlib.util.spec_from_file_location('app_shell_test', Path(__file__).resolve().parents[1] / 'app.py')
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict('sys.modules', {'rumps': fake_rumps, 'whisper': MagicMock()}):
            spec.loader.exec_module(self.module)
        self.fake_rumps = fake_rumps
        self.patches = [patch.object(self.module, 'data_directory', return_value=self.path),
                        patch.object(self.module.AudioDevices, 'refresh', return_value=[]),
                        patch.object(self.module.keyboard, 'Listener'),
                        patch.object(self.module, 'NSApplication')]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_first_prompt_is_deferred_until_ui_timer(self):
        preferences = Settings(self.path)
        app = self.module.WhisperBar(MagicMock(), preferences)
        self.fake_rumps.alert.assert_not_called()
        self.assertTrue(app.onboarding_pending)
        app.listener.start.assert_not_called()
        app.process_events(None)
        self.fake_rumps.alert.assert_called_once()
        app.listener.start.assert_called_once()
        self.assertTrue(Settings(self.path).values['history_enabled'])
        self.assertIsNotNone(app.history)
        app.process_events(None)
        self.fake_rumps.alert.assert_called_once()

    def test_no_history_mode_never_saves_or_restores_old_text(self):
        preferences = Settings(self.path)
        preferences.save(history_enabled=False)
        old = History(self.path)
        old.add('old text', {'model_id': 'small'})
        app = self.module.WhisperBar(MagicMock(), preferences)
        self.assertIsNone(app.controller.last_text)
        self.assertIsNone(app.save_transcript('new text', {}))
        self.assertEqual(len(old.list()), 1)
        self.fake_rumps.alert.assert_not_called()

    def test_restart_restores_last_and_preferences(self):
        preferences = Settings(self.path)
        preferences.save(microphone='Test mic', shortcut='ctrl+space')
        history = History(self.path)
        history.add('recover me', {'model_id': 'small'})
        app = self.module.WhisperBar(MagicMock(), Settings(self.path))
        self.assertEqual(app.controller.last_text, 'recover me')
        self.assertEqual(app.devices.selected, 'Test mic')
        self.assertEqual(app.values['shortcut'], 'ctrl+space')
