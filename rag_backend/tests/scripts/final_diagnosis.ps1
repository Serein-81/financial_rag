# 最终诊断：找出上传请求挂起的真正原因

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "最终诊断：上传请求挂起问题" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n🔍 核心问题：上传请求挂起，但其他请求正常" -ForegroundColor Red
Write-Host "`n可能原因分析:" -ForegroundColor Yellow
Write-Host "   1. 文件上传端点的特定问题" -ForegroundColor White
Write-Host "   2. 数据库连接池在文件上传时被耗尽" -ForegroundColor White
Write-Host "   3. 某个依赖服务在文件上传时无响应" -ForegroundColor White

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "步骤 1: 检查数据库连接池状态" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n在容器中检查连接池..." -ForegroundColor White

docker exec rag_backend python << 'PYTHON_EOF'
import asyncio
import time

async def check_db_pool():
    print("\n=== 数据库连接池诊断 ===")
    from app.db.session import engine, AsyncSessionLocal
    from sqlalchemy import text
    
    print(f"引擎池配置:")
    print(f"  pool_size: {engine.pool.size()}")
    print(f"  pool_overflow: {engine.pool._overflow}")
    print(f"  pool_timeout: {engine.pool._timeout}")
    
    # 测试获取连接
    print("\n尝试获取数据库连接...")
    start = time.time()
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1 as test"))
            value = result.scalar()
            elapsed = time.time() - start
            print(f"✅ 连接获取成功: {value} (耗时: {elapsed:.3f}s)")
    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ 连接获取失败 (耗时: {elapsed:.3f}s): {e}")
    
    # 测试多次查询（模拟并发）
    print("\n模拟并发查询 (5次)...")
    start = time.time()
    try:
        tasks = [AsyncSessionLocal().__aenter__() for _ in range(5)]
        sessions = await asyncio.gather(*tasks)
        for s in sessions:
            await s.close()
        elapsed = time.time() - start
        print(f"✅ 5次并发查询成功 (总耗时: {elapsed:.3f}s)")
    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ 并发查询失败 (耗时: {elapsed:.3f}s): {e}")

asyncio.run(check_db_pool())
PYTHON_EOF

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "步骤 2: 使用 curl 测试文件上传" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n创建测试 PDF 文件..." -ForegroundColor White
$testFile = "$env:TEMP\test_upload.pdf"
Set-Content -Path $testFile -Value "%PDF-1.4 test content" -Encoding UTF8

Write-Host "`n请提供你的测试 Token（用于认证）:" -ForegroundColor Yellow
Write-Host "(你可以在浏览器 Console 中输入 localStorage.getItem('rag_token') 获取)" -ForegroundColor Gray
$token = Read-Host "Token"

if ([string]::IsNullOrEmpty($token)) {
    Write-Host "`n⚠️ 没有提供 Token，跳过 curl 测试" -ForegroundColor Yellow
} else {
    Write-Host "`n使用 curl 测试上传..." -ForegroundColor White
    Write-Host "注意：这需要一个有效的 Token" -ForegroundColor Cyan
    
    # 使用 curl 测试
    $curlCmd = "curl.exe -X POST `"http://127.0.0.1:8000/api/v1/tax-reports/upload?tax_type=VAT`" -H `"Authorization: Bearer $token`" -F `"file=@$testFile`" --max-time 30 -v"
    
    Write-Host "`n执行命令: $curlCmd" -ForegroundColor Gray
    Invoke-Expression $curlCmd
}

Remove-Item $testFile -ErrorAction SilentlyContinue

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "步骤 3: 检查容器当前状态" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n查看最近 30 行日志..." -ForegroundColor White
docker logs --tail 30 rag_backend 2>&1

Write-Host "`n查看是否有 tax-reports 的 POST 请求..." -ForegroundColor White
docker logs --tail 500 rag_backend 2>&1 | Select-String -Pattern "tax-reports.*POST|POST.*tax-reports|TaxUpload"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "步骤 4: 检查是否有文件被卡住" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n检查上传目录..." -ForegroundColor White
docker exec rag_backend ls -la /app/uploads/tax-reports/ 2>&1 | Select-Object -First 20

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "诊断完成！" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n请告诉我:" -ForegroundColor Yellow
Write-Host "1. 步骤 1 的数据库连接池测试结果" -ForegroundColor White
Write-Host "2. 步骤 3 的日志中是否有 tax-reports 的请求" -ForegroundColor White
Write-Host "3. 如果有 Token，curl 测试的结果" -ForegroundColor White
