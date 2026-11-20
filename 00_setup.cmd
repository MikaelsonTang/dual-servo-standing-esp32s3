@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 -m venv .venv
goto install
:use_python
python -m venv .venv
:install
if not exist ".venv\Scripts\python.exe" goto failed
".venv\Scripts\python.exe" -m pip install -r requirements-workshop.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "import tkinter,serial,esptool; print('Setup OK')"
if errorlevel 1 goto failed
echo Next: 01_flash.cmd, then 02_open_demo.cmd. See README.md.
pause
exit /b 0
:failed
echo Setup failed. Install Python 3.12 or 3.13 from python.org and retry.
echo Check the error above and your network connection.
pause
exit /b 1
