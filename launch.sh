#!/bin/zsh
set -eu
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  echo "WhisperBar environment missing. Run ./scripts/setup.sh first." >&2
  exit 1
fi
.venv/bin/python scripts/check_environment.py
exec .venv/bin/python -u app.py
