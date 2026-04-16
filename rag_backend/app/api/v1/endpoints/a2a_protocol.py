"""
A2A Protocol API Endpoints

A2A 协议 HTTP 端点
提供任务提交、查询、流式推送等功能
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.a2a_protocol import (
    AgentRegistry,
    HybridDispatcher,
    TaskSubmitParams
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/a2a", tags=["a2a"])

DEFAULT_TENANT_ID = "default"


def get_registry(request: Request) -> AgentRegistry:
    """从 app.state 获取 registry"""
    if not hasattr(request.app.state, "a2a_registry"):
        request.app.state.a2a_registry = AgentRegistry.get_instance()
    return request.app.state.a2a_registry


def get_dispatcher(request: Request) -> HybridDispatcher:
    """从 app.state 获取 dispatcher"""
    if not hasattr(request.app.state, "a2a_dispatcher"):
        registry = get_registry(request)
        request.app.state.a2a_dispatcher = HybridDispatcher(registry=registry)
    return request.app.state.a2a_dispatcher


class TaskSubmitRequest(BaseModel):
    """任务提交请求"""
    agent_name: Optional[str] = None
    required_skills: list[str] = None
    message: str
    metadata: Dict[str, Any] = None


class TaskSubmitResponse(BaseModel):
    """任务提交响应"""
    task_id: str
    agent_name: str
    status: str


class DispatchRequest(BaseModel):
    """调度请求"""
    query: str
    agent_name: Optional[str] = None
    required_skills: Optional[list[str]] = None
    parallel: bool = False
    metadata: Optional[Dict[str, Any]] = None
    tenant_id: Optional[str] = DEFAULT_TENANT_ID


class DispatchResponse(BaseModel):
    """调度响应"""
    success: bool
    result: Any
    source: str
    agent_name: str
    duration_ms: float
    error: Optional[str] = None


@router.get("/.well-known/agent.json")
async def get_agent_card(request: Request):
    """获取主 Agent Card"""
    registry = get_registry(request)
    agents = registry.list_all_agents()
    if not agents:
        raise HTTPException(status_code=404, detail="No agents registered")
    return agents[0]


@router.get("/agents")
async def list_agents(request: Request):
    """列出所有注册的 Agent"""
    registry = get_registry(request)
    logger.info(f"🔍 [DEBUG] registry id: {id(registry)}, agents: {list(registry._agents.keys())}")
    return registry.get_agent_stats()


@router.get("/agents/{agent_name}/card")
async def get_agent_card_by_name(request: Request, agent_name: str):
    """获取指定 Agent 的 Card"""
    registry = get_registry(request)
    reg = registry.get_agent(agent_name)
    if not reg:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")
    return reg.card


@router.post("/tasks/send")
async def send_task(request: Request, params: TaskSubmitParams):
    """提交任务到指定 Agent"""
    dispatcher = get_dispatcher(request)
    agent_name = params.message.metadata.get("agent_name") if params.message.metadata else None
    
    result = await dispatcher.dispatch(
        query=params.message.parts[0].text if params.message.parts else "",
        agent_name=agent_name,
        metadata=params.message.metadata
    )
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    
    return {
        "id": result.agent_name,
        "status": "completed",
        "result": result.result
    }


@router.get("/tasks/{task_id}")
async def get_task(request: Request, task_id: str):
    """获取任务状态"""
    registry = get_registry(request)
    for name, reg in registry._agents.items():
        task = await registry.get_agent(name)
        if task:
            return task
    raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")


@router.post("/dispatch")
async def dispatch_task(request: Request, body: DispatchRequest):
    """统一调度接口"""
    dispatcher = get_dispatcher(request)
    metadata = body.metadata or {}
    metadata["tenant_id"] = body.tenant_id
    
    result = await dispatcher.dispatch(
        query=body.query,
        agent_name=body.agent_name,
        required_skills=body.required_skills,
        metadata=metadata
    )
    
    return DispatchResponse(
        success=result.success,
        result=result.result,
        source=result.source,
        agent_name=result.agent_name,
        duration_ms=result.duration_ms,
        error=result.error
    )


@router.post("/dispatch/multi")
async def dispatch_multi(request: Request, body: DispatchRequest):
    """多 Agent 并行调度"""
    dispatcher = get_dispatcher(request)
    metadata = body.metadata or {}
    metadata["tenant_id"] = body.tenant_id
    
    agent_names = body.required_skills or []
    
    result = await dispatcher.dispatch_multi(
        query=body.query,
        agent_names=agent_names if agent_names else None,
        parallel=body.parallel,
        metadata=metadata
    )
    
    return {
        "results": [
            {
                "success": r.success,
                "result": r.result,
                "source": r.source,
                "agent_name": r.agent_name,
                "duration_ms": r.duration_ms,
                "error": r.error
            }
            for r in result.results
        ],
        "final_response": result.final_response,
        "execution_time_ms": result.execution_time_ms
    }


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "protocol": "A2A"}


_a2a_servers: Dict[str, Dict[str, Any]] = {}


def register_a2a_server(agent_name: str, server: Any):
    """注册 A2A Server"""
    _a2a_servers[agent_name] = {"server": server}
    logger.info(f"✅ A2A Server 注册: {agent_name}")
