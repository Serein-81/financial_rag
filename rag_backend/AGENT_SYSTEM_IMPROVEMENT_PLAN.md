# Agent 系统改进方案（精简版）

> **文档版本**: v2.0  
> **更新日期**: 2025年1月  
> **核心原则**: 复用现有代码，最小化改动，渐进式改进

---

## 1. 需求回顾与反馈

| 原始需求 | 用户反馈 | 调整后方案 |
|----------|----------|------------|
| 新增 _schemas/ 和 _constraints/ 目录 | 不要新增目录，看现有文件能否补充 | 利用 `agent.yaml` 补充约束定义 |
| 新增 ToolDecisionEngine | 暂不修改，先根据描述选择 | 暂不实现 |
| 新增 evaluation/ 目录 | 质疑作用 | 暂不实现，按需后续添加 |
| 代码规范、鲁棒性 | 第一原则 | 全程遵循 |

---

## 2. 精简后的改进计划

### 2.1 改进一：OutputAgent 输出约束增强（唯一需要改动的）

**现状分析**：
- `agent.yaml` 已有 `constraints` 和 `quality_rules` 定义
- `synthesis.md` 已有基本结构
- **无需新增任何目录**

**改动范围**：

| 文件 | 改动类型 | 改动内容 |
|------|----------|----------|
| `agent.yaml` | 补充 | 增加输出格式约束、JSON Schema 定义 |
| `synthesis.md` | 补充 | 增加输出约束引用、格式要求说明 |
| `OutputAgentPrompts` (Python) | 补充 | 支持从 agent.yaml 读取约束 |

**具体改动**：

#### 2.1.1 补充 agent.yaml

```yaml
# 在现有 constraints 下补充

constraints:
  max_inputs: 10
  quality_score_min: 0.6
  length_limits:
    min_chars: 50
    max_chars: 2500
  timeout_seconds: 60

# 新增：输出格式约束
output_constraints:
  format: "markdown"
  json_required: false  # 是否强制返回 JSON
  
  # 新增：JSON 输出格式（可选）
  json_schema:
    required_fields:
      - "summary"
      - "key_points"
      - "recommendations"
    optional_fields:
      - "confidence"
      - "disclaimer"
      - "source_references"
    field_constraints:
      summary:
        min_length: 50
        max_length: 300
        description: "整体总结"
      key_points:
        min_items: 3
        max_items: 5
        item_max_length: 200
      recommendations:
        min_items: 1
        max_items: 3
        item_max_length: 150

  # 新增：Markdown 输出格式
  markdown_format:
    title_max_length: 20
    paragraph_max_length: 200
    use_emoji: true
    allowed_emoji_positions: ["title", "important", "suggestion"]
    min_paragraphs: 3
    max_paragraphs: 5
```

#### 2.1.2 补充 synthesis.md

```markdown
# 综合整合提示词

## 输入变量

| 变量名 | 类型 | 描述 | 示例 |
|--------|------|------|------|
| {user_query} | string | 用户原始问题 | "如何优化企业税务？" |
| {specialist_results} | string | 专家分析结果 | 多专家的输出内容 |
| {output_type} | string | 输出类型 | "summary"/"detailed"/"actionable" |
| {format_preference} | string | 格式偏好 | "markdown"/"json" |

## 输出约束（来自 agent.yaml）

{% set constraints = load_constraints("output_agent") %}

### 长度约束
- 最小长度：{{ constraints.length_limits.min_chars }} 字符
- 最大长度：{{ constraints.length_limits.max_chars }} 字符
- 段落数：{{ constraints.markdown_format.min_paragraphs }}-{{ constraints.markdown_format.max_paragraphs }}

### 格式要求
{% if format_preference == "json" %}
请严格按照以下 JSON 格式输出：

```json
{
  "summary": "整体总结（50-300字符）",
  "key_points": [
    {
      "title": "要点标题（≤20字符）",
      "description": "要点描述（≤200字符）",
      "source": "来源专家（可选）"
    }
  ],
  "recommendations": ["建议1", "建议2"],
  "confidence": 0.85{% if constraints.optional_fields and "disclaimer" in constraints.optional_fields %},
  "disclaimer": "此建议仅供参考"{% endif %}
}
```
{% else %}
请使用 Markdown 格式输出：

- 使用1-2级标题
- 每段不超过 {{ constraints.markdown_format.paragraph_max_length }} 字符
- 如需强调，使用 **粗体**
- 如需列表，使用有序或无序列表
{% endif %}

## 结构要求

{% if output_type == "summary" %}
- 简短总结式回答
- 3个以内关键点
- 可选行动建议
{% elif output_type == "detailed" %}
- 详细分析式回答
- 5个以上关键点
- 含来源标注
{% elif output_type == "actionable" %}
- 行动导向式回答
- 明确的步骤建议
- 预期结果说明
{% endif %}
```

### 2.2 改进二：其他需求（暂不实现）

| 需求 | 状态 | 原因 |
|------|------|------|
| 工具决策机制 | 暂不实现 | 先用现有描述匹配方式 |
| 评估目录 | 暂不实现 | reflection_agent 已足够 |
| 记忆机制 | 已有 | MemoryManager 三层架构完善 |
| A2A 扩展 | 已有 | 基础协议已完整 |

---

## 3. 实施步骤

### 第一步：修改 agent.yaml（5分钟）

在现有 `constraints` 后补充 `output_constraints` 配置。

### 第二步：修改 synthesis.md（10分钟）

添加输出约束说明和格式要求。

### 第三步：测试验证（15分钟）

运行测试确保输出格式符合约束。

---

## 4. 代码规范检查清单

- [ ] 类型注解完整
- [ ] 错误处理完善
- [ ] 日志记录适当
- [ ] 向后兼容（fallback 机制）
- [ ] 单元测试覆盖

---

## 5. 总结

**本次改动范围**：
- 仅修改 2 个文件（`agent.yaml`、`synthesis.md`）
- 不新增任何目录或文件
- 完全复用现有代码

**后续扩展方向**（按需实现）：
1. ToolDecisionEngine - 智能工具选择
2. 评估提示词文件化 - 工具执行评估
3. A2A 消息扩展 - 工具状态报告

---

> **下一步**：如需开始实施，请确认，我将修改 `agent.yaml` 和 `synthesis.md` 文件。
