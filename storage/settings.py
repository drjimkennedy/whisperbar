"""JSON preferences; atomic writes and explicit schema validation."""
import json
import os
from pathlib import Path
import tempfile

from config import SHORTCUT_KEY, WHISPER_MODEL

DEFAULTS = {'schema_version': 1, 'history_enabled': True, 'microphone': None,
            'shortcut': SHORTCUT_KEY, 'model': WHISPER_MODEL}


def data_directory():
    override = os.environ.get('WHISPERBAR_DATA_DIR')
    return Path(override).expanduser() if override else Path.home() / 'Library/Application Support/WhisperBar'


def private_directory(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def atomic_json(path, data):
    private_directory(path.parent)
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{path.name}-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate(data):
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data.get('schema_version') != 1:
        raise ValueError('Unsupported settings version; original file was not changed')
    if set(data) != set(DEFAULTS):
        raise ValueError('Unexpected or missing settings fields')
    if type(data['history_enabled']) is not bool:
        raise ValueError('Invalid history preference')
    if data['microphone'] is not None and not isinstance(data['microphone'], str):
        raise ValueError('Invalid microphone preference')
    for key in ('shortcut', 'model'):
        if not isinstance(data[key], str) or not data[key] or len(data[key]) > 200:
            raise ValueError(f'Invalid {key} preference')
    return dict(data)


class Settings:
    def __init__(self, directory):
        self.path = Path(directory) / 'settings.json'
        self.first_run = not self.path.exists()
        self.values = validate(json.loads(self.path.read_text())) if self.path.exists() else dict(DEFAULTS)

    def save(self, **changes):
        updated = validate({**self.values, **changes})
        atomic_json(self.path, updated)
        self.values = updated
        self.first_run = False
