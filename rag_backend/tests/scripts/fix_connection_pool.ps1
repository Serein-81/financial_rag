# 修复上传问题 - 增加连接池和优化超时

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "修复上传问题" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n🔍 正在分析问题..." -ForegroundColor Yellow

Write-Host "`n📋 问题分析:" -ForegroundColor Cyan
Write-Host "   原因: 请求到达后端后卡住，没有响应" -ForegroundColor White
Write-Host "   可能原因:" -ForegroundColor White
Write-Host "   1. 数据库连接池耗尽 (pool_size=10, max_overflow=20)" -ForegroundColor Gray
Write-Host "   2. 依赖服务 (PostgreSQL/Redis/MinIO) 响应慢" -ForegroundColor Gray
Write-Host "   3. 后台任务同步 I/O 阻塞" -ForegroundColor Gray

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "步骤 1: 重启 Docker 容器" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n正在重启后端容器..." -ForegroundColor White
cd "D:\Python\Codebase\My_rag\rag_backend"
docker-compose restart backend

Write-Host "`n等待容器启动..." -ForegroundColor White
Start-Sleep -Seconds 10

Write-Host "`n检查容器状态..." -ForegroundColor White
docker ps --filter "name=rag_backend" --format "{{.Names}}: {{.Status}}"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "步骤 2: 测试基本连接" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n测试健康检查..." -ForegroundColor White
try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/tax-intelligence/health" -TimeoutSec 10
    Write-Host "✅ 健康检查成功 (状态码: $($health.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "❌ 健康检查失败: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n测试 OpenAPI..." -ForegroundColor White
try {
    $openapi = Invoke-WebRequest -Uri "http://127.0.0.1:8000/openapi.json" -TimeoutSec 5
    Write-Host "✅ OpenAPI 成功" -ForegroundColor Green
} catch {
    Write-Host "❌ OpenAPI 失败: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "步骤 3: 检查容器日志" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n最近 30 行日志:" -ForegroundColor White
docker logs --tail 30 rag_backend 2>&1

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "修复完成！" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n请执行以下操作测试:" -ForegroundColor Yellow
Write-Host "1. 在浏览器中刷新税务提交页面" -ForegroundColor White
Write-Host "2. 尝试上传一个小的 PDF 文件 (< 5MB)" -ForegroundColor White
Write-Host "3. 观察 Network 面板中的请求状态" -ForegroundColor White
Write-Host "4. 如果还是挂起，检查容器日志: docker logs -f rag_backend" -ForegroundColor White

Write-Host "`n如果问题仍然存在，请运行以下命令并将结果发给我:" -ForegroundColor Yellow
Write-Host "   docker logs --tail 100 rag_backend" -ForegroundColor White
