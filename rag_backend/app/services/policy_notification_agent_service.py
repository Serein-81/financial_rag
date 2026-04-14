"""
政策通知智能体服务

集成 PolicyNotificationAgent 的服务层：
1. 管理 Agent 实例
2. 协调 LLM 调用
3. 提供智能匹配和通知生成
4. 降级到规则引擎
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from app.multi_agent_system.agents.policy_notification_agent import (
    PolicyNotificationAgent,
    EnterpriseProfile,
    MatchScore,
    PolicyUnderstanding,
    NotificationContent,
    create_policy_notification_agent
)
from app.services.policy_event_service import policy_event_service

logger = logging.getLogger(__name__)


class PolicyNotificationAgentService:
    """
    政策通知智能体服务
    
    功能：
    1. 初始化和管理 PolicyNotificationAgent
    2. 提供智能匹配接口
    3. 提供个性化通知生成接口
    4. 智能优先级排序
    5. 降级机制（LLM 不可用时回退到规则引擎）
    """
    
    def __init__(
        self,
        llm_adapter: Optional[BaseLLMAdapter] = None,
        tool_manager: Optional[ToolManager] = None
    ):
        """
        初始化服务
        
        Args:
            llm_adapter: LLM 适配器（可选）
            tool_manager: 工具管理器（可选）
        """
        self.llm_adapter = llm_adapter
        self.tool_manager = tool_manager
        self.agent: Optional[PolicyNotificationAgent] = None
        self.use_llm = llm_adapter is not None
        
        if self.use_llm:
            self.agent = create_policy_notification_agent(
                llm_adapter=llm_adapter,
                tool_manager=tool_manager
            )
            logger.info("✅ PolicyNotificationAgent 已启用（LLM 模式）")
        else:
            logger.warning("⚠️ LLM 适配器未提供，使用规则引擎模式")
    
    def _build_enterprise_profile(
        self,
        tenant_data: Dict[str, Any]
    ) -> EnterpriseProfile:
        """
        构建企业画像
        
        Args:
            tenant_data: 租户数据
            
        Returns:
            EnterpriseProfile: 企业画像
        """
        return EnterpriseProfile(
            enterprise_id=str(tenant_data.get("id", "")),
            name=tenant_data.get("name", "未知企业"),
            industry=tenant_data.get("industry"),
            region=tenant_data.get("region"),
            scale=tenant_data.get("scale"),
            tax_types=tenant_data.get("tax_types", []),
            keywords=tenant_data.get("keywords", []),
            business_scope=tenant_data.get("business_scope"),
            recent_interests=tenant_data.get("recent_interests", []),
            preferences=tenant_data.get("preferences", {})
        )
    
    async def match_policy_for_enterprise(
        self,
        policy: Dict[str, Any],
        enterprise_profile: EnterpriseProfile
    ) -> Dict[str, Any]:
        """
        匹配政策和企业的智能方法
        
        Args:
            policy: 政策数据
            enterprise_profile: 企业画像
            
        Returns:
            Dict: 匹配结果，包含：
            - match_score: 匹配分数
            - match_reasons: 匹配原因
            - policy_understanding: 政策理解
            - use_llm: 是否使用了 LLM
        """
        if self.use_llm and self.agent:
            try:
                match_score, reasons, understanding = await self.agent.match_enterprise_policy(
                    policy=policy,
                    enterprise_profile=enterprise_profile
                )
                
                return {
                    "match_score": match_score.total_score,
                    "semantic_score": match_score.semantic_score,
                    "industry_score": match_score.industry_score,
                    "region_score": match_score.region_score,
                    "scale_score": match_score.scale_score,
                    "tax_type_score": match_score.tax_type_score,
                    "urgency_score": match_score.urgency_score,
                    "match_reasons": [
                        {
                            "category": r.category,
                            "reason": r.reason,
                            "items": r.matched_items,
                            "confidence": r.confidence
                        }
                        for r in reasons
                    ],
                    "policy_understanding": {
                        "summary": understanding.summary,
                        "core_objectives": understanding.core_objectives,
                        "applicable_conditions": understanding.applicable_conditions,
                        "key_requirements": understanding.key_requirements,
                        "deadlines": understanding.deadlines,
                        "opportunities": understanding.opportunities,
                        "risks": understanding.risks,
                        "impact_level": understanding.impact_level
                    },
                    "use_llm": True
                }
                
            except Exception as e:
                logger.error(f"❌ LLM 匹配失败，降级到规则引擎: {e}")
                return await self._rule_based_match(policy, enterprise_profile)
        else:
            return await self._rule_based_match(policy, enterprise_profile)
    
    async def _rule_based_match(
        self,
        policy: Dict[str, Any],
        enterprise_profile: EnterpriseProfile
    ) -> Dict[str, Any]:
        """
        基于规则引擎的匹配（降级方案）
        
        Args:
            policy: 政策数据
            enterprise_profile: 企业画像
            
        Returns:
            Dict: 匹配结果
        """
        score = 0.0
        reasons = []
        
        if policy.get("industries") and enterprise_profile.industry:
            if enterprise_profile.industry in policy["industries"]:
                score += 0.4
                reasons.append(f"行业匹配: {enterprise_profile.industry}")
        
        if policy.get("regions") and enterprise_profile.region:
            if enterprise_profile.region in policy["regions"]:
                score += 0.2
                reasons.append(f"地区匹配: {enterprise_profile.region}")
        
        if policy.get("tax_types") and enterprise_profile.tax_types:
            matching = set(policy["tax_types"]) & set(enterprise_profile.tax_types)
            if matching:
                score += 0.3
                reasons.append(f"税种匹配: {', '.join(list(matching)[:3])}")
        
        if policy.get("scales") and enterprise_profile.scale:
            if enterprise_profile.scale in policy["scales"]:
                score += 0.1
                reasons.append(f"规模匹配: {enterprise_profile.scale}")
        
        if policy.get("priority") in ["critical", "high"]:
            score += 0.1
        
        score = min(1.0, score)
        
        return {
            "match_score": score,
            "semantic_score": 0.0,
            "industry_score": 0.4 if score >= 0.4 else 0.0,
            "region_score": 0.2 if score >= 0.2 else 0.0,
            "scale_score": 0.1 if score >= 0.1 else 0.0,
            "tax_type_score": 0.3 if score >= 0.3 else 0.0,
            "urgency_score": 0.5,
            "match_reasons": [{"category": "rule", "reason": r, "items": [], "confidence": 0.8} for r in reasons],
            "policy_understanding": None,
            "use_llm": False
        }
    
    async def generate_notification(
        self,
        policy: Dict[str, Any],
        enterprise_profile: EnterpriseProfile,
        match_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成个性化通知
        
        Args:
            policy: 政策数据
            enterprise_profile: 企业画像
            match_result: 匹配结果
            
        Returns:
            Dict: 通知内容
        """
        if self.use_llm and self.agent:
            try:
                understanding_data = match_result.get("policy_understanding")
                
                if understanding_data:
                    understanding = PolicyUnderstanding(
                        policy_id=policy.get("policy_id", ""),
                        title=policy.get("title", ""),
                        summary=understanding_data.get("summary", ""),
                        core_objectives=understanding_data.get("core_objectives", []),
                        applicable_conditions=understanding_data.get("applicable_conditions", []),
                        key_requirements=understanding_data.get("key_requirements", []),
                        deadlines=understanding_data.get("deadlines", []),
                        opportunities=understanding_data.get("opportunities", []),
                        risks=understanding_data.get("risks", []),
                        impact_level=understanding_data.get("impact_level", "medium")
                    )
                else:
                    understanding = PolicyUnderstanding(
                        policy_id=policy.get("policy_id", ""),
                        title=policy.get("title", ""),
                        summary=policy.get("summary", ""),
                        impact_level="medium"
                    )
                
                match_score = MatchScore(
                    total_score=match_result.get("match_score", 0.5),
                    semantic_score=match_result.get("semantic_score", 0.5),
                    industry_score=match_result.get("industry_score", 0.5),
                    region_score=match_result.get("region_score", 0.5),
                    scale_score=match_result.get("scale_score", 0.5),
                    tax_type_score=match_result.get("tax_type_score", 0.5),
                    urgency_score=match_result.get("urgency_score", 0.5)
                )
                
                content = await self.agent.generate_personalized_notification(
                    policy=policy,
                    enterprise=enterprise_profile,
                    understanding=understanding,
                    match_score=match_score
                )
                
                return {
                    "title": content.title,
                    "content": content.content,
                    "key_points": content.key_points,
                    "action_items": content.action_items,
                    "urgency_level": content.urgency_level,
                    "recommended_actions": content.recommended_actions,
                    "risk_warnings": content.risk_warnings,
                    "related_policies": content.related_policies,
                    "call_to_action": content.call_to_action,
                    "use_llm": True
                }
                
            except Exception as e:
                logger.error(f"❌ LLM 通知生成失败，降级到规则引擎: {e}")
                return self._rule_based_notification(policy, match_result)
        else:
            return self._rule_based_notification(policy, match_result)
    
    def _rule_based_notification(
        self,
        policy: Dict[str, Any],
        match_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        基于规则的通知生成（降级方案）

        Args:
            policy: 政策数据
            match_result: 匹配结果

        Returns:
            Dict: 通知内容
        """
        return {
            "title": f"政策通知: {policy.get('title', '未知政策')}",
            "content": f"有一条新的政策与您相关，请及时查看。匹配度：{match_result.get('match_score', 0):.0%}",
            "key_points": match_result.get("match_reasons", [])[:3],
            "action_items": ["查看政策详情", "评估适用性"],
            "action_steps": ["查看政策详情", "评估适用性"],
            "urgency_level": policy.get("priority", "medium"),
            "recommended_actions": ["了解政策详情", "准备申报材料"],
            "risk_warnings": [],
            "related_policies": [],
            "call_to_action": "查看详情",
            "deadline": policy.get("deadline") or policy.get("publish_date") or None,
            "use_llm": False
        }
    
    async def prioritize_policies(
        self,
        policies: List[Dict[str, Any]],
        enterprise_profile: EnterpriseProfile
    ) -> List[Dict[str, Any]]:
        """
        智能排序政策
        
        Args:
            policies: 政策列表
            enterprise_profile: 企业画像
            
        Returns:
            List[Dict]: 排序后的政策
        """
        if not policies:
            return []
        
        if len(policies) == 1:
            return policies
        
        if self.use_llm and self.agent:
            try:
                return await self.agent.prioritize_policies(
                    policies=policies,
                    enterprise=enterprise_profile
                )
            except Exception as e:
                logger.error(f"❌ LLM 排序失败，降级到规则引擎: {e}")
                return self._rule_based_priority(policies)
        else:
            return self._rule_based_priority(policies)
    
    def _rule_based_priority(
        self,
        policies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        基于规则的排序（降级方案）
        
        Args:
            policies: 政策列表
            
        Returns:
            List[Dict]: 排序后的政策
        """
        priority_map = {
            "critical": 3,
            "high": 2,
            "medium": 1,
            "low": 0
        }
        
        return sorted(
            policies,
            key=lambda p: (
                priority_map.get(p.get("priority", "medium").lower(), 1),
                p.get("match_score", 0)
            ),
            reverse=True
        )
    
    async def emit_notification_event(
        self,
        enterprise_id: str,
        policy_id: str,
        policy_title: str,
        match_score: float,
        notification_content: Dict[str, Any],
        use_llm: bool = False
    ):
        """
        发布通知事件
        
        Args:
            enterprise_id: 企业ID
            policy_id: 政策ID
            policy_title: 政策标题
            match_score: 匹配分数
            notification_content: 通知内容
            use_llm: 是否使用 LLM
        """
        try:
            impact_level = notification_content.get("urgency_level", "medium")
            
            match_details = {
                "policy_id": policy_id,
                "title": policy_title,
                "notification_title": notification_content.get("title"),
                "notification_content": notification_content.get("content"),
                "key_points": notification_content.get("key_points", []),
                "urgency_level": impact_level,
                "use_llm": use_llm,
                "recommended_actions": notification_content.get("recommended_actions", [])
            }
            
            await policy_event_service.emit_policy_matched(
                enterprise_id=enterprise_id,
                policy_id=policy_id,
                policy_title=policy_title,
                match_score=match_score,
                impact_level=impact_level,
                match_details=match_details
            )
            
            logger.info(f"📤 智能通知事件已发布: {enterprise_id} - {policy_title[:30]}... (LLM: {use_llm})")
            
        except Exception as e:
            logger.error(f"❌ 发布通知事件失败: {e}")


def create_agent_service(
    llm_adapter: Optional[BaseLLMAdapter] = None
) -> PolicyNotificationAgentService:
    """
    创建 Agent 服务的工厂函数
    
    Args:
        llm_adapter: LLM 适配器
        
    Returns:
        PolicyNotificationAgentService: Agent 服务实例
    """
    return PolicyNotificationAgentService(llm_adapter=llm_adapter)


policy_notification_agent_service: Optional[PolicyNotificationAgentService] = None


def get_agent_service() -> PolicyNotificationAgentService:
    """
    获取全局 Agent 服务实例（单例模式）
    
    Returns:
        PolicyNotificationAgentService: Agent 服务实例
    """
    global policy_notification_agent_service
    
    if policy_notification_agent_service is None:
        try:
            from app.core.config import settings
            from app.agent_framework.llm.factory import LLMAdapterFactory
            
            default_provider = settings.get_llm_provider_for_agent("chat")
            logger.info(f"📦 PolicyNotificationAgent 使用 LLM 提供商: {default_provider}")
            
            llm_adapter = LLMAdapterFactory.create_adapter(default_provider)
            policy_notification_agent_service = create_agent_service(llm_adapter)
            logger.info("✅ PolicyNotificationAgent 初始化成功（LLM 模式）")
            
        except Exception as e:
            logger.error(f"❌ LLM 适配器初始化失败: {e}")
            logger.warning("⚠️ PolicyNotificationAgent 回退到规则引擎模式")
            policy_notification_agent_service = create_agent_service(None)
    
    return policy_notification_agent_service
