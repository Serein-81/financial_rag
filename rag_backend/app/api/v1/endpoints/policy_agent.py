"""
PolicyNotificationAgent API 端点

提供政策通知智能体的核心功能接口：
- 政策理解与解析
- 企业-政策智能匹配
- 个性化通知生成
- 政策优先级排序
"""

import logging
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.policy_notification_agent_service import PolicyNotificationAgentService, get_agent_service
from app.api.deps import get_current_user, CurrentUser
from app.multi_agent_system.agents.policy_notification_agent import EnterpriseProfile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/policy-agent", tags=["政策通知智能体"])

MAX_POLICIES_PER_REQUEST = 100
MAX_POLICY_CONTENT_LENGTH = 50000


async def get_agent_service_dep() -> PolicyNotificationAgentService:
    """服务依赖注入"""
    return get_agent_service()


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
    tax_types: list[str] = Field(default_factory=list, description="纳税类型")
    qualifications: list[str] = Field(default_factory=list, description="资质认证")


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
    reasons: list[str]
    policy_id: str
    enterprise_id: str
    use_llm: bool


class NotificationRequest(BaseModel):
    """通知生成请求"""
    policy: dict[str, Any]
    enterprise_profile: EnterpriseProfileInput
    match_result: dict[str, Any]


class NotificationResponse(BaseModel):
    """通知生成响应"""
    title: str
    content: str
    urgency_level: str
    key_points: list[str] = Field(default_factory=list)
    action_steps: list[str] = Field(default_factory=list)
    deadline: Optional[str] = None
    use_llm: bool


class PriorityRequest(BaseModel):
    """优先级排序请求"""
    policies: list[dict[str, Any]]
    enterprise_profile: EnterpriseProfileInput


class PolicyTestRequest(BaseModel):
    """完整流程测试请求"""
    policies: list[PolicyInput]
    enterprise: EnterpriseProfileInput
    use_llm: bool = Field(default=True, description="是否使用 LLM")


class PolicyTestResponse(BaseModel):
    """完整流程测试响应"""
    enterprise_id: str
    policies_processed: int
    matches: list[PolicyMatchResponse]
    notifications: list[NotificationResponse]
    prioritized_policies: list[dict[str, Any]]
    use_llm: bool
    llm_provider: str
    processing_time: float


def _create_enterprise_profile(enterprise_input: EnterpriseProfileInput) -> EnterpriseProfile:
    """从输入模型创建企业画像"""
    return EnterpriseProfile(
        enterprise_id=enterprise_input.enterprise_id,
        name=enterprise_input.enterprise_name,
        industry=enterprise_input.industry,
        region=enterprise_input.region,
        scale=enterprise_input.scale,
        tax_types=enterprise_input.tax_types,
        keywords=getattr(enterprise_input, 'qualifications', []),
        business_scope=None,
        recent_interests=[],
        preferences={}
    )


def _policy_input_to_dict(policy_input: PolicyInput) -> dict[str, Any]:
    """将 PolicyInput 转换为字典"""
    return {
        "policy_id": policy_input.policy_id,
        "title": policy_input.title,
        "content": policy_input.content,
        "source": policy_input.source,
        "publish_date": policy_input.publish_date,
        "priority": policy_input.priority
    }


@router.post("/match", response_model=PolicyMatchResponse)
async def match_policy(
    request: PolicyMatchRequest,
    user: CurrentUser = Depends(get_current_user),
    service: PolicyNotificationAgentService = Depends(get_agent_service_dep)
):
    """
    匹配政策与企业

    根据政策内容和企业画像，计算匹配度分数和推荐理由

    Args:
        request: 包含政策和企业的请求
        user: 当前用户
        service: 政策通知智能体服务

    Returns:
        PolicyMatchResponse: 匹配结果
    """
    logger.info(
        "政策匹配请求",
        extra={
            "event": "policy_match_request",
            "policy_id": request.policy.policy_id,
            "enterprise_id": request.enterprise.enterprise_id,
            "user_id": str(user.id)
        }
    )

    try:
        if len(request.policy.content) > MAX_POLICY_CONTENT_LENGTH:
            logger.warning(
                f"政策内容过长: {len(request.policy.content)} 字符",
                extra={
                    "event": "policy_content_truncated",
                    "policy_id": request.policy.policy_id,
                    "content_length": len(request.policy.content)
                }
            )
            request.policy.content = request.policy.content[:MAX_POLICY_CONTENT_LENGTH]

        policy_dict = _policy_input_to_dict(request.policy)
        enterprise_profile = _create_enterprise_profile(request.enterprise)

        match_result = await service.match_policy_for_enterprise(
            policy=policy_dict,
            enterprise_profile=enterprise_profile
        )

        logger.info(
            "匹配完成",
            extra={
                "event": "policy_match_success",
                "policy_id": request.policy.policy_id,
                "enterprise_id": request.enterprise.enterprise_id,
                "match_score": match_result['match_score'],
                "use_llm": match_result['use_llm']
            }
        )

        return PolicyMatchResponse(**match_result)

    except ValueError as e:
        logger.warning(f"无效的请求参数: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"无效的请求参数: {str(e)}")
    except KeyError as e:
        logger.warning(f"缺少必需字段: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"缺少必需字段: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="文件操作失败")
    except Exception as e:
        logger.error(f"政策匹配失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"政策匹配失败: {str(e)}")


@router.post("/notify", response_model=NotificationResponse)
async def generate_notification(
    request: NotificationRequest,
    user: CurrentUser = Depends(get_current_user),
    service: PolicyNotificationAgentService = Depends(get_agent_service_dep)
):
    """
    生成个性化通知

    基于政策和企业画像，生成定制化的通知内容

    Args:
        request: 包含政策、匹配结果的请求
        user: 当前用户
        service: 政策通知智能体服务

    Returns:
        NotificationResponse: 个性化通知
    """
    policy_id = request.policy.get('policy_id', 'unknown')
    logger.info(
        "生成通知请求",
        extra={
            "event": "notification_request",
            "policy_id": policy_id,
            "enterprise_id": request.enterprise_profile.enterprise_id,
            "user_id": str(user.id)
        }
    )

    try:
        enterprise_profile = _create_enterprise_profile(request.enterprise_profile)

        notification = await service.generate_notification(
            policy=request.policy,
            enterprise_profile=enterprise_profile,
            match_result=request.match_result
        )

        if 'action_items' in notification and 'action_steps' not in notification:
            notification['action_steps'] = notification.pop('action_items')

        if 'deadline' not in notification:
            notification['deadline'] = None

        logger.info(
            "通知生成完成",
            extra={
                "event": "notification_success",
                "policy_id": policy_id,
                "enterprise_id": request.enterprise_profile.enterprise_id,
                "urgency_level": notification['urgency_level']
            }
        )

        return NotificationResponse(**notification)

    except ValueError as e:
        logger.warning(f"无效的请求参数: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"无效的请求参数: {str(e)}")
    except KeyError as e:
        logger.warning(f"缺少必需字段: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"缺少必需字段: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="文件操作失败")
    except Exception as e:
        logger.error(f"通知生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"通知生成失败: {str(e)}")


@router.post("/prioritize", response_model=list[dict[str, Any]])
async def prioritize_policies(
    request: PriorityRequest,
    user: CurrentUser = Depends(get_current_user),
    service: PolicyNotificationAgentService = Depends(get_agent_service_dep)
):
    """
    政策优先级排序

    根据企业画像和匹配度，对政策列表进行智能排序

    Args:
        request: 包含政策列表和企业画像的请求
        user: 当前用户
        service: 政策通知智能体服务

    Returns:
        list[dict[str, Any]]: 排序后的政策列表
    """
    if not request.policies:
        logger.warning(
            "优先级排序请求失败: 政策列表为空",
            extra={
                "event": "priority_request_empty",
                "enterprise_id": request.enterprise_profile.enterprise_id,
                "user_id": str(user.id)
            }
        )
        raise HTTPException(status_code=400, detail="政策列表不能为空")

    logger.info(
        "优先级排序请求",
        extra={
            "event": "priority_request",
            "policy_count": len(request.policies),
            "enterprise_id": request.enterprise_profile.enterprise_id,
            "user_id": str(user.id)
        }
    )

    try:
        enterprise_profile = _create_enterprise_profile(request.enterprise_profile)

        sorted_policies = await service.prioritize_policies(
            policies=request.policies,
            enterprise_profile=enterprise_profile
        )

        logger.info(
            "排序完成",
            extra={
                "event": "priority_success",
                "policy_count": len(sorted_policies),
                "enterprise_id": request.enterprise_profile.enterprise_id
            }
        )

        return sorted_policies

    except ValueError as e:
        logger.warning(f"无效的请求参数: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"无效的请求参数: {str(e)}")
    except KeyError as e:
        logger.warning(f"缺少必需字段: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"缺少必需字段: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="文件操作失败")
    except Exception as e:
        logger.error(f"优先级排序失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"优先级排序失败: {str(e)}")


@router.post("/test", response_model=PolicyTestResponse)
async def test_policy_agent(
    request: PolicyTestRequest,
    user: CurrentUser = Depends(get_current_user),
    service: PolicyNotificationAgentService = Depends(get_agent_service_dep)
):
    """
    完整流程测试

    测试政策智能体的完整流程：匹配 -> 生成通知 -> 优先级排序
    
    ⚠️ 注意：此端点会消耗较多资源，建议在测试环境中使用

    Args:
        request: 测试请求
        user: 当前用户
        service: 政策通知智能体服务

    Returns:
        PolicyTestResponse: 测试结果
    """
    import time

    if not request.policies:
        logger.warning(
            "完整流程测试失败: 政策列表为空",
            extra={
                "event": "test_request_empty",
                "enterprise_id": request.enterprise.enterprise_id,
                "user_id": str(user.id)
            }
        )
        raise HTTPException(status_code=400, detail="政策列表不能为空")

    if len(request.policies) > MAX_POLICIES_PER_REQUEST:
        logger.warning(
            f"完整流程测试: 政策数量超过限制 ({len(request.policies)} > {MAX_POLICIES_PER_REQUEST})",
            extra={
                "event": "test_request_too_large",
                "policy_count": len(request.policies),
                "enterprise_id": request.enterprise.enterprise_id,
                "user_id": str(user.id)
            }
        )
        raise HTTPException(
            status_code=400,
            detail=f"单次请求的政策数量不能超过 {MAX_POLICIES_PER_REQUEST} 个"
        )

    logger.info(
        "完整流程测试",
        extra={
            "event": "test_request",
            "policy_count": len(request.policies),
            "enterprise_id": request.enterprise.enterprise_id,
            "use_llm": request.use_llm,
            "user_id": str(user.id)
        }
    )
    start_time = time.time()

    try:
        enterprise_profile = _create_enterprise_profile(request.enterprise)

        matches = []
        notifications = []

        for idx, policy_input in enumerate(request.policies):
            if len(policy_input.content) > MAX_POLICY_CONTENT_LENGTH:
                logger.warning(
                    f"政策内容过长已截断: {policy_input.policy_id}",
                    extra={
                        "event": "policy_content_truncated",
                        "policy_id": policy_input.policy_id,
                        "content_length": len(policy_input.content),
                        "policy_index": idx
                    }
                )
                policy_input.content = policy_input.content[:MAX_POLICY_CONTENT_LENGTH]

            policy_dict = _policy_input_to_dict(policy_input)

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

        logger.info(
            "测试完成",
            extra={
                "event": "test_success",
                "policy_count": len(matches),
                "notification_count": len(notifications),
                "processing_time": processing_time,
                "enterprise_id": request.enterprise.enterprise_id
            }
        )

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

    except ValueError as e:
        logger.warning(f"无效的请求参数: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"无效的请求参数: {str(e)}")
    except KeyError as e:
        logger.warning(f"缺少必需字段: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"缺少必需字段: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="文件操作失败")
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


@router.get("/status")
async def get_agent_status(
    user: CurrentUser = Depends(get_current_user),
    service: PolicyNotificationAgentService = Depends(get_agent_service_dep)
):
    """
    获取 Agent 状态
    
    查看 PolicyNotificationAgent 的运行状态和配置
    
    Args:
        user: 当前用户
        service: 政策通知智能体服务
    
    Returns:
        dict: Agent 状态信息
    """
    logger.info(
        "获取Agent状态",
        extra={
            "event": "get_status",
            "user_id": str(user.id)
        }
    )
    
    try:
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
        logger.error(f"获取状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")
