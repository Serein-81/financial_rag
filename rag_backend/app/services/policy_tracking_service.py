"""
政策法规智能追踪服务
提供政策订阅、推送和追踪功能
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from app.schemas.policy_tracking import (
    PolicyCategory,
    PolicyImpactLevel,
    SubscriptionStatus,
    NotificationFrequency,
    PolicySubscriptionRequest,
    PolicyUpdate,
    PolicyTrendAnalysis,
    PolicyQueryRequest,
    ComplianceDeadline,
    ComplianceCalendar,
)
from app.services.policy_retrieval_service import PolicyRetrievalService
from app.services.agent_tracer import AgentTracer
from app.agent_framework.tools.financial_data_tools import FinancialDataQueryTool

logger = logging.getLogger(__name__)


class PolicyTrackingService:
    """
    政策追踪服务
    
    功能：
    1. 政策订阅管理
    2. 政策更新推送
    3. 政策趋势分析
    4. 合规截止日期管理
    """

    def __init__(self):
        self.policy_retrieval = PolicyRetrievalService()
        self.agent_tracer = AgentTracer()
        self.financial_data_tool = FinancialDataQueryTool()
        
        self._subscriptions = {}
        self._policy_updates_cache = {}
        
        logger.info("✅ 政策追踪服务初始化完成")

    async def create_subscription(
        self,
        request: PolicySubscriptionRequest
    ) -> Dict[str, Any]:
        """
        创建政策订阅
        
        Args:
            request: 订阅请求
            
        Returns:
            Dict: 订阅结果
        """
        subscription_id = str(uuid.uuid4())
        
        expires_at = datetime.now() + timedelta(days=request.subscription_days)
        
        categories = request.get_categories()
        notification_methods = request.get_notification_methods()
        
        notification_freq = request.notification_frequency
        if hasattr(notification_freq, 'value'):
            notification_freq = notification_freq.value
        elif isinstance(notification_freq, str):
            notification_freq = notification_freq
        else:
            notification_freq = NotificationFrequency.DAILY.value
        
        subscription = {
            "subscription_id": subscription_id,
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
            "enterprise_id": request.enterprise_id,
            "industry": request.industry,
            "region": request.region,
            "company_size": request.company_size,
            "funding_stage": request.funding_stage,
            "policy_categories": categories,
            "categories": categories,
            "business_scope": categories,
            "keywords": request.keywords,
            "notification_channels": notification_methods,
            "notification_methods": notification_methods,
            "notification_frequency": notification_freq,
            "notification_email": request.notification_email,
            "notification_webhook": request.notification_webhook,
            "notification_phone": request.notification_phone,
            "severity_threshold": request.severity_threshold,
            "status": SubscriptionStatus.ACTIVE.value,
            "created_at": datetime.now(),
            "expires_at": expires_at
        }
        
        self._subscriptions[subscription_id] = subscription
        
        logger.info(f"📧 创建政策订阅: {subscription_id}")
        
        return {
            "subscription_id": subscription_id,
            "status": SubscriptionStatus.ACTIVE.value,
            "created_at": datetime.now(),
            "expires_at": expires_at,
            "message": "政策订阅创建成功"
        }

    async def get_subscriptions(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        status: Optional[SubscriptionStatus] = None
    ) -> List[Dict[str, Any]]:
        """
        获取订阅列表
        
        Args:
            tenant_id: 租户ID
            user_id: 用户ID（可选）
            status: 订阅状态（可选）
            
        Returns:
            List[Dict]: 订阅列表
        """
        subscriptions = []
        
        for sub in self._subscriptions.values():
            if sub["tenant_id"] != tenant_id:
                continue
            
            if user_id and sub["user_id"] != user_id:
                continue
            
            if status and sub["status"] != status.value:
                continue
            
            subscriptions.append(sub)
        
        return subscriptions

    async def cancel_subscription(
        self,
        subscription_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        取消订阅
        
        Args:
            subscription_id: 订阅ID
            user_id: 用户ID
            
        Returns:
            Dict: 取消结果
        """
        if subscription_id not in self._subscriptions:
            raise ValueError(f"订阅不存在: {subscription_id}")
        
        subscription = self._subscriptions[subscription_id]
        
        if subscription["user_id"] != user_id:
            raise PermissionError("无权操作此订阅")
        
        subscription["status"] = SubscriptionStatus.CANCELLED.value
        subscription["updated_at"] = datetime.now()
        
        logger.info(f"❌ 取消政策订阅: {subscription_id}")
        
        return {
            "subscription_id": subscription_id,
            "status": SubscriptionStatus.CANCELLED.value,
            "message": "订阅已取消"
        }

    async def fetch_policy_updates(
        self,
        categories: Optional[List[PolicyCategory]] = None,
        keywords: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[PolicyUpdate]:
        """
        获取最新政策更新
        
        Args:
            categories: 政策类别筛选
            keywords: 关键词筛选
            limit: 返回数量
            
        Returns:
            List[PolicyUpdate]: 政策更新列表
        """
        try:
            search_keyword = " ".join(keywords) if keywords else "税收政策"
            
            results = await self.policy_retrieval.semantic_search(
                query=search_keyword,
                top_k=limit
            )
            
            policy_updates = []
            for item in results:
                policy_update = PolicyUpdate(
                    update_id=str(uuid.uuid4()),
                    policy_id=item.get("policy_id", str(uuid.uuid4())),
                    policy_name=item.get("title", "未知政策"),
                    policy_category=self._infer_category(item),
                    issuing_authority=item.get("issuing_authority", "未知机构"),
                    issue_date=item.get("issue_date", datetime.now().date()),
                    effective_date=item.get("effective_date"),
                    policy_summary=item.get("content", item.get("summary", ""))[:500],
                    impact_level=self._infer_impact_level(item),
                    affected_industries=item.get("industries", []),
                    key_changes=item.get("key_changes", []),
                    compliance_requirements=item.get("requirements", []),
                    related_policies=item.get("related_policies", []),
                    source_url=item.get("source_url"),
                    is_new=True,
                    is_amendment=False
                )
                policy_updates.append(policy_update)
            
            if categories:
                policy_updates = [
                    p for p in policy_updates
                    if p.policy_category in categories
                ]
            
            return policy_updates[:limit]
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 获取政策更新数据失败: {e}", exc_info=True)
            return []
        except (OSError, IOError) as e:
            logger.error(f"❌ 获取政策更新IO失败: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"❌ 获取政策更新失败: {e}", exc_info=True)
            return []

    def _infer_category(self, item: Dict[str, Any]) -> PolicyCategory:
        """推断政策类别"""
        content = (item.get("title", "") + item.get("content", "")).lower()
        
        if any(keyword in content for keyword in ["税", "增值税", "所得税", "税务"]):
            return PolicyCategory.TAX
        elif any(keyword in content for keyword in ["财务", "会计", "审计"]):
            return PolicyCategory.FINANCE
        elif any(keyword in content for keyword in ["劳动", "社保", "工资"]):
            return PolicyCategory.LABOR
        elif any(keyword in content for keyword in ["环境", "污染", "排放"]):
            return PolicyCategory.ENVIRONMENT
        elif any(keyword in content for keyword in ["贸易", "关税", "进出口"]):
            return PolicyCategory.TRADE
        elif any(keyword in content for keyword in ["技术", "高新", "创新"]):
            return PolicyCategory.TECHNOLOGY
        
        return PolicyCategory.LEGAL

    def _infer_impact_level(self, item: Dict[str, Any]) -> PolicyImpactLevel:
        """推断影响级别"""
        content = (item.get("title", "") + item.get("content", "")).lower()
        
        if any(keyword in content for keyword in ["重大", "重要", "关键", "强制"]):
            return PolicyImpactLevel.HIGH
        elif any(keyword in content for keyword in ["影响", "调整", "变化"]):
            return PolicyImpactLevel.MEDIUM
        
        return PolicyImpactLevel.LOW

    async def query_policies(
        self,
        request: PolicyQueryRequest
    ) -> Dict[str, Any]:
        """
        查询政策
        
        Args:
            request: 查询请求
            
        Returns:
            Dict: 查询结果
        """
        keywords = request.keywords or []
        categories = request.categories or []
        limit = request.limit
        
        policies = await self.fetch_policy_updates(
            categories=categories,
            keywords=keywords,
            limit=limit + request.offset
        )
        
        if request.offset > 0:
            policies = policies[request.offset:]
        
        has_more = len(policies) > limit
        policies = policies[:limit]
        
        return {
            "total_count": len(policies),
            "policies": [p.model_dump() for p in policies],
            "has_more": has_more
        }

    async def analyze_policy_trends(
        self,
        tenant_id: str,
        user_id: str,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        分析政策趋势
        
        Args:
            tenant_id: 租户ID
            user_id: 用户ID
            period_start: 分析期间开始
            period_end: 分析期间结束
            
        Returns:
            Dict: 趋势分析结果
        """
        trend_id = str(uuid.uuid4())
        
        logger.info(f"📊 开始政策趋势分析: {trend_id}")
        
        policies = await self.fetch_policy_updates(limit=200)
        
        policies_by_category = {}
        policies_by_impact = {}
        
        for policy in policies:
            category = policy.policy_category.value
            policies_by_category[category] = policies_by_category.get(category, 0) + 1
            
            impact = policy.impact_level.value
            policies_by_impact[impact] = policies_by_impact.get(impact, 0) + 1
        
        key_themes = self._extract_key_themes(policies)
        regulatory_focus = self._identify_regulatory_focus(policies)
        
        upcoming_changes = [
            f"{policy.policy_name} 将于 {policy.effective_date} 生效"
            for policy in policies
            if policy.effective_date and policy.effective_date > datetime.now().date()
        ][:5]
        
        compliance_deadlines = [
            {
                "policy_name": policy.policy_name,
                "deadline": str(policy.effective_date) if policy.effective_date else "待定",
                "requirement": requirement
            }
            for policy in policies
            for requirement in policy.compliance_requirements[:1]
            if policy.effective_date
        ][:10]
        
        analysis = PolicyTrendAnalysis(
            trend_id=trend_id,
            period_start=period_start,
            period_end=period_end,
            total_policies=len(policies),
            new_policies=sum(1 for p in policies if p.is_new),
            amended_policies=sum(1 for p in policies if p.is_amendment),
            policies_by_category=policies_by_category,
            policies_by_impact=policies_by_impact,
            key_themes=key_themes,
            regulatory_focus=regulatory_focus,
            upcoming_changes=upcoming_changes,
            compliance_deadlines=compliance_deadlines,
            insights=self._generate_trend_insights(policies),
            recommendations=self._generate_recommendations(policies)
        )
        
        return analysis.model_dump()

    def _extract_key_themes(self, policies: List[PolicyUpdate]) -> List[str]:
        """提取关键主题"""
        themes = []
        
        tax_policies = [p for p in policies if p.policy_category == PolicyCategory.TAX]
        if tax_policies:
            themes.append(f"税收优惠政策关注度提升，关注 {len(tax_policies)} 项相关政策")
        
        tech_policies = [p for p in policies if p.policy_category == PolicyCategory.TECHNOLOGY]
        if tech_policies:
            themes.append(f"科技创新政策持续发力，新增 {len(tech_policies)} 项政策")
        
        labor_policies = [p for p in policies if p.policy_category == PolicyCategory.LABOR]
        if labor_policies:
            themes.append(f"劳动用工政策变化，建议关注 {len(labor_policies)} 项规定")
        
        if not themes:
            themes.append("政策环境总体稳定")
        
        return themes

    def _identify_regulatory_focus(self, policies: List[PolicyUpdate]) -> List[str]:
        """识别监管重点"""
        focus_areas = []
        
        high_impact = [p for p in policies if p.impact_level == PolicyImpactLevel.HIGH]
        if high_impact:
            focus_areas.append(f"重点关注 {len(high_impact)} 项高影响政策")
        
        tax_focus = [p for p in policies if p.policy_category == PolicyCategory.TAX]
        if tax_focus:
            focus_areas.append("税务合规仍是监管重点")
        
        finance_focus = [p for p in policies if p.policy_category == PolicyCategory.FINANCE]
        if finance_focus:
            focus_areas.append("财务报告和信息披露要求趋严")
        
        return focus_areas

    def _generate_trend_insights(self, policies: List[PolicyUpdate]) -> List[str]:
        """生成趋势洞察"""
        insights = []
        
        if len(policies) > 100:
            insights.append("近期政策更新频繁，建议建立政策跟踪机制")
        else:
            insights.append("政策环境相对稳定，保持常规关注即可")
        
        high_impact_ratio = sum(1 for p in policies if p.impact_level == PolicyImpactLevel.HIGH) / max(len(policies), 1)
        if high_impact_ratio > 0.2:
            insights.append("高影响政策占比偏高，需重点关注合规风险")
        
        return insights

    def _generate_recommendations(self, policies: List[PolicyUpdate]) -> List[str]:
        """生成建议"""
        recommendations = []
        
        recommendations.append("定期审查最新政策，确保业务合规")
        
        urgent_policies = [
            p for p in policies
            if p.effective_date and (p.effective_date - datetime.now().date()).days <= 30
        ]
        if urgent_policies:
            recommendations.append(f"关注 {len(urgent_policies)} 项即将生效的政策，及时调整业务")
        
        recommendations.append("建议订阅政策推送服务，及时获取更新")
        
        return recommendations

    async def get_compliance_calendar(
        self,
        tenant_id: str,
        user_id: str,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        获取合规日历
        
        Args:
            tenant_id: 租户ID
            user_id: 用户ID
            period_start: 期间开始
            period_end: 期间结束
            
        Returns:
            Dict: 合规日历
        """
        calendar_id = str(uuid.uuid4())
        
        policies = await self.fetch_policy_updates(limit=100)
        
        deadlines = []
        current_date = datetime.now().date()
        
        for policy in policies:
            if policy.effective_date:
                days_remaining = (policy.effective_date - current_date).days
                
                urgency = "高" if days_remaining < 0 else ("中" if days_remaining < 30 else "低")
                
                deadline = ComplianceDeadline(
                    deadline_id=str(uuid.uuid4()),
                    policy_name=policy.policy_name,
                    requirement=policy.compliance_requirements[0] if policy.compliance_requirements else "合规要求待确认",
                    deadline_date=policy.effective_date,
                    days_remaining=days_remaining,
                    urgency_level=urgency,
                    status="逾期" if days_remaining < 0 else ("即将到期" if days_remaining < 30 else "正常"),
                    action_items=[
                        "审查政策要求",
                        "评估业务影响",
                        "制定合规计划"
                    ]
                )
                deadlines.append(deadline)
        
        deadlines.sort(key=lambda x: x.deadline_date)
        
        upcoming_count = sum(1 for d in deadlines if 0 <= d.days_remaining <= 30)
        overdue_count = sum(1 for d in deadlines if d.days_remaining < 0)
        
        calendar = ComplianceCalendar(
            calendar_id=calendar_id,
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            deadlines=deadlines,
            upcoming_count=upcoming_count,
            overdue_count=overdue_count,
            generated_at=datetime.now()
        )
        
        return calendar.model_dump()

    async def notify_subscribers(
        self,
        subscription_id: str
    ) -> Dict[str, Any]:
        """
        通知订阅者
        
        Args:
            subscription_id: 订阅ID
            
        Returns:
            Dict: 通知结果
        """
        if subscription_id not in self._subscriptions:
            raise ValueError(f"订阅不存在: {subscription_id}")
        
        subscription = self._subscriptions[subscription_id]
        
        categories = [PolicyCategory(cat) for cat in subscription["policy_categories"]]
        keywords = subscription["keywords"]
        
        updates = await self.fetch_policy_updates(categories=categories, keywords=keywords, limit=20)
        
        new_count = sum(1 for u in updates if u.is_new)
        amended_count = sum(1 for u in updates if u.is_amendment)
        high_impact_count = sum(1 for u in updates if u.impact_level == PolicyImpactLevel.HIGH)
        
        logger.info(
            f"📧 发送政策通知: 订阅={subscription_id}, "
            f"新政策={new_count}, 修订={amended_count}, 高影响={high_impact_count}"
        )
        
        return {
            "notification_id": str(uuid.uuid4()),
            "subscription_id": subscription_id,
            "user_id": subscription["user_id"],
            "policy_updates": [u.model_dump() for u in updates],
            "new_policies_count": new_count,
            "amended_policies_count": amended_count,
            "high_impact_count": high_impact_count,
            "sent_at": datetime.now(),
            "notification_channel": subscription["notification_channels"][0] if subscription["notification_channels"] else "in_app",
            "read_status": False
        }
