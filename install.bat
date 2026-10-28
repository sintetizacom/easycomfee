@echo off
REM One-time setup: Python environment, interface build and config.json.
setlocal
cd /d "%~dp0"

REM Python 3.11 to 3.13: some pinned packages have no wheels for 3.14 yet.
set PY=
for %%v in (3.13 3.12 3.11) do if not defined PY (py -%%v --version >nul 2>nul && set PY=py -%%v)
if not defined PY (python -c "import sys; sys.exit(not (3,11) <= sys.version_info[:2] <= (3,13))" >nul 2>nul && set PY=python)
if not defined PY (echo Python 3.11, 3.12 or 3.13 is required: https://www.python.org/downloads/ & exit /b 1)
echo Using %PY%
where npm >nul 2>nul || (echo Node.js 20+ is required: https://nodejs.org/ & exit /b 1)

if not exist backend\.venv (
  echo Creating the Python environment...
  %PY% -m venv backend\.venv || exit /b 1
)
backend\.venv\Scripts\python.exe -m pip install -q --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt || exit /b 1

echo Building the interface...
pushd frontend
call npm ci --no-audit --no-fund || exit /b 1
call npm run build || exit /b 1
popd

if not exist config.json (
  copy config.example.json config.json >nul
  echo.
  echo Created config.json. Open it and set "comfy_dir" to your ComfyUI folder.
)
echo.
call "%~dp0criar-atalho.bat"
echo Done. Open EasyComfee from the shortcut on your Desktop (or run start.bat)
