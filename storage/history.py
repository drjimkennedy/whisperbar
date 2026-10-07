"""Bounded SQLite history and strict versioned JSON interchange.

No recordings, native handles, or machine paths are stored. SQL always uses parameters.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import uuid

from storage.settings import private_directory, atomic_json

FIELDS = ('id', 'created_at', 'text', 'language', 'engine_id', 'model_id',
          'duration_ms', 'transcription_ms', 'delivery_status')
STATUSES = {'retained', 'insert_requested', 'manual_copy_required', 'failed'}
LIMIT = 20
MAX_FILE_BYTES = 5_000_000


def validate_record(record):
    if not isinstance(record, dict) or set(record) != set(FIELDS) | {'schema_version'}:
        raise ValueError('Unexpected or missing transcript fields')
    if type(record['schema_version']) is not int or record['schema_version'] != 1:
        raise ValueError('Unsupported transcript version')
    if not isinstance(record['id'], str) or str(uuid.UUID(record['id'])) != record['id']:
        raise ValueError('Invalid transcript identifier')
    stamp = record['created_at']
    if not isinstance(stamp, str) or not stamp.endswith('Z'):
        raise ValueError('Timestamp must use UTC with Z suffix')
    parsed = datetime.fromisoformat(stamp[:-1] + '+00:00')
    if parsed.tzinfo is None:
        raise ValueError('Timestamp must contain a time and UTC zone')
    for field in ('text', 'language', 'engine_id', 'model_id', 'delivery_status'):
        if not isinstance(record[field], str) or not record[field] or len(record[field]) > 100_000:
            raise ValueError(f'Invalid transcript {field}')
    for field in ('duration_ms', 'transcription_ms'):
        if record[field] is not None and (type(record[field]) is not int or not 0 <= record[field] <= 86_400_000):
            raise ValueError(f'Invalid transcript {field}')
    if record['delivery_status'] not in STATUSES:
        raise ValueError('Unknown delivery status')
    return {field: record[field] for field in FIELDS}


class History:
    def __init__(self, directory):
        self.path = private_directory(Path(directory)) / 'history.sqlite3'
        # First creation is private even before SQLite opens it.
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise ValueError('Unsupported history database version; file left intact')
            if version == 0:
                tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if tables:
                    raise ValueError('Unversioned history contains data; back up before migration')
                db.execute('''CREATE TABLE transcripts (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, text TEXT NOT NULL,
                    language TEXT NOT NULL, engine_id TEXT NOT NULL, model_id TEXT NOT NULL,
                    duration_ms INTEGER, transcription_ms INTEGER, delivery_status TEXT NOT NULL)''')
                db.execute('PRAGMA user_version=1')
            columns = tuple(row[1] for row in db.execute('PRAGMA table_info(transcripts)'))
            if columns != FIELDS:
                raise ValueError('Unexpected history schema; file left intact')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=2)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def trim(db):
        db.execute('DELETE FROM transcripts WHERE id NOT IN (SELECT id FROM transcripts ORDER BY created_at DESC, id DESC LIMIT ?)', (LIMIT,))

    def add(self, text, metadata):
        record = dict(schema_version=1, id=str(uuid.uuid4()),
                      created_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                      text=text, language='en', engine_id='openai-whisper',
                      model_id=metadata['model_id'], duration_ms=metadata.get('duration_ms'),
                      transcription_ms=metadata.get('transcription_ms'), delivery_status='retained')
        row = validate_record(record)
        with self.connect() as db:
            db.execute('INSERT INTO transcripts VALUES (?,?,?,?,?,?,?,?,?)', tuple(row[k] for k in FIELDS))
            self.trim(db)
        return record['id']

    def update(self, identifier, status):
        if status not in STATUSES:
            raise ValueError('Unknown delivery status')
        with self.connect() as db:
            db.execute('UPDATE transcripts SET delivery_status=? WHERE id=?', (status, identifier))

    def list(self):
        with self.connect() as db:
            return [dict(schema_version=1, **dict(row)) for row in db.execute('SELECT * FROM transcripts ORDER BY created_at DESC, id DESC')]

    def delete(self, identifier=None):
        with self.connect() as db:
            db.execute('PRAGMA secure_delete=ON')
            if identifier is None:
                db.execute('DELETE FROM transcripts')
            else:
                db.execute('DELETE FROM transcripts WHERE id=?', (identifier,))
        # Logical deletion is promised, not forensic erasure or backup removal.

    def export(self, path):
        if Path(path).resolve() in {self.path.resolve(), (self.path.parent / 'settings.json').resolve()}:
            raise ValueError('Export cannot replace the app database or settings')
        atomic_json(Path(path), {'schema_version': 1, 'transcripts': self.list()})

    def import_file(self, path):
        path = Path(path)
        with path.open('rb') as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise ValueError('Import exceeds 5 MB')
        document = json.loads(data)
        if not isinstance(document, dict) or set(document) != {'schema_version', 'transcripts'} or type(document['schema_version']) is not int or document['schema_version'] != 1:
            raise ValueError('Unsupported history export')
        if not isinstance(document['transcripts'], list) or len(document['transcripts']) > LIMIT:
            raise ValueError('Import must contain at most 20 transcripts')
        rows = [validate_record(record) for record in document['transcripts']]
        if len({row['id'] for row in rows}) != len(rows):
            raise ValueError('Duplicate identifiers in import')
        added = 0
        with self.connect() as db:
            for row in rows:
                existing = db.execute('SELECT * FROM transcripts WHERE id=?', (row['id'],)).fetchone()
                if existing:
                    if dict(existing) != row:
                        raise ValueError('Conflicting transcript identifier; import rolled back')
                    continue
                db.execute('INSERT INTO transcripts VALUES (?,?,?,?,?,?,?,?,?)', tuple(row[k] for k in FIELDS))
                added += 1
            self.trim(db)
        return added
