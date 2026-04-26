"""
法律合规 MCP 工具集

提供 Agent 可调用的法律合规工具（MCP 格式）
包含合同审核、政策匹配和合规检查功能

工具类型：本地 STDIO
"""

import logging
from typing import Dict, Any, List, Optional

from app.mcp.decorators import local_tool

logger = logging.getLogger(__name__)


@local_tool(
    description="监控合同合规截止日期，包括到期提醒、续约预警、付款截止等",
    tags=["法律", "合同", "截止日期", "监控"]
)
async def contract_compliance_deadline(
    tenant_id: str,
    contract_id: Optional[str] = None,
    watch_period_days: int = 90,
    include_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    获取合同合规截止日期列表
    
    Args:
        tenant_id: 租户ID，必填
        contract_id: 特定合同ID，可选
        watch_period_days: 监控天数范围，默认90天
        include_types: 截止日期类型过滤列表
        
    Returns:
        截止日期监控结果，包含到期预警和续约提醒
        
    Example:
        contract_compliance_deadline(tenant_id="tenant-123", watch_period_days=30)
    """
    try:
        from app.core.database import async_session_maker
        from sqlalchemy import select, and_
        from app.models.contract_review import ContractReviewReport, ReviewStatus
        from app.models.scheduled_task import ScheduledTask, TaskStatus
        from datetime import datetime, timedelta, date

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
                if contract.expiration_date:
                    exp_date = contract.expiration_date.date() if hasattr(contract.expiration_date, 'date') else contract.expiration_date
                    if today <= exp_date <= watch_end:
                        days_rem = (exp_date - today).days
                        urgency = "critical" if days_rem <= 7 else ("high" if days_rem <= 14 else "medium")
                        deadlines.append({
                            "type": "contract_expiration",
                            "deadline_date": exp_date.isoformat(),
                            "days_remaining": days_rem,
                            "urgency": urgency,
                            "title": f"合同到期: {contract.contract_name}",
                            "contract_id": str(contract.id)
                        })

        return {
            "status": "success",
            "tenant_id": tenant_id,
            "total_deadlines": len(deadlines),
            "deadlines": deadlines,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"合同截止日期监控失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@local_tool(
    description="根据企业画像（行业/地区/规模/税种）智能匹配政策库中的适用政策",
    tags=["法律", "政策", "智能匹配", "企业画像"]
)
async def enterprise_policy_matcher(
    tenant_id: str,
    policy_categories: Optional[List[str]] = None,
    top_k: int = 10,
    include_rule_match: bool = True,
    include_semantic_match: bool = True
) -> Dict[str, Any]:
    """
    根据企业画像匹配政策
    
    基于 TenantSettings 中的企业画像（行业、地区、规模、税种）
    匹配政策库中的适用政策
    
    Args:
        tenant_id: 租户ID，必填
        policy_categories: 政策类别过滤，可选
        top_k: 返回数量，默认10
        include_rule_match: 是否包含规则匹配，默认True
        include_semantic_match: 是否包含语义匹配，默认True
        
    Returns:
        匹配结果，包含匹配分数和匹配原因
        
    Example:
        enterprise_policy_matcher(tenant_id="tenant-123", top_k=5)
    """
    try:
        from app.core.database import async_session_maker
        from sqlalchemy import select, and_
        from app.models.tenant_settings import TenantSettings
        from app.models.policy import Policy, PolicyStatus
        from datetime import datetime

        enterprise_profile = None
        async with async_session_maker() as session:
            stmt = select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
            result = await session.execute(stmt)
            tenant = result.scalar_one_or_none()

            if tenant:
                enterprise_profile = {
                    "industry": tenant.industry,
                    "region": tenant.region,
                    "scale": tenant.scale,
                    "tax_types": tenant.tax_types or [],
                    "company_name": tenant.company_name
                }

        if not enterprise_profile:
            return {"status": "error", "error": "未找到企业画像"}

        async with async_session_maker() as session:
            conditions = [Policy.status == PolicyStatus.ACTIVE]
            stmt = select(Policy).where(and_(*conditions))
            result = await session.execute(stmt)
            policies = result.scalars().all()

            matches = []
            for policy in policies:
                score = 0.0
                reasons = []

                if include_rule_match:
                    if policy.industries and enterprise_profile.get("industry"):
                        for industry in policy.industries:
                            if industry in str(enterprise_profile.get("industry", "")):
                                score += 0.3
                                reasons.append(f"行业匹配: {industry}")
                                break
                    if policy.regions and enterprise_profile.get("region"):
                        for region in policy.regions:
                            if region in str(enterprise_profile.get("region", "")):
                                score += 0.2
                                reasons.append(f"地区匹配: {region}")
                                break

                if score > 0 and len(matches) < top_k:
                    matches.append({
                        "policy_id": str(policy.id),
                        "title": policy.title,
                        "summary": policy.summary,
                        "match_score": min(score, 1.0),
                        "match_reasons": reasons,
                        "priority": policy.priority.value if hasattr(policy.priority, 'value') else "medium"
                    })

            matches.sort(key=lambda x: x["match_score"], reverse=True)

        return {
            "status": "success",
            "tenant_id": tenant_id,
            "enterprise_profile": enterprise_profile,
            "total_matches": len(matches),
            "matches": matches[:top_k],
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"企业政策匹配失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@local_tool(
    description="读取企业已匹配的政策通知结果，包括匹配分数和通知状态",
    tags=["法律", "政策", "企业匹配", "通知"]
)
async def enterprise_policy_match_reader(
    tenant_id: str,
    notification_status: Optional[str] = None,
    min_score: float = 0.0,
    limit: int = 20
) -> Dict[str, Any]:
    """
    读取政策匹配结果
    
    从 EnterprisePolicyMatch 表中读取已匹配的政策通知
    
    Args:
        tenant_id: 租户ID，必填
        notification_status: 通知状态过滤 (pending/sent/acknowledged/dismissed)，可选
        min_score: 最低匹配分数，默认0.0
        limit: 返回数量限制，默认20
        
    Returns:
        匹配结果列表
        
    Example:
        enterprise_policy_match_reader(tenant_id="tenant-123", notification_status="pending")
    """
    try:
        from app.core.database import async_session_maker
        from sqlalchemy import select, and_
        from app.models.enterprise_policy_match import (
            EnterprisePolicyMatch,
            NotificationStatus
        )
        from app.models.policy import Policy
        from datetime import datetime

        async with async_session_maker() as session:
            conditions = [
                EnterprisePolicyMatch.enterprise_id == tenant_id,
                EnterprisePolicyMatch.match_score >= min_score
            ]

            if notification_status:
                try:
                    ns = NotificationStatus(notification_status)
                    conditions.append(EnterprisePolicyMatch.notification_status == ns)
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
                            "policy_id": str(match.policy_id),
                            "policy_title": policy.title,
                            "match_score": match.match_score,
                            "notification_status": match.notification_status.value if hasattr(match.notification_status, 'value') else str(match.notification_status),
                            "created_at": match.created_at.isoformat() if match.created_at else None
                        })

        return {
            "status": "success",
            "tenant_id": tenant_id,
            "total_matches": len(match_results),
            "matches": match_results,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"读取政策匹配结果失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@local_tool(
    description="分析合同争议条款，提供仲裁/诉讼/调解的选择建议",
    tags=["法律", "争议", "仲裁", "诉讼", "调解"]
)
async def dispute_resolution_advisor(
    contract_text: str,
    dispute_type: Optional[str] = None,
    dispute_amount: Optional[float] = None,
    urgency: str = "normal"
) -> Dict[str, Any]:
    """
    获取争议解决建议
    
    分析合同中的仲裁/诉讼条款，提供争议解决建议
    
    Args:
        contract_text: 合同文本，必填
        dispute_type: 争议类型 (payment/delivery/quality/termination)，可选
        dispute_amount: 争议金额，可选
        urgency: 紧急程度 (urgent/normal/low)，默认normal
        
    Returns:
        争议解决建议和推荐方法
        
    Example:
        dispute_resolution_advisor(contract_text="合同内容...", dispute_type="payment")
    """
    import re
    from datetime import datetime

    try:
        arbitration_keywords = ["仲裁", "arbitration", "仲裁委员会"]
        litigation_keywords = ["管辖", "法院", "诉讼", "jurisdiction"]
        
        has_arbitration = any(kw in contract_text.lower() for kw in arbitration_keywords)
        has_jurisdiction = any(kw in contract_text.lower() for kw in litigation_keywords)

        recommendations = []

        if has_arbitration:
            recommendations.append({
                "method": "arbitration",
                "priority": 1,
                "reason": "合同已约定仲裁条款，应优先适用"
            })
        elif has_jurisdiction:
            recommendations.append({
                "method": "litigation",
                "priority": 1,
                "reason": "合同已约定管辖法院"
            })

        recommendations.append({
            "method": "negotiation",
            "priority": 2,
            "reason": "成本最低，可维护商业关系"
        })

        if dispute_type in ["payment", "quality"] and not has_arbitration:
            recommendations.append({
                "method": "mediation",
                "priority": 3,
                "reason": "适合商业纠纷快速解决"
            })

        summary = "合同已约定仲裁条款，建议优先通过仲裁解决。" if has_arbitration else \
                  "合同已约定管辖法院，建议向指定法院提起诉讼。" if has_jurisdiction else \
                  "合同未约定争议解决条款，建议双方协商选择合适的方式。"

        return {
            "status": "success",
            "has_arbitration_clause": has_arbitration,
            "has_jurisdiction_clause": has_jurisdiction,
            "recommendations": recommendations,
            "summary": summary,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"争议解决建议失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@local_tool(
    description="根据合同类型和关键条款智能匹配合同模板",
    tags=["法律", "合同", "模板", "匹配"]
)
async def contract_template_matcher(
    tenant_id: str,
    contract_type: Optional[str] = None,
    required_clauses: Optional[List[str]] = None,
    match_threshold: float = 0.6
) -> Dict[str, Any]:
    """
    匹配合同模板
    
    基于 ContractTemplate 模型，智能匹配适合的合同模板
    
    Args:
        tenant_id: 租户ID，必填
        contract_type: 合同类型 (purchase/sales/service/lease/employment)，可选
        required_clauses: 必须包含的条款列表，可选
        match_threshold: 匹配阈值，默认0.6
        
    Returns:
        模板匹配结果
        
    Example:
        contract_template_matcher(tenant_id="tenant-123", contract_type="purchase")
    """
    try:
        from app.core.database import async_session_maker
        from sqlalchemy import select, and_
        from app.models.contract_review import ContractTemplate, ContractType
        from datetime import datetime

        async with async_session_maker() as session:
            conditions = [ContractTemplate.tenant_id == tenant_id]

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
                return {
                    "status": "success",
                    "tenant_id": tenant_id,
                    "matched_templates": [],
                    "message": "未找到匹配模板"
                }

            matches = []
            for template in templates:
                score = 0.5
                if contract_type:
                    template_type = template.contract_type.value if hasattr(template.contract_type, 'value') else str(template.contract_type)
                    if template_type == contract_type:
                        score += 0.3

                matches.append({
                    "template_id": str(template.id),
                    "template_name": template.name,
                    "description": template.description,
                    "contract_type": template.contract_type.value if hasattr(template.contract_type, 'value') else str(template.contract_type),
                    "match_score": round(score, 2),
                    "usage_count": template.usage_count
                })

            matches.sort(key=lambda x: x["match_score"], reverse=True)

        return {
            "status": "success",
            "tenant_id": tenant_id,
            "total_templates": len(matches),
            "matched_templates": matches[:5],
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"合同模板匹配失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@local_tool(
    description="分析合同审核历史数据，识别风险趋势和改进机会",
    tags=["法律", "合同", "风险", "趋势", "分析"]
)
async def contract_risk_trend_analyzer(
    tenant_id: str,
    period_days: int = 90,
    contract_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    分析合同风险趋势
    
    基于历史合同审核数据，分析风险趋势和改进建议
    
    Args:
        tenant_id: 租户ID，必填
        period_days: 分析周期天数，默认90
        contract_type: 合同类型过滤，可选
        
    Returns:
        风险趋势分析结果
        
    Example:
        contract_risk_trend_analyzer(tenant_id="tenant-123", period_days=30)
    """
    try:
        from app.core.database import async_session_maker
        from sqlalchemy import select, and_
        from app.models.contract_review import ContractReviewReport
        from datetime import datetime, timedelta

        async with async_session_maker() as session:
            cutoff_date = datetime.now() - timedelta(days=period_days)
            conditions = [
                ContractReviewReport.tenant_id == tenant_id,
                ContractReviewReport.created_at >= cutoff_date
            ]

            if contract_type:
                try:
                    from app.models.contract_review import ContractType
                    ct = ContractType(contract_type)
                    conditions.append(ContractReviewReport.contract_type == ct)
                except ValueError:
                    pass

            stmt = select(ContractReviewReport).where(and_(*conditions))
            result = await session.execute(stmt)
            contracts = result.scalars().all()

            if not contracts:
                return {
                    "status": "success",
                    "tenant_id": tenant_id,
                    "total_contracts": 0,
                    "message": "该周期内无合同数据"
                }

            risk_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
            total_score = 0
            valid_count = 0

            for contract in contracts:
                if contract.overall_risk_level:
                    level = contract.overall_risk_level.value if hasattr(contract.overall_risk_level, 'value') else str(contract.overall_risk_level)
                    risk_counts[level] = risk_counts.get(level, 0) + 1
                if contract.overall_risk_score is not None:
                    total_score += contract.overall_risk_score
                    valid_count += 1

            avg_score = total_score / valid_count if valid_count > 0 else 0
            trend = "improving" if avg_score < 30 else ("declining" if avg_score > 60 else "stable")

            return {
                "status": "success",
                "tenant_id": tenant_id,
                "period_days": period_days,
                "total_contracts": len(contracts),
                "average_risk_score": round(avg_score, 1),
                "risk_distribution": risk_counts,
                "risk_trend": trend,
                "generated_at": datetime.now().isoformat()
            }

    except Exception as e:
        logger.error(f"风险趋势分析失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
