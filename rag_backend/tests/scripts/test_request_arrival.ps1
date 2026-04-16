# Test if requests reach the backend

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Test: Is request reaching backend?" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`nChecking Docker container status..." -ForegroundColor Yellow
$containerStatus = docker ps --filter "name=rag_backend" --format "{{.Status}}"
if ($containerStatus -match "Up") {
    Write-Host "OK: Docker running: $containerStatus" -ForegroundColor Green
} else {
    Write-Host "ERROR: Docker not running" -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Test 1: /debug/ping endpoint" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

try {
    $ping = Invoke-RestMethod -Uri "http://127.0.0.1:8000/debug/ping" -Method GET -TimeoutSec 10
    Write-Host "OK: /debug/ping success: $($ping | ConvertTo-Json)" -ForegroundColor Green
} catch {
    Write-Host "ERROR: /debug/ping failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Test 2: /debug/test-upload endpoint (using curl)" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

$testFile = "$env:TEMP\test_upload_verify.pdf"
Set-Content -Path $testFile -Value "%PDF-1.4 test content" -Encoding UTF8

Write-Host "Creating test file: $testFile" -ForegroundColor White
Write-Host "Sending test upload request using curl.exe..." -ForegroundColor White

Write-Host "`nDocker logs (before request):" -ForegroundColor Gray
docker logs --tail 5 rag_backend 2>&1

Write-Host "`nSending curl request..." -ForegroundColor Yellow
$curlCmd = "curl.exe -X POST `"http://127.0.0.1:8000/debug/test-upload`" -F `"file=@$testFile`" --max-time 30 -v 2>&1"
Write-Host "Command: $curlCmd" -ForegroundColor Gray

$curlResult = Invoke-Expression $curlCmd
Write-Host "`ncurl result:" -ForegroundColor White
Write-Host $curlResult

Start-Sleep -Seconds 1

Write-Host "`nDocker logs (after request):" -ForegroundColor Gray
docker logs --tail 20 rag_backend 2>&1

Write-Host "`nDoes log contain [TEST-UPLOAD]?" -ForegroundColor Yellow
$hasTestUpload = docker logs --tail 30 rag_backend 2>&1 | Select-String -Pattern "TEST-UPLOAD"
if ($hasTestUpload) {
    Write-Host "YES! Request reached container" -ForegroundColor Green
} else {
    Write-Host "NO! Request did NOT reach container (check curl output above)" -ForegroundColor Red
}

Remove-Item $testFile -ErrorAction SilentlyContinue

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Test 3: /api/v1/tax-reports/upload endpoint" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "Enter JWT Token:" -ForegroundColor Yellow
Write-Host "(In browser Console: localStorage.getItem('rag_token'))" -ForegroundColor Gray
$token = Read-Host "Token"

if ([string]::IsNullOrEmpty($token)) {
    Write-Host "SKIP: tax-reports test (needs Token)" -ForegroundColor Yellow
} else {
    $testFile = "$env:TEMP\test_tax_upload.pdf"
    Set-Content -Path $testFile -Value "%PDF-1.4 test content" -Encoding UTF8
    
    Write-Host "`nSending tax-reports upload request using curl..." -ForegroundColor White
    Write-Host "Command: curl.exe -X POST `"http://127.0.0.1:8000/api/v1/tax-reports/upload?tax_type=VAT`" -H `"Authorization: Bearer $token`" -F `"file=@$testFile`" --max-time 60 -v" -ForegroundColor Gray
    
    $curlCmd2 = "curl.exe -X POST `"http://127.0.0.1:8000/api/v1/tax-reports/upload?tax_type=VAT`" -H `"Authorization: Bearer $token`" -F `"file=@$testFile`" --max-time 60 -v 2>&1"
    $curlResult2 = Invoke-Expression $curlCmd2
    Write-Host "`ncurl result:" -ForegroundColor White
    Write-Host $curlResult2
    
    Start-Sleep -Seconds 1
    
    Write-Host "`nLatest Docker logs:" -ForegroundColor Yellow
    docker logs --tail 50 rag_backend 2>&1
    
    Write-Host "`nLooking for tax-reports logs:" -ForegroundColor Yellow
    docker logs --tail 100 rag_backend 2>&1 | Select-String -Pattern "tax-reports|TaxUpload|TaxReport"
    
    Remove-Item $testFile -ErrorAction SilentlyContinue
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Done!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`nKey questions:" -ForegroundColor Yellow
Write-Host "1. Did /debug/ping succeed?" -ForegroundColor White
Write-Host "2. Did /debug/test-upload succeed?" -ForegroundColor White
Write-Host "3. Does Docker log contain [TEST-UPLOAD]?" -ForegroundColor White
Write-Host "4. What is curl output for tax-reports upload?" -ForegroundColor White
