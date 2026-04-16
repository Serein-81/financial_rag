# 检查 Docker 容器资源使用和进程状态

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "检查 Docker 容器状态和资源" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n1. 检查容器状态..." -ForegroundColor Yellow
docker ps --filter "name=rag_backend" --format "table {{.Names}}\t{{.Status}}\t{{.CPU}}\t{{.MEM}}"

Write-Host "`n2. 详细资源使用情况..." -ForegroundColor Yellow
docker stats rag_backend --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}\t{{.PIDs}}"

Write-Host "`n3. 检查容器内进程..." -ForegroundColor Yellow
Write-Host "正在运行的进程:" -ForegroundColor Cyan
docker top rag_backend 2>&1

Write-Host "`n4. 检查容器是否响应..." -ForegroundColor Yellow
Write-Host "测试容器内健康检查..." -ForegroundColor Cyan
$startTime = Get-Date
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/" -TimeoutSec 5
    $endTime = Get-Date
    $elapsed = ($endTime - $startTime).TotalMilliseconds
    Write-Host "✅ 容器响应正常 (状态码: $($response.StatusCode), 耗时: ${elapsed}ms)" -ForegroundColor Green
} catch {
    $endTime = Get-Date
    $elapsed = ($endTime - $startTime).TotalMilliseconds
    Write-Host "❌ 容器无响应 (耗时: ${elapsed}ms)" -ForegroundColor Red
    Write-Host "   错误: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n5. 检查容器日志中的错误..." -ForegroundColor Yellow
Write-Host "最近 30 行日志:" -ForegroundColor Cyan
docker logs --tail 30 rag_backend 2>&1 | Select-Object -Last 30

Write-Host "`n6. 检查是否有卡住的请求..." -ForegroundColor Yellow
Write-Host "查找任何长时间运行的请求:" -ForegroundColor Cyan
docker logs --tail 500 rag_backend 2>&1 | Select-String -Pattern "INFO.*127\.0\.0\.1.*POST|INFO.*172\..*POST"

Write-Host "`n7. 容器健康检查..." -ForegroundColor Yellow
docker inspect rag_backend --format='{{.State.Health.Status}} {{.State.Status}} {{.State.Running}}' 2>&1

Write-Host "`n========================================" -ForegroundColor Cyan
