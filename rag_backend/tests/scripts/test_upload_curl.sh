# 上传接口测试脚本
# 用法: .\test_upload_curl.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "测试税务报告上传接口" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 配置
$BACKEND_URL = "http://127.0.0.1:8000"
$TOKEN = ""  # 在这里填入你的 token，或者让脚本自动从 localStorage 获取

# 创建测试 PDF 文件
$testFilePath = "$env:TEMP\test_upload_$(Get-Date -Format 'yyyyMMddHHmmss').pdf"
$testContent = "%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 5 0 R
>>
>>
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
5 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000362 00000 n 
trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
437
%%EOF" 

# 保存测试文件
$testContent | Out-File -FilePath $testFilePath -Encoding UTF8
Write-Host "测试文件已创建: $testFilePath" -ForegroundColor Green

# 检查 token
if ([string]::IsNullOrEmpty($TOKEN)) {
    Write-Host "`n请提供 Token:" -ForegroundColor Yellow
    Write-Host "1. 登录前端应用" -ForegroundColor White
    Write-Host "2. 打开开发者工具 (F12) -> Application -> Local Storage" -ForegroundColor White
    Write-Host "3. 找到 rag_token 的值" -ForegroundColor White
    Write-Host "4. 重新运行脚本: .\test_upload_curl.ps1 -TOKEN 'your_token_here'" -ForegroundColor White
    Write-Host "`n或者直接在浏览器控制台执行以下代码获取 token:" -ForegroundColor Yellow
    Write-Host 'copy(localStorage.getItem("rag_token"))' -ForegroundColor Gray
    
    # 清理测试文件
    Remove-Item $testFilePath -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "`n正在测试上传接口..." -ForegroundColor Cyan

# 发送上传请求
try {
    $response = Invoke-WebRequest -Uri "$BACKEND_URL/api/v1/tax-reports/upload?tax_type=VAT" `
        -Method Post `
        -Headers @{
            "Authorization" = "Bearer $TOKEN"
        } `
        -FormFile $testFilePath `
        -ContentType "multipart/form-data" `
        -TimeoutSec 30 `
        -ErrorAction Stop

    Write-Host "`n✅ 上传成功!" -ForegroundColor Green
    Write-Host "状态码: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "响应内容:" -ForegroundColor Green
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
}
catch {
    Write-Host "`n❌ 上传失败!" -ForegroundColor Red
    Write-Host "错误: $($_.Exception.Message)" -ForegroundColor Red
    
    if ($_.Exception.Response) {
        Write-Host "`n响应状态: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Yellow
        
        try {
            $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
            $responseBody = $reader.ReadToEnd()
            $reader.Close()
            Write-Host "响应内容: $responseBody" -ForegroundColor Yellow
        }
        catch {
            Write-Host "无法读取响应内容" -ForegroundColor Yellow
        }
    }
    
    Write-Host "`n诊断建议:" -ForegroundColor Cyan
    Write-Host "1. 确认后端已启动: curl $BACKEND_URL/health" -ForegroundColor White
    Write-Host "2. 确认 Token 有效" -ForegroundColor White
    Write-Host "3. 检查后端日志" -ForegroundColor White
}

# 清理测试文件
Remove-Item $testFilePath -ErrorAction SilentlyContinue
Write-Host "`n测试文件已清理" -ForegroundColor Gray
