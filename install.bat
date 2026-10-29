@echo off
REM One-time setup: finds ComfyUI, then the Python environment, the interface and the shortcut.
setlocal
cd /d "%~dp0"
title EasyComfee setup

REM Python 3.11 to 3.13: some pinned packages have no wheels for 3.14 yet.
set PY=
for %%v in (3.13 3.12 3.11) do if not defined PY (py -%%v --version >nul 2>nul && set PY=py -%%v)
if not defined PY (python -c "import sys; sys.exit(not (3,11) <= sys.version_info[:2] <= (3,13))" >nul 2>nul && set PY=python)
if not defined PY (echo Python 3.11, 3.12 or 3.13 is required: https://www.python.org/downloads/ & goto falhou)
echo Using %PY%
where npm >nul 2>nul || (echo Node.js 20+ is required: https://nodejs.org/ & goto falhou)

REM EasyComfee runs on top of ComfyUI: find it first (Desktop, portable or manual install)
REM and save its folder in config.json. Without ComfyUI, stop here with a link to install it.
echo.
echo Looking for ComfyUI on this computer...
%PY% backend\detectar_comfy.py || goto falhou
echo.

if not exist backend\.venv (
  echo Creating the Python environment...
  %PY% -m venv backend\.venv || goto falhou
)
backend\.venv\Scripts\python.exe -m pip install -q --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt || goto falhou

echo Building the interface...
pushd frontend
call npm ci --no-audit --no-fund || (popd & goto falhou)
call npm run build || (popd & goto falhou)
popd

echo.
call "%~dp0criar-atalho.bat"
echo Done. Start ComfyUI, then open EasyComfee from the shortcut on your Desktop (or run start.bat).
pause
exit /b 0

:falhou
REM A janela espera: com dois cliques no install.bat ela fechava antes de a pessoa ler o erro.
echo.
echo Setup did not finish. Read the message above, fix it, and run install.bat again.
pause
exit /b 1
