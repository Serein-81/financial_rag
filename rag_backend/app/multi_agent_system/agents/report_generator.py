"""
报告生成器智能体 (Report Generator Agent)
负责整合多专家分析结果，生成结构化、可视化的报告
"""

from app.utils.json_compat import json
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator, TYPE_CHECKING
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from collections import defaultdict

from pydantic import BaseModel, Field

from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from app.agent_framework.core.base_agent import BaseAgent
from app.multi_agent_system.agents.base_agent_prompt import load_agent_prompt

if TYPE_CHECKING:
    from app.multi_agent_system.state_machine import AuditState

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


class AuditReport(BaseModel):
    """审查报告数据结构（整合自 multi_agent_system/report_generator.py）
    
    用于从 AuditState 生成结构化审查报告
    """
    task_id: str = Field(description="任务ID")
    tenant_id: str = Field(description="租户ID")
    audit_type: str = Field(description="审计类型")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    
    summary: str = Field(default="", description="执行摘要")
    overall_risk_score: float = Field(default=0.0, ge=0.0, le=100.0, description="综合风险评分")
    total_findings: int = Field(default=0, description="总发现数")
    high_risk_count: int = Field(default=0, description="高风险数量")
    medium_risk_count: int = Field(default=0, description="中风险数量")
    low_risk_count: int = Field(default=0, description="低风险数量")
    
    finance_findings: List[Dict[str, Any]] = Field(default_factory=list, description="财务发现")
    tax_findings: List[Dict[str, Any]] = Field(default_factory=list, description="税务发现")
    legal_findings: List[Dict[str, Any]] = Field(default_factory=list, description="法务发现")
    
    conflicts: List[Dict[str, Any]] = Field(default_factory=list, description="冲突列表")
    confidence_scores: Dict[str, float] = Field(default_factory=dict, description="置信度评分")
    reflection_summary: str = Field(default="", description="反思总结")
    
    immediate_actions: List[str] = Field(default_factory=list, description="立即行动")
    recommendations: List[str] = Field(default_factory=list, description="建议")
    legal_references: List[Dict[str, Any]] = Field(default_factory=list, description="法律依据")
    
    processing_time: float = Field(default=0.0, description="处理时间")
    rework_count: int = Field(default=0, description="重做次数")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump()
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class ReportGenerator(BaseAgent):
    """
    报告生成器智能体
    
    职责：
    1. 整合多个专家智能体的分析结果
    2. 生成结构化、可读的综合性报告
    3. 支持多种报告格式输出
    4. 提供可视化的分析洞察
    5. 生成行动建议和后续步骤
    6. 从 AuditState 生成审查报告
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
        system_prompt = self._load_system_prompt()
        
        super().__init__(
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
    
    def _load_system_prompt(self) -> str:
        """从外部文件加载系统提示词"""
        try:
            return load_agent_prompt(
                agent_name="report",
                filename="report_generator.md",
                context=self._get_prompt_context()
            )
        except Exception as e:
            logger.debug(f"[报告生成器智能体] 加载提示词失败，使用默认提示词: {e}")
            return self._build_default_prompt()
    
    def _get_prompt_context(self) -> Dict[str, Any]:
        """获取提示词渲染上下文"""
        return {
            "report_types": [r.value for r in ReportType],
            "report_formats": [f.value for f in ReportFormat],
        }
    
    def _build_default_prompt(self) -> str:
        """构建默认提示词"""
        return """你是一位专业的报告撰写专家，具有以下能力：
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
            
        except (ValueError, KeyError) as e:
            logger.error(f"报告生成数据失败: {e}")
            return self._generate_error_report(user_query, str(e))
        except (OSError, IOError) as e:
            logger.error(f"报告生成IO失败: {e}")
            return self._generate_error_report(user_query, str(e))
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
    
    async def generate_from_audit_state(
        self,
        state: "AuditState",
        task_id: str,
        processing_time: float = 0.0
    ) -> AuditReport:
        """
        从 AuditState 生成审查报告（整合自 multi_agent_system/report_generator.py）
        
        Args:
            state: 审查全局状态
            task_id: 任务 ID
            processing_time: 处理时间（秒）
            
        Returns:
            AuditReport: 结构化审查报告
        """
        try:
            report = AuditReport(
                task_id=task_id,
                tenant_id=state.get('tenant_id', 'unknown'),
                audit_type=state.get('audit_type', 'comprehensive'),
                processing_time=processing_time,
                rework_count=state.get('rework_count', 0)
            )
            
            report.finance_findings = self._serialize_findings(
                state.get('finance_findings', [])
            )
            report.tax_findings = self._serialize_findings(
                state.get('tax_findings', [])
            )
            report.legal_findings = self._serialize_findings(
                state.get('legal_findings', [])
            )
            
            all_findings = (
                report.finance_findings + 
                report.tax_findings + 
                report.legal_findings
            )
            report.total_findings = len(all_findings)
            
            risk_counts = self._classify_risk_levels(all_findings)
            report.high_risk_count = risk_counts['high']
            report.medium_risk_count = risk_counts['medium']
            report.low_risk_count = risk_counts['low']
            
            report.overall_risk_score = self._calculate_risk_score(
                report.high_risk_count,
                report.medium_risk_count,
                report.low_risk_count
            )
            
            report.conflicts = self._serialize_conflicts(state.get('conflicts', []))
            report.confidence_scores = state.get('confidence_scores', {})
            report.reflection_summary = state.get('reflection_summary', '')
            
            report.summary = self._generate_audit_summary(report)
            report.immediate_actions = self._generate_immediate_actions_from_findings(all_findings)
            report.recommendations = self._generate_recommendations_from_findings(all_findings)
            report.legal_references = self._extract_legal_references_from_findings(all_findings)
            
            logger.info(
                f"[报告生成器] 从AuditState生成报告完成: "
                f"总发现数={report.total_findings}, "
                f"风险分数={report.overall_risk_score}"
            )
            
            return report
            
        except Exception as e:
            logger.error(f"[报告生成器] 从AuditState生成报告失败: {e}")
            raise
    
    def _serialize_findings(self, findings: List[Any]) -> List[Dict[str, Any]]:
        """序列化发现列表"""
        result = []
        for finding in findings:
            if isinstance(finding, dict):
                result.append(finding)
            else:
                result.append({
                    'type': getattr(finding, 'type', 'info'),
                    'message': getattr(finding, 'message', ''),
                    'severity': getattr(finding, 'severity', 'low'),
                    'evidence': getattr(finding, 'evidence', ''),
                    'legal_basis': getattr(finding, 'legal_basis', ''),
                    'confidence': getattr(finding, 'confidence', 1.0)
                })
        return result
    
    def _serialize_conflicts(self, conflicts: List[Any]) -> List[Dict[str, Any]]:
        """序列化冲突列表"""
        result = []
        for conflict in conflicts:
            if isinstance(conflict, dict):
                result.append(conflict)
            else:
                result.append({
                    'type': getattr(conflict, 'type', 'unknown'),
                    'agent1': getattr(conflict, 'agent1', ''),
                    'agent2': getattr(conflict, 'agent2', ''),
                    'description': getattr(conflict, 'description', ''),
                    'severity': getattr(conflict, 'severity', 'medium'),
                    'resolved': getattr(conflict, 'resolved', False)
                })
        return result
    
    def _classify_risk_levels(self, findings: List[Dict[str, Any]]) -> Dict[str, int]:
        """分类风险等级"""
        counts = {'high': 0, 'medium': 0, 'low': 0}
        
        for finding in findings:
            severity = str(finding.get('severity', 'low')).lower()
            
            if severity in ['high', 'critical', 'error', 'risk']:
                counts['high'] += 1
            elif severity in ['medium', 'warning', 'moderate']:
                counts['medium'] += 1
            else:
                counts['low'] += 1
        
        return counts
    
    def _calculate_risk_score(self, high: int, medium: int, low: int) -> float:
        """计算综合风险分数 (0-100)"""
        if high + medium + low == 0:
            return 0.0
        
        weighted_score = high * 10 + medium * 5 + low * 1
        max_possible = 20 * 10
        normalized = min(100.0, (weighted_score / max_possible) * 100)
        
        return round(normalized, 2)
    
    def _generate_audit_summary(self, report: AuditReport) -> str:
        """生成审查摘要"""
        summary_parts = [
            f"本次审查共发现 {report.total_findings} 个问题，"
            f"综合风险评分为 {report.overall_risk_score:.1f}/100。"
        ]
        
        if report.high_risk_count > 0:
            summary_parts.append(f"其中高风险问题 {report.high_risk_count} 个，需要立即处理。")
        
        if report.medium_risk_count > 0:
            summary_parts.append(f"中风险问题 {report.medium_risk_count} 个，建议尽快处理。")
        
        return "".join(summary_parts)
    
    def _generate_immediate_actions_from_findings(self, findings: List[Dict[str, Any]]) -> List[str]:
        """从发现生成立即行动"""
        actions = []
        high_risk_findings = [
            f for f in findings 
            if str(f.get('severity', 'low')).lower() in ['high', 'critical']
        ]
        
        for finding in high_risk_findings[:5]:
            actions.append(f"处理高风险问题: {finding.get('message', '详情见报告')}")
        
        return actions
    
    def _generate_recommendations_from_findings(self, findings: List[Dict[str, Any]]) -> List[str]:
        """从发现生成建议"""
        recommendations = []
        seen = set()
        
        for finding in findings:
            if isinstance(finding, dict):
                recs = finding.get('recommendations', [])
                for rec in recs:
                    rec_key = rec[:50]
                    if rec_key not in seen:
                        recommendations.append(rec)
                        seen.add(rec_key)
        
        return recommendations[:10]
    
    def _extract_legal_references_from_findings(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从发现提取法律依据"""
        references = []
        seen = set()
        
        for finding in findings:
            if isinstance(finding, dict):
                legal_basis = finding.get('legal_basis', [])
                if isinstance(legal_basis, list):
                    for ref in legal_basis:
                        ref_key = str(ref)[:50]
                        if ref_key not in seen:
                            references.append({
                                'source': finding.get('type', 'unknown'),
                                'reference': ref
                            })
                            seen.add(ref_key)
        
        return references
    
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
            
        except (ValueError, KeyError) as e:
            logger.error(f"报告生成咨询数据失败: {e}")
            return {
                "success": False,
                "error": f"数据错误: {str(e)}",
                "report": None
            }
        except (OSError, IOError) as e:
            logger.error(f"报告生成咨询IO失败: {e}")
            return {
                "success": False,
                "error": f"IO错误: {str(e)}",
                "report": None
            }
        except Exception as e:
            logger.error(f"报告生成咨询失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "report": None
            }
    
    async def stream_run(
        self,
        user_input: str,
        history: Optional[List[Dict]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式执行报告生成
        
        Args:
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数
            
        Yields:
            逐步生成的内容
        """
        specialist_results = kwargs.get("specialist_results", [])
        context = kwargs.get("context", {})
        report_type = kwargs.get("report_type", ReportType.COMPREHENSIVE)
        
        yield "# 正在生成报告...\n\n"
        
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
        
        report = await self.run(
            specialist_results=analysis_results,
            user_query=user_input,
            context=context,
            report_type=report_type
        )
        
        yield self._to_markdown(report)
    
    def set_output_agent(self, output_agent) -> None:
        """设置输出审查智能体（兼容 ReportAgent 接口，已弃用）"""
        import warnings
        warnings.warn(
            "set_output_agent 方法已弃用，请直接使用 ResultSynthesizer",
            DeprecationWarning,
            stacklevel=2
        )
        self.output_agent = output_agent
    
    def recognize_report_type(self, user_input: str) -> Optional[str]:
        """
        识别报表类型（兼容 ReportAgent 接口）
        
        Args:
            user_input: 用户输入
            
        Returns:
            报表类型，如 "sales", "financial" 等
        """
        REPORT_TYPES = {
            "sales": ["销售", "销量", "销售额", "订单"],
            "financial": ["财务", "收支", "利润", "成本"],
            "operation": ["运营", "用户", "活跃", "留存"],
            "inventory": ["库存", "仓储", "物流"]
        }
        
        user_input_lower = user_input.lower()
        
        for report_type, keywords in REPORT_TYPES.items():
            for keyword in keywords:
                if keyword in user_input:
                    return report_type
        
        return "general"
    
    async def generate_report(
        self,
        user_input: str,
        time_range: str = "本月",
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成报表（兼容 ReportAgent 接口）
        
        Args:
            user_input: 用户输入
            time_range: 时间范围
            **kwargs: 其他参数
            
        Returns:
            报表数据
        """
        report_type = self.recognize_report_type(user_input)
        
        data = self._generate_mock_data(report_type, time_range)
        
        report_content = self._format_report(report_type, data, time_range)
        
        return {
            "report_type": report_type,
            "report_name": f"{report_type}报表",
            "time_range": time_range,
            "data": data,
            "content": report_content,
            "generated_at": datetime.now().isoformat()
        }
    
    def _generate_mock_data(self, report_type: str, time_range: str) -> Dict[str, Any]:
        """
        生成模拟数据（用于演示）
        
        Args:
            report_type: 报表类型
            time_range: 时间范围
            
        Returns:
            模拟的报表数据
        """
        mock_data = {
            "sales": {
                "total_orders": 1256,
                "total_amount": 895670.50,
                "avg_order_value": 713.11,
                "top_products": [
                    {"name": "产品A", "sales": 156000, "growth": "+12%"},
                    {"name": "产品B", "sales": 98000, "growth": "+8%"},
                    {"name": "产品C", "sales": 87500, "growth": "+15%"}
                ]
            },
            "financial": {
                "revenue": 895670.50,
                "cost": 520000.00,
                "profit": 375670.50,
                "profit_margin": "41.9%",
                "expenses": [
                    {"item": "人力成本", "amount": 200000},
                    {"item": "运营成本", "amount": 150000},
                    {"item": "营销成本", "amount": 100000}
                ]
            },
            "operation": {
                "total_users": 25680,
                "active_users": 18650,
                "new_users": 1256,
                "retention_rate": "72.5%",
                "avg_session_duration": "15分钟"
            },
            "inventory": {
                "total_products": 4580,
                "low_stock_items": 23,
                "out_of_stock": 5,
                "turnover_rate": "4.2次/月"
            },
            "general": {
                "summary": f"{time_range}数据汇总",
                "highlights": ["数据1", "数据2", "数据3"]
            }
        }
        
        return mock_data.get(report_type, mock_data["general"])
    
    def _format_report(
        self,
        report_type: str,
        data: Dict[str, Any],
        time_range: str
    ) -> str:
        """
        格式化报表内容
        
        Args:
            report_type: 报表类型
            data: 报表数据
            time_range: 时间范围
            
        Returns:
            格式化的报表文本
        """
        if report_type == "sales":
            return f"""【{time_range}销售报表】

📊 销售概况
• 总订单数：{data['total_orders']} 单
• 总销售额：¥{data['total_amount']:,.2f}
• 平均订单金额：¥{data['avg_order_value']:.2f}

🏆 热销产品 TOP3
1. {data['top_products'][0]['name']}：¥{data['top_products'][0]['sales']:,}（{data['top_products'][0]['growth']}）
2. {data['top_products'][1]['name']}：¥{data['top_products'][1]['sales']:,}（{data['top_products'][1]['growth']}）
3. {data['top_products'][2]['name']}：¥{data['top_products'][2]['sales']:,}（{data['top_products'][2]['growth']}）

---
报表生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        elif report_type == "financial":
            return f"""【{time_range}财务报表】

💰 财务概要
• 营业收入：¥{data['revenue']:,.2f}
• 营业成本：¥{data['cost']:,.2f}
• 净利润：¥{data['profit']:,.2f}
• 利润率：{data['profit_margin']}

📋 费用明细
• 人力成本：¥{data['expenses'][0]['amount']:,}
• 运营成本：¥{data['expenses'][1]['amount']:,}
• 营销成本：¥{data['expenses'][2]['amount']:,}

---
报表生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        elif report_type == "operation":
            return f"""【{time_range}运营报表】

👥 用户数据
• 总用户数：{data['total_users']:,}
• 活跃用户：{data['active_users']:,}
• 新增用户：{data['new_users']:,}
• 留存率：{data['retention_rate']}
• 平均会话时长：{data['avg_session_duration']}

---
报表生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        elif report_type == "inventory":
            return f"""【{time_range}库存报表】

📦 库存概况
• 商品总数：{data['total_products']:,}
• 低库存商品：{data['low_stock_items']} 种
• 缺货商品：{data['out_of_stock']} 种
• 库存周转率：{data['turnover_rate']}

---
报表生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        else:
            return f"""【{time_range}数据汇总】

{data.get('summary', '暂无数据')}

亮点：
{chr(10).join(['• ' + h for h in data.get('highlights', [])])}

---
报表生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"""
