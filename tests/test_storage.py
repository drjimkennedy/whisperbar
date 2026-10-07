import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from storage.history import History
from storage.settings import Settings


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.history = History(self.root)

    def add(self, text='first'):
        return self.history.add(text, {'model_id': 'small', 'duration_ms': 1000, 'transcription_ms': 20})

    def test_restart_restore_and_delivery_status(self):
        identifier = self.add('Unicode café 日本語')
        self.history.update(identifier, 'manual_copy_required')
        records = History(self.root).list()
        self.assertEqual(records[0]['text'], 'Unicode café 日本語')
        self.assertEqual(records[0]['delivery_status'], 'manual_copy_required')
        self.assertEqual(self.history.path.stat().st_mode & 0o777, 0o600)

    def test_retention_newest_twenty(self):
        for n in range(25):
            self.add(str(n))
        rows = self.history.list()
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0]['text'], '24')
        self.assertNotIn('0', [row['text'] for row in rows])

    def test_roundtrip_and_idempotent_import(self):
        self.add()
        path = self.root / 'export.json'
        self.history.export(path)
        other = History(self.root / 'other')
        self.assertEqual(other.import_file(path), 1)
        self.assertEqual(other.list(), self.history.list())
        self.assertEqual(other.import_file(path), 0)

    def test_export_cannot_overwrite_live_data(self):
        self.add()
        settings = Settings(self.root)
        settings.save(history_enabled=True)
        for path in (self.history.path, settings.path):
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                self.history.export(path)
            self.assertEqual(path.read_bytes(), original)

    def test_conflicting_identifier_and_invalid_file_are_atomic(self):
        self.add()
        path = self.root / 'export.json'
        self.history.export(path)
        payload = json.loads(path.read_text())
        payload['transcripts'][0]['text'] = 'different'
        path.write_text(json.dumps(payload))
        before = self.history.list()
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.history.import_file(path)
        self.assertEqual(self.history.list(), before)
        payload['transcripts'][0]['duration_ms'] = -1
        path.write_text(json.dumps(payload))
        with self.assertRaises(ValueError):
            self.history.import_file(path)
        self.assertEqual(self.history.list(), before)

    def test_future_version_is_rejected_without_replacing_data(self):
        self.add()
        with sqlite3.connect(self.history.path) as db:
            db.execute('PRAGMA user_version=99')
        before = self.history.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            History(self.root)
        self.assertEqual(before, self.history.path.read_bytes())

    def test_unversioned_nonempty_database_is_preserved(self):
        root = self.root / 'legacy'
        root.mkdir()
        with sqlite3.connect(root / 'history.sqlite3') as db:
            db.execute('CREATE TABLE old_data (text TEXT)')
            db.execute("INSERT INTO old_data VALUES ('keep me')")
        with self.assertRaisesRegex(ValueError, 'Unversioned'):
            History(root)
        with sqlite3.connect(root / 'history.sqlite3') as db:
            self.assertEqual(db.execute('SELECT text FROM old_data').fetchone()[0], 'keep me')

    def test_delete_one_and_all(self):
        first = self.add('one')
        self.add('two')
        self.history.delete(first)
        self.assertEqual([r['text'] for r in self.history.list()], ['two'])
        self.history.delete()
        self.assertEqual(History(self.root).list(), [])

    def test_settings_roundtrip_and_failed_write_keeps_original(self):
        settings = Settings(self.root)
        settings.save(history_enabled=False, microphone='AirPods', shortcut='ctrl+space')
        self.assertFalse(Settings(self.root).values['history_enabled'])
        self.assertEqual(Settings(self.root).values['microphone'], 'AirPods')
        old = settings.path.read_bytes()
        with patch('storage.settings.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                settings.save(model='large')
        self.assertEqual(settings.path.read_bytes(), old)
        self.assertEqual(settings.values['model'], 'small')

    def test_malformed_settings_are_preserved(self):
        path = self.root / 'settings.json'
        path.write_text('{bad json')
        with self.assertRaises(ValueError):
            Settings(self.root)
        self.assertEqual(path.read_text(), '{bad json')
