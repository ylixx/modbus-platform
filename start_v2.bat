@echo off
REM Modbus 平台一键启动（前端运行 V2，端口 3001）
setlocal
set ROOT=E:\modbus-platform
set NODE=C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2
set PATH=%NODE%;%PATH%
set PYTHON=%ROOT%\backend\.venv\Scripts\python.exe
set PNPM=C:\Users\Administrator\AppData\Roaming\npm\pnpm.cmd

if not exist "%PYTHON%" (
  echo [错误] 未找到后端 venv，请先按部署说明安装依赖。
  pause
  exit /b 1
)

echo =========================================
echo  Modbus 平台启动 (前端 V2)
echo =========================================
echo [1/2] 启动后端 uvicorn :8000
start "modbus-backend" cmd /k "cd /d %ROOT%\backend && %PYTHON% -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo [2/2] 启动前端 V2 (vite :3001)
start "modbus-frontend-v2" cmd /k "cd /d %ROOT%\frontend-v2 && %PNPM% dev"

echo 等待服务就绪...
timeout /t 25 >nul
echo 已在浏览器打开 http://localhost:3001
start http://localhost:3001
echo.
echo 前端: http://localhost:3001
echo 后端: http://localhost:8000  (API 文档: http://localhost:8000/docs)
echo 默认账号: admin / admin123
echo 关闭：结束上述两个 cmd 窗口，或任务管理器结束 uvicorn / vite 进程。
endlocal
