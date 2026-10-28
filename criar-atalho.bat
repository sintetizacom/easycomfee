@echo off
REM Cria o atalho "EasyComfee" na Area de Trabalho e no Menu Iniciar, com o icone
REM da marca. Abre o start.bat com a janela minimizada (so o navegador aparece).
REM Chamado pelo install.bat e pelo botao Update; pode rodar sozinho tambem.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$r = (Get-Location).Path; $w = New-Object -ComObject WScript.Shell; foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) { $s = $w.CreateShortcut((Join-Path $d 'EasyComfee.lnk')); $s.TargetPath = (Join-Path $r 'start.bat'); $s.WorkingDirectory = $r; $s.IconLocation = (Join-Path $r 'frontend\public\brand\easycomfee.ico') + ',0'; $s.WindowStyle = 7; $s.Description = 'EasyComfee creative studio'; $s.Save() }" && echo Created the EasyComfee shortcut on your Desktop and in the Start menu.
