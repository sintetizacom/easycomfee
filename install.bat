@echo off
REM One-time setup: finds ComfyUI, then the Python environment, the interface and the shortcut.
REM Everything important also goes to logs\install.log, so a failed setup can be sent to us
REM (attach it to an issue on GitHub; the app's "Send a report" adds it to the .zip too).
setlocal
cd /d "%~dp0"
title EasyComfee setup
if not exist logs mkdir logs
set "LOG=%~dp0logs\install.log"
echo ==== EasyComfee setup %date% %time% ====> "%LOG%"
ver>> "%LOG%"

REM Python 3.11 to 3.13: some pinned packages have no wheels for 3.14 yet.
set PY=
for %%v in (3.13 3.12 3.11) do if not defined PY (py -%%v --version >nul 2>nul && set PY=py -%%v)
if not defined PY (python -c "import sys; sys.exit(not (3,11) <= sys.version_info[:2] <= (3,13))" >nul 2>nul && set PY=python)
if not defined PY (echo Python 3.11, 3.12 or 3.13 is required: https://www.python.org/downloads/ & echo FAIL: no Python 3.11-3.13>> "%LOG%" & goto falhou)
echo Using %PY%
echo Python: %PY% >> "%LOG%"
%PY% --version>> "%LOG%" 2>&1
where npm >nul 2>nul || (echo Node.js 20+ is required: https://nodejs.org/ & echo FAIL: no npm>> "%LOG%" & goto falhou)
for /f "delims=" %%n in ('node --version 2^>nul') do echo Node: %%n >> "%LOG%"

REM ComfyUI (PyTorch) needs the Microsoft Visual C++ Redistributable. Without it ComfyUI
REM installs fine but stops at start with "WinError 126 ... c10.dll" (seen on 29/10/2026).
set VCDIR=%SystemRoot%\System32
if exist "%VCDIR%\msvcp140.dll" if exist "%VCDIR%\vcruntime140_1.dll" goto vc_ok
echo.
echo ComfyUI needs the Microsoft Visual C++ Redistributable, which is missing on this PC.
echo Visual C++ Redistributable missing>> "%LOG%"
where winget >nul 2>nul || goto vc_link
echo Installing it now (Windows may ask for permission)...
winget install --id Microsoft.VCRedist.2015+.x64 -e --accept-source-agreements --accept-package-agreements
if exist "%VCDIR%\msvcp140.dll" if exist "%VCDIR%\vcruntime140_1.dll" goto vc_ok
:vc_link
echo Install it from Microsoft: https://aka.ms/vs/17/release/vc_redist.x64.exe
echo then run install.bat again.
echo FAIL: Visual C++ Redistributable not installed>> "%LOG%"
goto falhou
:vc_ok
echo Visual C++ Redistributable: ok>> "%LOG%"

REM Smart App Control (Windows 11) may block ComfyUI's PyTorch/CUDA files ("An Application Control
REM policy has blocked this file"), often only at first: just a note, setup goes on.
set SAC=
for /f "tokens=3" %%e in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy" /v VerifiedAndReputablePolicyState 2^>nul ^| find "0x"') do set SAC=%%e
echo Smart App Control state: %SAC% >> "%LOG%"
if not "%SAC%"=="0x1" goto sac_ok
echo.
echo Note: Windows Smart App Control is on. It may block ComfyUI's files at first
echo ("An Application Control policy has blocked this file"). This often clears up by itself
echo after a while or a restart. If ComfyUI keeps failing, see "Smart App Control" in the README.
:sac_ok

REM EasyComfee runs on top of ComfyUI: find it first (Desktop, portable or manual install)
REM and save its folder in config.json. Without ComfyUI, stop here with a link to install it.
REM detectar_comfy.py also writes what it found to logs\install.log.
echo.
echo Looking for ComfyUI on this computer...
%PY% backend\detectar_comfy.py || (echo FAIL: ComfyUI not found or not installed>> "%LOG%" & goto falhou)
echo.

if not exist backend\.venv (
  echo Creating the Python environment...
  %PY% -m venv backend\.venv >> "%LOG%" 2>&1 || goto falhou
)
echo Installing the Python packages (details in logs\install.log)...
echo ---- pip ---->> "%LOG%"
backend\.venv\Scripts\python.exe -m pip install -q --upgrade pip >> "%LOG%" 2>&1
backend\.venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt >> "%LOG%" 2>&1 || (echo FAIL: pip install>> "%LOG%" & goto falhou)

echo Building the interface (details in logs\install.log)...
echo ---- npm ---->> "%LOG%"
pushd frontend
call npm ci --no-audit --no-fund >> "%LOG%" 2>&1 || (popd & echo FAIL: npm ci>> "%LOG%" & goto falhou)
call npm run build >> "%LOG%" 2>&1 || (popd & echo FAIL: npm run build>> "%LOG%" & goto falhou)
popd

echo.
call "%~dp0criar-atalho.bat"
echo OK: setup finished>> "%LOG%"
echo Done. Open EasyComfee from the shortcut on your Desktop (or run start.bat).
pause
exit /b 0

:falhou
REM A janela espera: com dois cliques no install.bat ela fechava antes de a pessoa ler o erro.
echo.
echo Setup did not finish. Read the message above, fix it, and run install.bat again.
echo.
echo Still stuck? Open an issue at https://github.com/sintetizacom/easycomfee/issues/new
echo and attach this file: %~dp0logs\install.log
pause
exit /b 1
