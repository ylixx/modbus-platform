#!/bin/bash
echo "停止 Modbus 数据采集平台..."

if [ -f logs/backend.pid ]; then
    kill $(cat logs/backend.pid) 2>/dev/null
    rm logs/backend.pid
    echo "  后端已停止"
fi

if [ -f logs/frontend.pid ]; then
    kill $(cat logs/frontend.pid) 2>/dev/null
    rm logs/frontend.pid
    echo "  前端已停止"
fi

echo "全部服务已停止"
