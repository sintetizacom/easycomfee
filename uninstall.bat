@echo off
REM Removes EasyComfee: closes it, deletes its shortcuts and this folder.
REM backend\desinstalar.ps1 shows what goes and asks first; this file deletes the folder at the end.
setlocal
cd /d "%~dp0"
title EasyComfee uninstall
set "RAIZ=%~dp0"
set "RAIZ=%RAIZ:~0,-1%"
REM Pasta de desenvolvimento (tem as notas privadas): nunca se apaga sozinha.
if exist AGENTS.md (echo This is the development folder: uninstall is disabled here. & pause & exit /b 1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%RAIZ%\backend\desinstalar.ps1" -Raiz "%RAIZ%"
if errorlevel 1 (pause & exit /b 1)
echo.
echo Deleting %RAIZ% ...
REM "(goto)" sai deste .bat antes de apagar a pasta: o resto da linha ja foi lido e roda sem ele
REM (sem o aviso "arquivo em lotes nao encontrado"). Segunda tentativa: um programa pode demorar a soltar a pasta.
(goto) 2>nul & cd /d "%TEMP%" & rmdir /s /q "%RAIZ%" 2>nul & (if exist "%RAIZ%" (ping -n 4 127.0.0.1 >nul & rmdir /s /q "%RAIZ%" 2>nul)) & (if exist "%RAIZ%" (echo Some files could not be deleted ^(still in use?^). Delete this folder by hand: %RAIZ%) else (echo EasyComfee was removed.)) & pause
