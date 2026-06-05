"""
政策通知服务 (Policy Notification Service)

统一管理政策通知全流程：
1. 政策匹配 - 基于规则和 LLM 的智能匹配
2. 通知生成 - 个性化通知文案生成
3. 事件发布 - 通过事件系统推送通知
4. 订阅管理 - 企业订阅和通知追踪

整合了以下能力：
- PolicyNotificationAgent (LLM 智能匹配和生成)
- PolicyEventService (事件发布)
- 规则引擎 (降级方案)

提示词来源：app/prompts/agents/policy_notification/system.md
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from uuid import UUID

from app.models.enterprise_policy_match import EnterprisePolicyMatch, NotificationStatus, MatchStatus
from app.models.policy import Policy
from app.db.session import AsyncSessionLocal
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)


class PolicyNotificationService:
    """
    统一政策通知服务
    
    功能：
    1. 智能匹配 - LLM + 规则引擎双重匹配
    2. 通知生成 - 个性化通知文案
    3. 事件发布 - SSE 实时推送
    4. 状态追踪 - 通知状态管理
    """

    def __init__(self):
        self.match_threshold = 0.6
        self.batch_size = 100
        self._llm_agent = None
        self._use_llm = False
        
        self._initialize_llm_agent()

    def _initialize_llm_agent(self):
        """初始化 LLM Agent"""
        try:
            from app.agent_framework.llm.factory import LLMAdapterFactory
            from app.agent_framework.tools.tool_manager import ToolManager
            from app.multi_agent_system.agents.policy_notification_agent import (
                PolicyNotificationAgent,
                EnterpriseProfile
            )
            from app.core.config import settings
            
            try:
                default_provider = settings.get_llm_provider_for_agent("chat")
                llm_adapter = LLMAdapterFactory.create_adapter(default_provider)
                tool_manager = ToolManager()
                
                from app.skills.skill_registry import SkillRegistry as _SR

                self._llm_agent = PolicyNotificationAgent(
                    llm_adapter=llm_adapter,
                    tool_manager=tool_manager,
                    skill_registry=_SR,  # 🆕 技能系统
                )
                self._use_llm = True
                logger.info("✅ PolicyNotificationService: LLM Agent 初始化成功")
                
            except Exception as e:
                logger.warning(f"⚠️ PolicyNotificationService: LLM Agent 初始化失败: {e}")
                self._use_llm = False
                
        except ImportError as e:
            logger.warning(f"⚠️ PolicyNotificationService: 缺少必要依赖: {e}")
            self._use_llm = False
        except Exception as e:
            logger.warning(f"⚠️ PolicyNotificationService: Agent 初始化异常: {e}")
            self._use_llm = False

    async def on_policy_added(
        self,
        policy_id: UUID,
        enterprise_ids: Optional[List[str]] = None
    ):
        """
        政策新增时触发匹配
        
        Args:
            policy_id: 政策ID
            enterprise_ids: 指定企业ID列表（None表示匹配所有）
        """
        logger.info(f"📋 触发政策匹配: {policy_id}")
        
        try:
            from app.services.policy_service import policy_service
            
            policy_data = await policy_service.get_policy_by_id(policy_id)
            
            if not policy_data:
                logger.warning(f"⚠️ 未找到政策: {policy_id}")
                return
            
            if enterprise_ids:
                await self._match_specific_enterprises(policy_data, enterprise_ids)
            else:
                await self._match_all_enterprises(policy_data)
            
            logger.info(f"✅ 政策匹配完成: {policy_id}")
            
        except Exception as e:
            logger.error(f"❌ 政策匹配失败: {e}", exc_info=True)

    async def _match_all_enterprises(self, policy_data: Dict[str, Any]):
        """
        匹配所有企业
        
        Args:
            policy_data: 政策数据
        """
        from app.models.tenant_settings import TenantSettings

        # 先取出企业画像并释放会话，避免在 LLM 匹配期间占用数据库连接
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TenantSettings).where(TenantSettings.is_active.is_(True))
            )
            tenants = result.scalars().all()
            profiles = [self._get_enterprise_profile(tenant) for tenant in tenants]

        logger.info(f"🏢 匹配 {len(profiles)} 个企业")

        for enterprise_profile in profiles:
            if self._use_llm and self._llm_agent:
                match_result = await self._llm_match(
                    policy_data,
                    enterprise_profile
                )
            else:
                match_result = self._rule_based_match(
                    policy_data,
                    enterprise_profile
                )

            match_score = match_result.get("match_score", 0)

            if match_score >= self.match_threshold:
                await self._create_match_and_notification(
                    enterprise_profile["enterprise_id"],
                    policy_data,
                    match_result
                )

    async def _match_specific_enterprises(
        self,
        policy_data: Dict[str, Any],
        enterprise_ids: List[str]
    ):
        """
        匹配指定企业
        
        Args:
            policy_data: 政策数据
            enterprise_ids: 企业ID列表
        """
        for enterprise_id in enterprise_ids:
            try:
                enterprise_profile = await self._get_enterprise_profile_by_id(enterprise_id)
                
                if not enterprise_profile:
                    continue
                
                if self._use_llm and self._llm_agent:
                    match_result = await self._llm_match(
                        policy_data,
                        enterprise_profile
                    )
                else:
                    match_result = self._rule_based_match(
                        policy_data,
                        enterprise_profile
                    )
                
                match_score = match_result.get("match_score", 0)
                
                if match_score >= self.match_threshold:
                    await self._create_match_and_notification(
                        enterprise_id,
                        policy_data,
                        match_result
                    )
                    
            except Exception as e:
                logger.error(f"❌ 匹配企业失败 [{enterprise_id}]: {e}")

    async def _llm_match(
        self,
        policy_data: Dict[str, Any],
        enterprise_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        LLM 智能匹配
        
        Args:
            policy_data: 政策数据
            enterprise_profile: 企业画像
            
        Returns:
            Dict: 匹配结果
        """
        try:
            from app.multi_agent_system.agents.policy_notification_agent import (
                EnterpriseProfile as AgentProfile
            )
            
            agent_profile = AgentProfile(
                enterprise_id=str(enterprise_profile.get("enterprise_id", "")),
                name=enterprise_profile.get("name", "未知企业"),
                industry=enterprise_profile.get("industry"),
                region=enterprise_profile.get("region"),
                scale=enterprise_profile.get("scale"),
                tax_types=enterprise_profile.get("tax_types", []),
                keywords=enterprise_profile.get("keywords", []),
                business_scope=enterprise_profile.get("business_scope"),
                recent_interests=enterprise_profile.get("recent_interests", []),
                preferences=enterprise_profile.get("preferences", {})
            )
            
            match_score, reasons, understanding = await self._llm_agent.match_enterprise_policy(
                policy=policy_data,
                enterprise_profile=agent_profile
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
                    {"category": r.category, "reason": r.reason}
                    for r in reasons
                ],
                "policy_understanding": {
                    "summary": understanding.summary,
                    "core_objectives": understanding.core_objectives,
                    "impact_level": understanding.impact_level
                } if understanding else None,
                "use_llm": True
            }
            
        except Exception as e:
            logger.warning(f"⚠️ LLM 匹配失败，降级到规则引擎: {e}")
            return self._rule_based_match(policy_data, enterprise_profile)

    def _rule_based_match(
        self,
        policy_data: Dict[str, Any],
        enterprise_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        规则引擎匹配（降级方案）
        
        Args:
            policy_data: 政策数据
            enterprise_profile: 企业画像
            
        Returns:
            Dict: 匹配结果
        """
        score = 0.0
        reasons = []
        
        if policy_data.get("industries") and enterprise_profile.get("industry"):
            if enterprise_profile["industry"] in policy_data["industries"]:
                score += 0.4
                reasons.append(f"行业匹配: {enterprise_profile['industry']}")
        
        if policy_data.get("regions") and enterprise_profile.get("region"):
            if enterprise_profile["region"] in policy_data["regions"]:
                score += 0.2
                reasons.append(f"地区匹配: {enterprise_profile['region']}")
        
        if policy_data.get("tax_types") and enterprise_profile.get("tax_types"):
            matching = set(policy_data["tax_types"]) & set(enterprise_profile["tax_types"])
            if matching:
                score += 0.3
                reasons.append(f"税种匹配: {', '.join(list(matching)[:3])}")
        
        if policy_data.get("scales") and enterprise_profile.get("scale"):
            if enterprise_profile["scale"] in policy_data["scales"]:
                score += 0.1
                reasons.append(f"规模匹配: {enterprise_profile['scale']}")
        
        if policy_data.get("priority") in ["critical", "high"]:
            score += 0.1
        
        score = min(1.0, score)
        
        return {
            "match_score": score,
            "match_reasons": [{"category": "rule", "reason": r} for r in reasons],
            "use_llm": False
        }

    async def _get_enterprise_profile_by_id(
        self,
        enterprise_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取企业画像
        
        Args:
            enterprise_id: 企业ID
            
        Returns:
            Optional[Dict]: 企业画像
        """
        from app.models.tenant_settings import TenantSettings

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TenantSettings).where(TenantSettings.tenant_id == enterprise_id)
            )
            tenant = result.scalar_one_or_none()

            if tenant:
                return self._get_enterprise_profile(tenant)

            return None

    def _get_enterprise_profile(self, tenant) -> Dict[str, Any]:
        """
        从租户获取企业画像
        
        Args:
            tenant: 租户对象
            
        Returns:
            Dict: 企业画像
        """
        profile = {
            "enterprise_id": str(getattr(tenant, "tenant_id", "") or getattr(tenant, "id", "")),
            "name": getattr(tenant, "company_name", None) or getattr(tenant, "name", "未知企业"),
            "industry": getattr(tenant, "industry", None),
            "region": getattr(tenant, "region", None),
            "scale": getattr(tenant, "scale", None),
            "tax_types": getattr(tenant, "tax_types", []),
            "keywords": []
        }
        
        if hasattr(tenant, "meta_info") and tenant.meta_info:
            profile["keywords"] = tenant.meta_info.get("keywords", [])
        elif hasattr(tenant, "extra_settings") and tenant.extra_settings:
            profile["keywords"] = tenant.extra_settings.get("keywords", [])
        
        return profile

    async def _create_match_and_notification(
        self,
        enterprise_id: str,
        policy_data: Dict[str, Any],
        match_result: Optional[Dict[str, Any]] = None,
        match_score: Optional[float] = None
    ):
        """
        创建匹配记录和通知
        
        Args:
            enterprise_id: 企业ID
            policy_data: 政策数据
            match_result: 匹配结果
        """
        try:
            match_result = match_result or {
                "match_score": match_score or 0,
                "match_reasons": [],
                "use_llm": False,
            }
            policy_id = policy_data.get("id") or policy_data.get("policy_id", "")
            match_id = None

            async with AsyncSessionLocal() as db:
                try:
                    policy_uuid = UUID(str(policy_id))
                except (TypeError, ValueError):
                    result = await db.execute(
                        select(Policy).where(Policy.policy_id == str(policy_id))
                    )
                    policy = result.scalar_one_or_none()
                    if not policy:
                        logger.warning(f"⚠️ 无法找到匹配记录对应的政策: {policy_id}")
                        return
                    policy_uuid = policy.id

                result = await db.execute(
                    select(EnterprisePolicyMatch).where(
                        and_(
                            EnterprisePolicyMatch.enterprise_id == enterprise_id,
                            EnterprisePolicyMatch.policy_id == policy_uuid
                        )
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    logger.debug(f"⏭️ 跳过已有匹配: {enterprise_id} - {policy_id}")
                    return

                match_reasons = [
                    r.get("reason", "")
                    for r in match_result.get("match_reasons", [])
                ]

                match = EnterprisePolicyMatch(
                    enterprise_id=enterprise_id,
                    policy_id=policy_uuid,
                    match_score=match_result.get("match_score", 0),
                    match_status=MatchStatus.ACTIVE,
                    notification_status=NotificationStatus.PENDING,
                    match_reasons=match_reasons
                )

                db.add(match)
                await db.commit()
                await db.refresh(match)
                match_id = match.id

            logger.info(
                f"📬 创建匹配: {enterprise_id} - "
                f"{policy_data.get('title', '')[:30]}... "
                f"(分数: {match_result.get('match_score', 0):.2f})"
            )

            await self._emit_notification_event(
                enterprise_id=enterprise_id,
                policy_data=policy_data,
                match_result=match_result,
                match_id=str(match_id)
            )

            await self._update_notification_status(match_id)

        except Exception as e:
            logger.error(f"❌ 创建匹配失败: {e}", exc_info=True)

    async def _emit_notification_event(
        self,
        enterprise_id: str,
        policy_data: Dict[str, Any],
        match_result: Dict[str, Any],
        match_id: str
    ):
        """
        发布通知事件
        
        Args:
            enterprise_id: 企业ID
            policy_data: 政策数据
            match_result: 匹配结果
            match_id: 匹配记录ID
        """
        try:
            from app.services.policy_event_service import policy_event_service
            
            policy_id = policy_data.get("policy_id") or policy_data.get("id", "")
            
            impact_level = "low"
            priority = policy_data.get("priority", "medium")
            if priority == "critical":
                impact_level = "high"
            elif priority == "high":
                impact_level = "medium"
            
            # 取完整企业画像，让 LLM 生成真正个性化的文案（而非"未知企业"）
            enterprise_profile = await self._get_enterprise_profile_by_id(enterprise_id)
            if not enterprise_profile:
                enterprise_profile = {"enterprise_id": enterprise_id}

            notification_content = await self.generate_notification(
                policy_data,
                enterprise_profile,
                match_result
            )
            
            match_details = {
                "match_id": match_id,
                "policy_id": policy_id,
                "title": policy_data.get("title", ""),
                "industries": policy_data.get("industries", []),
                "regions": policy_data.get("regions", []),
                "tax_types": policy_data.get("tax_types", []),
                "priority": priority,
                "source": policy_data.get("source_name"),
                "notification_title": notification_content.get("title"),
                "notification_content": notification_content.get("content"),
                "key_points": notification_content.get("key_points", []),
                "urgency_level": notification_content.get("urgency_level", "medium"),
                "use_llm": match_result.get("use_llm", False)
            }
            
            await policy_event_service.emit_policy_matched(
                enterprise_id=enterprise_id,
                policy_id=str(policy_id),
                policy_title=policy_data.get("title", ""),
                match_score=match_result.get("match_score", 0),
                impact_level=impact_level,
                match_details=match_details
            )
            
            logger.info(f"📤 通知事件已发布: {enterprise_id} - {policy_data.get('title', '')[:30]}...")
            
        except Exception as e:
            logger.error(f"❌ 发布通知事件失败: {e}", exc_info=True)

    async def generate_notification(
        self,
        policy_data: Dict[str, Any],
        enterprise_profile: Dict[str, Any],
        match_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成个性化通知
        
        Args:
            policy_data: 政策数据
            enterprise_profile: 企业画像
            match_result: 匹配结果
            
        Returns:
            Dict: 通知内容
        """
        if self._use_llm and self._llm_agent:
            try:
                from app.multi_agent_system.agents.policy_notification_agent import (
                    EnterpriseProfile as AgentProfile,
                    PolicyUnderstanding,
                    MatchScore,
                    NotificationContent
                )
                
                enterprise_id = enterprise_profile.get("enterprise_id", "")
                
                agent_profile = AgentProfile(
                    enterprise_id=enterprise_id,
                    name=enterprise_profile.get("name", "未知企业"),
                    industry=enterprise_profile.get("industry"),
                    region=enterprise_profile.get("region"),
                    scale=enterprise_profile.get("scale"),
                    tax_types=enterprise_profile.get("tax_types", []),
                    keywords=enterprise_profile.get("keywords", []),
                    business_scope=enterprise_profile.get("business_scope"),
                    recent_interests=enterprise_profile.get("recent_interests", []),
                    preferences=enterprise_profile.get("preferences", {})
                )
                
                understanding_data = match_result.get("policy_understanding")
                if understanding_data:
                    understanding = PolicyUnderstanding(
                        policy_id=policy_data.get("policy_id", ""),
                        title=policy_data.get("title", ""),
                        summary=understanding_data.get("summary", ""),
                        core_objectives=understanding_data.get("core_objectives", []),
                        applicable_conditions=[],
                        key_requirements=[],
                        deadlines=[],
                        opportunities=[],
                        risks=[],
                        impact_level=understanding_data.get("impact_level", "medium")
                    )
                else:
                    understanding = PolicyUnderstanding(
                        policy_id=policy_data.get("policy_id", ""),
                        title=policy_data.get("title", ""),
                        summary=policy_data.get("summary", ""),
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
                
                content = await self._llm_agent.generate_personalized_notification(
                    policy=policy_data,
                    enterprise=agent_profile,
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
                logger.warning(f"⚠️ LLM 通知生成失败，使用规则引擎: {e}")
                return self._rule_based_notification(policy_data, match_result)
        else:
            return self._rule_based_notification(policy_data, match_result)

    def _rule_based_notification(
        self,
        policy_data: Dict[str, Any],
        match_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        规则引擎通知生成（降级方案）
        
        Args:
            policy_data: 政策数据
            match_result: 匹配结果
            
        Returns:
            Dict: 通知内容
        """
        return {
            "title": f"政策通知: {policy_data.get('title', '未知政策')}",
            "content": f"有一条新的政策与您相关，请及时查看。匹配度：{match_result.get('match_score', 0):.0%}",
            "key_points": [r.get("reason", "") for r in match_result.get("match_reasons", [])[:3]],
            "action_items": ["查看政策详情", "评估适用性"],
            "urgency_level": policy_data.get("priority", "medium"),
            "recommended_actions": ["了解政策详情", "准备申报材料"],
            "risk_warnings": [],
            "related_policies": [],
            "call_to_action": "查看详情",
            "use_llm": False
        }

    async def _update_notification_status(self, match_id):
        """
        更新通知状态
        
        Args:
            match_id: 匹配记录ID
        """
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(EnterprisePolicyMatch).where(EnterprisePolicyMatch.id == match_id)
                )
                match = result.scalar_one_or_none()

                if match:
                    match.notification_status = NotificationStatus.SENT
                    match.notified_at = datetime.now()
                    await db.commit()

        except Exception as e:
            logger.error(f"❌ 更新通知状态失败: {e}", exc_info=True)

    async def get_enterprise_notifications(
        self,
        enterprise_id: str,
        status: Optional[NotificationStatus] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取企业通知列表
        
        Args:
            enterprise_id: 企业ID
            status: 通知状态筛选
            limit: 返回数量
            
        Returns:
            List[Dict]: 通知列表
        """
        async with AsyncSessionLocal() as db:
            query = select(EnterprisePolicyMatch, Policy).join(
                Policy, EnterprisePolicyMatch.policy_id == Policy.id
            ).where(
                EnterprisePolicyMatch.enterprise_id == enterprise_id
            )

            if status:
                query = query.where(
                    EnterprisePolicyMatch.notification_status == status
                )

            query = query.order_by(
                EnterprisePolicyMatch.created_at.desc()
            ).limit(limit)

            rows = (await db.execute(query)).all()

            results = []
            for match, policy in rows:
                policy_data = {
                    "id": str(policy.id),
                    "policy_id": policy.policy_id,
                    "title": policy.title,
                    "content": policy.content,
                    "summary": policy.summary,
                    "source_name": policy.source_name,
                    "source_url": policy.source_url,
                    "published_date": policy.published_date.isoformat() if policy.published_date else None,
                    "effective_date": policy.effective_date.isoformat() if policy.effective_date else None,
                    "expiry_date": policy.expiry_date.isoformat() if policy.expiry_date else None,
                    "status": policy.status.value if policy.status else None,
                    "priority": policy.priority.value if policy.priority else None,
                    "industries": policy.industries or [],
                    "regions": policy.regions or [],
                    "scales": policy.scales or [],
                    "tax_types": policy.tax_types or [],
                    "tags": policy.tags or [],
                    "view_count": policy.view_count or 0,
                    "meta_info": policy.meta_info or {},
                    "created_at": policy.created_at.isoformat() if policy.created_at else None,
                    "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
                }
                results.append({
                    "id": str(match.id),
                    "policy_id": str(match.policy_id),
                    "policy_title": policy.title,
                    "policy": policy_data,
                    "match_score": match.match_score,
                    "match_status": match.match_status.value,
                    "notification_status": match.notification_status.value,
                    # 兼容前端 PolicyNotification.status 字段
                    "status": match.notification_status.value,
                    "match_reasons": match.match_reasons,
                    "acknowledged": match.acknowledged_at is not None,
                    "acknowledged_at": match.acknowledged_at.isoformat() if match.acknowledged_at else None,
                    "created_at": match.created_at.isoformat() if match.created_at else None
                })

            return results

    async def prioritize_policies(
        self,
        policies: List[Dict[str, Any]],
        enterprise_profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        智能优先级排序
        
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
        
        if self._use_llm and self._llm_agent:
            try:
                from app.multi_agent_system.agents.policy_notification_agent import (
                    EnterpriseProfile as AgentProfile
                )
                
                agent_profile = AgentProfile(
                    enterprise_id=str(enterprise_profile.get("enterprise_id", "")),
                    name=enterprise_profile.get("name", "未知企业"),
                    industry=enterprise_profile.get("industry"),
                    region=enterprise_profile.get("region"),
                    scale=enterprise_profile.get("scale"),
                    tax_types=enterprise_profile.get("tax_types", []),
                    keywords=enterprise_profile.get("keywords", []),
                    business_scope=enterprise_profile.get("business_scope"),
                    recent_interests=enterprise_profile.get("recent_interests", []),
                    preferences=enterprise_profile.get("preferences", {})
                )
                
                return await self._llm_agent.prioritize_policies(
                    policies=policies,
                    enterprise=agent_profile
                )
                
            except Exception as e:
                logger.warning(f"⚠️ LLM 优先级排序失败，使用规则引擎: {e}")
                return self._rule_based_priority(policies)
        else:
            return self._rule_based_priority(policies)

    def _rule_based_priority(
        self,
        policies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        规则引擎优先级排序（降级方案）
        
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

    async def acknowledge_notification(
        self,
        match_id: UUID,
        feedback: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        确认通知

        Args:
            match_id: 匹配记录ID
            feedback: 用户反馈

        Returns:
            bool: 是否成功
        """
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(EnterprisePolicyMatch).where(EnterprisePolicyMatch.id == match_id)
                )
                match = result.scalar_one_or_none()

                if not match:
                    logger.warning(f"⚠️ 确认通知失败，匹配记录不存在: {match_id}")
                    return False

                match.notification_status = NotificationStatus.ACKNOWLEDGED
                match.acknowledged_at = datetime.now()

                if feedback:
                    match.feedback = feedback

                await db.commit()

            logger.info(f"✅ 通知已确认: {match_id}")
            return True

        except Exception as e:
            logger.error(f"❌ 确认通知失败 [{match_id}]: {e}", exc_info=True)
            return False

    async def dismiss_notification(
        self,
        match_id: UUID,
        reason: Optional[str] = None
    ) -> bool:
        """
        忽略通知

        Args:
            match_id: 匹配记录ID
            reason: 忽略原因

        Returns:
            bool: 是否成功
        """
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(EnterprisePolicyMatch).where(EnterprisePolicyMatch.id == match_id)
                )
                match = result.scalar_one_or_none()

                if not match:
                    logger.warning(f"⚠️ 忽略通知失败，匹配记录不存在: {match_id}")
                    return False

                match.notification_status = NotificationStatus.DISMISSED
                match.dismissed_at = datetime.now()

                if reason:
                    match.feedback = {**(match.feedback or {}), "dismiss_reason": reason}

                await db.commit()

            logger.info(f"✅ 通知已忽略: {match_id}")
            return True

        except Exception as e:
            logger.error(f"❌ 忽略通知失败 [{match_id}]: {e}", exc_info=True)
            return False


policy_notification_service = PolicyNotificationService()
