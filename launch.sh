#!/bin/zsh
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

if [[ -x "$SCRIPT_DIR/.venv/bin/python3" ]]; then
  exec "$SCRIPT_DIR/.venv/bin/python3" -u app.py
fi

echo "WARNING: .venv is missing; falling back to /usr/bin/python3" >&2
exec /usr/bin/python3 -u app.py
