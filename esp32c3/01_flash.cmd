@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" -X utf8 flash_c3.py
pause
exit /b
:missing
echo Run 00_setup.cmd first.
pause
exit /b 1
