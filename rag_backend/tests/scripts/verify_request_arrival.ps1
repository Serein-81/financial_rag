# 验证请求是否到达后端
# 这个脚本会创建一个测试端点并检查请求是否到达

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "验证请求是否到达后端" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n请提供你的 JWT Token:" -ForegroundColor Yellow
Write-Host "(在浏览器 Console 输入: localStorage.getItem('rag_token'))" -ForegroundColor Gray
$token = Read-Host "Token"

if ([string]::IsNullOrEmpty($token)) {
    Write-Host "`n❌ 需要 Token 才能测试" -ForegroundColor Red
    exit 1
}

Write-Host "`n创建测试 PDF 文件..." -ForegroundColor White
$testFile = "$env:TEMP\test_upload_verify.pdf"
Set-Content -Path $testFile -Value "%PDF-1.4 test content" -Encoding UTF8

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "测试 1: 检查后端是否运行" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/" -Method GET -TimeoutSec 5
    Write-Host "✅ 后端运行正常" -ForegroundColor Green
} catch {
    Write-Host "❌ 后端未运行或无法访问: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "测试 2: 检查 OpenAPI 文档" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

try {
    $openapi = Invoke-RestMethod -Uri "http://127.0.0.1:8000/openapi.json" -Method GET -TimeoutSec 10
    $uploadPath = $openapi.paths.'/api/v1/tax-reports/upload'
    
    if ($uploadPath) {
        Write-Host "✅ /api/v1/tax-reports/upload 路由存在" -ForegroundColor Green
        Write-Host "   支持的方法: $($uploadPath.PSObject.Properties.Name -join ', ')" -ForegroundColor White
    } else {
        Write-Host "❌ /api/v1/tax-reports/upload 路由不存在!" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ 无法获取 OpenAPI 文档: $_" -ForegroundColor Red
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "测试 3: 检查 Docker 日志（请求前）" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "查看最近的日志..." -ForegroundColor White
$beforeLogs = docker logs --tail 10 rag_backend 2>&1
Write-Host $beforeLogs

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "测试 4: 发送测试上传请求" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "URL: http://127.0.0.1:8000/api/v1/tax-reports/upload?tax_type=VAT" -ForegroundColor White
Write-Host "文件: $testFile" -ForegroundColor White
Write-Host "Token: $($token.Substring(0, [Math]::Min(20, $token.Length)))..." -ForegroundColor White

Write-Host "`n发送请求中..." -ForegroundColor Yellow

$startTime = Get-Date
try {
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/tax-reports/upload?tax_type=VAT" `
        -Method POST `
        -Headers @{
            "Authorization" = "Bearer $token"
        } `
        -Form @{
            "file" = Get-Item $testFile
        } `
        -TimeoutSec 30
    
    $elapsed = (Get-Date) - $startTime
    Write-Host "✅ 请求成功! 耗时: $($elapsed.TotalSeconds)s" -ForegroundColor Green
    Write-Host "响应: $($response | ConvertTo-Json -Depth 3)" -ForegroundColor White
} catch {
    $elapsed = (Get-Date) - $startTime
    Write-Host "❌ 请求失败! 耗时: $($elapsed.TotalSeconds)s" -ForegroundColor Red
    Write-Host "错误: $_" -ForegroundColor Red
    
    # 检查 HTTP 状态码
    if ($_.Exception.Response) {
        $statusCode = [int]$_.Exception.Response.StatusCode
        Write-Host "HTTP 状态码: $statusCode" -ForegroundColor Yellow
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "测试 5: 检查 Docker 日志（请求后）" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "查看最新的日志（应该有 tax-reports 相关）..." -ForegroundColor White
docker logs --tail 30 rag_backend 2>&1

Write-Host "`n查找 tax-reports 相关的日志..." -ForegroundColor White
docker logs --tail 100 rag_backend 2>&1 | Select-String -Pattern "tax-reports|upload|TaxUpload|TaxReport"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "测试 6: 使用 curl 测试（更详细）" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n使用 curl.exe 测试..." -ForegroundColor White
$curlCmd = "curl.exe -X POST `"http://127.0.0.1:8000/api/v1/tax-reports/upload?tax_type=VAT`" -H `"Authorization: Bearer $token`" -F `"file=@$testFile`" --max-time 30 -v"
Write-Host "命令: $curlCmd" -ForegroundColor Gray

Write-Host "`n执行中..." -ForegroundColor Yellow
Invoke-Expression $curlCmd 2>&1

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "测试 7: 检查中间件是否拦截" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "查看是否有 AUTH 相关的日志..." -ForegroundColor White
docker logs --tail 100 rag_backend 2>&1 | Select-String -Pattern "\[AUTH\]|Missing tenant|Token"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "诊断完成！" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n请告诉我:" -ForegroundColor Yellow
Write-Host "1. curl 测试的结果（成功还是失败）" -ForegroundColor White
Write-Host "2. Docker 日志中是否有 tax-reports 相关的记录" -ForegroundColor White
Write-Host "3. 如果有 AUTH 错误，请告诉我具体内容" -ForegroundColor White

Remove-Item $testFile -ErrorAction SilentlyContinue
