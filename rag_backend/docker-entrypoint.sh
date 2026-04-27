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

echo "Checking vector index, retrying up to 3 times..."
for i in 1 2 3; do
    echo "Attempt $i/3..."

    if python3 -m app.migrations.auto_create_vector_index 2>&1; then
        echo "Vector index check completed."
        break
    fi

    if [ "$i" -lt 3 ]; then
        echo "Vector index check failed, retrying in 5 seconds..."
        sleep 5
    else
        echo "Vector index check failed after 3 attempts."
        exit 1
    fi
done

echo "Starting FastAPI application..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --loop uvloop \
    --http h11
