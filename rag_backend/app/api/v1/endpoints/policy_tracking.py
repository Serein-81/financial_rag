"""
政策法规智能追踪 API 端点
提供政策订阅、推送和追踪的 RESTful 接口
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Optional, List
from datetime import datetime, timedelta

from app.api.deps import get_current_user, CurrentUser
from app.schemas.policy_tracking import (
    PolicySubscriptionRequest,
    PolicySubscriptionResponse,
    PolicyCategory,
    PolicyQueryRequest,
    PolicyQueryResponse,
    PolicyUpdate,
    SubscriptionStatus,
)
from app.services.policy_tracking_service import PolicyTrackingService

router = APIRouter(prefix="/policy-tracking", tags=["政策法规追踪"])
logger = logging.getLogger(__name__)

policy_tracking_service = PolicyTrackingService()


@router.post("/subscribe", response_model=PolicySubscriptionResponse)
async def subscribe_policies(
    request: PolicySubscriptionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    订阅政策更新
    
    支持订阅多种政策类别和关键词，设置通知偏好
    """
    try:
        request.user_id = str(user.id)
        request.tenant_id = user.tenant_id
        
        result = await policy_tracking_service.create_subscription(request)
        
        return PolicySubscriptionResponse(**result)
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 订阅数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"订阅数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 订阅IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"订阅IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 订阅失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"订阅失败: {str(e)}")


@router.get("/subscriptions")
async def get_subscriptions(
    status: Optional[str] = Query(None, description="订阅状态"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    获取订阅列表
    
    查看当前用户的政策订阅
    """
    try:
        status_enum = None
        if status:
            try:
                status_enum = SubscriptionStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的订阅状态")
        
        subscriptions = await policy_tracking_service.get_subscriptions(
            tenant_id=user.tenant_id,
            user_id=str(user.id),
            status=status_enum
        )
        
        return {
            "subscriptions": subscriptions,
            "count": len(subscriptions)
        }
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 获取订阅列表数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"获取数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 获取订阅列表IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 获取订阅列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.delete("/subscribe/{subscription_id}")
async def cancel_subscription(
    subscription_id: str = Path(..., description="订阅ID"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    取消订阅
    
    取消指定的政策订阅
    """
    try:
        result = await policy_tracking_service.cancel_subscription(
            subscription_id=subscription_id,
            user_id=str(user.id)
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 取消订阅数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"取消数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 取消订阅IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"取消IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 取消订阅失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"取消失败: {str(e)}")


@router.get("/updates", response_model=List[PolicyUpdate])
async def get_policy_updates(
    categories: Optional[str] = Query(None, description="政策类别，逗号分隔"),
    keywords: Optional[str] = Query(None, description="关键词，逗号分隔"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    获取最新政策更新
    
    支持按类别和关键词筛选
    """
    try:
        category_list = None
        if categories:
            try:
                category_list = [PolicyCategory(cat) for cat in categories.split(",")]
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的政策类别")
        
        keyword_list = keywords.split(",") if keywords else None
        
        updates = await policy_tracking_service.fetch_policy_updates(
            categories=category_list,
            keywords=keyword_list,
            limit=limit
        )
        
        return updates
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 获取政策更新数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"获取数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 获取政策更新IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 获取政策更新失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/query", response_model=PolicyQueryResponse)
async def query_policies(
    keywords: Optional[str] = Query(None, description="关键词，逗号分隔"),
    categories: Optional[str] = Query(None, description="政策类别，逗号分隔"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    查询政策
    
    支持关键词、类别筛选，分页查询
    """
    try:
        keyword_list = keywords.split(",") if keywords else None
        
        category_list = None
        if categories:
            try:
                category_list = [PolicyCategory(cat) for cat in categories.split(",")]
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的政策类别")
        
        request = PolicyQueryRequest(
            tenant_id=user.tenant_id,
            keywords=keyword_list,
            categories=category_list,
            limit=limit,
            offset=offset
        )
        
        result = await policy_tracking_service.query_policies(request)
        
        return PolicyQueryResponse(**result)
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 查询政策数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"查询数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 查询政策IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 查询政策失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/trends")
async def get_policy_trends(
    period_days: int = Query(90, ge=30, le=365, description="分析期间天数"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    获取政策趋势分析
    
    分析指定期间的政策趋势和监管重点
    """
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=period_days)
        
        result = await policy_tracking_service.analyze_policy_trends(
            tenant_id=user.tenant_id,
            user_id=str(user.id),
            period_start=start_date,
            period_end=end_date
        )
        
        return result
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 趋势分析数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"分析数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 趋势分析IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 趋势分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.get("/calendar")
async def get_compliance_calendar(
    period_days: int = Query(180, ge=30, le=365, description="日历期间天数"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    获取合规日历
    
    显示政策生效日期和合规截止日期
    """
    try:
        end_date = datetime.now().date() + timedelta(days=period_days)
        start_date = datetime.now().date()
        
        result = await policy_tracking_service.get_compliance_calendar(
            tenant_id=user.tenant_id,
            user_id=str(user.id),
            period_start=start_date,
            period_end=end_date
        )
        
        return result
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 获取合规日历数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"获取数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 获取合规日历IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 获取合规日历失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.post("/notify/{subscription_id}")
async def notify_subscriber(
    subscription_id: str = Path(..., description="订阅ID"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    手动触发通知
    
    立即向订阅者发送政策更新通知
    """
    try:
        result = await policy_tracking_service.notify_subscribers(
            subscription_id=subscription_id
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 发送通知数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"发送数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 发送通知IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"发送IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 发送通知失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)}")


@router.get("/categories")
async def list_policy_categories():
    """
    获取政策类别列表
    
    返回所有可订阅的政策类别
    """
    return {
        "categories": [
            {"value": cat.value, "label": _get_category_label(cat)}
            for cat in PolicyCategory
        ]
    }


def _get_category_label(category: PolicyCategory) -> str:
    """获取类别标签"""
    labels = {
        PolicyCategory.TAX: "税务政策",
        PolicyCategory.FINANCE: "财务政策",
        PolicyCategory.LEGAL: "法律法规",
        PolicyCategory.LABOR: "劳动用工",
        PolicyCategory.ENVIRONMENT: "环境保护",
        PolicyCategory.INDUSTRY: "产业政策",
        PolicyCategory.TRADE: "贸易政策",
        PolicyCategory.TECHNOLOGY: "科技创新",
    }
    return labels.get(category, category.value)


@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "policy_tracking",
        "version": "1.0.0"
    }
