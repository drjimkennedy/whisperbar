"""Platform-independent presentation of lifecycle events and live input levels."""
from dataclasses import dataclass
import math
from core.session import State


class InputActivity:
    """Transient scalar telemetry; ignore brief spikes when detecting low input."""
    LOW_RMS = 0.001  # -60 dBFS: near-silent signal, not a speech/mute classifier.
    ACTIVE_SECONDS = 0.2

    def __init__(self):
        self.latest = (0.0, 0.0, 0.0)
        self.active_since = None

    def observe(self, rms, timestamp):
        rms = rms if math.isfinite(rms) and rms > 0 else 0.0
        last_sound = self.latest[2]
        if rms >= self.LOW_RMS:
            if self.active_since is None or timestamp - self.latest[1] > 0.5:
                self.active_since = timestamp
            if timestamp - self.active_since >= self.ACTIVE_SECONDS:
                last_sound = timestamp
        else:
            self.active_since = None
        self.latest = (rms, timestamp, last_sound)


@dataclass(frozen=True)
class Presentation:
    title: str
    detail: str
    menu_title: str
    visible: bool
    recording: bool = False
    level: float = 0.0


def meter_level(rms):
    """Map -60..0 dBFS to 0..1; this is activity, not a calibrated loudness meter."""
    if not math.isfinite(rms) or rms <= 0:
        return 0.0
    return max(0.0, min(1.0, (20 * math.log10(rms) + 60) / 60))


class Feedback:
    def __init__(self):
        self.state = State.IDLE
        self.message = 'Ready'
        self.changed_at = 0.0
        self.sequence = -1

    def accept(self, event, now):
        if event.session_id < self.sequence:
            return
        if event.session_id != self.sequence or event.state != self.state:
            self.changed_at = now
        self.sequence, self.state, self.message = event.session_id, event.state, event.message

    def render(self, now, shortcut, rms=0.0, sampled_at=0.0, last_sound_at=0.0):
        elapsed = max(0.0, now - self.changed_at)
        if self.state == State.RECORDING:
            seconds = int(elapsed)
            clock = f'{seconds // 60}:{seconds % 60:02d}'
            quiet = elapsed >= 3 and now - max(last_sound_at, self.changed_at) >= 3
            detail = 'Very little audio — check mute or selected microphone' if quiet else f'{shortcut} to finish · Esc to cancel'
            level = meter_level(rms) if now - sampled_at < 0.5 else 0.0
            return Presentation(f'Recording {clock}', detail, f'● {clock}', True, True, level)
        labels = {
            State.ARMING: ('Starting microphone…', 'Wait for Recording before speaking', '… Starting'),
            State.TRANSCRIBING: ('Transcribing…', 'Your audio is processing locally · Esc to cancel', '… Transcribing'),
            State.DELIVERING: ('Inserting text…', 'Checking the original text field', '… Inserting'),
            State.CANCELLING: ('Cancelling…', 'Waiting for processing to finish · text will be discarded', '… Cancelling'),
            State.ERROR: ('Dictation needs attention', self.message, '⚠ WhisperBar'),
            State.IDLE: ('Ready' if self.message == 'Ready' else 'Dictation finished', self.message, '🎙'),
            State.CLOSED: ('Closing', '', '🎙'),
        }
        title, detail, menu = labels[self.state]
        active = self.state in (State.ARMING, State.TRANSCRIBING, State.DELIVERING, State.CANCELLING)
        visible = active or (self.sequence >= 0 and elapsed < (10 if self.state == State.ERROR else 5))
        return Presentation(title, detail, menu, visible and self.state != State.CLOSED)
