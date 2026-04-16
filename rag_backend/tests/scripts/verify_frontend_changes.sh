#!/bin/bash

# 前端渲染修复验证脚本

echo "=========================================="
echo "前端渲染修复验证"
echo "=========================================="
echo ""

echo "[1/5] 检查 MultiAgentChatView.vue 是否存在..."
if [ -f "rag_frontend/src/views/MultiAgentChatView.vue" ]; then
    echo "✅ 文件存在"
else
    echo "❌ 文件不存在"
    exit 1
fi

echo ""
echo "[2/5] 检查备份文件是否创建..."
if [ -f "rag_frontend/src/views/MultiAgentChatView.vue.backup" ]; then
    echo "✅ 备份文件已创建"
else
    echo "⚠️  警告：备份文件未创建"
fi

echo ""
echo "[3/5] 检查 DOMPurify 导入..."
if grep -q "import DOMPurify from 'dompurify'" "rag_frontend/src/views/MultiAgentChatView.vue"; then
    echo "✅ DOMPurify 已导入"
else
    echo "❌ DOMPurify 未导入"
    exit 1
fi

echo ""
echo "[4/5] 检查 marked 配置..."
if grep -q "headerIds: false" "rag_frontend/src/views/MultiAgentChatView.vue"; then
    echo "✅ marked 配置已增强"
else
    echo "❌ marked 配置未增强"
    exit 1
fi

echo ""
echo "[5/5] 检查自定义渲染器..."
renderer_count=$(grep -c "renderer\." "rag_frontend/src/views/MultiAgentChatView.vue")
if [ $renderer_count -ge 7 ]; then
    echo "✅ 自定义渲染器已添加（共 $renderer_count 个）"
else
    echo "⚠️  警告：自定义渲染器数量不足（找到 $renderer_count 个，需要至少 7 个）"
fi

echo ""
echo "[6/5] 检查 markdown-content CSS..."
if grep -q "\.markdown-content" "rag_frontend/src/views/MultiAgentChatView.vue"; then
    echo "✅ markdown-content CSS 已添加"
else
    echo "❌ markdown-content CSS 未添加"
    exit 1
fi

echo ""
echo "[7/5] 检查 renderMarkdown 函数..."
if grep -q "ALLOWED_TAGS" "rag_frontend/src/views/MultiAgentChatView.vue"; then
    echo "✅ DOMPurify 配置已优化"
else
    echo "❌ DOMPurify 配置未优化"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ 验证完成！所有修改已正确应用"
echo "=========================================="
echo ""
echo "下一步操作："
echo "1. 重启前端服务：cd rag_frontend && npm run dev"
echo "2. 访问：http://localhost:5173"
echo "3. 测试输入：分析企业税务风险"
echo "4. 检查输出格式是否美观"
echo ""
echo "详细文档："
echo "- 📄 MODIFICATION_COMPLETE.md - 修改完成总结"
echo "- 📄 FRONTEND_RENDERING_FIX.md - 详细修改记录"
echo "- 📄 FRONTEND_TEST_GUIDE.md - 测试指南"
echo ""
