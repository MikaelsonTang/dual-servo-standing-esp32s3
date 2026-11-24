@echo off
if not defined VCVARS64 (
  echo Set VCVARS64 to your Visual Studio vcvars64.bat path before running native tests.
  exit /b 1
)
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
cd /d "%~dp0"
cl /nologo /EHsc /std:c++17 /O2 test_c3_numeric.cpp /Fe:test_c3_numeric.exe
if errorlevel 1 exit /b 1
test_c3_numeric.exe
