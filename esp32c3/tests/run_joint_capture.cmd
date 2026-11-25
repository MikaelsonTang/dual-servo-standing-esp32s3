@echo off
if not defined VCVARS64 (
 echo Set VCVARS64 to your Visual Studio vcvars64.bat path.
 exit /b 1
)
call "%VCVARS64%" >nul
cd /d "%~dp0"
cl /nologo /EHsc /std:c++17 /O2 test_joint_capture.cpp /Fe:test_joint_capture.exe
if errorlevel 1 exit /b 1
test_joint_capture.exe
if errorlevel 1 exit /b 1
cl /nologo /EHsc /std:c++17 /O2 test_joint_storage.cpp /Fe:test_joint_storage.exe
if errorlevel 1 exit /b 1
test_joint_storage.exe
