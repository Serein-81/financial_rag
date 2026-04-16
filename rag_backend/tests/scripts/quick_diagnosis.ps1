# 快速诊断：测试上传端点的依赖服务

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "测试依赖服务连通性" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n1. 测试健康检查端点..." -ForegroundColor Yellow
$start = Get-Date
try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/tax-intelligence/health" -TimeoutSec 10
    $end = Get-Date
    $elapsed = ($end - $start).TotalMilliseconds
    Write-Host "✅ 健康检查响应正常 (${elapsed}ms)" -ForegroundColor Green
    Write-Host $health.Content -ForegroundColor Cyan
} catch {
    $end = Get-Date
    $elapsed = ($end - $start).TotalMilliseconds
    Write-Host "❌ 健康检查失败 (${elapsed}ms): $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n2. 测试 OpenAPI 文档..." -ForegroundColor Yellow
$start = Get-Date
try {
    $openapi = Invoke-WebRequest -Uri "http://127.0.0.1:8000/openapi.json" -TimeoutSec 5
    $end = Get-Date
    $elapsed = ($end - $start).TotalMilliseconds
    Write-Host "✅ OpenAPI 响应正常 (${elapsed}ms)" -ForegroundColor Green
} catch {
    $end = Get-Date
    $elapsed = ($end - $start).TotalMilliseconds
    Write-Host "❌ OpenAPI 失败 (${elapsed}ms): $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n3. 简单 Python 脚本测试..." -ForegroundColor Yellow
Write-Host "在容器中执行测试..." -ForegroundColor Cyan

docker exec rag_backend python << 'PYTHON_EOF'
import asyncio
import time
from app.db.session import AsyncSessionLocal
from sqlalchemy import text

async def test_db():
    print("\n=== 数据库连接测试 ===")
    start = time.time()
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(text('SELECT 1 as test'))
            value = result.scalar()
            elapsed = time.time() - start
            print(f"✅ 数据库查询成功: {value} (耗时: {elapsed:.3f}s)")
    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ 数据库查询失败 (耗时: {elapsed:.3f}s): {e}")

asyncio.run(test_db())
PYTHON_EOF

Write-Host "`n4. 检查最近的 FastAPI 日志..." -ForegroundColor Yellow
docker logs --tail 20 rag_backend 2>&1 | Select-Object -Last 20

Write-Host "`n5. 模拟简单请求..." -ForegroundColor Yellow
Write-Host "发送一个不涉及文件的请求，测试系统是否正常..." -ForegroundColor Cyan

docker exec rag_backend python << 'PYTHON_EOF'
import asyncio
import httpx

async def test_simple_request():
    print("\n=== 模拟简单 API 请求 ===")
    async with httpx.AsyncClient() as client:
        try:
            # 测试一个简单的 GET 请求
            response = await client.get("http://127.0.0.1:8000/api/v1/tenant-settings/me", timeout=5.0)
            print(f"响应状态: {response.status_code}")
            if response.status_code == 200:
                print("✅ 简单请求成功")
            elif response.status_code == 401:
                print("⚠️ 需要认证 (这是正常的)")
            else:
                print(f"响应: {response.text[:200]}")
        except Exception as e:
            print(f"❌ 请求失败: {e}")

asyncio.run(test_simple_request())
PYTHON_EOF

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "诊断完成!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
