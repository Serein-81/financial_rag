#!/bin/bash
set -e

echo "🐳 RAG Backend 容器启动中..."

# 等待数据库服务启动
echo "⏳ 等待数据库服务启动..."
sleep 5

# 启动应用
echo "🚀 启动应用..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
