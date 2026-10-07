import unittest
from core.feedback import Feedback, meter_level, InputActivity
from core.session import Event, State


class FeedbackTests(unittest.TestCase):
    def test_recording_clock_stays_stable_on_busy_event(self):
        feedback = Feedback()
        feedback.accept(Event(1, State.RECORDING, 'Recording'), 10)
        feedback.accept(Event(1, State.RECORDING, 'Busy'), 12)
        result = feedback.render(15, 'option+space', 0.1, 15, 15)
        self.assertEqual(result.title, 'Recording 0:05')
        self.assertGreater(result.level, 0)
        self.assertTrue(result.recording)

    def test_quiet_input_warning_and_stale_meter(self):
        feedback = Feedback()
        feedback.accept(Event(2, State.RECORDING, 'Recording'), 20)
        self.assertNotIn('Very little audio', feedback.render(22, 'shortcut').detail)
        self.assertIn('Very little audio', feedback.render(24, 'shortcut').detail)
        result = feedback.render(25, 'shortcut', 0.2, 22, 24)
        self.assertEqual(result.level, 0)
        self.assertNotIn('Very little audio', result.detail)

    def test_low_background_and_brief_spikes_do_not_suppress_hint(self):
        activity = InputActivity()
        feedback = Feedback()
        feedback.accept(Event(1, State.RECORDING, 'Recording'), 10)
        for step in range(41):
            # Low background with one short tap per second.
            activity.observe(0.03 if step % 10 == 5 else 0.0002, 10 + step / 10)
        self.assertIn('Very little audio', feedback.render(14, 'shortcut', *activity.latest).detail)
        for step in range(4):
            activity.observe(0.04, 14.1 + step / 10)
        self.assertNotIn('Very little audio', feedback.render(14.4, 'shortcut', *activity.latest).detail)

    def test_quieter_sustained_audio_is_not_treated_as_missing_input(self):
        activity = InputActivity()
        feedback = Feedback()
        feedback.accept(Event(1, State.RECORDING, 'Recording'), 10)
        for step in range(41):
            activity.observe(0.004, 10 + step / 10)
        self.assertNotIn('Very little audio', feedback.render(14, 'shortcut', *activity.latest).detail)

    def test_sample_gap_cannot_be_counted_as_sustained_activity(self):
        activity = InputActivity()
        activity.observe(0.04, 1)
        activity.observe(0.04, 3)
        self.assertEqual(activity.latest[2], 0)

    def test_stale_session_ignored_and_completion_expires(self):
        feedback = Feedback()
        feedback.accept(Event(2, State.TRANSCRIBING, 'Transcribing'), 10)
        feedback.accept(Event(1, State.IDLE, 'old'), 11)
        self.assertEqual(feedback.state, State.TRANSCRIBING)
        feedback.accept(Event(2, State.IDLE, 'Cancelled'), 12)
        self.assertTrue(feedback.render(13, 'shortcut').visible)
        self.assertFalse(feedback.render(18, 'shortcut').visible)

    def test_invalid_meter_values_are_safe(self):
        for value in (float('nan'), float('inf'), -1, 0):
            self.assertEqual(meter_level(value), 0)
        self.assertEqual(meter_level(2), 1)
