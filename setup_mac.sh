#!/usr/bin/env bash
#
# Gemini AI Assistant — macOS setup and launcher (macOS 12 Monterey or newer).
#
# Verifies Python 3.10+, creates a virtual environment, installs pinned
# dependencies and starts the app. Safe to re-run: existing environments are
# reused and dependencies are only reinstalled when requirements.txt changes.
#
# Usage:  chmod +x setup_mac.sh && ./setup_mac.sh

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

VENV_DIR=".venv"
STAMP_FILE="$VENV_DIR/.requirements.sha"

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
info() { printf '\033[0;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[0;33m[!]\033[0m %s\n' "$1"; }
fail() { printf '\033[0;31m[x] %s\033[0m\n' "$1" >&2; exit 1; }

bold "Gemini AI Assistant — macOS setup"

# --------------------------------------------------------------------------- #
# 1. Locate a Python 3.10+ interpreter
# --------------------------------------------------------------------------- #
# macOS 12 ships Python 3.8 at /usr/bin/python3, which is too old for the SDK,
# so search newest-first and validate the version before accepting a candidate.
PYTHON=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)' 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    detected="$(python3 --version 2>/dev/null || echo 'not found')"
    fail "Python 3.10 or newer is required (detected: $detected).
    Install it with one of:
      brew install python@3.12
      or download from https://www.python.org/downloads/macos/
    Then re-run this script."
fi

info "Using $($PYTHON --version) at $(command -v "$PYTHON")"

# --------------------------------------------------------------------------- #
# 2. Create or reuse the virtual environment
# --------------------------------------------------------------------------- #
if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment in $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR" || fail "Could not create the virtual environment."
else
    info "Reusing existing virtual environment in $VENV_DIR"
fi

# Use the venv's interpreter directly; no need to 'activate' in a script.
VENV_PY="$VENV_DIR/bin/python"
[ -x "$VENV_PY" ] || fail "Virtual environment looks broken. Delete $VENV_DIR and re-run."

# --------------------------------------------------------------------------- #
# 3. Install dependencies (skipped when requirements.txt is unchanged)
# --------------------------------------------------------------------------- #
REQ_HASH="$(shasum -a 256 requirements.txt | awk '{print $1}')"
if [ -f "$STAMP_FILE" ] && [ "$(cat "$STAMP_FILE")" = "$REQ_HASH" ]; then
    info "Dependencies already up to date."
else
    info "Installing dependencies (this can take a minute)…"
    "$VENV_PY" -m pip install --quiet --upgrade pip
    "$VENV_PY" -m pip install --quiet --require-virtualenv -r requirements.txt \
        || fail "Dependency installation failed. Check your network connection and retry."
    printf '%s' "$REQ_HASH" > "$STAMP_FILE"
    info "Dependencies installed."
fi

# --------------------------------------------------------------------------- #
# 4. Check for an API key
# --------------------------------------------------------------------------- #
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp ".env.example" ".env"
        warn "Created .env from .env.example — add your key to it."
    fi
    warn "No GEMINI_API_KEY configured yet."
    warn "Get a free key at https://aistudio.google.com/apikey, then either put it"
    warn "in .env as GEMINI_API_KEY=... or paste it into the app's sidebar."
fi

# --------------------------------------------------------------------------- #
# 5. Launch
# --------------------------------------------------------------------------- #
info "Starting the app — it will open in your browser."
info "Press Ctrl+C to stop."
exec "$VENV_PY" -m streamlit run app.py
