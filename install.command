#!/bin/bash
# One-time setup for macOS (Apple Silicon): finds ComfyUI (or installs it), then the Python
# environment, the interface and the app icon. Double-click this file in Finder.
# Everything important also goes to logs/install.log, so a failed setup can be sent to us
# (attach it to an issue on GitHub; the app's "Send a report" adds it to the .zip too).
cd "$(dirname "$0")" || exit 1
RAIZ="$(pwd)"
mkdir -p logs
LOG="$RAIZ/logs/install.log"
echo "==== EasyComfee setup (macOS) $(date) ====" > "$LOG"
sw_vers >> "$LOG" 2>&1
uname -m >> "$LOG"

falhou() {
  echo
  echo "Setup did not finish. Read the message above, fix it, and run install.command again."
  echo
  echo "Still stuck? Open an issue at https://github.com/sintetizacom/easycomfee/issues/new"
  echo "and attach this file: $LOG"
  echo
  read -r -p "Press Enter to close this window..." _
  exit 1
}

# Python 3.11 to 3.13: some pinned packages have no wheels for 3.14 yet.
PY=""
for v in 3.13 3.12 3.11; do
  if command -v "python$v" >/dev/null 2>&1; then PY="python$v"; break; fi
done
if [ -z "$PY" ] && command -v python3 >/dev/null 2>&1 \
   && python3 -c "import sys; sys.exit(not (3,11) <= sys.version_info[:2] <= (3,13))" >/dev/null 2>&1; then
  PY="python3"
fi
if [ -z "$PY" ]; then
  echo "Python 3.11, 3.12 or 3.13 is required."
  echo "Install it from https://www.python.org/downloads/macos/  (or: brew install python@3.12)"
  echo "FAIL: no Python 3.11-3.13" >> "$LOG"
  falhou
fi
echo "Using $PY"
{ echo "Python: $PY"; "$PY" --version; } >> "$LOG" 2>&1

if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js 20+ is required: https://nodejs.org/  (or: brew install node)"
  echo "FAIL: no npm" >> "$LOG"
  falhou
fi
echo "Node: $(node --version 2>/dev/null)" >> "$LOG"

# git is also what ComfyUI is downloaded with, and what the Update button uses.
if ! command -v git >/dev/null 2>&1 || ! xcode-select -p >/dev/null 2>&1; then
  echo "Git is required. macOS will offer to install the Command Line Tools: accept, wait for it"
  echo "to finish, then run install.command again."
  xcode-select --install >/dev/null 2>&1
  echo "FAIL: no git / Command Line Tools" >> "$LOG"
  falhou
fi

# This Mac must have an Apple Silicon chip to run models locally. Intel Macs can still use Comfy Cloud.
if [ "$(uname -m)" != "arm64" ]; then
  echo
  echo "Note: this is an Intel Mac. ComfyUI cannot run models locally here (PyTorch dropped Intel Macs),"
  echo "but EasyComfee works with Comfy Cloud. When asked, choose 'Continue without ComfyUI'."
fi

# EasyComfee runs on top of ComfyUI: find it first (Comfy Desktop, manual install) and save
# its folder in config.json. Without one it offers to install it. detectar_comfy.py also writes
# what it found to logs/install.log.
echo
echo "Looking for ComfyUI on this computer..."
"$PY" backend/detectar_comfy.py || { echo "FAIL: ComfyUI not found or not installed" >> "$LOG"; falhou; }
echo

if [ ! -x backend/.venv/bin/python ]; then
  echo "Creating the Python environment..."
  "$PY" -m venv backend/.venv >> "$LOG" 2>&1 || { echo "FAIL: venv" >> "$LOG"; falhou; }
fi
echo "Installing the Python packages (details in logs/install.log)..."
echo "---- pip ----" >> "$LOG"
backend/.venv/bin/python -m pip install -q --upgrade pip >> "$LOG" 2>&1
backend/.venv/bin/python -m pip install -q -r backend/requirements.txt >> "$LOG" 2>&1 \
  || { echo "FAIL: pip install" >> "$LOG"; falhou; }

echo "Building the interface (details in logs/install.log)..."
echo "---- npm ----" >> "$LOG"
( cd frontend && npm ci --no-audit --no-fund >> "$LOG" 2>&1 && npm run build >> "$LOG" 2>&1 ) \
  || { echo "FAIL: npm" >> "$LOG"; falhou; }

chmod +x ./*.command 2>/dev/null
echo
./criar-atalho.command
echo "OK: setup finished" >> "$LOG"
echo "Done. Open EasyComfee from the icon on your Desktop (or double-click start.command)."
read -r -p "Press Enter to close this window..." _
exit 0
