"""
PolicyNotificationAgent API 端点

提供政策通知智能体的核心功能接口：
- 政策理解与解析
- 企业-政策智能匹配
- 个性化通知生成
- 政策优先级排序
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.policy_notification_agent_service import get_agent_service
from app.api.deps import get_current_user, CurrentUser
from app.multi_agent_system.agents.policy_notification_agent import EnterpriseProfile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/policy-agent", tags=["政策通知智能体"])


class PolicyInput(BaseModel):
    """政策输入模型"""
    policy_id: str = Field(..., description="政策ID")
    title: str = Field(..., description="政策标题")
    content: str = Field(..., description="政策全文内容")
    source: str = Field(default="manual", description="政策来源")
    publish_date: Optional[str] = Field(None, description="发布日期")
    priority: str = Field(default="medium", description="优先级: high/medium/low")


class EnterpriseProfileInput(BaseModel):
    """企业画像输入模型"""
    enterprise_id: str = Field(..., description="企业ID")
    enterprise_name: str = Field(..., description="企业名称")
    industry: str = Field(..., description="所属行业")
    region: str = Field(..., description="所在地区")
    scale: str = Field(..., description="企业规模")
    tax_types: List[str] = Field(default_factory=list, description="纳税类型")
    qualifications: List[str] = Field(default_factory=list, description="资质认证")


class PolicyMatchRequest(BaseModel):
    """政策匹配请求"""
    policy: PolicyInput
    enterprise: EnterpriseProfileInput
    use_llm: bool = Field(default=True, description="是否使用 LLM")


class PolicyMatchResponse(BaseModel):
    """政策匹配响应"""
    match_score: float
    semantic_score: float
    industry_score: float
    region_score: float
    scale_score: float
    tax_type_score: float
    urgency_score: float
    reasons: List[str]
    policy_id: str
    enterprise_id: str
    use_llm: bool


class NotificationRequest(BaseModel):
    """通知生成请求"""
    policy: Dict[str, Any]
    enterprise_profile: EnterpriseProfileInput
    match_result: Dict[str, Any]


class NotificationResponse(BaseModel):
    """通知生成响应"""
    title: str
    content: str
    urgency_level: str
    key_points: List[str] = Field(default_factory=list)
    action_steps: List[str] = Field(default_factory=list)
    deadline: Optional[str] = None
    use_llm: bool


class PriorityRequest(BaseModel):
    """优先级排序请求"""
    policies: List[Dict[str, Any]]
    enterprise_profile: EnterpriseProfileInput


class PolicyTestRequest(BaseModel):
    """完整流程测试请求"""
    policies: List[PolicyInput]
    enterprise: EnterpriseProfileInput
    use_llm: bool = Field(default=True, description="是否使用 LLM")


class PolicyTestResponse(BaseModel):
    """完整流程测试响应"""
    enterprise_id: str
    policies_processed: int
    matches: List[PolicyMatchResponse]
    notifications: List[NotificationResponse]
    prioritized_policies: List[Dict[str, Any]]
    use_llm: bool
    llm_provider: str
    processing_time: float


@router.post("/match", response_model=PolicyMatchResponse)
async def match_policy(
    request: PolicyMatchRequest,
    user: CurrentUser = Depends(get_current_user)
):
    """
    匹配政策与企业

    根据政策内容和企业画像，计算匹配度分数和推荐理由

    Args:
        request: 包含政策和企业的请求
        user: 当前用户

    Returns:
        PolicyMatchResponse: 匹配结果
    """
    logger.info(f"🔍 政策匹配请求: policy={request.policy.policy_id}, enterprise={request.enterprise.enterprise_id}")

    try:
        service = get_agent_service()

        policy_dict = {
            "policy_id": request.policy.policy_id,
            "title": request.policy.title,
            "content": request.policy.content,
            "source": request.policy.source,
            "publish_date": request.policy.publish_date,
            "priority": request.policy.priority
        }

        enterprise_profile = EnterpriseProfile(
            enterprise_id=request.enterprise.enterprise_id,
            name=request.enterprise.enterprise_name,
            industry=request.enterprise.industry,
            region=request.enterprise.region,
            scale=request.enterprise.scale,
            tax_types=request.enterprise.tax_types,
            keywords=request.enterprise.qualifications if hasattr(request.enterprise, 'qualifications') else [],
            business_scope=None,
            recent_interests=[],
            preferences={}
        )

        match_result = await service.match_policy_for_enterprise(
            policy=policy_dict,
            enterprise_profile=enterprise_profile
        )

        logger.info(f"✅ 匹配完成: score={match_result['match_score']:.2f}, use_llm={match_result['use_llm']}")

        return PolicyMatchResponse(**match_result)

    except Exception as e:
        logger.error(f"❌ 政策匹配失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"政策匹配失败: {str(e)}")


@router.post("/notify", response_model=NotificationResponse)
async def generate_notification(
    request: NotificationRequest,
    user: CurrentUser = Depends(get_current_user)
):
    """
    生成个性化通知

    基于政策和企业画像，生成定制化的通知内容

    Args:
        request: 包含政策、匹配结果的请求
        user: 当前用户

    Returns:
        NotificationResponse: 个性化通知
    """
    logger.info(f"📝 生成通知请求: policy={request.policy.get('policy_id')}")

    try:
        service = get_agent_service()

        enterprise_profile = EnterpriseProfile(
            enterprise_id=request.enterprise_profile.enterprise_id,
            name=request.enterprise_profile.enterprise_name,
            industry=request.enterprise_profile.industry,
            region=request.enterprise_profile.region,
            scale=request.enterprise_profile.scale,
            tax_types=request.enterprise_profile.tax_types,
            keywords=request.enterprise_profile.qualifications if hasattr(request.enterprise_profile, 'qualifications') else [],
            business_scope=None,
            recent_interests=[],
            preferences={}
        )

        notification = await service.generate_notification(
            policy=request.policy,
            enterprise_profile=enterprise_profile,
            match_result=request.match_result
        )

        if 'action_items' in notification and 'action_steps' not in notification:
            notification['action_steps'] = notification.pop('action_items')

        if 'deadline' not in notification:
            notification['deadline'] = None

        logger.info(f"✅ 通知生成完成: urgency={notification['urgency_level']}")

        return NotificationResponse(**notification)

    except Exception as e:
        logger.error(f"❌ 通知生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"通知生成失败: {str(e)}")


@router.post("/prioritize", response_model=List[Dict[str, Any]])
async def prioritize_policies(
    request: PriorityRequest,
    user: CurrentUser = Depends(get_current_user)
):
    """
    政策优先级排序

    根据企业画像和匹配度，对政策列表进行智能排序

    Args:
        request: 包含政策列表和企业画像的请求
        user: 当前用户

    Returns:
        List[Dict[str, Any]]: 排序后的政策列表
    """
    logger.info(f"📊 优先级排序请求: {len(request.policies)} 个政策")

    try:
        service = get_agent_service()

        enterprise_profile = EnterpriseProfile(
            enterprise_id=request.enterprise_profile.enterprise_id,
            name=request.enterprise_profile.enterprise_name,
            industry=request.enterprise_profile.industry,
            region=request.enterprise_profile.region,
            scale=request.enterprise_profile.scale,
            tax_types=request.enterprise_profile.tax_types,
            keywords=request.enterprise_profile.qualifications if hasattr(request.enterprise_profile, 'qualifications') else [],
            business_scope=None,
            recent_interests=[],
            preferences={}
        )

        sorted_policies = await service.prioritize_policies(
            policies=request.policies,
            enterprise_profile=enterprise_profile
        )

        logger.info(f"✅ 排序完成: {len(sorted_policies)} 个政策")

        return sorted_policies

    except Exception as e:
        logger.error(f"❌ 优先级排序失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"优先级排序失败: {str(e)}")


@router.post("/test", response_model=PolicyTestResponse)
async def test_policy_agent(
    request: PolicyTestRequest,
    user: CurrentUser = Depends(get_current_user)
):
    """
    完整流程测试

    测试政策智能体的完整流程：匹配 -> 生成通知 -> 优先级排序

    Args:
        request: 测试请求
        user: 当前用户

    Returns:
        PolicyTestResponse: 测试结果
    """
    import time

    logger.info(f"🧪 完整流程测试: {len(request.policies)} 个政策, enterprise={request.enterprise.enterprise_id}")
    start_time = time.time()

    try:
        service = get_agent_service()

        enterprise_profile = EnterpriseProfile(
            enterprise_id=request.enterprise.enterprise_id,
            name=request.enterprise.enterprise_name,
            industry=request.enterprise.industry,
            region=request.enterprise.region,
            scale=request.enterprise.scale,
            tax_types=request.enterprise.tax_types,
            keywords=[],
            business_scope=None,
            recent_interests=[],
            preferences={}
        )

        matches = []
        notifications = []

        for policy_input in request.policies:
            policy_dict = {
                "policy_id": policy_input.policy_id,
                "title": policy_input.title,
                "content": policy_input.content,
                "source": policy_input.source,
                "publish_date": policy_input.publish_date,
                "priority": policy_input.priority
            }

            match_result = await service.match_policy_for_enterprise(
                policy=policy_dict,
                enterprise_profile=enterprise_profile
            )
            matches.append(PolicyMatchResponse(**match_result))

            notification = await service.generate_notification(
                policy=policy_dict,
                enterprise_profile=enterprise_profile,
                match_result=match_result
            )

            if 'action_items' in notification and 'action_steps' not in notification:
                notification['action_steps'] = notification.pop('action_items')
            if 'deadline' not in notification:
                notification['deadline'] = None

            notifications.append(NotificationResponse(**notification))

        policy_dicts = [p.model_dump() for p in request.policies]
        prioritized = await service.prioritize_policies(
            policies=policy_dicts,
            enterprise_profile=enterprise_profile
        )

        processing_time = time.time() - start_time

        logger.info(f"✅ 测试完成: {len(matches)} 个匹配, {len(notifications)} 个通知, 耗时 {processing_time:.2f}s")

        return PolicyTestResponse(
            enterprise_id=request.enterprise.enterprise_id,
            policies_processed=len(request.policies),
            matches=matches,
            notifications=notifications,
            prioritized_policies=prioritized,
            use_llm=service.use_llm,
            llm_provider=service.agent.llm_adapter.__class__.__name__ if service.use_llm else "fallback",
            processing_time=processing_time
        )

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


@router.get("/status")
async def get_agent_status(
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取 Agent 状态
    
    查看 PolicyNotificationAgent 的运行状态和配置
    
    Returns:
        dict: Agent 状态信息
    """
    try:
        service = get_agent_service()
        
        return {
            "status": "healthy",
            "use_llm": service.use_llm,
            "llm_provider": service.agent.llm_adapter.__class__.__name__ if service.use_llm else None,
            "agent_capabilities": {
                "policy_understanding": True,
                "semantic_matching": service.use_llm,
                "personalized_generation": service.use_llm,
                "fallback_mode": not service.use_llm
            },
            "match_weights": service.agent.match_weights if service.agent else None
        }
        
    except Exception as e:
        logger.error(f"❌ 获取状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")
