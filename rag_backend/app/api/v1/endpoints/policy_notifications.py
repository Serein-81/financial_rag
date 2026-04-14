"""
政策通知实时推送 API 端点

提供 SSE 实时推送政策匹配通知
"""

import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette import status

from app.services.policy_event_service import policy_event_service, PolicyEventType
from app.api.deps import get_current_user, CurrentUser

router = APIRouter(prefix="/policy-notifications", tags=["政策通知推送"])
logger = logging.getLogger(__name__)


@router.get("/stream")
async def stream_policy_notifications(
    request: Request,
    user: CurrentUser = Depends(get_current_user)
):
    """
    SSE 流式推送政策通知

    建立 SSE 连接，实时推送政策匹配通知

    Returns:
        StreamingResponse: SSE 流
    """
    logger.info(f"🔍 [DEBUG] 收到 SSE 请求")
    logger.info(f"🔍 [DEBUG] URL: {request.url}")
    logger.info(f"🔍 [DEBUG] Query params: {dict(request.query_params)}")
    logger.info(f"🔍 [DEBUG] User: {user}, user.tenant_id: {user.tenant_id if user else 'N/A'}")

    # 优先从 query 参数获取 tenant_id（SSE 连接场景）
    enterprise_id = request.query_params.get("tenant_id")
    logger.info(f"🔍 [DEBUG] 从 query_params 获取的 tenant_id: {enterprise_id}")

    if not enterprise_id:
        # 备用：从用户对象获取
        enterprise_id = user.tenant_id if user else None
        logger.info(f"🔍 [DEBUG] 从 user 对象获取的 tenant_id: {enterprise_id}")

    if not enterprise_id:
        logger.error(f"❌ [AUTH] Missing tenant_id")
        logger.error(f"   query_params.get('tenant_id'): {request.query_params.get('tenant_id')}")
        logger.error(f"   user.tenant_id: {user.tenant_id if user else 'N/A'}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing tenant context"
        )

    logger.info(f"🔔 建立政策通知连接: enterprise_id={enterprise_id}")
    
    async def event_generator():
        queue = await policy_event_service.subscribe(enterprise_id)
        
        try:
            heartbeat_count = 0
            
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    if event is None:
                        break
                    
                    yield event.to_sse_data()
                    heartbeat_count = 0
                    
                    if event.event_type == PolicyEventType.POLICY_NOTIFICATION_ACKNOWLEDGED:
                        await asyncio.sleep(1)
                        break
                        
                except asyncio.TimeoutError:
                    heartbeat_count += 1
                    if heartbeat_count > 3:
                        logger.info(f"💓 政策通知心跳超时，关闭连接: enterprise_id={enterprise_id}")
                        break
                    
                    yield f"data: {{'event_type': 'heartbeat', 'timestamp': '{__import__('datetime').datetime.now().isoformat()}'}}\n\n"
                    
        except asyncio.CancelledError:
            logger.info(f"📡 政策通知SSE连接取消: enterprise_id={enterprise_id}")
        except Exception as e:
            logger.error(f"❌ 政策通知SSE连接错误: {e}", exc_info=True)
        finally:
            await policy_event_service.unsubscribe(enterprise_id, queue)
            logger.info(f"📡 政策通知SSE连接关闭: enterprise_id={enterprise_id}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/recent")
async def get_recent_notifications(
    limit: int = 50,
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取最近的政策通知
    
    Args:
        limit: 返回数量限制
        
    Returns:
        dict: 最近的通知列表
    """
    enterprise_id = user.tenant_id
    
    notifications = await policy_event_service.get_recent_notifications(
        enterprise_id,
        limit=limit
    )
    
    return {
        "enterprise_id": enterprise_id,
        "count": len(notifications),
        "notifications": notifications
    }


@router.get("/status")
async def get_notification_status(
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取通知状态
    
    Returns:
        dict: 订阅状态信息
    """
    enterprise_id = user.tenant_id
    
    subscriber_count = policy_event_service.get_subscriber_count(enterprise_id)
    recent_count = len(policy_event_service._notifications.get(enterprise_id, []))
    
    return {
        "enterprise_id": enterprise_id,
        "active_subscribers": subscriber_count,
        "total_notifications": recent_count,
        "stream_endpoint": "/api/v1/policy-notifications/stream"
    }
