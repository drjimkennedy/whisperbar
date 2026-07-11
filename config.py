# WhisperBar configuration

# Global shortcut — change here if Option+Space conflicts with anything
# Format: modifier+key  (modifiers: option, cmd, ctrl, shift)
# Examples: "option+space", "cmd+shift+space", "ctrl+option+d"
SHORTCUT_KEY = "option+space"

# Whisper model — tradeoff between speed and accuracy
# Options: "tiny", "base", "small", "medium", "large"
# "base" is a good default — fast enough to feel instant, accurate enough for normal speech
WHISPER_MODEL = "base"

# Audio sample rate — 16000 is what Whisper expects natively
SAMPLE_RATE = 16000

# Use the macOS default input when None. Set this to an exact device name from
# System Settings → Sound → Input if the default microphone is not the one used.
# Example: "Judge Jumbo Microphone"
INPUT_DEVICE = "MacBook Pro Microphone"

# Bound memory use if recording is accidentally left running.
MAX_RECORDING_SECONDS = 300

# Gives macOS time to settle the foreground app after the global hotkey.
PASTE_DELAY_SECONDS = 0.35

# Treat recordings quieter than this as a microphone/input problem.
SILENCE_THRESHOLD = 0.001
