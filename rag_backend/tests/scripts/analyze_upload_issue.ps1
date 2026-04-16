# 分析上传问题的详细诊断

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "详细诊断上传问题" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n1. 检查容器状态..." -ForegroundColor Yellow
$containerStatus = docker ps --filter "name=rag_backend" --format "{{.Names}} {{.Status}} {{.Ports}}"
if ([string]::IsNullOrEmpty($containerStatus)) {
    Write-Host "❌ 容器未运行!" -ForegroundColor Red
} else {
    Write-Host "✅ 容器状态: $containerStatus" -ForegroundColor Green
}

Write-Host "`n2. 检查容器端口映射..." -ForegroundColor Yellow
docker port rag_backend 2>&1

Write-Host "`n3. 检查是否有 tax-reports/upload 请求..." -ForegroundColor Yellow
Write-Host "搜索最近的 POST /api/v1/tax-reports 日志:" -ForegroundColor Cyan
docker logs --tail 500 rag_backend 2>&1 | Select-String -Pattern "tax-reports.*POST|POST.*tax-reports" -Context 2,0

if ($LASTEXITCODE -ne 0 -or $null -eq (docker logs --tail 500 rag_backend 2>&1 | Select-String -Pattern "tax-reports.*POST|POST.*tax-reports")) {
    Write-Host "`n⚠️ 没有找到 tax-reports 的 POST 请求!" -ForegroundColor Yellow
    Write-Host "这意味着请求没有到达后端，或者被拒绝了。" -ForegroundColor Yellow
}

Write-Host "`n4. 检查是否有任何 400/401/403/404/500 错误..." -ForegroundColor Yellow
docker logs --tail 500 rag_backend 2>&1 | Select-String -Pattern " 4[0-9]{2} | 5[0-9]{2} " -Context 1,1

Write-Host "`n5. 检查 CORS 配置..." -ForegroundColor Yellow
Write-Host "查看 CORS 相关配置:" -ForegroundColor Cyan
docker exec rag_backend env | Select-String -Pattern "CORS|ORIGIN|ALLOWED"

Write-Host "`n6. 实时监控日志 (15秒)..." -ForegroundColor Yellow
Write-Host "请现在在浏览器中触发上传操作，然后观察..." -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止监控" -ForegroundColor Gray
Start-Sleep -Seconds 15

Write-Host "`n7. 检查是否有新的 tax-reports 请求..." -ForegroundColor Yellow
docker logs --tail 50 rag_backend 2>&1 | Select-String -Pattern "tax-reports|TaxUpload|127\.0\.0\.1.*POST"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "诊断完成" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
