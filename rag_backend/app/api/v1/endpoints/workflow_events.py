"""
工作流事件 API 端点

提供 SSE 实时推送工作流状态
"""

import asyncio
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from typing import Optional

from app.services.workflow_event_service import workflow_event_service, WorkflowEventType
from app.api.deps import get_current_user, CurrentUser

router = APIRouter(prefix="/workflow-events", tags=["工作流事件"])
logger = logging.getLogger(__name__)


@router.get("/stream/{workflow_id}")
async def stream_workflow_events(
    workflow_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """
    SSE 流式推送工作流事件
    
    建立 SSE 连接，实时推送工作流状态更新
    
    Args:
        workflow_id: 工作流ID
        
    Returns:
        StreamingResponse: SSE 流
    """
    logger.info(f"📡 建立 SSE 连接: workflow_id={workflow_id}")
    
    async def event_generator():
        queue = await workflow_event_service.subscribe(workflow_id)
        
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    if event is None:
                        break
                    
                    yield event.to_sse_data()
                    
                    if event.event_type in [
                        WorkflowEventType.COMPLETED,
                        WorkflowEventType.FAILED
                    ]:
                        await asyncio.sleep(1)
                        break
                        
                except asyncio.TimeoutError:
                    yield f"data: {{'event_type': 'heartbeat', 'timestamp': '{__import__('datetime').datetime.now().isoformat()}'}}\n\n"
                    
        except asyncio.CancelledError:
            logger.info(f"📡 SSE 连接取消: workflow_id={workflow_id}")
        except Exception as e:
            logger.error(f"❌ SSE 连接错误: {e}", exc_info=True)
        finally:
            await workflow_event_service.unsubscribe(workflow_id, queue)
            logger.info(f"📡 SSE 连接关闭: workflow_id={workflow_id}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/state/{workflow_id}")
async def get_workflow_state(
    workflow_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取工作流当前状态
    
    Args:
        workflow_id: 工作流ID
        
    Returns:
        dict: 当前状态
    """
    state = await workflow_event_service.get_current_state(workflow_id)
    
    if not state:
        return {
            "exists": False,
            "message": "工作流不存在或已过期"
        }
    
    return {
        "exists": True,
        "state": state
    }


@router.get("/history/{workflow_id}")
async def get_workflow_history(
    workflow_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取工作流历史事件
    
    Args:
        workflow_id: 工作流ID
        
    Returns:
        dict: 历史事件列表
    """
    history = await workflow_event_service.get_history(workflow_id)
    
    return {
        "workflow_id": workflow_id,
        "event_count": len(history),
        "events": history
    }
