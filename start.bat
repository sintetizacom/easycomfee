@echo off
REM Starts the studio and opens it in the browser. ComfyUI must already be running.
setlocal
cd /d "%~dp0"
if not exist backend\.venv (echo Run install.bat first. & exit /b 1)
for /f %%p in ('backend\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend'); import config; print(config.APP_PORTA)"') do set PORT=%%p
REM "start.bat noopen" (usado pelo Update) nao abre outra aba: a pagina aberta se recarrega sozinha.
if /i not "%~1"=="noopen" start "" http://127.0.0.1:%PORT%
cd backend
REM Sem uma linha por pedido de rotina (o Config Models consulta o progresso); erros continuam aparecendo.
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port %PORT% --no-access-log
