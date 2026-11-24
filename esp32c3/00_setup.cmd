@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Setup complete. Next: 01_flash.cmd or 02_open_demo.cmd
pause
exit /b 0
:failed
echo Install Python 3.11 or 3.12 with py launcher and Tcl/Tk, then retry.
pause
exit /b 1
