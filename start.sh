#!/bin/sh
# Railway 启动脚本 - 确保使用 PORT 环境变量
PORT=${PORT:-8080}
echo "Starting on port $PORT"
exec uvicorn main:app --host 0.0.0.0 --port $PORT
