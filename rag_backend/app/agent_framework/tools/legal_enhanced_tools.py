"""
法务合规增强工具集

基于项目现有数据模型和基础设施的增强工具
与 contract_review、scheduled_task、notification 等模块无缝配合
"""

import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, date
from enum import Enum

from .base import ToolBase

logger = logging.getLogger(__name__)


class DeadlineType(str, Enum):
    """截止日期类型"""
    CONTRACT_EXPIRATION = "contract_expiration"
    CONTRACT_RENEWAL = "contract_renewal"
    PAYMENT_DUE = "payment_due"
    REVIEW_SCHEDULE = "review_schedule"
    SLA_DEADLINE = "sla_deadline"
    REGULATORY_FILING = "regulatory_filing"


class UrgencyLevel(str, Enum):
    """紧急程度"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContractComplianceDeadlineTool(ToolBase):
    """
    合同合规截止日期监控工具
    
    集成现有 scheduled_task 模型和通知服务
    监控合同到期、续约提醒、付款截止等关键日期
    """

    def __init__(self):
        super().__init__(
            name="contract_compliance_deadline",
            description="监控合同合规截止日期，包括到期提醒、续约预警、付款截止等",
            timeout=30,
            tags=["法律", "合同", "截止日期", "监控", "合规"]
        )

    async def execute(
        self,
        tenant_id: str,
        contract_id: Optional[str] = None,
        watch_period_days: int = 90,
        include_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        获取合同合规截止日期列表
        
        Args:
            tenant_id: 租户ID
            contract_id: 特定合同ID，不提供则查询所有合同
            watch_period_days: 监控天数范围，默认90天
            include_types: 截止日期类型过滤
            
        Returns:
            截止日期监控结果
        """
        try:
            from app.core.database import async_session_maker
            from sqlalchemy import select, and_, or_
            from app.models.contract_review import ContractReviewReport, ReviewStatus
            from app.models.scheduled_task import ScheduledTask, TaskStatus

            deadlines = []
            today = datetime.now().date()
            watch_end = today + timedelta(days=watch_period_days)

            async with async_session_maker() as session:
                conditions = [
                    ContractReviewReport.tenant_id == tenant_id,
                    ContractReviewReport.review_status == ReviewStatus.APPROVED
                ]

                if contract_id:
                    conditions.append(ContractReviewReport.id == contract_id)

                stmt = select(ContractReviewReport).where(and_(*conditions))
                result = await session.execute(stmt)
                contracts = result.scalars().all()

                for contract in contracts:
                    contract_deadlines = self._extract_deadlines(
                        contract, today, watch_end, include_types
                    )
                    deadlines.extend(contract_deadlines)

                scheduled_conditions = [
                    ScheduledTask.tenant_id == tenant_id,
                    ScheduledTask.status == TaskStatus.PENDING
                ]

                task_stmt = select(ScheduledTask).where(and_(*scheduled_conditions))
                task_result = await session.execute(task_stmt)
                tasks = task_result.scalars().all()

                for task in tasks:
                    if task.due_date:
                        due_date = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
                        if today <= due_date <= watch_end:
                            deadlines.append({
                                "type": DeadlineType.REVIEW_SCHEDULE.value,
                                "deadline_date": due_date.isoformat(),
                                "days_remaining": (due_date - today).days,
                                "urgency": self._calculate_urgency((due_date - today).days),
                                "title": task.title or "计划任务",
                                "task_id": str(task.id),
                                "description": task.description,
                                "status": task.status.value if hasattr(task.status, 'value') else task.status
                            })

            deadlines.sort(key=lambda x: x["days_remaining"])

            critical_count = sum(1 for d in deadlines if d["urgency"] == UrgencyLevel.CRITICAL.value)
            high_count = sum(1 for d in deadlines if d["urgency"] == UrgencyLevel.HIGH.value)

            return {
                "tenant_id": tenant_id,
                "watch_period_days": watch_period_days,
                "period_start": today.isoformat(),
                "period_end": watch_end.isoformat(),
                "total_deadlines": len(deadlines),
                "critical_count": critical_count,
                "high_count": high_count,
                "deadlines": deadlines,
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"合同截止日期监控失败: {str(e)}", exc_info=True)
            return {
                "tenant_id": tenant_id,
                "error": f"截止日期监控失败: {str(e)}",
                "deadlines": [],
                "total_deadlines": 0,
                "generated_at": datetime.now().isoformat()
            }

    def _extract_deadlines(
        self,
        contract: Any,
        today: date,
        watch_end: date,
        include_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """从合同中提取截止日期"""
        deadlines = []

        if contract.expiration_date:
            exp_date = contract.expiration_date.date() if hasattr(contract.expiration_date, 'date') else contract.expiration_date
            if today <= exp_date <= watch_end:
                days_rem = (exp_date - today).days
                deadlines.append({
                    "type": DeadlineType.CONTRACT_EXPIRATION.value,
                    "deadline_date": exp_date.isoformat(),
                    "days_remaining": days_rem,
                    "urgency": self._calculate_urgency(days_rem),
                    "title": f"合同到期: {contract.contract_name}",
                    "contract_id": str(contract.id),
                    "contract_type": contract.contract_type.value if hasattr(contract.contract_type, 'value') else str(contract.contract_type),
                    "counterparty": contract.counterparty,
                    "contract_value": contract.contract_value,
                    "currency": contract.currency,
                    "action_required": "合同续约或终止",
                    "reminder_window": self._get_reminder_window(days_rem)
                })

            renewal_date = exp_date - timedelta(days=30)
            if today <= renewal_date <= watch_end:
                days_rem = (renewal_date - today).days
                deadlines.append({
                    "type": DeadlineType.CONTRACT_RENEWAL.value,
                    "deadline_date": renewal_date.isoformat(),
                    "days_remaining": days_rem,
                    "urgency": self._calculate_urgency(days_rem),
                    "title": f"合同续约审查: {contract.contract_name}",
                    "contract_id": str(contract.id),
                    "action_required": "评估是否续约",
                    "reminder_window": self._get_reminder_window(days_rem)
                })

        return [d for d in deadlines if not include_types or d["type"] in include_types]

    def _calculate_urgency(self, days_remaining: int) -> str:
        """计算紧急程度"""
        if days_remaining <= 7:
            return UrgencyLevel.CRITICAL.value
        elif days_remaining <= 14:
            return UrgencyLevel.HIGH.value
        elif days_remaining <= 30:
            return UrgencyLevel.MEDIUM.value
        return UrgencyLevel.LOW.value

    def _get_reminder_window(self, days_remaining: int) -> str:
        """获取提醒窗口"""
        if days_remaining <= 7:
            return "立即处理"
        elif days_remaining <= 14:
            return "本周内处理"
        elif days_remaining <= 30:
            return "本月内处理"
        return "提前规划"


class ContractTemplateMatcher(ToolBase):
    """
    合同模板智能匹配工具
    
    基于 ContractTemplate 模型，智能匹配适合的合同模板
    """

    def __init__(self):
        super().__init__(
            name="contract_template_matcher",
            description="根据合同类型和关键条款智能匹配合同模板",
            timeout=30,
            tags=["法律", "合同", "模板", "匹配"]
        )

        self.template_keywords = {
            "purchase": ["采购", "购买", "供货", "货物", "商品"],
            "sales": ["销售", "卖方", "分销", "代理"],
            "service": ["服务", "咨询", "外包", "委托", "技术支持"],
            "lease": ["租赁", "租用", "出租", "场地", "设备"],
            "employment": ["劳动", "雇佣", "聘用", "员工", "劳动合同"],
            "partnership": ["合作", "合伙", "联盟", "战略"],
            "loan": ["借款", "贷款", "融资", "信贷"],
        }

    async def execute(
        self,
        tenant_id: str,
        contract_type: Optional[str] = None,
        contract_content: Optional[str] = None,
        required_clauses: Optional[List[str]] = None,
        match_threshold: float = 0.6
    ) -> Dict[str, Any]:
        """
        匹配合同模板
        
        Args:
            tenant_id: 租户ID
            contract_type: 合同类型
            contract_content: 合同内容摘要
            required_clauses: 必须包含的条款
            match_threshold: 匹配阈值
            
        Returns:
            模板匹配结果
        """
        try:
            from app.core.database import async_session_maker
            from sqlalchemy import select, and_
            from app.models.contract_review import ContractTemplate, ContractType

            async with async_session_maker() as session:
                conditions = [
                    ContractTemplate.tenant_id == tenant_id,
                    ContractTemplate.is_public == True
                ]

                if contract_type:
                    try:
                        ct = ContractType(contract_type)
                        conditions.append(ContractTemplate.contract_type == ct)
                    except ValueError:
                        pass

                stmt = select(ContractTemplate).where(and_(*conditions))
                result = await session.execute(stmt)
                templates = result.scalars().all()

                if not templates:
                    tenant_stmt = select(ContractTemplate).where(
                        ContractTemplate.tenant_id == tenant_id
                    )
                    result = await session.execute(tenant_stmt)
                    templates = result.scalars().all()

                matches = []
                for template in templates:
                    score = self._calculate_match_score(
                        template, contract_type, contract_content, required_clauses
                    )
                    if score >= match_threshold:
                        matches.append({
                            "template_id": str(template.id),
                            "template_name": template.name,
                            "description": template.description,
                            "contract_type": template.contract_type.value if hasattr(template.contract_type, 'value') else str(template.contract_type),
                            "match_score": round(score * 100, 1),
                            "usage_count": template.usage_count,
                            "clauses_library_size": len(template.clauses_library) if template.clauses_library else 0,
                            "suggested_clauses": self._extract_suggested_clauses(template, required_clauses)
                        })

                matches.sort(key=lambda x: (x["match_score"], x["usage_count"]), reverse=True)

                return {
                    "tenant_id": tenant_id,
                    "query_contract_type": contract_type,
                    "match_threshold": match_threshold,
                    "total_templates": len(matches),
                    "matched_templates": matches[:5],
                    "generated_at": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"合同模板匹配失败: {str(e)}", exc_info=True)
            return {
                "tenant_id": tenant_id,
                "error": f"模板匹配失败: {str(e)}",
                "matched_templates": [],
                "total_templates": 0,
                "generated_at": datetime.now().isoformat()
            }

    def _calculate_match_score(
        self,
        template: Any,
        contract_type: Optional[str],
        contract_content: Optional[str],
        required_clauses: Optional[List[str]]
    ) -> float:
        """计算模板匹配分数"""
        score = 0.5

        if contract_type:
            template_type = template.contract_type.value if hasattr(template.contract_type, 'value') else str(template.contract_type)
            if template_type == contract_type:
                score += 0.3

        if contract_content:
            keywords = self.template_keywords.get(contract_type, [])
            for kw in keywords:
                if kw in contract_content and kw in (template.template_content or ""):
                    score += 0.05

        if required_clauses and template.clauses_library:
            matched = sum(1 for clause in required_clauses if clause in str(template.clauses_library))
            score += (matched / len(required_clauses)) * 0.2

        return min(score, 1.0)

    def _extract_suggested_clauses(
        self,
        template: Any,
        required_clauses: Optional[List[str]]
    ) -> List[str]:
        """提取建议条款"""
        suggested = []
        if template.clauses_library:
            for clause in template.clauses_library[:5]:
                if isinstance(clause, dict):
                    suggested.append(clause.get("title", str(clause)))
        return suggested


class DisputeResolutionAdvisor(ToolBase):
    """
    争议解决建议工具
    
    基于合同内容和条款提供争议解决建议
    与现有 dispute_resolution 条款分析无缝配合
    """

    def __init__(self):
        super().__init__(
            name="dispute_resolution_advisor",
            description="分析合同争议条款，提供仲裁/诉讼/调解的选择建议",
            timeout=30,
            tags=["法律", "争议", "仲裁", "诉讼", "调解"]
        )

        self.resolution_methods = {
            "arbitration": {
                "name": "仲裁",
                "advantages": ["一裁终局，速度快", "保密性强", "专业性强", "费用可控"],
                "disadvantages": ["裁决约束力有限", "无法上诉", "适用范围有限"],
                "suitable_cases": ["商业合同纠纷", "知识产权争议", "金额较大的合同纠纷"]
            },
            "litigation": {
                "name": "诉讼",
                "advantages": ["具有强制执行力", "可上诉", "适用范围广", "程序规范"],
                "disadvantages": ["周期长", "费用高", "公开审理", "效率较低"],
                "suitable_cases": ["需要强制执行的案件", "涉及第三方利益", "金额巨大或复杂案件"]
            },
            "mediation": {
                "name": "调解",
                "advantages": ["快速便捷", "成本低", "维护关系", "灵活高效"],
                "disadvantages": ["无强制执行力", "依赖双方意愿", "结果不确定"],
                "suitable_cases": ["双方关系重要", "金额较小", "希望快速解决"]
            },
            "negotiation": {
                "name": "协商",
                "advantages": ["零成本", "完全自主", "保密", "效率最高"],
                "disadvantages": ["无法律约束力", "可能无效"],
                "suitable_cases": ["争议较小", "双方都有诚意", "希望维持长期合作"]
            }
        }

    async def execute(
        self,
        contract_text: str,
        dispute_type: Optional[str] = None,
        dispute_amount: Optional[float] = None,
        urgency: str = "normal"
    ) -> Dict[str, Any]:
        """
        获取争议解决建议
        
        Args:
            contract_text: 合同文本
            dispute_type: 争议类型（payment/delivery/quality/termination/other）
            dispute_amount: 争议金额
            urgency: 紧急程度（urgent/normal/low）
            
        Returns:
            争议解决建议
        """
        try:
            contract_has_arbitration_clause = self._check_arbitration_clause(contract_text)
            contract_has_jurisdiction = self._check_jurisdiction_clause(contract_text)
            governing_law = self._extract_governing_law(contract_text)

            recommendations = self._generate_recommendations(
                contract_text, dispute_type, dispute_amount, urgency,
                contract_has_arbitration_clause, contract_has_jurisdiction, governing_law
            )

            return {
                "contract_has_arbitration_clause": contract_has_arbitration_clause,
                "contract_has_jurisdiction_clause": contract_has_jurisdiction,
                "governing_law": governing_law,
                "recommended_methods": recommendations,
                "analysis_summary": self._generate_summary(
                    contract_has_arbitration_clause, contract_has_jurisdiction, recommendations
                ),
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"争议解决建议失败: {str(e)}", exc_info=True)
            return {
                "error": f"生成建议失败: {str(e)}",
                "generated_at": datetime.now().isoformat()
            }

    def _check_arbitration_clause(self, text: str) -> bool:
        """检查是否有仲裁条款"""
        arbitration_keywords = ["仲裁", "arbitration", "仲裁委员会", "仲裁庭"]
        return any(kw in text.lower() for kw in arbitration_keywords)

    def _check_jurisdiction_clause(self, text: str) -> bool:
        """检查是否有管辖权条款"""
        jurisdiction_keywords = ["管辖", "法院", "诉讼", "jurisdiction", "court"]
        return any(kw in text.lower() for kw in jurisdiction_keywords)

    def _extract_governing_law(self, text: str) -> str:
        """提取适用法律"""
        law_patterns = [
            r"适用(.+?)法律",
            r"管辖法院(.+?)法院",
            r"适用(.+?)法律",
        ]
        for pattern in law_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return "中华人民共和国法律"

    def _generate_recommendations(
        self,
        contract_text: str,
        dispute_type: Optional[str],
        dispute_amount: Optional[float],
        urgency: str,
        has_arb: bool,
        has_jur: bool,
        governing_law: str
    ) -> List[Dict[str, Any]]:
        """生成建议"""
        recommendations = []

        if has_arb:
            rec = {
                "method": "arbitration",
                "name": "仲裁",
                "priority": 1,
                "reason": "合同已约定仲裁条款，应优先适用",
                "action": "按合同约定向指定仲裁机构申请仲裁"
            }
            recommendations.append(rec)

        if has_jur and not has_arb:
            rec = {
                "method": "litigation",
                "name": "诉讼",
                "priority": 1,
                "reason": "合同已约定管辖法院",
                "action": f"向约定的{governing_law}管辖法院提起诉讼"
            }
            recommendations.append(rec)

        if urgency == "urgent" and dispute_amount and dispute_amount > 100000:
            recommendations.append({
                "method": "injunction",
                "name": "申请行为保全",
                "priority": 2,
                "reason": "紧急情况下，为防止损失扩大",
                "action": "考虑向法院申请诉前或诉中财产保全"
            })

        recommendations.append({
            "method": "negotiation",
            "name": "协商谈判",
            "priority": 3,
            "reason": "成本最低，可维护商业关系",
            "action": "建议先尝试友好协商解决争议"
        })

        if dispute_type in ["payment", "quality"] and not has_arb:
            recommendations.append({
                "method": "mediation",
                "name": "调解",
                "priority": 4,
                "reason": "适合商业纠纷快速解决",
                "action": "可考虑行业调解组织或人民调解"
            })

        return recommendations

    def _generate_summary(
        self,
        has_arb: bool,
        has_jur: bool,
        recommendations: List[Dict[str, Any]]
    ) -> str:
        """生成总结"""
        if has_arb:
            return "合同已约定仲裁条款，建议优先通过仲裁解决争议。如仲裁无法达成一致，可考虑申请法院执行仲裁裁决。"
        elif has_jur:
            return "合同已约定管辖法院，建议按照约定向指定法院提起诉讼。在诉讼前可尝试协商或调解。"
        else:
            return "合同未约定争议解决条款，建议双方协商选择合适的争议解决方式。协商不成时，可向被告住所地或合同履行地法院起诉。"


class ContractRiskTrendAnalyzer(ToolBase):
    """
    合同风险趋势分析工具
    
    基于历史合同审核数据，分析风险趋势和改进建议
    """

    def __init__(self):
        super().__init__(
            name="contract_risk_trend_analyzer",
            description="分析合同审核历史数据，识别风险趋势和改进机会",
            timeout=30,
            tags=["法律", "合同", "风险", "趋势", "分析"]
        )

    async def execute(
        self,
        tenant_id: str,
        period_days: int = 90,
        contract_type: Optional[str] = None,
        include_improvements: bool = True
    ) -> Dict[str, Any]:
        """
        分析合同风险趋势
        
        Args:
            tenant_id: 租户ID
            period_days: 分析周期天数
            contract_type: 合同类型过滤
            include_improvements: 是否包含改进建议
            
        Returns:
            风险趋势分析结果
        """
        try:
            from app.core.database import async_session_maker
            from sqlalchemy import select, and_, func
            from app.models.contract_review import ContractReviewReport, RiskLevel
            from datetime import datetime, timedelta

            async with async_session_maker() as session:
                cutoff_date = datetime.now() - timedelta(days=period_days)

                conditions = [
                    ContractReviewReport.tenant_id == tenant_id,
                    ContractReviewReport.created_at >= cutoff_date
                ]

                if contract_type:
                    from app.models.contract_review import ContractType
                    try:
                        ct = ContractType(contract_type)
                        conditions.append(ContractReviewReport.contract_type == ct)
                    except ValueError:
                        pass

                stmt = select(ContractReviewReport).where(and_(*conditions))
                result = await session.execute(stmt)
                contracts = result.scalars().all()

                if not contracts:
                    return {
                        "tenant_id": tenant_id,
                        "period_days": period_days,
                        "total_contracts": 0,
                        "message": "该周期内无合同数据",
                        "generated_at": datetime.now().isoformat()
                    }

                analysis = self._analyze_risk_trend(contracts)

                if include_improvements:
                    analysis["improvement_suggestions"] = self._generate_improvement_suggestions(analysis)

                return {
                    "tenant_id": tenant_id,
                    "period_days": period_days,
                    "period_start": cutoff_date.isoformat(),
                    "period_end": datetime.now().isoformat(),
                    "total_contracts": len(contracts),
                    **analysis,
                    "generated_at": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"风险趋势分析失败: {str(e)}", exc_info=True)
            return {
                "tenant_id": tenant_id,
                "error": f"趋势分析失败: {str(e)}",
                "generated_at": datetime.now().isoformat()
            }

    def _analyze_risk_trend(self, contracts: List[Any]) -> Dict[str, Any]:
        """分析风险趋势"""
        risk_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        total_score = 0
        valid_scores = 0

        for contract in contracts:
            if contract.overall_risk_level:
                level = contract.overall_risk_level.value if hasattr(contract.overall_risk_level, 'value') else str(contract.overall_risk_level)
                risk_counts[level] = risk_counts.get(level, 0) + 1

            if contract.overall_risk_score is not None:
                total_score += contract.overall_risk_score
                valid_scores += 1

        avg_score = total_score / valid_scores if valid_scores > 0 else 0

        high_risk_ratio = risk_counts["high"] / len(contracts) if len(contracts) > 0 else 0
        critical_ratio = risk_counts["critical"] / len(contracts) if len(contracts) > 0 else 0

        trend_direction = "stable"
        if avg_score < 30:
            trend_direction = "improving"
        elif avg_score > 60:
            trend_direction = "declining"

        return {
            "risk_distribution": risk_counts,
            "average_risk_score": round(avg_score, 1),
            "risk_trend": trend_direction,
            "high_risk_ratio": round(high_risk_ratio * 100, 1),
            "critical_ratio": round(critical_ratio * 100, 1),
            "summary": self._generate_trend_summary(risk_counts, avg_score, trend_direction)
        }

    def _generate_trend_summary(
        self,
        risk_counts: Dict[str, int],
        avg_score: float,
        trend: str
    ) -> str:
        """生成趋势总结"""
        summary_parts = []

        if trend == "improving":
            summary_parts.append("合同风险呈改善趋势")
        elif trend == "declining":
            summary_parts.append("合同风险需关注，部分合同风险较高")
        else:
            summary_parts.append("合同风险整体保持稳定")

        summary_parts.append(f"平均风险评分{avg_score:.1f}分")

        high_total = risk_counts.get("high", 0) + risk_counts.get("critical", 0)
        if high_total > 0:
            summary_parts.append(f"其中{high_total}份合同存在中高风险")

        return "，".join(summary_parts)

    def _generate_improvement_suggestions(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成改进建议"""
        suggestions = []

        avg_score = analysis.get("average_risk_score", 50)
        if avg_score > 40:
            suggestions.append({
                "category": "风险培训",
                "priority": "high",
                "suggestion": "建议加强合同审核人员培训，提高风险识别能力",
                "impact": "降低中高风险合同比例"
            })

        high_ratio = analysis.get("high_risk_ratio", 0)
        if high_ratio > 20:
            suggestions.append({
                "category": "模板优化",
                "priority": "high",
                "suggestion": "建议完善标准合同模板，减少不利条款出现",
                "impact": "降低高风险合同比例"
            })

        suggestions.append({
            "category": "流程优化",
            "priority": "medium",
            "suggestion": "建议建立合同审核前置流程，在签订前识别风险",
            "impact": "提高审核效率，降低风险"
        })

        return suggestions


class EnterprisePolicyMatchReader(ToolBase):
    """
    企业政策匹配结果读取工具
    
    读取 EnterprisePolicyMatch 表中的匹配结果
    支持查询已匹配的政策通知
    """

    def __init__(self):
        super().__init__(
            name="enterprise_policy_match_reader",
            description="读取企业已匹配的政策通知结果，包括匹配分数和通知状态",
            timeout=30,
            tags=["法律", "政策", "企业匹配", "通知"]
        )

    async def execute(
        self,
        tenant_id: str,
        notification_status: Optional[str] = None,
        match_status: Optional[str] = None,
        min_score: float = 0.0,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        读取企业政策匹配结果
        
        Args:
            tenant_id: 租户ID
            notification_status: 通知状态过滤 (pending/sent/acknowledged/dismissed/failed)
            match_status: 匹配状态过滤 (active/inactive/expired)
            min_score: 最低匹配分数
            limit: 返回数量限制
            
        Returns:
            匹配结果列表
        """
        try:
            from app.core.database import async_session_maker
            from sqlalchemy import select, and_
            from app.models.enterprise_policy_match import (
                EnterprisePolicyMatch,
                NotificationStatus,
                MatchStatus
            )
            from app.models.policy import Policy

            async with async_session_maker() as session:
                conditions = [
                    EnterprisePolicyMatch.enterprise_id == tenant_id,
                    EnterprisePolicyMatch.match_score >= min_score
                ]

                if notification_status:
                    try:
                        ns = NotificationStatus(notification_status)
                        conditions.append(
                            EnterprisePolicyMatch.notification_status == ns
                        )
                    except ValueError:
                        pass

                if match_status:
                    try:
                        ms = MatchStatus(match_status)
                        conditions.append(EnterprisePolicyMatch.match_status == ms)
                    except ValueError:
                        pass

                stmt = select(EnterprisePolicyMatch).where(and_(*conditions))
                stmt = stmt.order_by(EnterprisePolicyMatch.match_score.desc())
                stmt = stmt.limit(limit)

                result = await session.execute(stmt)
                matches = result.scalars().all()

                match_results = []
                policy_ids = [m.policy_id for m in matches]

                if policy_ids:
                    policy_stmt = select(Policy).where(Policy.id.in_(policy_ids))
                    policy_result = await session.execute(policy_stmt)
                    policies = {str(p.id): p for p in policy_result.scalars().all()}

                    for match in matches:
                        policy = policies.get(match.policy_id)
                        if policy:
                            match_results.append({
                                "match_id": str(match.id),
                                "policy_id": str(match.policy_id),
                                "policy_title": policy.title,
                                "policy_summary": policy.summary,
                                "policy_source": policy.source_name,
                                "policy_priority": policy.priority.value if hasattr(policy.priority, 'value') else str(policy.priority),
                                "match_score": match.match_score,
                                "match_reasons": match.match_reasons or [],
                                "notification_status": match.notification_status.value if hasattr(match.notification_status, 'value') else str(match.notification_status),
                                "match_status": match.match_status.value if hasattr(match.match_status, 'value') else str(match.match_status),
                                "notified_at": match.notified_at.isoformat() if match.notified_at else None,
                                "acknowledged_at": match.acknowledged_at.isoformat() if match.acknowledged_at else None,
                                "created_at": match.created_at.isoformat() if match.created_at else None
                            })

                pending_count = sum(
                    1 for m in matches
                    if hasattr(m.notification_status, 'value') and m.notification_status.value == "pending"
                )

                return {
                    "tenant_id": tenant_id,
                    "total_matches": len(match_results),
                    "pending_notifications": pending_count,
                    "matches": match_results,
                    "query_params": {
                        "notification_status": notification_status,
                        "match_status": match_status,
                        "min_score": min_score,
                        "limit": limit
                    },
                    "generated_at": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"读取政策匹配结果失败: {str(e)}", exc_info=True)
            return {
                "tenant_id": tenant_id,
                "error": f"读取匹配结果失败: {str(e)}",
                "matches": [],
                "total_matches": 0,
                "generated_at": datetime.now().isoformat()
            }


class EnterprisePolicyMatcher(ToolBase):
    """
    企业政策智能匹配工具
    
    基于 TenantSettings 中的企业画像（行业、地区、规模、税种）
    匹配政策库中的适用政策
    """

    def __init__(self):
        super().__init__(
            name="enterprise_policy_matcher",
            description="根据企业画像（行业/地区/规模/税种）智能匹配政策库中的适用政策",
            timeout=30,
            tags=["法律", "政策", "智能匹配", "企业画像"]
        )

        self.industry_keywords = {
            "科技": ["高新技术", "软件", "互联网", "电子", "信息技术"],
            "制造": ["制造业", "工业", "机械", "汽车", "化工"],
            "服务": ["服务业", "咨询", "商务", "代理"],
            "金融": ["金融", "银行", "保险", "证券", "投资"],
            "建筑": ["建筑", "房地产", "工程", "物业"],
            "零售": ["零售", "商贸", "批发", "电商"],
            "农业": ["农业", "农产品", "种植", "养殖"]
        }

    async def execute(
        self,
        tenant_id: str,
        policy_categories: Optional[List[str]] = None,
        priority_filter: Optional[List[str]] = None,
        top_k: int = 10,
        include_rule_match: bool = True,
        include_semantic_match: bool = True
    ) -> Dict[str, Any]:
        """
        根据企业画像匹配政策
        
        Args:
            tenant_id: 租户ID
            policy_categories: 政策类别过滤
            priority_filter: 优先级过滤 (high/medium/low)
            top_k: 返回数量
            include_rule_match: 是否包含规则匹配
            include_semantic_match: 是否包含语义匹配
            
        Returns:
            匹配结果
        """
        try:
            from app.core.database import async_session_maker
            from sqlalchemy import select, and_
            from app.models.tenant_settings import TenantSettings
            from app.models.policy import Policy, PolicyStatus, PolicyPriority

            enterprise_profile = await self._get_enterprise_profile(tenant_id)

            if not enterprise_profile:
                return {
                    "tenant_id": tenant_id,
                    "error": "未找到企业画像信息",
                    "matches": [],
                    "generated_at": datetime.now().isoformat()
                }

            async with async_session_maker() as session:
                conditions = [Policy.status == PolicyStatus.ACTIVE]

                if policy_categories:
                    category_conditions = []
                    for cat in policy_categories:
                        category_conditions.append(Policy.categories.ilike(f"%{cat}%"))
                    if category_conditions:
                        from sqlalchemy import or_
                        conditions.append(or_(*category_conditions))

                if priority_filter:
                    priority_enums = []
                    for p in priority_filter:
                        try:
                            priority_enums.append(PolicyPriority(p))
                        except ValueError:
                            pass
                    if priority_enums:
                        conditions.append(Policy.priority.in_(priority_enums))

                stmt = select(Policy).where(and_(*conditions))
                result = await session.execute(stmt)
                policies = result.scalars().all()

                rule_matches = []
                semantic_matches = []

                for policy in policies:
                    if include_rule_match:
                        rule_score, rule_reasons = self._rule_based_match(
                            policy, enterprise_profile
                        )
                        if rule_score > 0:
                            rule_matches.append({
                                "policy_id": str(policy.id),
                                "title": policy.title,
                                "summary": policy.summary,
                                "match_score": rule_score,
                                "match_reasons": rule_reasons,
                                "match_type": "rule",
                                "source": policy.source_name,
                                "priority": policy.priority.value if hasattr(policy.priority, 'value') else str(policy.priority),
                                "industries": policy.industries,
                                "regions": policy.regions,
                                "tax_types": policy.tax_types
                            })

                    if include_semantic_match:
                        semantic_score, semantic_reasons = await self._semantic_match(
                            policy, enterprise_profile
                        )
                        if semantic_score > 0:
                            semantic_matches.append({
                                "policy_id": str(policy.id),
                                "title": policy.title,
                                "summary": policy.summary,
                                "match_score": semantic_score,
                                "match_reasons": semantic_reasons,
                                "match_type": "semantic",
                                "source": policy.source_name,
                                "priority": policy.priority.value if hasattr(policy.priority, 'value') else str(policy.priority)
                            })

                all_matches = rule_matches + semantic_matches
                all_matches.sort(key=lambda x: x["match_score"], reverse=True)
                top_matches = all_matches[:top_k]

                return {
                    "tenant_id": tenant_id,
                    "enterprise_profile": enterprise_profile,
                    "total_policies_searched": len(policies),
                    "rule_match_count": len(rule_matches),
                    "semantic_match_count": len(semantic_matches),
                    "top_k": top_k,
                    "matches": top_matches,
                    "high_priority_policies": [
                        m for m in top_matches
                        if m.get("priority") == "high" and m.get("match_score", 0) > 0.7
                    ],
                    "generated_at": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"企业政策匹配失败: {str(e)}", exc_info=True)
            return {
                "tenant_id": tenant_id,
                "error": f"政策匹配失败: {str(e)}",
                "matches": [],
                "generated_at": datetime.now().isoformat()
            }

    async def _get_enterprise_profile(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """获取企业画像"""
        from app.core.database import async_session_maker
        from sqlalchemy import select
        from app.models.tenant_settings import TenantSettings

        async with async_session_maker() as session:
            stmt = select(TenantSettings).where(
                TenantSettings.tenant_id == tenant_id
            )
            result = await session.execute(stmt)
            tenant = result.scalar_one_or_none()

            if not tenant:
                return None

            return {
                "industry": tenant.industry,
                "region": tenant.region,
                "scale": tenant.scale,
                "tax_types": tenant.tax_types or [],
                "company_name": tenant.company_name,
                "company_description": tenant.company_description
            }

    def _rule_based_match(
        self,
        policy: Any,
        profile: Dict[str, Any]
    ) -> tuple[float, List[str]]:
        """基于规则的政策匹配"""
        score = 0.0
        reasons = []

        if policy.industries and profile.get("industry"):
            for industry in policy.industries:
                if industry in str(profile.get("industry", "")):
                    score += 0.3
                    reasons.append(f"行业匹配: {industry}")
                    break

        if policy.regions and profile.get("region"):
            for region in policy.regions:
                if region in str(profile.get("region", "")):
                    score += 0.2
                    reasons.append(f"地区匹配: {region}")
                    break

        if policy.tax_types and profile.get("tax_types"):
            matched_tax_types = []
            for tt in policy.tax_types:
                if tt in profile.get("tax_types", []):
                    matched_tax_types.append(tt)
            if matched_tax_types:
                score += 0.3 * (len(matched_tax_types) / len(policy.tax_types))
                reasons.append(f"税种匹配: {', '.join(matched_tax_types)}")

        scale = profile.get("scale", "")
        if "小微" in scale or "微型" in scale:
            if any(kw in policy.content for kw in ["小微企业", "小微", "中小企业"]):
                score += 0.2
                reasons.append("企业规模匹配: 小微企业")
        elif "中型" in scale:
            if any(kw in policy.content for kw in ["中型企业", "中小企业"]):
                score += 0.2
                reasons.append("企业规模匹配: 中型企业")

        return min(score, 1.0), reasons

    async def _semantic_match(
        self,
        policy: Any,
        profile: Dict[str, Any]
    ) -> tuple[float, List[str]]:
        """基于语义的政策匹配"""
        try:
            from app.services.embedding_service import EmbeddingService

            embedding_service = EmbeddingService()
            profile_text = self._build_profile_text(profile)
            query_embedding = await embedding_service.get_embedding(profile_text)

            if not policy.embedding:
                return 0.0, []

            from app.services.policy_retrieval_service import PolicyRetrievalService
            retrieval_service = PolicyRetrievalService()
            score = retrieval_service._cosine_similarity(
                query_embedding,
                policy.embedding
            )

            if score > 0.5:
                reasons = [f"语义相似度: {score:.2f}"]
            else:
                reasons = []

            return score, reasons

        except Exception as e:
            logger.debug(f"语义匹配失败: {e}")
            return 0.0, []

    def _build_profile_text(self, profile: Dict[str, Any]) -> str:
        """构建企业画像文本"""
        parts = []

        if profile.get("company_name"):
            parts.append(f"企业名称: {profile['company_name']}")

        if profile.get("industry"):
            parts.append(f"所属行业: {profile['industry']}")

        if profile.get("region"):
            parts.append(f"所在地区: {profile['region']}")

        if profile.get("scale"):
            parts.append(f"企业规模: {profile['scale']}")

        if profile.get("tax_types"):
            parts.append(f"涉及税种: {', '.join(profile['tax_types'])}")

        if profile.get("company_description"):
            parts.append(f"企业描述: {profile['company_description']}")

        return "; ".join(parts)
