@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup_monitor.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "monitor\monitor.py" %*
if errorlevel 1 pause
