"""Detect a complete chord once until the chord is released."""
import threading


class Chord:
    def __init__(self, required, trigger):
        self.required = set(required)
        self.trigger = trigger
        self.pressed = set()
        self.latched = False
        self.lock = threading.Lock()

    def press(self, key):
        with self.lock:
            self.pressed.add(key)
            fire = self.required <= self.pressed and not self.latched
            if fire:
                self.latched = True
        if fire:
            self.trigger()

    def release(self, key):
        with self.lock:
            self.pressed.discard(key)
            if not self.required <= self.pressed:
                self.latched = False

    def held(self):
        with self.lock:
            return bool(self.required & self.pressed)
