#!/bin/bash
set -e

echo "Starting RAG backend container..."

echo "Preparing writable directories..."
mkdir -p /app/uploads/tax_reports
mkdir -p /app/uploads/chat_files
mkdir -p /app/uploads/avatars
mkdir -p /app/uploads/documents
mkdir -p /app/logs

if [ "$(stat -c '%U' /app/uploads 2>/dev/null || true)" = "root" ]; then
    echo "Changing /app/uploads ownership from root to appuser..."
    chown -R appuser:appuser /app/uploads 2>/dev/null || true
    chmod -R 755 /app/uploads 2>/dev/null || true
fi

if [ -d "/app/logs" ] && [ "$(stat -c '%U' /app/logs 2>/dev/null || true)" = "root" ]; then
    echo "Changing /app/logs ownership from root to appuser..."
    chown -R appuser:appuser /app/logs 2>/dev/null || true
    chmod -R 755 /app/logs 2>/dev/null || true
fi

echo "→ 向量索引检查..."
for i in 1 2 3; do
    if python3 -m app.migrations.auto_create_vector_index > /dev/null 2>&1; then
        break
    fi
    if [ "$i" -lt 3 ]; then
        sleep 5
    else
        echo "⚠️ 向量索引检查失败，向量搜索性能可能受影响"
    fi
done

echo "Starting FastAPI application..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --loop uvloop \
    --http h11
