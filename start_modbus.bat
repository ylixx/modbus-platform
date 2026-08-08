@echo off
REM 一键启动 Modbus 平台：调起 start_modbus.py（脚本自动探测 venv / 依赖 / 端口）
setlocal
set "SCRIPT=%~dp0start_modbus.py"

where py >nul 2>&1
if %errorlevel%==0 (
  py "%SCRIPT%"
) else (
  python "%SCRIPT%"
)
pause
