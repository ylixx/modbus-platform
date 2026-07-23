@echo off
chcp 65001 >nul 2>&1
setlocal
REM 一键启动 Modbus 平台：用托管 Python 调起 start_modbus.py
set "PYTHON=C:\Users\liyan\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
set "SCRIPT=%~dp0start_modbus.py"

if not exist "%PYTHON%" (
  where py >nul 2>&1 && set "PYTHON=py"
  if errorlevel 1 set "PYTHON=python"
)

"%PYTHON%" "%SCRIPT%"
pause
