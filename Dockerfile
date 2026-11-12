# 1) 构建 Vue 登录页
FROM node:20-alpine AS frontend

WORKDIR /build
COPY 前端/package*.json ./
RUN npm ci
COPY 前端/ ./
RUN npm run build

# 2) 运行 Python 服务
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY static ./static
COPY --from=frontend /static/dist ./static/dist

EXPOSE 8290

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${UVICORN_PORT:-8290} --proxy-headers --forwarded-allow-ips='*'"]
