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

REM ComfyUI (PyTorch) needs the Microsoft Visual C++ Redistributable. Without it ComfyUI
REM installs fine but stops at start with "WinError 126 ... c10.dll" (seen on 29/10/2026).
set VCDIR=%SystemRoot%\System32
if exist "%VCDIR%\msvcp140.dll" if exist "%VCDIR%\vcruntime140_1.dll" goto vc_ok
echo.
echo ComfyUI needs the Microsoft Visual C++ Redistributable, which is missing on this PC.
where winget >nul 2>nul || goto vc_link
echo Installing it now (Windows may ask for permission)...
winget install --id Microsoft.VCRedist.2015+.x64 -e --accept-source-agreements --accept-package-agreements
if exist "%VCDIR%\msvcp140.dll" if exist "%VCDIR%\vcruntime140_1.dll" goto vc_ok
:vc_link
echo Install it from Microsoft: https://aka.ms/vs/17/release/vc_redist.x64.exe
echo then run install.bat again.
goto falhou
:vc_ok

REM Smart App Control (Windows 11) blocks ComfyUI's PyTorch/CUDA files ("An Application Control
REM policy has blocked this file") and has no exceptions. Warn now; setup can go on.
set SAC=
for /f "tokens=3" %%e in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy" /v VerifiedAndReputablePolicyState 2^>nul ^| find "0x"') do set SAC=%%e
if not "%SAC%"=="0x1" goto sac_ok
echo.
echo WARNING: Windows Smart App Control is ON on this PC.
echo It blocks the files ComfyUI needs to run locally, and it has no exceptions.
echo To turn it off: Windows Security ^> App ^& browser control ^> Smart App Control settings ^> Off.
echo Windows does not let you turn it back on without reinstalling; Microsoft Defender keeps working.
echo Setup will continue. Turn it off before starting EasyComfee.
pause
:sac_ok

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
