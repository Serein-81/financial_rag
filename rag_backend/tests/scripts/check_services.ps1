# 检查依赖服务状态

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "检查依赖服务状态" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n1. 检查 Docker 容器..." -ForegroundColor Yellow
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | Select-String -Pattern "postgres|redis|minio|neo4j|backend"

Write-Host "`n2. 检查 PostgreSQL 连接..." -ForegroundColor Yellow
try {
    $pgResult = docker exec rag_backend python -c "
import asyncio
from app.db.session import engine
async def test():
    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT 1'))
        print('OK')
asyncio.run(test())
" 2>&1
    Write-Host "PostgreSQL: $pgResult" -ForegroundColor Cyan
} catch {
    Write-Host "PostgreSQL 连接失败: $_" -ForegroundColor Red
}

Write-Host "`n3. 检查 Redis 连接..." -ForegroundColor Yellow
try {
    $redisResult = docker exec rag_backend python -c "
from app.services.token_blacklist_service import token_blacklist_service
print('Redis OK:', token_blacklist_service.redis_client.ping())
" 2>&1
    Write-Host "Redis: $redisResult" -ForegroundColor Cyan
} catch {
    Write-Host "Redis 连接失败: $_" -ForegroundColor Red
}

Write-Host "`n4. 检查 MinIO 连接..." -ForegroundColor Yellow
try {
    $minioResult = docker exec rag_backend python -c "
from app.services.minio_service import minio_service
print('MinIO OK:', minio_service.client.bucket_exists(minio_service.bucket_name))
" 2>&1
    Write-Host "MinIO: $minioResult" -ForegroundColor Cyan
} catch {
    Write-Host "MinIO 连接失败: $_" -ForegroundColor Red
}

Write-Host "`n5. 检查数据库连接池..." -ForegroundColor Yellow
docker exec rag_backend python -c "
from app.db.session import engine
print('连接池配置:')
print('  pool_size:', engine.pool.size())
print('  pool_overflow:', engine.pool._overflow)
print('  pool_timeout:', engine.pool._timeout)
" 2>&1

Write-Host "`n6. 快速测试数据库查询..." -ForegroundColor Yellow
$start = Get-Date
try {
    $testResult = docker exec rag_backend python -c "
import asyncio
from app.db.session import AsyncSessionLocal
async def test():
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text
        result = await db.execute(text('SELECT 1'))
        return result.scalar()
r = asyncio.run(test())
print('OK:', r)
" 2>&1
    $end = Get-Date
    $elapsed = ($end - $start).TotalMilliseconds
    Write-Host "数据库查询: $testResult (耗时: ${elapsed}ms)" -ForegroundColor Cyan
} catch {
    Write-Host "数据库查询失败: $_" -ForegroundColor Red
}

Write-Host "`n7. 检查是否有大量卡住的请求..." -ForegroundColor Yellow
Write-Host "查找长时间运行的请求:" -ForegroundColor Cyan
$recentLogs = docker logs --tail 1000 rag_backend 2>&1
$postRequests = $recentLogs | Select-String -Pattern "INFO.*127\.0\.0\.1.*POST"
Write-Host "POST 请求数量: $($postRequests.Count)" -ForegroundColor White

if ($postRequests.Count -gt 10) {
    Write-Host "⚠️ 检测到大量 POST 请求，可能存在连接池耗尽问题" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
