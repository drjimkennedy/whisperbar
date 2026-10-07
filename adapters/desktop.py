"""macOS keyboard output and process lock; explicit about paste assurance."""
import fcntl
import logging
import os
from pathlib import Path
import tempfile
import time

import pyautogui
import pyperclip
from ApplicationServices import AXIsProcessTrusted


class InstanceLock:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(tempfile.gettempdir()) / f'whisperbar-{os.getuid()}.lock'
        self.handle = None

    def acquire(self):
        handle = self.path.open('a+')
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return False
        self.handle = handle
        return True

    def close(self):
        if self.handle is not None:
            self.handle.close()
            self.handle = None
        # Never unlink: other processes may already be waiting on this inode.


class Output:
    def __init__(self, held=lambda: False):
        self.held = held
        self.manual_only = False

    def prepare(self, cancelled):
        deadline = time.monotonic() + 2.0
        while self.held() and time.monotonic() < deadline:
            if cancelled.wait(0.02):
                return
        self.manual_only = self.held()
        cancelled.wait(0.15)

    def deliver(self, text):
        pyperclip.copy(text)
        if self.manual_only:
            return 'Copied — release shortcut keys, then paste manually'
        if not AXIsProcessTrusted():
            return 'Copied — enable Accessibility or paste manually'
        # Keep the irreversible commit short; do not use PyAutoGUI's global pause.
        pyautogui.hotkey('command', 'v', _pause=False)
        logging.getLogger('whisperbar').info('Paste requested; insertion is not confirmed')
        return 'Paste requested — use Copy last transcript if needed'
