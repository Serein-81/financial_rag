# 检查 Docker 容器中是否加载了 tax-reports 路由

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "检查 tax-reports 路由是否注册" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n1. 检查容器是否运行..." -ForegroundColor Yellow
$containerStatus = docker ps --filter "name=rag_backend" --format "{{.Status}}")
if ([string]::IsNullOrEmpty($containerStatus)) {
    Write-Host "❌ 容器未运行" -ForegroundColor Red
    exit 1
}
Write-Host "✅ 容器状态: $containerStatus" -ForegroundColor Green

Write-Host "`n2. 测试 tax-reports 路由是否存在..." -ForegroundColor Yellow
Write-Host "获取 OpenAPI 文档..." -ForegroundColor Cyan

try {
    $openApi = Invoke-RestMethod -Uri "http://127.0.0.1:8000/openapi.json" -TimeoutSec 10
    $taxPaths = $openApi.paths | Get-Member -MemberType NoteProperty | Where-Object { $_.Name -like "*tax*" }
    
    if ($taxPaths) {
        Write-Host "✅ 找到 tax 相关路由:" -ForegroundColor Green
        foreach ($path in $taxPaths) {
            Write-Host "   $path" -ForegroundColor White
        }
    } else {
        Write-Host "❌ 未找到任何 tax 相关路由!" -ForegroundColor Red
        Write-Host "`n这意味着 tax_report 路由没有正确加载!" -ForegroundColor Red
        Write-Host "可能原因: 容器内缺少依赖模块 (fitz/PyMuPDF)" -ForegroundColor Yellow
    }
    
    Write-Host "`n所有注册的路径:" -ForegroundColor Cyan
    $allPaths = $openApi.paths | Get-Member -MemberType NoteProperty
    foreach ($path in $allPaths) {
        Write-Host "   $path" -ForegroundColor Gray
    }
}
catch {
    Write-Host "❌ 无法获取 OpenAPI 文档: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n3. 检查容器日志中的错误..." -ForegroundColor Yellow
docker logs --tail 50 rag_backend 2>&1 | Select-String -Pattern "error|Error|ERROR|warning|Warning|fail|Fail" -Context 0,2

Write-Host "`n========================================" -ForegroundColor Cyan
