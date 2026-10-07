"""One session worker; serialized commands and session-scoped completion events.

Adapters own audio/library objects. The coordinator owns lifecycle and cancellation.
Delivery is an irreversible commit: cancellation wins until deliver() begins.
"""
from dataclasses import dataclass
from enum import Enum
import logging
import threading
import time


class State(str, Enum):
    IDLE = 'idle'
    ARMING = 'arming'
    RECORDING = 'recording'
    TRANSCRIBING = 'transcribing'
    DELIVERING = 'delivering'
    CANCELLING = 'cancelling'
    ERROR = 'error'
    CLOSED = 'closed'


@dataclass(frozen=True)
class Event:
    session_id: int
    state: State
    message: str


@dataclass
class Session:
    id: int
    stop: threading.Event
    cancelled: threading.Event
    ready_at: float = 0.0
    delivery_committed: bool = False


class Coordinator:
    def __init__(self, capture_factory, recognize, prepare_delivery, deliver, emit,
                 max_seconds=300, ready_timeout=5, stall_timeout=3):
        self.capture_factory = capture_factory
        self.recognize = recognize
        self.prepare_delivery = prepare_delivery
        self.deliver = deliver
        self.emit = emit  # Must enqueue only; never call a GUI directly.
        self.max_seconds = max_seconds
        self.ready_timeout = ready_timeout
        self.stall_timeout = stall_timeout
        self.lock = threading.RLock()
        self.state = State.IDLE
        self.session = None
        self.worker = None
        self.sequence = 0
        self.closed = False
        self.last_text = None
        self.log = logging.getLogger('whisperbar')

    def _set(self, state, message):
        self.state = state
        self.emit(Event(self.sequence, state, message))

    def toggle(self):
        with self.lock:
            if self.closed:
                return False
            if self.state in (State.IDLE, State.ERROR):
                self.sequence += 1
                session = Session(self.sequence, threading.Event(), threading.Event())
                self.session = session
                self._set(State.ARMING, 'Starting microphone…')
                self.worker = threading.Thread(target=self._run, args=(session,), daemon=True,
                                               name=f'dictation-{session.id}')
                try:
                    self.worker.start()
                except Exception:
                    self.session = None
                    self._set(State.ERROR, 'Unable to start worker — retry')
                    self.log.exception('Worker creation failed')
                    return False
                return True
            if self.state == State.ARMING:
                self.cancel()  # A stop during startup must never leave recording on.
                return True
            if self.state == State.RECORDING:
                self._set(State.TRANSCRIBING, 'Transcribing…')
                self.session.stop.set()
                return True
            self.emit(Event(self.sequence, self.state, 'Busy — wait or cancel'))
            return False

    def cancel(self):
        with self.lock:
            if self.session is None or self.closed or self.session.delivery_committed:
                return False
            self.session.cancelled.set()
            self.session.stop.set()
            self._set(State.CANCELLING, 'Cancelled — waiting for worker to finish')
            return True

    def close(self):
        with self.lock:
            self.closed = True
            if self.session:
                self.session.cancelled.set()
                self.session.stop.set()
            self._set(State.CLOSED, 'Closing')
        if self.worker and self.worker is not threading.current_thread():
            self.worker.join(timeout=2)

    def _ready(self, session):
        with self.lock:
            if self.session is session and self.state == State.ARMING and not session.cancelled.is_set():
                session.ready_at = time.monotonic()
                self._set(State.RECORDING, 'Recording — press shortcut to finish')

    def _finish(self, session, state, message):
        with self.lock:
            if self.session is not session:
                return
            self.session = None
            if not self.closed:
                if session.cancelled.is_set():
                    self._set(State.IDLE, 'Cancelled')
                else:
                    self._set(state, message)

    def _run(self, session):
        capture = None
        terminal_state, message = State.IDLE, 'Ready'
        try:
            capture = self.capture_factory()
            if session.cancelled.is_set():
                return
            started = time.monotonic()
            capture.start(lambda: self._ready(session))
            while not session.stop.wait(0.02):
                now = time.monotonic()
                if not session.ready_at and now - started > self.ready_timeout:
                    raise RuntimeError('No microphone samples — check input and permissions')
                if session.ready_at and now - capture.last_sample_at > self.stall_timeout:
                    raise RuntimeError('Microphone stopped sending audio — reconnect and retry')
                if session.ready_at and now - session.ready_at >= self.max_seconds:
                    with self.lock:
                        if not session.cancelled.is_set():
                            self._set(State.TRANSCRIBING, 'Recording limit reached — transcribing')
                    break
            capture.close()
            if session.cancelled.is_set():
                return
            audio = capture.snapshot()
            text = self.recognize(audio).strip()
            if session.cancelled.is_set():
                return
            if not text:
                raise RuntimeError('No speech detected')
            with self.lock:
                if session.cancelled.is_set():
                    return
                self._set(State.DELIVERING, 'Preparing paste…')
            self.prepare_delivery(session.cancelled)
            with self.lock:
                if session.cancelled.is_set() or self.closed:
                    return
                # Retain before the output attempt so a failed paste can be recovered.
                self.last_text = text
                # This short irreversible operation and cancel() have one defined order.
                session.delivery_committed = True
                message = self.deliver(text)
        except Exception as exc:
            self.log.exception('Session %s failed', session.id)
            terminal_state, message = State.ERROR, str(exc)
        finally:
            if capture is not None:
                try:
                    capture.close()
                except Exception:
                    self.log.exception('Session %s capture cleanup failed', session.id)
                    terminal_state, message = State.ERROR, 'Microphone cleanup failed — restart app'
            self._finish(session, terminal_state, message)
