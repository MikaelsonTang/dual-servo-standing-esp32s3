@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" tools\flash_workshop.py
pause
exit /b
:missing
echo Run 00_setup.cmd first.
pause
exit /b 1
