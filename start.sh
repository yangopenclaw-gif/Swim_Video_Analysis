#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== 启动游泳比赛视频分析系统 ==="

pkill -9 -f "uvicorn backend.main:app" 2>/dev/null
sleep 2

export PYTHONPATH="$SCRIPT_DIR"

echo "正在启动后端服务..."
nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --log-level info > /tmp/uvicorn.log 2>&1 &
BACKEND_PID=$!

sleep 3

if kill -0 $BACKEND_PID 2>/dev/null; then
    echo "后端服务已启动 (PID: $BACKEND_PID)"
    echo "访问地址: http://localhost:8000"
    echo "日志文件: /tmp/uvicorn.log"
else
    echo "后端服务启动失败，请查看日志: /tmp/uvicorn.log"
    exit 1
fi
