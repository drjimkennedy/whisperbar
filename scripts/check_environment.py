"""Non-recording startup preflight. Does not import GUI/input hooks or download models."""
import importlib.util
from pathlib import Path
import platform
import shutil
import sys


def main():
    errors = []
    if platform.system() != "Darwin" or platform.machine() != "arm64" or sys.version_info[:2] != (3, 9):
        errors.append("This baseline is validated for macOS arm64 / Python 3.9 only.")
    cfg = Path(sys.prefix) / "pyvenv.cfg"
    if not cfg.exists() or "include-system-site-packages = false" not in cfg.read_text().lower():
        errors.append("Use an isolated environment: run ./scripts/setup.sh.")
    for module, package in [("numpy", "numpy"), ("sounddevice", "sounddevice"),
                            ("scipy", "scipy"), ("whisper", "openai-whisper"),
                            ("pyperclip", "pyperclip"), ("pyautogui", "PyAutoGUI"),
                            ("rumps", "rumps"), ("pynput", "pynput")]:
        if importlib.util.find_spec(module) is None:
            errors.append(f"Missing {package}. Run ./scripts/setup.sh.")
    if shutil.which("ffmpeg") is None:
        errors.append("Missing ffmpeg. Install it with: brew install ffmpeg")
    for error in errors:
        print(f"SETUP: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"Environment ready: Python {platform.python_version()}, {platform.machine()}; ffmpeg found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
