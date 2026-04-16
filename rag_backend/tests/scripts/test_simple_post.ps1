# 极端诊断：找出请求卡在哪里

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "极端诊断：请求挂起问题" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n🔍 问题：上传请求挂起，后端无响应" -ForegroundColor Red
Write-Host "`n目标：找出请求卡在哪个环节" -ForegroundColor Yellow

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "步骤 1: 创建最简单的测试端点" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n正在创建测试端点..." -ForegroundColor White

docker exec rag_backend python << 'PYTHON_EOF'
import asyncio
from fastapi import FastAPI, UploadFile, File
from fastapi.routing import APIRoute
import logging

# 创建一个最简单的测试
test_code = '''
from fastapi import APIRouter, UploadFile, File
import asyncio

test_router = APIRouter()

@test_router.post("/test-simple-upload")
async def test_simple_upload(file: UploadFile = File(...)):
    return {"filename": file.filename, "size": file.size}

# 将测试路由添加到主应用
from app.main import app
app.include_router(test_router, prefix="/api/v1", tags=["Test"])
print("✅ 测试端点已添加: /api/v1/test-simple-upload")
'''

exec(test_code)
PYTHON_EOF

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "步骤 2: 测试简单的 POST 请求（不上传文件）" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n测试 /api/v1/tenant-settings/me ..." -ForegroundColor White
$start = Get-Date
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/tenant-settings/me" -TimeoutSec 10
    $end = Get-Date
    $elapsed = ($end - $start).TotalMilliseconds
    Write-Host "✅ 响应正常 (${elapsed}ms) - 状态码: $($response.StatusCode)" -ForegroundColor Green
} catch {
    $end = Get-Date
    $elapsed = ($end - $start).TotalMilliseconds
    Write-Host "❌ 请求失败 (${elapsed}ms): $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "步骤 3: 测试带文件上传的请求" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n创建测试文件..." -ForegroundColor White
$testFile = "$env:TEMP\test_upload.txt"
Set-Content -Path $testFile -Value "test content" -Encoding UTF8

Write-Host "`n测试 POST 请求到 /api/v1/test-simple-upload ..." -ForegroundColor White
$start = Get-Date
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/test-simple-upload" `
        -Method POST `
        -ContentType "multipart/form-data" `
        -InFile $testFile `
        -TimeoutSec 30
    $end = Get-Date
    $elapsed = ($end - $start).TotalMilliseconds
    Write-Host "✅ 响应正常 (${elapsed}ms) - 状态码: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "响应内容: $($response.Content)" -ForegroundColor Cyan
} catch {
    $end = Get-Date
    $elapsed = ($end - $start).TotalMilliseconds
    Write-Host "❌ 请求失败 (${elapsed}ms): $($_.Exception.Message)" -ForegroundColor Red
}

Remove-Item $testFile -ErrorAction SilentlyContinue

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "步骤 4: 检查容器当前处理的请求" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n查看当前容器的进程..." -ForegroundColor White
docker exec rag_backend ps aux 2>&1 | Select-Object -First 20

Write-Host "`n查看最近的日志..." -ForegroundColor White
docker logs --tail 50 rag_backend 2>&1

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "诊断完成" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
