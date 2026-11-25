@echo off
if not defined VCVARS64 (
 echo Set VCVARS64 to your Visual Studio vcvars64.bat path.
 exit /b 1
)
call "%VCVARS64%" >nul
cd /d "%~dp0"
cl /nologo /EHsc /std:c++17 /O2 test_power_caps.cpp /Fe:test_power_caps.exe
if errorlevel 1 exit /b 1
test_power_caps.exe
