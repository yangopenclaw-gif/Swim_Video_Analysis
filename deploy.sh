#!/bin/bash
set -e

PROJECT_DIR="/root/IDEProjects/Swim_Video_Analysis"
STAGING_DIR="$PROJECT_DIR/staging"
PROD_PORT=8000
STAGING_PORT=8001

case "$1" in
  prod)
    echo "=== 正式环境部署 ==="
    cd "$PROJECT_DIR/frontend" && npm run build
    pkill -f "uvicorn backend.main:app --host 0.0.0.0 --port $PROD_PORT" 2>/dev/null || true
    sleep 2
    cd "$PROJECT_DIR" && nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port $PROD_PORT > /tmp/prod.log 2>&1 &
    echo "正式环境已启动: http://139.159.249.62:$PROD_PORT"
    ;;

  staging)
    echo "=== 验证环境部署 ==="
    mkdir -p "$STAGING_DIR/data" "$STAGING_DIR/uploads" "$STAGING_DIR/avatars"
    cp -n "$PROJECT_DIR/.env" "$STAGING_DIR/.env" 2>/dev/null || true
    cd "$PROJECT_DIR/frontend" && npm run build
    pkill -f "uvicorn backend.main:app --host 0.0.0.0 --port $STAGING_PORT" 2>/dev/null || true
    sleep 2
    cd "$PROJECT_DIR" && STAGING_MODE=1 STAGING_DIR="$STAGING_DIR" nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port $STAGING_PORT > /tmp/staging.log 2>&1 &
    echo "验证环境已启动: http://139.159.249.62:$STAGING_PORT"
    ;;

  stop)
    echo "=== 停止服务 ==="
    pkill -f "uvicorn backend.main:app --host 0.0.0.0 --port $PROD_PORT" 2>/dev/null || true
    pkill -f "uvicorn backend.main:app --host 0.0.0.0 --port $STAGING_PORT" 2>/dev/null || true
    echo "所有服务已停止"
    ;;

  status)
    echo "=== 服务状态 ==="
    PROD_PID=$(pgrep -f "uvicorn backend.main:app --host 0.0.0.0 --port $PROD_PORT" 2>/dev/null || echo "未运行")
    STAGING_PID=$(pgrep -f "uvicorn backend.main:app --host 0.0.0.0 --port $STAGING_PORT" 2>/dev/null || echo "未运行")
    echo "正式环境 (端口$PROD_PORT): $PROD_PID"
    echo "验证环境 (端口$STAGING_PORT): $STAGING_PID"
    ;;

  promote)
    echo "=== 验证环境 → 正式环境发布 ==="
    echo "1. 停止验证环境..."
    pkill -f "uvicorn backend.main:app --host 0.0.0.0 --port $STAGING_PORT" 2>/dev/null || true
    sleep 2
    echo "2. 构建前端..."
    cd "$PROJECT_DIR/frontend" && npm run build
    echo "3. 重启正式环境..."
    pkill -f "uvicorn backend.main:app --host 0.0.0.0 --port $PROD_PORT" 2>/dev/null || true
    sleep 2
    cd "$PROJECT_DIR" && nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port $PROD_PORT > /tmp/prod.log 2>&1 &
    sleep 4
    echo "4. 验证正式环境..."
    if curl -s http://127.0.0.1:$PROD_PORT/api/health | grep -q "ok"; then
      echo "正式环境发布成功: http://139.159.249.62:$PROD_PORT"
    else
      echo "正式环境启动失败，请检查 /tmp/prod.log"
    fi
    ;;

  *)
    echo "用法: $0 {prod|staging|stop|status|promote}"
    echo ""
    echo "  prod      - 部署正式环境 (端口$PROD_PORT)"
    echo "  staging   - 部署验证环境 (端口$STAGING_PORT)"
    echo "  stop      - 停止所有服务"
    echo "  status    - 查看服务状态"
    echo "  promote   - 验证环境通过后发布到正式环境"
    exit 1
    ;;
esac