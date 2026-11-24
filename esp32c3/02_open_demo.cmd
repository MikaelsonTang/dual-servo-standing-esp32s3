@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" goto missing
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0desktop\event_app.py"
exit /b
:missing
echo Run 00_setup.cmd first.
pause
exit /b 1
