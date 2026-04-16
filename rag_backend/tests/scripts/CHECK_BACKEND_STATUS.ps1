# Backend Status Diagnostic Script
# Purpose: Check if backend is running and if requests are reaching it

Write-Host "=== Backend Status Diagnostic ===" -ForegroundColor Cyan

# 1. Check Docker containers
Write-Host "`n[1] Docker Containers Status:" -ForegroundColor Yellow
docker ps --filter "name=rag_" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 2. Check backend logs (last 20 lines)
Write-Host "`n[2] Backend Logs (last 20 lines):" -ForegroundColor Yellow
docker logs rag_backend --tail 20 2>&1

# 3. Test backend connectivity
Write-Host "`n[3] Backend Connectivity Test:" -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/" -TimeoutSec 5 -UseBasicParsing
    Write-Host "Backend is reachable: $($response.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "Backend is NOT reachable: $($_.Exception.Message)" -ForegroundColor Red
}

# 4. Test ping endpoint
Write-Host "`n[4] Testing /debug/ping endpoint:" -ForegroundColor Yellow
try {
    $pingResponse = Invoke-WebRequest -Uri "http://localhost:8000/debug/ping" -TimeoutSec 5 -UseBasicParsing
    Write-Host "Ping OK: $($pingResponse.Content)" -ForegroundColor Green
} catch {
    Write-Host "Ping failed: $($_.Exception.Message)" -ForegroundColor Red
}

# 5. Test OpenAPI docs
Write-Host "`n[5] Testing OpenAPI docs:" -ForegroundColor Yellow
try {
    $docsResponse = Invoke-WebRequest -Uri "http://localhost:8000/docs" -TimeoutSec 5 -UseBasicParsing
    Write-Host "Docs available: $($docsResponse.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "Docs failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== Diagnostic Complete ===" -ForegroundColor Cyan
Write-Host "`nPlease check:" -ForegroundColor Yellow
Write-Host "1. Make sure Docker containers are running"
Write-Host "2. Check if there are any errors in backend logs"
Write-Host "3. Open browser console (F12) to see frontend debug logs"
Write-Host "4. Check browser Network tab to see if request is sent"
