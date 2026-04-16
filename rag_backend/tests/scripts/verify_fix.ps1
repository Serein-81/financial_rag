Write-Host "=========================================="
Write-Host "Fix Verification Script"
Write-Host "=========================================="
Write-Host ""

$filePath = "D:\Python\Codebase\My_rag\rag_frontend\src\views\MultiAgentChatView.vue"
$content = Get-Content $filePath -Raw

Write-Host "[1/5] Checking file exists..."
if (Test-Path $filePath) {
    Write-Host "[OK] File exists"
} else {
    Write-Host "[FAIL] File not found"
    exit 1
}

Write-Host ""
Write-Host "[2/5] Checking simplified marked configuration..."
if ($content -match "marked\.setOptions\(\{[\s\S]*?breaks:\s*true[\s\S]*?gfm:\s*true[\s\S]*?\}\)") {
    Write-Host "[OK] Marked configuration simplified"
} else {
    Write-Host "[WARN] Marked configuration might not be simplified"
}

Write-Host ""
Write-Host "[3/5] Checking renderMarkdown function..."
$renderMarkdownPattern = "return DOMPurify\?\.sanitize\(html\) \|\| html \|\| content"
if ($content -match $renderMarkdownPattern) {
    Write-Host "[OK] renderMarkdown function simplified"
} else {
    Write-Host "[WARN] renderMarkdown might not be simplified"
}

Write-Host ""
Write-Host "[4/5] Checking custom renderers removed..."
$customRenderers = @(
    "renderer\.heading\s*=",
    "renderer\.paragraph\s*=",
    "renderer\.list\s*=",
    "renderer\.listitem\s*=",
    "renderer\.blockquote\s*=",
    "renderer\.hr\s*="
)

$foundCustomRenderers = 0
foreach ($pattern in $customRenderers) {
    if ($content -match $pattern) {
        $foundCustomRenderers++
    }
}

if ($foundCustomRenderers -eq 0) {
    Write-Host "[OK] All custom renderers removed"
} else {
    Write-Host "[WARN] Found $foundCustomRenderers custom renderers still present"
}

Write-Host ""
Write-Host "[5/5] Checking renderer.code is preserved..."
if ($content -match "renderer\.code\s*=") {
    Write-Host "[OK] renderer.code is preserved"
} else {
    Write-Host "[FAIL] renderer.code is missing"
    exit 1
}

Write-Host ""
Write-Host "[6/5] Checking markdown-content CSS..."
if ($content -match "\.markdown-content\s*\{") {
    Write-Host "[OK] markdown-content CSS present"
} else {
    Write-Host "[FAIL] markdown-content CSS missing"
    exit 1
}

Write-Host ""
Write-Host "=========================================="
Write-Host "VERIFICATION COMPLETE"
Write-Host "=========================================="
Write-Host ""
Write-Host "Next Steps:"
Write-Host "1. Force refresh browser: Ctrl + Shift + R"
Write-Host "2. Test input: 'analyze enterprise tax risk'"
Write-Host "3. Verify no 'undefined' appears"
Write-Host ""
Write-Host "Expected Result:"
Write-Host "- No 'undefined' displayed"
Write-Host "- Complete markdown content"
Write-Host "- Clear formatting"
Write-Host ""
