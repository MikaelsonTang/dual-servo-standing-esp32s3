@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" goto missing
start "" ".venv\Scripts\pythonw.exe" "desktop\event_app.py"
exit /b 0
:missing
echo Run 00_setup.cmd first.
pause
exit /b 1
