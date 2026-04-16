"""
A2A Protocol v1 API Endpoints

A2A 协议 v1 HTTP 端点
提供完整的传输层支持：
1. 任务提交和查询
2. SSE 流式事件推送
3. 多租户安全穿透
4. 传输层健康检查
"""

import json
import logging
from typing import Optional, Dict, Any, AsyncGenerator, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.a2a_protocol import (
    get_transport_manager,
    TransportManager,
    TransportError
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/a2a/v1", tags=["a2a_v1"])

TENANT_ID_HEADER = "x-tenant-id"
AUTHORIZATION_HEADER = "authorization"


class TaskSendRequest(BaseModel):
    """任务发送请求"""
    message: Dict[str, Any]
    sessionId: Optional[str] = None
    acceptedOutputModes: List[str] = Field(default_factory=lambda: ["text"])
    pushNotification: Optional[Dict[str, Any]] = None


class TaskSendResponse(BaseModel):
    """任务发送响应"""
    id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    agent_name: str


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    id: str
    status: str
    messages: List[Dict[str, Any]]
    artifacts: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    createdAt: str
    updatedAt: str


class NotificationRequest(BaseModel):
    """通知请求"""
    to_agent: str
    content: Dict[str, Any]
    timestamp: Optional[str] = None


class SubscriptionRequest(BaseModel):
    """订阅请求"""
    agent: str
    event_types: List[str]


class SubscriptionResponse(BaseModel):
    """订阅响应"""
    subscription_id: str
    agent: str
    event_types: List[str]


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    timestamp: str
    transport_manager: Dict[str, Any]
    local_agents: List[str]
    remote_agents: List[str]


def get_tenant_id(x_tenant_id: Optional[str] = Header(None)) -> Optional[str]:
    """获取租户 ID"""
    return x_tenant_id


def get_authorization(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """获取授权头"""
    return authorization


async def get_transport(request: Request) -> TransportManager:
    """获取传输管理器"""
    if not hasattr(request.app.state, "transport_manager"):
        request.app.state.transport_manager = await get_transport_manager()
    return request.app.state.transport_manager


@router.get("/health")
async def health_check(request: Request):
    """健康检查"""
    try:
        transport = await get_transport(request)
        health = await transport.health_check_all()
        stats = transport.get_statistics()
        
        return HealthResponse(
            status="healthy" if health.get("manager") else "unhealthy",
            timestamp=datetime.utcnow().isoformat(),
            transport_manager=health,
            local_agents=[name for name, loc in stats.get("registry", {}).items() if loc == "local"],
            remote_agents=[name for name, loc in stats.get("registry", {}).items() if loc == "remote"]
        )
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 健康检查数据错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except (OSError, IOError) as e:
        logger.error(f"❌ 健康检查IO错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 健康检查失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/send")
async def send_task(
    request: Request,
    body: TaskSendRequest,
    x_tenant_id: Optional[str] = Header(None)
) -> TaskSendResponse:
    """
    发送任务到 Agent
    
    RESTful: POST /a2a/v1/tasks/send
    自动选择最优传输方式
    """
    try:
        transport = await get_transport(request)
        
        to_agent = body.message.get("metadata", {}).get("agent_name", "default")
        
        result = await transport.send_message(
            to_agent=to_agent,
            message=body.message,
            tenant_id=x_tenant_id,
            wait_for_response=True
        )
        
        return TaskSendResponse(
            id=result.get("task_id", to_agent),
            status="completed",
            result=result,
            agent_name=to_agent
        )
        
    except TransportError as e:
        logger.error(f"❌ 任务发送失败: {e}")
        raise HTTPException(status_code=e.code, detail=e.message)
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 任务发送数据错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except (OSError, IOError) as e:
        logger.error(f"❌ 任务发送IO错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 任务发送异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task_status(
    request: Request,
    task_id: str,
    x_tenant_id: Optional[str] = Header(None),
    history_length: Optional[int] = None
) -> TaskStatusResponse:
    """
    获取任务状态
    
    RESTful: GET /a2a/v1/tasks/{task_id}
    """
    try:
        registry = request.app.state.get("a2a_registry")
        if registry:
            agent = registry.get_agent(task_id)
            if agent:
                task = await registry.get_task_status(task_id)
                if task:
                    return TaskStatusResponse(**task)
        
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 获取任务状态数据错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except (OSError, IOError) as e:
        logger.error(f"❌ 获取任务状态IO错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 获取任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    request: Request,
    task_id: str,
    x_tenant_id: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    取消任务
    
    RESTful: POST /a2a/v1/tasks/{task_id}/cancel
    """
    try:
        registry = request.app.state.get("a2a_registry")
        if registry:
            result = await registry.cancel_task(task_id)
            if result:
                return {"status": "canceled", "task_id": task_id}
        
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 取消任务数据错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except (OSError, IOError) as e:
        logger.error(f"❌ 取消任务IO错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 取消任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/subscribe")
async def subscribe_task_events(
    request: Request,
    task_id: str,
    x_tenant_id: Optional[str] = Header(None)
) -> StreamingResponse:
    """
    订阅任务事件流（SSE）
    
    RESTful: GET /a2a/v1/tasks/{task_id}/subscribe
    返回 Server-Sent Events 流
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            transport = await get_transport(request)
            
            async for event in transport.stream_task_events(
                to_agent="default",
                task_id=task_id,
                tenant_id=x_tenant_id
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ SSE 流数据错误: {e}")
            yield f"data: {json.dumps({'error': f'数据错误: {str(e)}'})}\n\n"
        except (OSError, IOError) as e:
            logger.error(f"❌ SSE 流IO错误: {e}")
            yield f"data: {json.dumps({'error': f'IO错误: {str(e)}'})}\n\n"
        except (OSError, IOError) as e:
            raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
        except Exception as e:
            logger.error(f"❌ SSE 流异常: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/notifications")
async def send_notification(
    request: Request,
    body: NotificationRequest,
    x_tenant_id: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    发送通知（单向消息）
    
    RESTful: POST /a2a/v1/notifications
    """
    try:
        transport = await get_transport(request)
        
        await transport.send_message(
            to_agent=body.to_agent,
            message=body.content,
            tenant_id=x_tenant_id,
            wait_for_response=False
        )
        
        return {
            "status": "sent",
            "to_agent": body.to_agent,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except TransportError as e:
        logger.error(f"❌ 通知发送失败: {e}")
        raise HTTPException(status_code=e.code, detail=e.message)
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 通知发送数据错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except (OSError, IOError) as e:
        logger.error(f"❌ 通知发送IO错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 通知发送异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscriptions")
async def create_subscription(
    request: Request,
    body: SubscriptionRequest,
    x_tenant_id: Optional[str] = Header(None)
) -> SubscriptionResponse:
    """
    创建订阅
    
    RESTful: POST /a2a/v1/subscriptions
    """
    try:
        transport = await get_transport(request)
        
        subscription_id = await transport.subscribe_events(
            agent=body.agent,
            event_types=body.event_types,
            callback=None,
            tenant_id=x_tenant_id
        )
        
        return SubscriptionResponse(
            subscription_id=subscription_id,
            agent=body.agent,
            event_types=body.event_types
        )
        
    except TransportError as e:
        logger.error(f"❌ 创建订阅失败: {e}")
        raise HTTPException(status_code=e.code, detail=e.message)
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 创建订阅数据错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except (OSError, IOError) as e:
        logger.error(f"❌ 创建订阅IO错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 创建订阅异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(
    request: Request,
    subscription_id: str
) -> Dict[str, Any]:
    """
    删除订阅
    
    RESTful: DELETE /a2a/v1/subscriptions/{subscription_id}
    """
    try:
        transport = await get_transport(request)
        
        if hasattr(transport, "unsubscribe"):
            await transport.unsubscribe(subscription_id)
        
        return {
            "status": "deleted",
            "subscription_id": subscription_id
        }
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 删除订阅数据错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except (OSError, IOError) as e:
        logger.error(f"❌ 删除订阅IO错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 删除订阅失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
async def list_agents(request: Request) -> Dict[str, Any]:
    """
    列出所有注册的 Agent
    
    RESTful: GET /a2a/v1/agents
    """
    try:
        transport = await get_transport(request)
        stats = transport.get_statistics()
        
        return {
            "total": stats.get("local_agents", 0) + stats.get("remote_agents", 0),
            "local_agents": stats.get("local_agents", 0),
            "remote_agents": stats.get("remote_agents", 0),
            "registry": stats.get("registry", {})
        }
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 列出 Agent 数据错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except (OSError, IOError) as e:
        logger.error(f"❌ 列出 Agent IO错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 列出 Agent 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/register")
async def register_agent(
    request: Request,
    agent_name: str,
    url: Optional[str] = None,
    x_tenant_id: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    注册 Agent
    
    RESTful: POST /a2a/v1/agents/register
    """
    try:
        transport = await get_transport(request)
        
        if url:
            transport.register_remote_agent(agent_name, url)
            location = "remote"
        else:
            location = "local"
        
        return {
            "status": "registered",
            "agent_name": agent_name,
            "location": location,
            "url": url
        }
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ 注册 Agent 数据错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except (OSError, IOError) as e:
        logger.error(f"❌ 注册 Agent IO错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 注册 Agent 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
