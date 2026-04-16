# 在 Docker 容器中安装缺失的依赖并重启

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "修复 Docker 容器依赖问题" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n1. 检查 PyMuPDF 是否已安装..." -ForegroundColor Yellow
$checkResult = docker exec rag_backend pip show PyMuPDF 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ PyMuPDF 已安装:" -ForegroundColor Green
    Write-Host $checkResult -ForegroundColor White
} else {
    Write-Host "❌ PyMuPDF 未安装" -ForegroundColor Red
}

Write-Host "`n2. 检查容器启动时的错误..." -ForegroundColor Yellow
Write-Host "查看最近 50 行日志:" -ForegroundColor Cyan
docker logs --tail 50 rag_backend 2>&1 | Select-Object -Last 50

Write-Host "`n3. 重新构建并启动容器..." -ForegroundColor Yellow
Write-Host "这可能需要几分钟..." -ForegroundColor Cyan

Set-Location "D:\Python\Codebase\My_rag\rag_backend"
docker-compose down
docker-compose up -d --build

Write-Host "`n4. 等待容器启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host "`n5. 验证修复..." -ForegroundColor Yellow
$healthCheck = curl -f http://127.0.0.1:8000/ 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 容器健康检查通过" -ForegroundColor Green
} else {
    Write-Host "❌ 容器健康检查失败" -ForegroundColor Red
}

Write-Host "`n6. 检查 tax-reports 路由..." -ForegroundColor Yellow
try {
    $openApi = Invoke-RestMethod -Uri "http://127.0.0.1:8000/openapi.json" -TimeoutSec 10
    if ($openApi.paths.'/api/v1/tax-reports/upload') {
        Write-Host "✅ /api/v1/tax-reports/upload 路由已注册" -ForegroundColor Green
    } else {
        Write-Host "❌ /api/v1/tax-reports/upload 路由未找到" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ 无法获取 OpenAPI 文档: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "完成!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
