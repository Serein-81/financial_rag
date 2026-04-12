# 前端 Markdown 渲染修复

## 修改时间
2026-04-11

## 修改文件
`rag_frontend/src/views/MultiAgentChatView.vue`

## 修改内容

### 1. 增强 marked 配置（第 54-68 行）
```javascript
marked.setOptions({
  breaks: true,
  gfm: true,
  headerIds: false,
  mangle: false
})
```

**添加的配置**：
- `headerIds: false`：禁用自动生成的 header ID
- `mangle: false`：禁用 header ID 混淆

### 2. 添加自定义渲染器（第 70-134 行）

**新增的渲染函数**：

1. **renderer.heading**
   - 为不同级别的标题添加 Tailwind 样式类
   - h1: text-2xl
   - h2: text-xl
   - h3: text-lg
   - 等等...

2. **renderer.paragraph**
   - 为段落添加 mb-4 和 leading-relaxed 样式
   - 确保行间距充足

3. **renderer.list**
   - 为有序列表和无序列表添加样式
   - ml-6 mb-4 space-y-1
   - 区分有序（list-decimal）和无序（list-disc）列表

4. **renderer.listitem**
   - 为列表项添加 ml-4 和 leading-relaxed
   - 确保列表项之间的间距

5. **renderer.blockquote**
   - 添加左侧蓝色边框（border-l-4 border-blue-500）
   - 添加灰色背景（bg-gray-50）
   - 斜体样式

6. **renderer.hr**
   - 添加分隔线样式
   - my-6 border-gray-300

### 3. 增强 DOMPurify 配置（第 1125-1149 行）

**ALLOWED_TAGS**（允许的标签）：
- 文本标签：p, br, strong, em, u, s, code, pre
- 标题标签：h1, h2, h3, h4, h5, h6
- 列表标签：ul, ol, li
- 引用标签：blockquote
- 链接标签：a, img
- 表格标签：table, thead, tbody, tr, th, td
- 其他标签：hr, span, div

**ALLOWED_ATTR**（允许的属性）：
- href, src, alt, class, target, rel

### 4. 添加 Markdown 样式（第 1837-1957 行）

**新增的 CSS 类** `.markdown-content`：

```css
.markdown-content {
  line-height: 1.8;           /* 增加行高 */
  letter-spacing: 0.02em;    /* 增加字间距 */
}

.markdown-content p {
  margin-bottom: 1rem;        /* 段落间距 */
}

.markdown-content ul,
.markdown-content ol {
  margin: 1rem 0;
  padding-left: 1.5rem;
}

.markdown-content li {
  margin: 0.5rem 0;
}

.markdown-content h1-h4 {
  margin-top: 1.5rem;
  margin-bottom: 1rem;
  font-weight: 600;
  line-height: 1.4;
}

.markdown-content blockquote {
  margin: 1rem 0;
  padding: 0.75rem 1rem;
  border-left: 4px solid #3b82f6;
  background-color: #f9fafb;
}

.markdown-content pre {
  margin: 1rem 0;
  overflow-x: auto;
}

.markdown-content code {
  font-family: 'Courier New', Courier, monospace;
  background-color: #f3f4f6;
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
  font-size: 0.875em;
}

.markdown-content hr {
  margin: 1.5rem 0;
  border: none;
  border-top: 1px solid #e5e7eb;
}
```

### 5. 更新渲染 div（第 1342 行）

```vue
<div class="prose prose-sm max-w-none markdown-content" v-html="renderMarkdown(msg.content)"></div>
```

添加了 `markdown-content` class。

## 备份文件
- `MultiAgentChatView.vue.backup`：原始文件的完整备份

## 预期效果

修改后，前端应该能够正确显示：

1. ✅ **清晰的标题层级**：不同级别的标题有不同的字体大小
2. ✅ **良好的段落间距**：每个段落之间有充足的间距
3. ✅ **漂亮的列表样式**：缩进正确，项目符号清晰
4. ✅ **优雅的引用块**：左侧有蓝色边框，背景为浅灰色
5. ✅ **合理的代码块**：带语法高亮和复制按钮
6. ✅ **明确的分隔线**：章节之间有水平线分隔

## 测试步骤

1. 重启前端服务：
   ```bash
   cd rag_frontend
   npm run dev
   ```

2. 访问 http://localhost:5173

3. 在输入框中输入："分析企业税务风险"

4. 检查输出是否：
   - 标题层级清晰
   - 段落之间有适当间距
   - 列表项缩进正确
   - 引用块有蓝色边框
   - 整体美观易读

## 回滚方法

如果修改后出现问题，可以恢复备份：

```bash
cp MultiAgentChatView.vue.backup MultiAgentChatView.vue
```

然后重启前端服务即可。

## 相关文件

- **后端格式化代码**：`rag_backend/app/multi_agent_system/orchestrator.py`
  - 方法：`_format_no_data_response`（第 2040-2126 行）
  - 状态：✅ 已确认生成正确的 Markdown

- **输出智能体**：`rag_backend/app/agent_framework/core/output_agent.py`
  - 方法：`_clean_output`（第 932-1011 行）
  - 状态：✅ 已修复，不再破坏表格格式

- **提示词文件**：
  - `rag_backend/app/prompts/output_agent/system_prompt.txt`
  - `rag_backend/app/prompts/output_agent/synthesis_prompt.txt`
  - 状态：✅ 已强化格式要求
