#!/bin/zsh
set -eu
cd "${0:A:h}/.."
python_bin="${WHISPERBAR_PYTHON:-/usr/bin/python3}"
"$python_bin" -c 'import platform, sys; sys.exit(0 if sys.version_info[:2] == (3, 9) and platform.system() == "Darwin" and platform.machine() == "arm64" else "Baseline setup requires macOS arm64 and Python 3.9; set WHISPERBAR_PYTHON to that interpreter.")'
if [[ -f .venv/pyvenv.cfg ]] && /usr/bin/grep -qi 'include-system-site-packages = true' .venv/pyvenv.cfg; then
  echo "Existing .venv inherits machine packages. Preserve it elsewhere before running setup." >&2
  exit 1
fi
"$python_bin" -m venv .venv
.venv/bin/python -m pip install pip==25.3 setuptools==75.8.0 wheel==0.45.1
.venv/bin/python -m pip install -r requirements/macos-arm64-py39.txt
.venv/bin/python -m pip check
.venv/bin/python scripts/check_environment.py
