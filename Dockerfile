# Railway 部署 - 使用 Dockerfile 确保 Python 3.12 和依赖正确安装
FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# Railway 默认 PORT=8080，Generate Domain 时请填 8080
ENV PORT=8080
EXPOSE 8080

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
