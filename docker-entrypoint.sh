#!/bin/bash

# docker-entrypoint.sh
# Docker 容器启动脚本，用于自动运行数据库迁移和启动应用

set -e

echo "🐳 RAG Backend 容器启动中..."

# 等待数据库服务启动
echo "⏳ 等待数据库服务启动..."
python -c "
import asyncio
import sys
import os
sys.path.insert(0, '/app')
from migrations.docker_migration import wait_for_db

async def main():
    success = await wait_for_db()
    sys.exit(0 if success else 1)

asyncio.run(main())
"

if [ $? -ne 0 ]; then
    echo "❌ 数据库连接失败，容器启动中止"
    exit 1
fi

# 运行数据库迁移
echo "🔄 运行数据库迁移..."
python migrations/docker_migration.py

if [ $? -ne 0 ]; then
    echo "❌ 数据库迁移失败，容器启动中止"
    exit 1
fi

echo "✅ 数据库迁移完成"

# 启动应用
echo "🚀 启动 FastAPI 应用..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload