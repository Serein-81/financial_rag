# 意图分类提示词

## 任务描述

分析以下用户输入的意图，并返回结构化的JSON分析结果。

## 输入信息

```
用户输入：{user_input}

已识别的实体：{entities}
```

## 输出要求

请返回JSON格式的意图分析：

```json
{{
  "intent": "意图类别",
  "sub_intent": "子意图（可选）",
  "params": {{"建议参数"}},
  "confidence": 0.0-1.0,
  "reasoning": "推理过程",
  "needs_report_generation": true/false
}}
```

## 意图类别说明

### 日常类
- **greeting**: 问候语（如"你好"、"您好"、"hi"等）
- **chit_chat**: 闲聊内容

### 知识类
- **knowledge_query**: 知识库查询
- **document_search**: 文档搜索

### 财务类
- **financial_analysis**: 财务分析（财务报表、利润分析、资产分析等）
- **accounting_query**: 会计核算
- **investment_advisory**: 投资咨询
- **cost_control**: 成本控制
- **risk_analysis**: 风险分析（财务风险、信用风险、经营风险等）

### 税务类
- **tax_calculation**: 税务计算
- **tax_planning**: 税务筹划
- **tax_compliance**: 税务合规
- **tax_declaration**: 税务申报
- **tax_risk**: 税务风险

### 法务类
- **contract_review**: 合同审查
- **legal_consultation**: 法律咨询
- **compliance_check**: 合规检查
- **ip_protection**: 知识产权

### 报告类
- **report_generation**: 报告生成
- **data_extraction**: 数据提取

### 复杂类
- **complex_task**: 复杂任务（需要多专家协作）
- **multi_specialist**: 多专家协作

### 其他
- **unknown**: 未知意图

## 特殊标记

### needs_report_generation

当用户明确要求生成报告时，设置为 `true`。

**触发关键词**：
- "生成报告"、"生成一份报告"、"输出一份报告"
- "给我一份报告"、"给我报告"、"需要报告"
- "生成分析报告"、"生成财务报告"、"生成税务报告"
- "生成分析文档"、"生成分析材料"、"请生成报告"

## 分类规则

1. **问候语检测**：如果输入是"你好"、"您好"、"hi"、"hello"、"嗨"等，返回 `greeting`
2. **闲聊检测**：如果输入不包含实质性问题，返回 `chit_chat`
3. **财务关键词**：包含"财务"、"报表"、"利润"、"成本"、"投资"、"资产"、"负债"等 → `financial_analysis`
4. **风险关键词**：包含"风险"、"风险分析"、"信用风险"、"经营风险"、"财务风险"、"风险评估"等 → `risk_analysis`
5. **税务关键词**：包含"税务"、"税"、"发票"、"申报"、"抵扣"等 → `tax_calculation`
6. **法务关键词**：包含"法律"、"合同"、"合规"、"条款"、"违约"等 → `legal_consultation`
7. **报告要求**：用户明确要求生成报告 → `needs_report_generation: true`
8. **多专家检测**：问题涉及多个领域 → `complex_task` 或 `multi_specialist`

## 置信度指南

- **0.9-1.0**: 非常确定（包含明确的领域关键词）
- **0.7-0.9**: 较确定（有相关关键词但不够明确）
- **0.5-0.7**: 一般确定（需要结合上下文判断）
- **< 0.5**: 不太确定（建议使用规则匹配兜底）

## 示例

### 示例1：简单财务查询
输入："分析一下我们公司的财务状况"
```json
{{
  "intent": "financial_analysis",
  "confidence": 0.85,
  "reasoning": "检测到'财务'关键词，涉及财务状况分析",
  "needs_report_generation": false
}}
```

### 示例2：要求生成报告
输入："分析企业的财务风险，生成一份报告"
```json
{{
  "intent": "financial_analysis",
  "confidence": 0.9,
  "reasoning": "检测到'财务'和'风险'关键词，用户明确要求生成报告",
  "needs_report_generation": true
}}
```

### 示例3：税务问题
输入："我们公司这个月需要交多少增值税？"
```json
{{
  "intent": "tax_calculation",
  "params": {{"tax_type": "增值税"}},
  "confidence": 0.92,
  "reasoning": "检测到'增值税'关键词，涉及税务计算",
  "needs_report_generation": false
}}
```
