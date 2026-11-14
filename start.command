#!/bin/bash
# Starts the studio and opens it in the browser (macOS). Keep this window open while you use it.
# "start.command noopen" (used by Update) does not open another tab.
cd "$(dirname "$0")" || exit 1
if [ ! -x backend/.venv/bin/python ]; then echo "Run install.command first."; exit 1; fi
PY=backend/.venv/bin/python
PORT="$($PY -c "import sys; sys.path.insert(0, 'backend'); import config; print(config.APP_PORTA)")"
# ComfyUI installed by EasyComfee itself starts with it (see backend/iniciar_comfy.py).
$PY backend/iniciar_comfy.py
# The browser opens only when the server answers (waits up to 2 minutes, in the background).
if [ "$1" != "noopen" ]; then
  nohup $PY backend/abrir_navegador.py "$PORT" >/dev/null 2>&1 &
fi
cd backend || exit 1
exec .venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port "$PORT" --no-access-log --log-level warning --no-use-colors
