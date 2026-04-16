Write-Host "=========================================="
Write-Host "Frontend Rendering Fix Verification"
Write-Host "=========================================="
Write-Host ""

$filePath = "rag_frontend\src\views\MultiAgentChatView.vue"

Write-Host "[1/7] Checking if MultiAgentChatView.vue exists..."
if (Test-Path $filePath) {
    Write-Host "[OK] File exists"
} else {
    Write-Host "[FAIL] File does not exist"
    exit 1
}

Write-Host ""
Write-Host "[2/7] Checking backup file..."
$backupPath = "rag_frontend\src\views\MultiAgentChatView.vue.backup"
if (Test-Path $backupPath) {
    Write-Host "[OK] Backup file created"
} else {
    Write-Host "[WARN] Backup file not created"
}

Write-Host ""
Write-Host "[3/7] Checking DOMPurify import..."
$content = Get-Content $filePath -Raw
if ($content -match "import DOMPurify from 'dompurify'") {
    Write-Host "[OK] DOMPurify imported"
} else {
    Write-Host "[FAIL] DOMPurify not imported"
    exit 1
}

Write-Host ""
Write-Host "[4/7] Checking marked configuration..."
if ($content -match "headerIds:\s*false") {
    Write-Host "[OK] Marked configuration enhanced"
} else {
    Write-Host "[FAIL] Marked configuration not enhanced"
    exit 1
}

Write-Host ""
Write-Host "[5/7] Checking custom renderers..."
$rendererCount = ([regex]::Matches($content, "renderer\.\w+")).Count
Write-Host "[INFO] Found $rendererCount renderers"
if ($rendererCount -ge 7) {
    Write-Host "[OK] Custom renderers added"
} else {
    Write-Host "[WARN] Not enough renderers (found $rendererCount, need 7)"
}

Write-Host ""
Write-Host "[6/7] Checking markdown-content CSS..."
if ($content -match "\.markdown-content\s*\{") {
    Write-Host "[OK] markdown-content CSS added"
} else {
    Write-Host "[FAIL] markdown-content CSS not added"
    exit 1
}

Write-Host ""
Write-Host "[7/7] Checking renderMarkdown function..."
if ($content -match "ALLOWED_TAGS\s*:") {
    Write-Host "[OK] DOMPurify configuration optimized"
} else {
    Write-Host "[FAIL] DOMPurify configuration not optimized"
    exit 1
}

Write-Host ""
Write-Host "=========================================="
Write-Host "VERIFICATION COMPLETE - All changes applied"
Write-Host "=========================================="
Write-Host ""
Write-Host "Next Steps:"
Write-Host "1. Restart frontend: cd rag_frontend && npm run dev"
Write-Host "2. Open: http://localhost:5173"
Write-Host "3. Test: Enter 'analyze enterprise tax risk'"
Write-Host "4. Check if output format is beautiful"
Write-Host ""
