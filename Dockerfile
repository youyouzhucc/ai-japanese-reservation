# Railway 部署 - 使用 Dockerfile 确保 Python 3.12 和依赖正确安装
FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# Railway 会注入 PORT 环境变量
ENV PORT=8000
EXPOSE $PORT

CMD uvicorn main:app --host 0.0.0.0 --port $PORT
