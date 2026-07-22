#!/bin/bash
# Modbus Data Acquisition Platform - Start Script
set -e

echo "========================================="
echo " Modbus 数据采集平台 启动脚本"
echo "========================================="

# Check dependencies
command -v python3 >/dev/null 2>&1 || { echo "需要安装 Python 3.8+"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "需要安装 Node.js 16+"; exit 1; }

# === Backend ===
echo ""
echo "[1/4] 安装后端依赖..."
cd backend
python3 -m pip install -r requirements.txt -q

echo "[2/4] 启动后端服务..."
# Copy .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  已创建 .env 配置文件，请根据需要修改"
fi

# Start backend in background
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > ../logs/backend.log 2>&1 &
echo $! > ../logs/backend.pid
echo "  后端已启动: http://localhost:8000"
echo "  API 文档: http://localhost:8000/docs"
cd ..

# === Frontend ===
echo ""
echo "[3/4] 安装前端依赖..."
cd frontend
npm install --silent

echo "[4/4] 启动前端服务..."
nohup npm run dev > ../logs/frontend.log 2>&1 &
echo $! > ../logs/frontend.pid
echo "  前端已启动: http://localhost:3000"
cd ..

echo ""
echo "========================================="
echo " 启动完成！"
echo " 前端: http://localhost:3000"
echo " 后端: http://localhost:8000"
echo " API 文档: http://localhost:8000/docs"
echo " 默认账号: admin / admin123"
echo "========================================="
echo ""
echo "日志文件:"
echo "  后端: logs/backend.log"
echo "  前端: logs/frontend.log"
echo ""
echo "停止服务: ./scripts/stop.sh"
