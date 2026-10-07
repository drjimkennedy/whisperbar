"""macOS keyboard output and process lock; explicit about paste assurance."""
import fcntl
import logging
import os
from pathlib import Path
import tempfile
import time

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
    def __init__(self, held=lambda: False, focus=None):
        from adapters.focus import Focus
        self.held = held
        self.focus = focus or Focus()
        self.target = None
        self.manual_only = False

    def begin(self):
        self.target = self.focus.snapshot()

    def prepare(self, cancelled):
        deadline = time.monotonic() + 2.0
        while self.held() and time.monotonic() < deadline:
            if cancelled.wait(0.02):
                return
        self.manual_only = self.held()
        cancelled.wait(0.15)

    def deliver(self, text):
        from core.session import DeliveryResult
        if self.manual_only:
            return DeliveryResult('manual_copy_required', 'Text ready — release keys and use Copy last transcript')
        if not AXIsProcessTrusted():
            return DeliveryResult('manual_copy_required', 'Text ready — enable Accessibility or use Copy last transcript')
        if self.focus.insert(self.target, text):
            logging.getLogger('whisperbar').info('Insertion requested in verified field; clipboard unchanged')
            return DeliveryResult('insert_requested', 'Insertion requested — clipboard preserved')
        return DeliveryResult('manual_copy_required', 'Target changed or unsupported — use Copy last transcript')
