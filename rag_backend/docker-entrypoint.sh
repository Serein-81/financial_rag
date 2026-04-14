#!/bin/bash
set -e

echo "🐳 RAG Backend 容器启动中..."

echo "📊 检查并创建向量索引 (最多重试 3 次)..."
for i in 1 2 3; do
    echo "   尝试 $i/3..."
    if python3 -m app.migrations.auto_create_vector_index 2>&1; then
        echo "✅ 索引创建完成"
        break
    fi
    if [ $i -lt 3 ]; then
        echo "⚠️ 索引创建失败，5秒后重试..."
        sleep 5
    fi
done

echo "🚀 启动应用（uvloop 高性能模式 + 热重载）..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --loop uvloop \
    --http h11 \
    --reload
