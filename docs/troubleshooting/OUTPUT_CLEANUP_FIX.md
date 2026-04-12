# 输出格式问题根因分析报告

## 📋 问题诊断日期
2026-04-11

## 🎯 问题描述

用户反馈输出"没有换行和结构"，从实际输出看：
1. **表格格式完全错误**：`| | 风险类别 |` 而不是 `| 风险类别 |`
2. **内容被截断**：如 "✅ 稽查应对预案定制 | **📅 服务时效**3"
3. **列表项格式混乱**：编号列表后直接跟列表项，没有换行
4. **段落间距不足**：内容紧凑，阅读体验差

---

## 🔍 根本原因分析

### 问题1：`_clean_output` 方法严重破坏表格格式

**位置**：`output_agent.py` 第983-989行（修改前）

**原始代码**：
```python
if line.strip().startswith('|') and line.strip().endswith('|'):
    cells = line.split('|')
    processed_cells = []
    for cell in cells:
        cell_text = cell.strip()
        if len(cell_text) > 50:
            cell_text = cell_text[:47] + '...'
        processed_cells.append(cell_text)
    line = '| ' + ' | '.join(processed_cells) + ' |'
```

**问题分析**：
- `split('|')` 会产生空字符串元素（开头和结尾）
- `cell.strip()` 后变成空字符串
- 然后用 `'| ' + ' | '.join(processed_cells) + ' |'` 重新拼接
- 导致每个单元格前都多了一个 `|` 符号

**结果对比**：

❌ **修改前（错误输出）**：
```markdown
| | 风险类别 | 典型表现 | 建议措施 | |
| | ---------- | ---------- | ---------- | |
| | 申报风险 | 申报时间延误 | 按时申报 | |
```

✅ **修改后（正确输出）**：
```markdown
| 风险类别 | 典型表现 | 建议措施 |
|----------|----------|----------|
| 申报风险 | 申报时间延误 | 按时申报 |
```

---

### 问题2：表格单元格强制截断

**原始代码**：
```python
if len(cell_text) > 50:
    cell_text = cell_text[:47] + '...'
```

**问题分析**：
- 强制截断超过50字符的单元格内容
- 导致内容不完整，如 "✅ 稽查应对预案定制 | **📅 服务时效**3"
- 用户无法获得完整信息

**修改**：
- ✅ 移除了强制截断逻辑
- ✅ 保留表格单元格内容完整性

---

### 问题3：段落空格过度清理

**原始代码**：
```python
cleaned = re.sub(r'\n\s{2,}', '\n', cleaned)
```

**问题分析**：
- 会移除所有换行后跟2个或更多空格的字符
- 影响列表项、段落格式

**修改**：
```python
# 只移除非表格行的多余空格
if line.strip().startswith('|'):
    processed_lines.append(line)  # 保留表格行原样
else:
    processed_lines.append(line.strip())
```

---

### 问题4：Emoji限制过于严格

**原始代码**：
```python
if len(emojis) > 2:
    # 只保留前2个emoji
```

**问题分析**：
- 限制每行最多2个emoji
- 但在提示词中已经限制不超过5个emoji
- 双重限制导致不一致

**修改**：
```python
if line.strip().startswith('|'):
    # 表格行：移除emoji但移除控制字符
    line = emoji_pattern.sub('', line)
else:
    # 非表格行：限制每行最多3个emoji
    emojis = emoji_pattern.findall(line)
    if len(emojis) > 3:
        line = emoji_pattern.sub(lambda m: '' if m.group() in emojis[3:] else m.group(), line)
```

---

## 📊 测试验证

### 测试代码
```python
test_content = """## 企业税务风险分析报告

| 风险类别 | 典型表现 | 建议措施 |
|----------|----------|----------|
| 申报风险 | 申报时间延误、税额计算错误 | 按时申报、仔细核对 |
"""
```

### 测试结果

#### ❌ 原始 `_clean_output` 输出（379字符，表格格式错误）：
```markdown
| | 风险类别 | 典型表现 | 建议措施 | |
| | ---------- | ---------- | ---------- | |
| | 申报风险 | 申报时间延误、税额计算错误 | 按时申报、仔细核对 | |
```

#### ✅ 新的 `_clean_output` 输出（349字符，表格格式正确）：
```markdown
| 风险类别 | 典型表现 | 建议措施 |
|----------|----------|----------|
| 申报风险 | 申报时间延误、税额计算错误 | 按时申报、仔细核对 |
```

---

## 🔧 修复方案

### 1. 移除表格格式破坏逻辑

**修改位置**：`output_agent.py` 第983-989行

**修改前**：
```python
if line.strip().startswith('|') and line.strip().endswith('|'):
    cells = line.split('|')
    processed_cells = []
    for cell in cells:
        cell_text = cell.strip()
        if len(cell_text) > 50:
            cell_text = cell_text[:47] + '...'
        processed_cells.append(cell_text)
    line = '| ' + ' | '.join(processed_cells) + ' |'
processed_lines.append(line)
```

**修改后**：
```python
# 只移除非表格行的多余空格
if line.strip().startswith('|'):
    # 保留表格行原样
    processed_lines.append(line)
else:
    # 非表格行移除首尾空格
    processed_lines.append(line.strip())
```

### 2. 移除表格单元格截断逻辑

**修改前**：
```python
if len(cell_text) > 50:
    cell_text = cell_text[:47] + '...'
```

**修改后**：
```python
# 不再截断单元格内容
```

### 3. 优化段落空格清理逻辑

**修改前**：
```python
cleaned = re.sub(r'\n\s{2,}', '\n', cleaned)
```

**修改后**：
```python
lines = cleaned.split('\n')
processed_lines = []
for line in lines:
    if line.strip().startswith('|'):
        processed_lines.append(line)
    else:
        processed_lines.append(line.strip())
cleaned = '\n'.join(processed_lines)
```

### 4. 调整Emoji限制

**修改前**：
```python
if len(emojis) > 2:
    # 只保留前2个emoji
```

**修改后**：
```python
if line.strip().startswith('|'):
    # 表格行：移除emoji
    line = emoji_pattern.sub('', line)
else:
    # 非表格行：限制每行最多3个emoji
    if len(emojis) > 3:
        line = emoji_pattern.sub(...)
```

---

## 📁 修改文件清单

1. **output_agent.py** - 修复 `_clean_output` 方法
   - 移除表格格式破坏逻辑（第983-989行）
   - 移除单元格截断逻辑
   - 优化段落空格清理
   - 调整Emoji限制

2. **system_prompt.txt** - 优化提示词
   - 放宽长度限制（800-1500 → 1500-2500字符）
   - 添加明确的表格格式规范
   - 新增质量标准

3. **synthesis_prompt.txt** - 优化合成提示词
   - 放宽长度限制
   - 添加表格格式警告
   - 新增质量检查清单

4. **orchestrator.py** - 添加 `max_tokens=4000` 参数
   - 避免输出被截断

---

## 🚀 预期效果

### 美观性提升
- ✅ **表格格式正确**：`| 风险类别 |` 而不是 `| | 风险类别 |`
- ✅ **内容完整**：不会被强制截断
- ✅ **列表规范**：编号列表格式正确
- ✅ **段落清晰**：内容层次分明

### 可读性提升
- ✅ **信息完整**：保留所有重要信息
- ✅ **格式规范**：Markdown格式正确
- ✅ **用户体验**：阅读流畅，赏心悦目

---

## ⚠️ 注意事项

### 1. 缓存问题
- 提示词文件可能被缓存
- 修改后需要重启后端服务

### 2. 测试建议
- 重启后端后先测试"分析企业税务风险"
- 验证表格格式是否正确
- 验证内容是否完整
- 验证段落是否有适当间距

### 3. 性能影响
- 不再截断内容，token消耗会略微增加
- 但用户体验显著提升，值得

---

## 📝 总结

### 核心问题
输出没有换行和结构的原因**不是前端不支持**，而是**后端的 `_clean_output` 方法过度清理了内容**，导致：
1. 表格格式被破坏
2. 内容被截断
3. 段落间距不足

### 修复方案
优化 `_clean_output` 方法，移除破坏性的清理逻辑，保留Markdown格式的完整性。

### 验证方法
重启后端服务后，输入"分析企业税务风险"，验证：
- ✅ 表格格式是否正确
- ✅ 内容是否完整
- ✅ 段落是否有适当间距
- ✅ 整体美观度是否提升

---

**文档版本**: v1.0
**最后更新**: 2026-04-11
**问题诊断**: AI Assistant
**修复执行**: AI Assistant
