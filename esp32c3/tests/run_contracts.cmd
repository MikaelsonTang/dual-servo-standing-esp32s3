@echo off
if not defined VCVARS64 (
 echo Set VCVARS64 to your Visual Studio vcvars64.bat path.
 exit /b 1
)
call "%VCVARS64%" >nul
cd /d "%~dp0"
cl /nologo /EHsc /std:c++17 /O2 test_motion.cpp /Fe:test_motion.exe
if errorlevel 1 exit /b 1
test_motion.exe
if errorlevel 1 exit /b 1
cl /nologo /EHsc /std:c++17 /O2 test_direction.cpp /Fe:test_direction.exe
if errorlevel 1 exit /b 1
test_direction.exe
if errorlevel 1 exit /b 1
cl /nologo /EHsc /std:c++17 /O2 test_imu_scale.cpp /Fe:test_imu_scale.exe
if errorlevel 1 exit /b 1
test_imu_scale.exe
if errorlevel 1 exit /b 1
cl /nologo /EHsc /std:c++17 /O2 test_servo.cpp /Fe:test_servo.exe
if errorlevel 1 exit /b 1
test_servo.exe
if errorlevel 1 exit /b 1
cl /nologo /EHsc /std:c++17 /O2 test_zero.cpp /Fe:test_zero.exe
if errorlevel 1 exit /b 1
test_zero.exe
if errorlevel 1 exit /b 1
cl /nologo /EHsc /std:c++17 /O2 test_router_gap.cpp /Fe:test_router_gap.exe
if errorlevel 1 exit /b 1
test_router_gap.exe
if errorlevel 1 exit /b 1

cl /nologo /EHsc /std:c++17 /O2 test_write_limits.cpp /Fe:test_write_limits.exe
if errorlevel 1 exit /b 1
test_write_limits.exe
