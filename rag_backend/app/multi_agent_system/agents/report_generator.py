"""
报告生成器智能体 (Report Generator Agent)
负责整合多专家分析结果，生成结构化、可视化的报告
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from collections import defaultdict

from pydantic import BaseModel, Field

from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from app.agent_framework.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ReportFormat(str, Enum):
    """报告格式"""
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    TEXT = "text"


class ReportType(str, Enum):
    """报告类型"""
    COMPREHENSIVE = "comprehensive"  # 综合报告
    SPECIALIST = "specialist"  # 专家分析报告
    EXECUTIVE = "executive"  # 高管摘要报告
    TECHNICAL = "technical"  # 技术细节报告
    COMPARISON = "comparison"  # 对比分析报告


class ReportSection(BaseModel):
    """报告章节"""
    title: str = Field(description="章节标题")
    content: str = Field(description="章节内容")
    subsections: List["ReportSection"] = Field(default_factory=list, description="子章节")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="章节元数据")
    priority: int = Field(default=0, description="优先级")


class ReportMetadata(BaseModel):
    """报告元数据"""
    title: str = Field(description="报告标题")
    report_type: ReportType = Field(description="报告类型")
    format: ReportFormat = Field(default=ReportFormat.JSON, description="报告格式")
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")
    session_id: Optional[str] = Field(None, description="会话ID")
    user_id: Optional[str] = Field(None, description="用户ID")
    specialist_results: List[str] = Field(default_factory=list, description="涉及的专业领域")
    confidence_score: float = Field(ge=0.0, le=1.0, description="整体置信度")


class GeneratedReport(BaseModel):
    """生成的报告"""
    metadata: ReportMetadata = Field(description="报告元数据")
    sections: List[ReportSection] = Field(default_factory=list, description="报告章节")
    summary: str = Field(default="", description="执行摘要")
    recommendations: List[str] = Field(default_factory=list, description="建议")
    action_items: List[Dict[str, Any]] = Field(default_factory=list, description="行动项")
    risks: List[Dict[str, Any]] = Field(default_factory=list, description="识别的风险")
    next_steps: List[str] = Field(default_factory=list, description="后续步骤")


@dataclass
class AnalysisResult:
    """分析结果"""
    specialist_name: str
    analysis_content: Dict[str, Any]
    confidence: float
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class ReportGenerator(BaseAgent):
    """
    报告生成器智能体
    
    职责：
    1. 整合多个专家智能体的分析结果
    2. 生成结构化、可读的综合性报告
    3. 支持多种报告格式输出
    4. 提供可视化的分析洞察
    5. 生成行动建议和后续步骤
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager
    ):
        """
        初始化报告生成器
        
        Args:
            llm_adapter: 大模型适配器
            tool_manager: 工具管理器
        """
        system_prompt = """你是一位专业的报告撰写专家，具有以下能力：
        1. 整合和分析来自不同专家领域的信息
        2. 生成清晰、专业的结构化报告
        3. 提供有价值的洞察和建议
        4. 用简洁易懂的语言表达复杂概念
        5. 合理组织报告结构和内容层次
        
        在生成报告时，请：
        - 使用清晰的小标题组织内容
        - 突出关键发现和建议
        - 提供具体的行动项
        - 保持语言简洁专业
        - 确保逻辑连贯、层次分明
        """
        
        super().__init__(
            agent_id="report_generator",
            agent_name="Report Generator",
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=5,
            timeout=120.0
        )
        
        self.report_templates = self._load_report_templates()
        self.section_weights = {
            "executive_summary": 10,
            "analysis": 8,
            "recommendations": 7,
            "risks": 6,
            "next_steps": 5
        }
    
    def _load_report_templates(self) -> Dict[str, Any]:
        """加载报告模板"""
        return {
            "comprehensive": {
                "sections": [
                    {"name": "executive_summary", "title": "执行摘要", "required": True},
                    {"name": "background", "title": "背景介绍", "required": True},
                    {"name": "analysis", "title": "分析结果", "required": True},
                    {"name": "specialist_insights", "title": "专家洞察", "required": True},
                    {"name": "recommendations", "title": "建议", "required": True},
                    {"name": "risks", "title": "风险提示", "required": False},
                    {"name": "action_items", "title": "行动项", "required": False},
                    {"name": "next_steps", "title": "后续步骤", "required": False}
                ],
                "format": ReportFormat.MARKDOWN
            },
            "executive": {
                "sections": [
                    {"name": "executive_summary", "title": "执行摘要", "required": True},
                    {"name": "key_findings", "title": "关键发现", "required": True},
                    {"name": "prioritized_recommendations", "title": "优先建议", "required": True},
                    {"name": "immediate_actions", "title": "立即行动", "required": False}
                ],
                "format": ReportFormat.TEXT
            },
            "technical": {
                "sections": [
                    {"name": "introduction", "title": "技术背景", "required": True},
                    {"name": "methodology", "title": "方法论", "required": True},
                    {"name": "detailed_analysis", "title": "详细分析", "required": True},
                    {"name": "technical_recommendations", "title": "技术建议", "required": True},
                    {"name": "appendix", "title": "附录", "required": False}
                ],
                "format": ReportFormat.MARKDOWN
            }
        }
    
    async def run(
        self,
        specialist_results: List[AnalysisResult],
        user_query: str,
        context: Optional[Dict[str, Any]] = None,
        report_type: ReportType = ReportType.COMPREHENSIVE,
        format: ReportFormat = ReportFormat.JSON,
        **kwargs
    ) -> GeneratedReport:
        """
        生成综合报告
        
        Args:
            specialist_results: 专家分析结果列表
            user_query: 用户原始查询
            context: 上下文信息
            report_type: 报告类型
            format: 输出格式
            **kwargs: 其他参数
            
        Returns:
            生成的报告
        """
        try:
            if not specialist_results:
                return self._generate_empty_report(user_query)
            
            aggregated_data = self._aggregate_specialist_results(specialist_results)
            
            sections = await self._generate_sections(
                aggregated_data,
                user_query,
                report_type
            )
            
            summary = await self._generate_summary(
                aggregated_data,
                user_query
            )
            
            recommendations = self._extract_recommendations(specialist_results)
            action_items = self._extract_action_items(specialist_results)
            risks = self._identify_risks(specialist_results)
            next_steps = self._generate_next_steps(specialist_results)
            
            metadata = ReportMetadata(
                title=self._generate_report_title(user_query, report_type),
                report_type=report_type,
                format=format,
                specialist_results=[r.specialist_name for r in specialist_results],
                confidence_score=self._calculate_overall_confidence(specialist_results)
            )
            
            if context:
                metadata.session_id = context.get("session_id")
                metadata.user_id = context.get("user_id")
            
            return GeneratedReport(
                metadata=metadata,
                sections=sections,
                summary=summary,
                recommendations=recommendations,
                action_items=action_items,
                risks=risks,
                next_steps=next_steps
            )
            
        except Exception as e:
            logger.error(f"报告生成失败: {e}")
            return self._generate_error_report(user_query, str(e))
    
    def _aggregate_specialist_results(
        self,
        specialist_results: List[AnalysisResult]
    ) -> Dict[str, Any]:
        """
        聚合专家分析结果
        
        Args:
            specialist_results: 专家结果列表
            
        Returns:
            聚合后的数据
        """
        aggregated = {
            "by_specialist": {},
            "common_themes": [],
            "key_findings": [],
            "conflicting_advice": [],
            "entities": defaultdict(list)
        }
        
        for result in specialist_results:
            aggregated["by_specialist"][result.specialist_name] = result.analysis_content
            
            if isinstance(result.analysis_content, dict):
                findings = result.analysis_content.get("findings", [])
                recommendations = result.analysis_content.get("recommendations", [])
                risks = result.analysis_content.get("risks", [])
                
                aggregated["key_findings"].extend(findings)
                aggregated["entities"][result.specialist_name] = result.analysis_content.get("entities", [])
        
        aggregated["common_themes"] = self._find_common_themes(specialist_results)
        aggregated["conflicting_advice"] = self._find_conflicts(specialist_results)
        
        return aggregated
    
    def _find_common_themes(self, results: List[AnalysisResult]) -> List[str]:
        """找出共同主题"""
        all_keywords = []
        for result in results:
            content_str = json.dumps(result.analysis_content, ensure_ascii=False)
            all_keywords.append(content_str)
        
        common = []
        if len(all_keywords) >= 2:
            first_set = set(all_keywords[0])
            for kw_set in all_keywords[1:]:
                common_set = first_set.intersection(set(kw_set))
                common.extend(list(common_set)[:5])
        
        return list(set(common))[:10]
    
    def _find_conflicts(self, results: List[AnalysisResult]) -> List[Dict[str, Any]]:
        """识别冲突建议"""
        conflicts = []
        recommendations_by_specialist = {}
        
        for result in results:
            content = result.analysis_content
            if isinstance(content, dict):
                recs = content.get("recommendations", [])
                if recs:
                    recommendations_by_specialist[result.specialist_name] = recs
        
        specialist_names = list(recommendations_by_specialist.keys())
        for i in range(len(specialist_names)):
            for j in range(i + 1, len(specialist_names)):
                name1, name2 = specialist_names[i], specialist_names[j]
                recs1 = recommendations_by_specialist[name1]
                recs2 = recommendations_by_specialist[name2]
                
                if recs1 and recs2:
                    conflicts.append({
                        "specialist_1": name1,
                        "specialist_2": name2,
                        "recommendations_1": recs1[:2],
                        "recommendations_2": recs2[:2]
                    })
        
        return conflicts[:5]
    
    async def _generate_sections(
        self,
        aggregated_data: Dict[str, Any],
        user_query: str,
        report_type: ReportType
    ) -> List[ReportSection]:
        """
        生成报告章节
        
        Args:
            aggregated_data: 聚合数据
            user_query: 用户查询
            report_type: 报告类型
            
        Returns:
            报告章节列表
        """
        sections = []
        
        background_section = ReportSection(
            title="背景介绍",
            content=f"用户查询：{user_query}\n\n本报告整合了以下专业领域的分析结果：{', '.join(aggregated_data['by_specialist'].keys())}",
            priority=10
        )
        sections.append(background_section)
        
        analysis_section = await self._generate_analysis_section(aggregated_data)
        sections.append(analysis_section)
        
        specialist_insights = await self._generate_specialist_insights(aggregated_data)
        sections.extend(specialist_insights)
        
        return sections
    
    async def _generate_analysis_section(
        self,
        aggregated_data: Dict[str, Any]
    ) -> ReportSection:
        """生成分析章节"""
        analysis_content_parts = ["## 综合分析\n"]
        
        if aggregated_data["common_themes"]:
            analysis_content_parts.append("### 共同主题\n")
            for theme in aggregated_data["common_themes"]:
                analysis_content_parts.append(f"- {theme}\n")
            analysis_content_parts.append("\n")
        
        if aggregated_data["conflicting_advice"]:
            analysis_content_parts.append("### 建议差异\n")
            analysis_content_parts.append("不同专家的建议存在以下差异：\n\n")
            for conflict in aggregated_data["conflicting_advice"]:
                analysis_content_parts.append(
                    f"- **{conflict['specialist_1']}** vs **{conflict['specialist_2']}**: "
                    f"建议可能存在权衡\n"
                )
            analysis_content_parts.append("\n")
        
        for specialist, content in aggregated_data["by_specialist"].items():
            analysis_content_parts.append(f"### {specialist}分析\n")
            if isinstance(content, dict):
                for key, value in content.items():
                    if key not in ["entities", "metadata"]:
                        analysis_content_parts.append(f"- {key}: {value}\n")
            analysis_content_parts.append("\n")
        
        return ReportSection(
            title="综合分析",
            content="".join(analysis_content_parts),
            priority=8
        )
    
    async def _generate_specialist_insights(
        self,
        aggregated_data: Dict[str, Any]
    ) -> List[ReportSection]:
        """生成专家洞察章节"""
        insights = []
        
        for specialist_name, content in aggregated_data["by_specialist"].items():
            insight_content = f"### {specialist_name} 洞察\n\n"
            
            if isinstance(content, dict):
                entities = content.get("entities", [])
                if entities:
                    insight_content += "#### 识别的实体\n"
                    for entity in entities[:5]:
                        insight_content += f"- {entity}\n"
                    insight_content += "\n"
                
                risk_factors = content.get("risk_factors", [])
                if risk_factors:
                    insight_content += "#### 风险因素\n"
                    for risk in risk_factors:
                        insight_content += f"- {risk}\n"
                    insight_content += "\n"
            
            insights.append(ReportSection(
                title=f"{specialist_name}洞察",
                content=insight_content,
                priority=7
            ))
        
        return insights
    
    async def _generate_summary(
        self,
        aggregated_data: Dict[str, Any],
        user_query: str
    ) -> str:
        """生成执行摘要"""
        summary_parts = [
            "本报告基于用户查询",
            f"「{user_query}」",
            f"，综合了{len(aggregated_data['by_specialist'])}个专业领域的分析。\n\n"
        ]
        
        key_count = len(aggregated_data["key_findings"])
        if key_count > 0:
            summary_parts.append(f"我们识别出{key_count}个关键发现，")
        
        if aggregated_data["common_themes"]:
            summary_parts.append(f"并发现{len(aggregated_data['common_themes'])}个共同关注点。")
        
        if aggregated_data["conflicting_advice"]:
            summary_parts.append("\n\n请注意，不同专家的建议存在一定差异，建议综合考虑后做出决策。")
        
        return "".join(summary_parts)
    
    def _extract_recommendations(self, results: List[AnalysisResult]) -> List[str]:
        """提取建议"""
        recommendations = []
        seen = set()
        
        for result in results:
            content = result.analysis_content
            if isinstance(content, dict):
                recs = content.get("recommendations", [])
                for rec in recs:
                    rec_key = rec[:50]
                    if rec_key not in seen:
                        recommendations.append(rec)
                        seen.add(rec_key)
        
        return recommendations[:10]
    
    def _extract_action_items(self, results: List[AnalysisResult]) -> List[Dict[str, Any]]:
        """提取行动项"""
        action_items = []
        
        for result in results:
            content = result.analysis_content
            if isinstance(content, dict):
                actions = content.get("action_items", [])
                for action in actions:
                    if isinstance(action, dict):
                        action_items.append({
                            "specialist": result.specialist_name,
                            "action": action.get("description", str(action)),
                            "priority": action.get("priority", "medium"),
                            "deadline": action.get("deadline")
                        })
                    elif isinstance(action, str):
                        action_items.append({
                            "specialist": result.specialist_name,
                            "action": action,
                            "priority": "medium",
                            "deadline": None
                        })
        
        return action_items[:10]
    
    def _identify_risks(self, results: List[AnalysisResult]) -> List[Dict[str, Any]]:
        """识别风险"""
        risks = []
        
        for result in results:
            content = result.analysis_content
            if isinstance(content, dict):
                risk_factors = content.get("risk_factors", [])
                risk_level = content.get("risk_level", "medium")
                
                for risk in risk_factors:
                    risks.append({
                        "specialist": result.specialist_name,
                        "description": risk,
                        "level": risk_level,
                        "mitigation": f"建议咨询{result.specialist_name}获取详细的风险缓解建议"
                    })
        
        return risks[:10]
    
    def _generate_next_steps(self, results: List[AnalysisResult]) -> List[str]:
        """生成后续步骤"""
        steps = []
        step_by_specialist = {
            "finance": ["进一步分析财务影响", "准备财务预算"],
            "tax": ["确认税务合规要求", "准备税务申报材料"],
            "legal": ["审阅法律文件", "获取法律意见"],
            "reflection": ["实施质量改进", "跟踪执行效果"]
        }
        
        for result in results:
            specialist_lower = result.specialist_name.lower()
            for key, suggestions in step_by_specialist.items():
                if key in specialist_lower:
                    steps.extend(suggestions[:2])
                    break
        
        if not steps:
            steps = [
                "审阅本报告内容",
                "根据建议制定行动计划",
                "安排相关专家进一步咨询",
                "定期跟踪执行效果"
            ]
        
        return list(dict.fromkeys(steps))[:8]
    
    def _generate_report_title(
        self,
        user_query: str,
        report_type: ReportType
    ) -> str:
        """生成报告标题"""
        title_map = {
            ReportType.COMPREHENSIVE: "综合分析报告",
            ReportType.EXECUTIVE: "高管摘要报告",
            ReportType.TECHNICAL: "技术分析报告",
            ReportType.SPECIALIST: "专家分析报告",
            ReportType.COMPARISON: "对比分析报告"
        }
        
        base_title = title_map.get(report_type, "分析报告")
        
        query_preview = user_query[:30]
        if len(user_query) > 30:
            query_preview += "..."
        
        return f"{base_title} - {query_preview}"
    
    def _calculate_overall_confidence(self, results: List[AnalysisResult]) -> float:
        """计算整体置信度"""
        if not results:
            return 0.0
        
        confidences = [r.confidence for r in results if r.confidence]
        
        if not confidences:
            return 0.0
        
        return sum(confidences) / len(confidences)
    
    def _generate_empty_report(self, user_query: str) -> GeneratedReport:
        """生成空报告"""
        return GeneratedReport(
            metadata=ReportMetadata(
                title="空报告",
                report_type=ReportType.COMPREHENSIVE,
                generated_at=datetime.now()
            ),
            sections=[
                ReportSection(
                    title="提示",
                    content="未找到相关的专家分析结果，请确保已提供足够的上下文信息。",
                    priority=10
                )
            ],
            summary="本报告暂无内容。",
            recommendations=["请提供更多的问题细节或咨询相关专家"],
            action_items=[],
            risks=[],
            next_steps=["完善问题描述", "提供相关文档", "咨询专业人士"]
        )
    
    def _generate_error_report(self, user_query: str, error: str) -> GeneratedReport:
        """生成错误报告"""
        return GeneratedReport(
            metadata=ReportMetadata(
                title="错误报告",
                report_type=ReportType.COMPREHENSIVE,
                generated_at=datetime.now()
            ),
            sections=[
                ReportSection(
                    title="报告生成错误",
                    content=f"在生成报告时遇到以下错误：{error}",
                    priority=10
                )
            ],
            summary="报告生成失败，请查看错误详情。",
            recommendations=["请稍后重试", "如果问题持续存在，请联系技术支持"],
            action_items=[],
            risks=[],
            next_steps=["重新尝试生成报告", "检查系统日志", "联系技术支持"]
        )
    
    async def export_report(
        self,
        report: GeneratedReport,
        format: ReportFormat = ReportFormat.JSON
    ) -> str:
        """
        导出报告
        
        Args:
            report: 报告对象
            format: 输出格式
            
        Returns:
            格式化后的报告字符串
        """
        if format == ReportFormat.JSON:
            return report.model_dump_json(ensure_ascii=False, indent=2)
        
        elif format == ReportFormat.MARKDOWN:
            return self._to_markdown(report)
        
        elif format == ReportFormat.HTML:
            return self._to_html(report)
        
        elif format == ReportFormat.TEXT:
            return self._to_text(report)
        
        else:
            return report.model_dump_json(ensure_ascii=False)
    
    def _to_markdown(self, report: GeneratedReport) -> str:
        """转换为Markdown格式"""
        md_parts = [f"# {report.metadata.title}\n"]
        md_parts.append(f"**报告类型**: {report.metadata.report_type.value}\n")
        md_parts.append(f"**生成时间**: {report.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
        md_parts.append(f"**置信度**: {report.metadata.confidence_score:.2%}\n")
        
        if report.metadata.session_id:
            md_parts.append(f"**会话ID**: {report.metadata.session_id}\n")
        
        md_parts.append(f"\n## 执行摘要\n\n{report.summary}\n\n")
        
        if report.recommendations:
            md_parts.append("## 建议\n\n")
            for i, rec in enumerate(report.recommendations, 1):
                md_parts.append(f"{i}. {rec}\n")
            md_parts.append("\n")
        
        for section in report.sections:
            md_parts.append(f"## {section.title}\n\n{section.content}\n\n")
        
        if report.action_items:
            md_parts.append("## 行动项\n\n")
            md_parts.append("| 专家 | 行动 | 优先级 |\n")
            md_parts.append("|------|------|--------|\n")
            for item in report.action_items:
                md_parts.append(
                    f"| {item.get('specialist', 'N/A')} | "
                    f"{item.get('action', 'N/A')} | "
                    f"{item.get('priority', 'medium')} |\n"
                )
            md_parts.append("\n")
        
        if report.risks:
            md_parts.append("## 风险提示\n\n")
            for risk in report.risks:
                md_parts.append(
                    f"- **{risk.get('description', 'N/A')}** "
                    f"(级别: {risk.get('level', 'medium')})\n"
                )
            md_parts.append("\n")
        
        if report.next_steps:
            md_parts.append("## 后续步骤\n\n")
            for i, step in enumerate(report.next_steps, 1):
                md_parts.append(f"{i}. {step}\n")
            md_parts.append("\n")
        
        return "".join(md_parts)
    
    def _to_html(self, report: GeneratedReport) -> str:
        """转换为HTML格式"""
        html_parts = [
            "<!DOCTYPE html>\n<html>\n<head>\n",
            f"<title>{report.metadata.title}</title>\n",
            "<style>\n",
            "body { font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }\n",
            "h1 { color: #333; border-bottom: 2px solid #007bff; }\n",
            "h2 { color: #555; margin-top: 30px; }\n",
            ".metadata { background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }\n",
            ".section { margin: 20px 0; }\n",
            ".recommendations, .risks, .action-items { background: #f9f9f9; padding: 15px; border-radius: 5px; }\n",
            "ul { line-height: 1.8; }\n",
            ".risk-high { color: #dc3545; }\n",
            ".risk-medium { color: #ffc107; }\n",
            ".risk-low { color: #28a745; }\n",
            "</style>\n</head>\n<body>\n",
            f"<h1>{report.metadata.title}</h1>\n",
            "<div class='metadata'>\n",
            f"<p><strong>报告类型:</strong> {report.metadata.report_type.value}</p>\n",
            f"<p><strong>生成时间:</strong> {report.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}</p>\n",
            f"<p><strong>置信度:</strong> {report.metadata.confidence_score:.2%}</p>\n",
            "</div>\n"
        ]
        
        html_parts.append(f"<h2>执行摘要</h2>\n<div>{report.summary.replace(chr(10), '<br>')}</div>\n")
        
        if report.recommendations:
            html_parts.append("<div class='recommendations'>\n<h2>建议</h2>\n<ul>\n")
            for rec in report.recommendations:
                html_parts.append(f"<li>{rec}</li>\n")
            html_parts.append("</ul>\n</div>\n")
        
        if report.risks:
            html_parts.append("<div class='risks'>\n<h2>风险提示</h2>\n<ul>\n")
            for risk in report.risks:
                risk_class = f"risk-{risk.get('level', 'low')}"
                html_parts.append(
                    f"<li class='{risk_class}'>{risk.get('description', 'N/A')} "
                    f"(级别: {risk.get('level', 'medium')})</li>\n"
                )
            html_parts.append("</ul>\n</div>\n")
        
        html_parts.append("</body>\n</html>")
        
        return "".join(html_parts)
    
    def _to_text(self, report: GeneratedReport) -> str:
        """转换为纯文本格式"""
        text_parts = [
            "=" * 60 + "\n",
            f"{report.metadata.title}\n",
            "=" * 60 + "\n\n",
            f"报告类型: {report.metadata.report_type.value}\n",
            f"生成时间: {report.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"置信度: {report.metadata.confidence_score:.2%}\n",
            "\n" + "-" * 60 + "\n\n",
            "执行摘要\n",
            "-" * 60 + "\n",
            f"{report.summary}\n\n"
        ]
        
        if report.recommendations:
            text_parts.append("\n建议\n")
            text_parts.append("-" * 60 + "\n")
            for i, rec in enumerate(report.recommendations, 1):
                text_parts.append(f"{i}. {rec}\n")
            text_parts.append("\n")
        
        if report.action_items:
            text_parts.append("\n行动项\n")
            text_parts.append("-" * 60 + "\n")
            for item in report.action_items:
                text_parts.append(
                    f"- [{item.get('specialist', 'N/A')}] "
                    f"{item.get('action', 'N/A')} "
                    f"[优先级: {item.get('priority', 'medium')}]\n"
                )
            text_parts.append("\n")
        
        if report.next_steps:
            text_parts.append("\n后续步骤\n")
            text_parts.append("-" * 60 + "\n")
            for i, step in enumerate(report.next_steps, 1):
                text_parts.append(f"{i}. {step}\n")
            text_parts.append("\n")
        
        return "".join(text_parts)
    
    async def consult(
        self,
        context: Dict[str, Any],
        user_query: str
    ) -> Dict[str, Any]:
        """
        咨询报告生成器（兼容编排器接口）
        
        Args:
            context: 编排上下文，包含专家结果等
            user_query: 用户查询
            
        Returns:
            包含报告内容的字典
        """
        try:
            specialist_results = context.get("specialist_results", [])
            
            analysis_results = []
            for sr in specialist_results:
                if isinstance(sr, dict):
                    analysis_results.append(AnalysisResult(
                        specialist_name=sr.get("specialist_type", "unknown"),
                        analysis_content=sr.get("analysis", {}),
                        confidence=sr.get("confidence", 0.8)
                    ))
                else:
                    analysis_results.append(sr)
            
            report_type = ReportType(context.get("report_type", "comprehensive"))
            
            report = await self.run(
                specialist_results=analysis_results,
                user_query=user_query,
                context=context,
                report_type=report_type
            )
            
            return {
                "success": True,
                "report": report,
                "report_content": self._to_markdown(report),
                "metadata": report.metadata.model_dump()
            }
            
        except Exception as e:
            logger.error(f"报告生成咨询失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "report": None
            }
