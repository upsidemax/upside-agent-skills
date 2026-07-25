#!/usr/bin/env bash
# One-shot dependency installer. Idempotent.

set -euo pipefail

PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "error: $PYTHON not found. Install Python 3.9+ first." >&2
    exit 1
fi

echo "→ Installing Python dependencies via pip…"
"$PYTHON" -m pip install --user --upgrade \
    eth-account \
    eth-keys \
    eth-utils \
    'eth-hash[pycryptodome]' \
    requests \
    websocket-client

echo
echo "✓ Dependencies installed. Try:"
echo "    $PYTHON examples/quick_start.py"
