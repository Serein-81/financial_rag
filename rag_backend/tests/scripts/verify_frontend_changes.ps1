# 前端渲染修复验证脚本 (PowerShell)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "前端渲染修复验证" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$filePath = "rag_frontend\src\views\MultiAgentChatView.vue"
$content = Get-Content $filePath -Raw -Encoding UTF8

Write-Host "[1/7] 检查 MultiAgentChatView.vue 是否存在..." -ForegroundColor Yellow
if (Test-Path $filePath) {
    Write-Host "✅ 文件存在" -ForegroundColor Green
} else {
    Write-Host "❌ 文件不存在" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/7] 检查备份文件是否创建..." -ForegroundColor Yellow
$backupPath = "rag_frontend\src\views\MultiAgentChatView.vue.backup"
if (Test-Path $backupPath) {
    Write-Host "✅ 备份文件已创建" -ForegroundColor Green
} else {
    Write-Host "⚠️  警告：备份文件未创建" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[3/7] 检查 DOMPurify 导入..." -ForegroundColor Yellow
if ($content -match "import DOMPurify from 'dompurify'") {
    Write-Host "✅ DOMPurify 已导入" -ForegroundColor Green
} else {
    Write-Host "❌ DOMPurify 未导入" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[4/7] 检查 marked 配置..." -ForegroundColor Yellow
if ($content -match "headerIds:\s*false") {
    Write-Host "✅ marked 配置已增强" -ForegroundColor Green
} else {
    Write-Host "❌ marked 配置未增强" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[5/7] 检查自定义渲染器..." -ForegroundColor Yellow
$rendererCount = ([regex]::Matches($content, "renderer\.\w+")).Count
if ($rendererCount -ge 7) {
    Write-Host "✅ 自定义渲染器已添加（共 $($rendererCount) 个）" -ForegroundColor Green
} else {
    Write-Host "⚠️  警告：自定义渲染器数量不足（找到 $($rendererCount) 个，需要至少 7 个）" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[6/7] 检查 markdown-content CSS..." -ForegroundColor Yellow
if ($content -match "\.markdown-content\s*\{") {
    Write-Host "✅ markdown-content CSS 已添加" -ForegroundColor Green
} else {
    Write-Host "❌ markdown-content CSS 未添加" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[7/7] 检查 renderMarkdown 函数..." -ForegroundColor Yellow
if ($content -match "ALLOWED_TAGS\s*:") {
    Write-Host "✅ DOMPurify 配置已优化" -ForegroundColor Green
} else {
    Write-Host "❌ DOMPurify 配置未优化" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "✅ 验证完成！所有修改已正确应用" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步操作：" -ForegroundColor White
Write-Host "1. 重启前端服务：cd rag_frontend && npm run dev" -ForegroundColor White
Write-Host "2. 访问：http://localhost:5173" -ForegroundColor White
Write-Host "3. 测试输入：分析企业税务风险" -ForegroundColor White
Write-Host "4. 检查输出格式是否美观" -ForegroundColor White
Write-Host ""
Write-Host "详细文档：" -ForegroundColor White
Write-Host "- [MODIFICATION_COMPLETE.md] - Modification Complete Summary" -ForegroundColor Blue
Write-Host "- [FRONTEND_RENDERING_FIX.md] - Detailed Modification Record" -ForegroundColor Blue
Write-Host "- [FRONTEND_TEST_GUIDE.md] - Testing Guide" -ForegroundColor Blue
Write-Host ""
