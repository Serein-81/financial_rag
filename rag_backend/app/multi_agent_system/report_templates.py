# app/multi_agent_system/report_templates.py
"""
报告模板系统 - Phase 7
支持多种报告类型和自定义模板
"""
from typing import Dict, Any, Optional
from enum import Enum
from jinja2 import Template


class ReportType(Enum):
    """报告类型"""
    SIMPLE = "simple"      # 简版报告
    STANDARD = "standard"  # 标准报告
    PROFESSIONAL = "professional"  # 专业报告


class ReportTemplates:
    """报告模板管理器"""
    
    def __init__(self):
        self.templates = {
            ReportType.SIMPLE: self._get_simple_template(),
            ReportType.STANDARD: self._get_standard_template(),
            ReportType.PROFESSIONAL: self._get_professional_template()
        }
        print("[报告模板] 初始化完成，加载 3 种模板")
    
    def render(
        self, 
        report_type: ReportType, 
        data: Dict[str, Any],
        custom_template: Optional[str] = None
    ) -> str:
        """
        渲染报告模板
        
        Args:
            report_type: 报告类型
            data: 报告数据
            custom_template: 自定义模板（可选）
        
        Returns:
            渲染后的报告文本
        """
        if custom_template:
            template = Template(custom_template)
        else:
            template = Template(self.templates.get(report_type, self.templates[ReportType.STANDARD]))
        
        return template.render(**data)
    
    def _get_simple_template(self) -> str:
        """简版报告模板 - 只包含执行摘要和风险清单"""
        return """
# 审查报告（简版）

## 基本信息
- 任务ID: {{ task_id }}
- 审查类型: {{ audit_type }}
- 生成时间: {{ created_at }}
- 处理时间: {{ processing_time }}秒

## 执行摘要
{{ summary }}

## 风险评分
- 综合风险分数: {{ overall_risk_score }}/100
- 总发现数: {{ total_findings }}
- 高风险: {{ high_risk_count }}
- 中风险: {{ medium_risk_count }}
- 低风险: {{ low_risk_count }}

## 风险清单

### 高风险问题
{% for action in immediate_actions %}
- {{ action }}
{% endfor %}

### 建议优化
{% for rec in recommendations %}
- {{ rec }}
{% endfor %}

---
报告生成时间: {{ created_at }}
"""
    
    def _get_standard_template(self) -> str:
        """标准报告模板 - 包含详细发现和改进建议"""
        return """
# 审查报告（标准版）

## 1. 基本信息
- **任务ID**: {{ task_id }}
- **租户ID**: {{ tenant_id }}
- **审查类型**: {{ audit_type }}
- **生成时间**: {{ created_at }}
- **处理时间**: {{ processing_time }}秒
- **重做次数**: {{ rework_count }}

## 2. 执行摘要
{{ summary }}

## 3. 风险评估

### 3.1 综合风险分数
**{{ overall_risk_score }}/100**

### 3.2 风险分布
- 高风险问题: {{ high_risk_count }} 个
- 中风险问题: {{ medium_risk_count }} 个
- 低风险问题: {{ low_risk_count }} 个
- 总计: {{ total_findings }} 个

### 3.3 置信度评估
{% for domain, score in confidence_scores.items() %}
- {{ domain }}: {{ "%.0f"|format(score * 100) }}%
{% endfor %}

## 4. 详细发现

### 4.1 财务审查发现（{{ finance_findings|length }} 个）
{% for finding in finance_findings %}
#### {{ loop.index }}. {{ finding.message }}
- **严重性**: {{ finding.severity }}
- **置信度**: {{ "%.0f"|format(finding.confidence * 100) }}%
{% if finding.evidence %}
- **证据**: {{ finding.evidence }}
{% endif %}
{% if finding.legal_basis %}
- **法律依据**: {{ finding.legal_basis }}
{% endif %}

{% endfor %}

### 4.2 税务审查发现（{{ tax_findings|length }} 个）
{% for finding in tax_findings %}
#### {{ loop.index }}. {{ finding.message }}
- **严重性**: {{ finding.severity }}
- **置信度**: {{ "%.0f"|format(finding.confidence * 100) }}%
{% if finding.evidence %}
- **证据**: {{ finding.evidence }}
{% endif %}
{% if finding.legal_basis %}
- **法律依据**: {{ finding.legal_basis }}
{% endif %}

{% endfor %}

### 4.3 法务审查发现（{{ legal_findings|length }} 个）
{% for finding in legal_findings %}
#### {{ loop.index }}. {{ finding.message }}
- **严重性**: {{ finding.severity }}
- **置信度**: {{ "%.0f"|format(finding.confidence * 100) }}%
{% if finding.evidence %}
- **证据**: {{ finding.evidence }}
{% endif %}
{% if finding.legal_basis %}
- **法律依据**: {{ finding.legal_basis }}
{% endif %}

{% endfor %}

## 5. 跨领域冲突
{% if conflicts %}
检测到 {{ conflicts|length }} 个跨领域冲突：
{% for conflict in conflicts %}
### {{ loop.index }}. {{ conflict.type }}
- **涉及领域**: {{ conflict.agent1 }} vs {{ conflict.agent2 }}
- **描述**: {{ conflict.description }}
- **严重性**: {{ conflict.severity }}
- **状态**: {{ "已解决" if conflict.resolved else "待解决" }}

{% endfor %}
{% else %}
未检测到跨领域冲突。
{% endif %}

## 6. 改进建议

### 6.1 立即整改项
{% for action in immediate_actions %}
{{ loop.index }}. {{ action }}
{% endfor %}

### 6.2 建议优化项
{% for rec in recommendations %}
{{ loop.index }}. {{ rec }}
{% endfor %}

## 7. 法律依据
{% for ref in legal_references %}
### {{ loop.index }}. {{ ref.law }}
相关内容: {{ ref.context }}

{% endfor %}

---
**报告生成时间**: {{ created_at }}  
**报告版本**: 标准版 v1.0
"""
    
    def _get_professional_template(self) -> str:
        """专业报告模板 - 包含完整分析、法律依据、图表"""
        return """
# 企业财税法务合规审查报告（专业版）

---

## 报告概览

| 项目 | 内容 |
|------|------|
| 任务ID | {{ task_id }} |
| 租户ID | {{ tenant_id }} |
| 审查类型 | {{ audit_type }} |
| 生成时间 | {{ created_at }} |
| 处理时间 | {{ processing_time }}秒 |
| 重做次数 | {{ rework_count }} |

---

## 一、执行摘要

{{ summary }}

---

## 二、风险评估与分析

### 2.1 综合风险评分

```
风险分数: {{ overall_risk_score }}/100
风险等级: {% if overall_risk_score >= 70 %}高风险{% elif overall_risk_score >= 40 %}中风险{% else %}低风险{% endif %}
```

### 2.2 风险分布统计

| 风险等级 | 数量 | 占比 |
|---------|------|------|
| 高风险 | {{ high_risk_count }} | {{ "%.1f"|format((high_risk_count / total_findings * 100) if total_findings > 0 else 0) }}% |
| 中风险 | {{ medium_risk_count }} | {{ "%.1f"|format((medium_risk_count / total_findings * 100) if total_findings > 0 else 0) }}% |
| 低风险 | {{ low_risk_count }} | {{ "%.1f"|format((low_risk_count / total_findings * 100) if total_findings > 0 else 0) }}% |
| **总计** | **{{ total_findings }}** | **100%** |

### 2.3 领域分布统计

| 审查领域 | 发现数量 | 占比 |
|---------|---------|------|
| 财务审查 | {{ finance_findings|length }} | {{ "%.1f"|format((finance_findings|length / total_findings * 100) if total_findings > 0 else 0) }}% |
| 税务审查 | {{ tax_findings|length }} | {{ "%.1f"|format((tax_findings|length / total_findings * 100) if total_findings > 0 else 0) }}% |
| 法务审查 | {{ legal_findings|length }} | {{ "%.1f"|format((legal_findings|length / total_findings * 100) if total_findings > 0 else 0) }}% |

### 2.4 置信度评估

| 审查领域 | 置信度 | 评价 |
|---------|--------|------|
{% for domain, score in confidence_scores.items() %}
| {{ domain }} | {{ "%.0f"|format(score * 100) }}% | {% if score >= 0.8 %}高{% elif score >= 0.6 %}中{% else %}低{% endif %} |
{% endfor %}

---

## 三、详细审查发现

### 3.1 财务审查（{{ finance_findings|length }} 项）

{% for finding in finance_findings %}
#### 3.1.{{ loop.index }} {{ finding.message }}

**基本信息**
- 严重性: `{{ finding.severity }}`
- 置信度: `{{ "%.0f"|format(finding.confidence * 100) }}%`
- 类型: `{{ finding.type }}`

{% if finding.evidence %}
**证据材料**
```
{{ finding.evidence }}
```
{% endif %}

{% if finding.legal_basis %}
**法律依据**
> {{ finding.legal_basis }}
{% endif %}

---
{% endfor %}

### 3.2 税务审查（{{ tax_findings|length }} 项）

{% for finding in tax_findings %}
#### 3.2.{{ loop.index }} {{ finding.message }}

**基本信息**
- 严重性: `{{ finding.severity }}`
- 置信度: `{{ "%.0f"|format(finding.confidence * 100) }}%`
- 类型: `{{ finding.type }}`

{% if finding.evidence %}
**证据材料**
```
{{ finding.evidence }}
```
{% endif %}

{% if finding.legal_basis %}
**法律依据**
> {{ finding.legal_basis }}
{% endif %}

---
{% endfor %}

### 3.3 法务审查（{{ legal_findings|length }} 项）

{% for finding in legal_findings %}
#### 3.3.{{ loop.index }} {{ finding.message }}

**基本信息**
- 严重性: `{{ finding.severity }}`
- 置信度: `{{ "%.0f"|format(finding.confidence * 100) }}%`
- 类型: `{{ finding.type }}`

{% if finding.evidence %}
**证据材料**
```
{{ finding.evidence }}
```
{% endif %}

{% if finding.legal_basis %}
**法律依据**
> {{ finding.legal_basis }}
{% endif %}

---
{% endfor %}

---

## 四、跨领域协同分析

{% if conflicts %}
### 4.1 检测到的冲突

本次审查中，反思智能体检测到 **{{ conflicts|length }}** 个跨领域冲突：

{% for conflict in conflicts %}
#### 4.1.{{ loop.index }} {{ conflict.type }}

| 项目 | 内容 |
|------|------|
| 冲突类型 | {{ conflict.type }} |
| 涉及领域 | {{ conflict.agent1 }} ↔ {{ conflict.agent2 }} |
| 严重性 | {{ conflict.severity }} |
| 状态 | {{ "✅ 已解决" if conflict.resolved else "⚠️ 待解决" }} |

**冲突描述**
{{ conflict.description }}

---
{% endfor %}

### 4.2 协调处理

{% if rework_count > 0 %}
系统已自动触发 **{{ rework_count }}** 次重做，确保跨领域一致性。
{% else %}
未触发重做，各领域结论一致。
{% endif %}

{% else %}
### 4.1 协同状态

✅ 未检测到跨领域冲突，各专业领域结论一致。

{% endif %}

{% if reflection_summary %}
### 4.3 反思总结

{{ reflection_summary }}
{% endif %}

---

## 五、改进建议

### 5.1 立即整改项（高优先级）

{% if immediate_actions %}
以下问题需要**立即处理**：

{% for action in immediate_actions %}
{{ loop.index }}. {{ action }}
{% endfor %}
{% else %}
✅ 无需立即整改的高风险问题。
{% endif %}

### 5.2 建议优化项（中优先级）

{% if recommendations %}
以下问题建议**尽快优化**：

{% for rec in recommendations %}
{{ loop.index }}. {{ rec }}
{% endfor %}
{% else %}
✅ 无需优化的中低风险问题。
{% endif %}

---

## 六、法律法规依据

{% if legal_references %}
本次审查引用的法律法规：

{% for ref in legal_references %}
### 6.{{ loop.index }} {{ ref.law }}

**适用场景**
{{ ref.context }}

---
{% endfor %}
{% else %}
本次审查未引用特定法律法规。
{% endif %}

---

## 七、附录

### 7.1 审查方法论

本报告采用多智能体协同审查方法，包括：
- 财务审查智能体：审查财务报表、会计科目、财务指标
- 税务审查智能体：审查税务申报、税额计算、税收优惠
- 法务审查智能体：审查合同条款、法律合规、风险条款
- 反思智能体：跨领域冲突检测、证据验证、置信度评估

### 7.2 置信度说明

- **高置信度（≥80%）**: 结论可靠，建议直接采纳
- **中置信度（60-80%）**: 结论基本可靠，建议人工复核
- **低置信度（<60%）**: 结论不确定，建议专家审查

### 7.3 免责声明

本报告由 AI 智能体自动生成，仅供参考。对于重大决策，建议咨询专业人士。

---

**报告生成时间**: {{ created_at }}  
**报告版本**: 专业版 v1.0  
**生成系统**: 智能财税法务合规审查引擎
"""


# 导出
__all__ = ['ReportTemplates', 'ReportType']
