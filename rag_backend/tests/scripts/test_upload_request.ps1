# 测试 tax-reports/upload 接口

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "测试 tax-reports/upload 接口" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n1. 创建测试文件..." -ForegroundColor Yellow
$testFile = "$env:TEMP\test_tax.pdf"
Set-Content -Path $testFile -Value "%PDF-1.4 test" -Encoding UTF8
Write-Host "✅ 测试文件已创建: $testFile" -ForegroundColor Green

Write-Host "`n2. 获取认证 Token..." -ForegroundColor Yellow
Write-Host "请输入测试用的 Token (或者直接按回车跳过认证测试):" -ForegroundColor Cyan
$token = Read-Host "Token"

if ([string]::IsNullOrEmpty($token)) {
    Write-Host "⚠️ 跳过认证测试，仅测试路由是否存在" -ForegroundColor Yellow
    
    Write-Host "`n3. 测试路由是否存在..." -ForegroundColor Yellow
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/openapi.json" -TimeoutSec 10
        $openApi = $response.Content | ConvertFrom-Json
        if ($openApi.paths.'/api/v1/tax-reports/upload') {
            Write-Host "✅ /api/v1/tax-reports/upload 路由存在!" -ForegroundColor Green
            Write-Host "   方法: POST" -ForegroundColor White
        } else {
            Write-Host "❌ /api/v1/tax-reports/upload 路由不存在!" -ForegroundColor Red
        }
    } catch {
        Write-Host "❌ 无法获取 OpenAPI 文档: $($_.Exception.Message)" -ForegroundColor Red
    }
} else {
    Write-Host "`n3. 测试上传接口..." -ForegroundColor Yellow
    Write-Host "注意: 这只是一个 OPTIONS/HEAD 请求，不会上传真实文件" -ForegroundColor Cyan
    
    try {
        # 先检查 OPTIONS
        Write-Host "发送 OPTIONS 请求..." -ForegroundColor White
        $optionsResponse = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/tax-reports/upload" `
            -Method OPTIONS `
            -Headers @{"Authorization" = "Bearer $token"} `
            -TimeoutSec 10
        Write-Host "✅ OPTIONS 响应: $($optionsResponse.StatusCode)" -ForegroundColor Green
    } catch {
        Write-Host "OPTIONS 请求失败: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    
    Write-Host "`n4. 检查容器日志..." -ForegroundColor Yellow
    Write-Host "查看最近的请求记录:" -ForegroundColor Cyan
    docker logs --tail 20 rag_backend 2>&1 | Select-Object -Last 20
}

Write-Host "`n5. 检查是否有未决的请求..." -ForegroundColor Yellow
Write-Host "正在检查网络连接..." -ForegroundColor Cyan
try {
    $pingResult = Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -WarningAction SilentlyContinue
    if ($pingResult.TcpTestSucceeded) {
        Write-Host "✅ 127.0.0.1:8000 端口开放" -ForegroundColor Green
    } else {
        Write-Host "❌ 127.0.0.1:8000 端口无法连接" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ 连接测试失败: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "测试完成!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
