#!/usr/bin/env bash
# LEGACY STARTER: not the approved default setup path. Do not run automatically.
# The working environment is env; this script creates a separate .venv.
# See reference_files/SAFE_ROOM_PROJECT8_IMPLEMENTATION_PLAN.md before use.
# Installs system prerequisites and creates an isolated Python environment.
# Run on Ubuntu 22.04 x86_64 from the starter folder, not on an NVIDIA Jetson.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "Expected x86_64 laptop; found $(uname -m). Review setup before proceeding." >&2
  exit 1
fi
if ! python3 -c 'import sys; assert sys.version_info[:2] == (3,10)' 2>/dev/null; then
  echo "This starter kit expects python3=3.10.x. Found: $(python3 --version 2>&1)" >&2
  exit 1
fi

sudo apt update
sudo apt install -y python3-venv python3-pip libgl1 libglib2.0-0 v4l-utils
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
python tools/check_setup.py

echo
echo 'Python environment created. In a new terminal: source .venv/bin/activate'
echo 'For serial access, if needed: sudo usermod -aG dialout "$USER"'
echo 'Log out and back in after changing dialout group membership.'
echo 'Arduino IDE AppImage (if needed) additionally requires: sudo apt install libfuse2'
