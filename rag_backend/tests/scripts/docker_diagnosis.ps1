# Docker 网络诊断脚本
# 用于诊断后端在 Docker 中运行时的连接问题

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Docker 网络诊断" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n1. 检查 Docker 容器状态..." -ForegroundColor Yellow
docker ps -a --filter "name=rag_backend" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

Write-Host "`n2. 检查端口映射..." -ForegroundColor Yellow
docker port rag_backend 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 容器 'rag_backend' 不存在或未运行" -ForegroundColor Red
} else {
    Write-Host "✅ 端口映射:" -ForegroundColor Green
    docker port rag_backend
}

Write-Host "`n3. 测试容器内健康检查..." -ForegroundColor Yellow
docker exec rag_backend curl -f http://localhost:8000/ 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 容器内健康检查通过" -ForegroundColor Green
} else {
    Write-Host "❌ 容器内健康检查失败" -ForegroundColor Red
}

Write-Host "`n4. 测试宿主机到容器的连接..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✅ 宿主机可以访问容器 (状态码: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "❌ 宿主机无法访问容器: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "`n可能的解决方案:" -ForegroundColor Cyan
    Write-Host "1. 重启 Docker 容器:" -ForegroundColor White
    Write-Host "   docker-compose down && docker-compose up -d" -ForegroundColor Gray
    Write-Host "2. 检查防火墙设置" -ForegroundColor White
    Write-Host "3. 检查端口是否被占用: netstat -ano | findstr 8000" -ForegroundColor White
}

Write-Host "`n5. 检查容器日志..." -ForegroundColor Yellow
Write-Host "最近 20 行日志:" -ForegroundColor Cyan
docker logs --tail 20 rag_backend 2>&1 | Select-Object -Last 20

Write-Host "`n6. 如果容器正在运行但无法访问..." -ForegroundColor Yellow
Write-Host "请执行以下命令重启容器:" -ForegroundColor Cyan
Write-Host "cd rag_backend" -ForegroundColor White
Write-Host "docker-compose down" -ForegroundColor White
Write-Host "docker-compose up -d" -ForegroundColor White
Write-Host "docker logs -f rag_backend" -ForegroundColor White

Write-Host "`n========================================" -ForegroundColor Cyan
