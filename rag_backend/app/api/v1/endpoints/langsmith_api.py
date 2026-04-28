"""
LangSmith 集成 API 端点

提供 LangSmith 监控状态、统计和配置管理功能
"""

import logging
import time
from typing import Optional, Dict
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from app.api import deps
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.agent_trace import AgentTrace
from app.models.tool_trace import ToolCallTrace
from app.langsmith_integration import get_langsmith_config, get_tracer, LangSmithTracer

logger = logging.getLogger(__name__)
router = APIRouter()


class LangSmithStatusResponse(BaseModel):
    enabled: bool
    api_key_configured: bool
    project: str
    endpoint: str
    tracing_enabled: bool
    client_initialized: bool
    last_check: str


class LangSmithStatsResponse(BaseModel):
    total_traces: int
    total_llm_calls: int
    total_tool_calls: int
    active_runs: int
    error_count: int
    last_trace_time: Optional[str]
    uptime_seconds: float


class LangSmithConfigRequest(BaseModel):
    api_key: Optional[str] = None
    project: Optional[str] = None
    endpoint: Optional[str] = None
    tracing: Optional[bool] = None


class LangSmithDashboardResponse(BaseModel):
    dashboard_url: str
    project_url: str
    traces_url: str
    datasets_url: str
    evaluations_url: str


class LangSmithProjectInfo(BaseModel):
    project_name: str
    run_count: int
    last_run_time: Optional[str]
    trace_count: int


_stats_tracker = {
    "total_traces": 0,
    "total_llm_calls": 0,
    "total_tool_calls": 0,
    "error_count": 0,
    "last_trace_time": None,
    "start_time": time.time()
}


def track_langsmith_event(event_type: str):
    """追踪 LangSmith 事件"""
    if event_type == "trace":
        _stats_tracker["total_traces"] += 1
        _stats_tracker["last_trace_time"] = datetime.now().isoformat()
    elif event_type == "llm_call":
        _stats_tracker["total_llm_calls"] += 1
    elif event_type == "tool_call":
        _stats_tracker["total_tool_calls"] += 1
    elif event_type == "error":
        _stats_tracker["error_count"] += 1


def get_dashboard_url(project: str, endpoint: str = "https://smith.langchain.com") -> Dict[str, str]:
    """生成 LangSmith Dashboard URL"""
    base_url = "https://smith.langchain.com"
    return {
        "dashboard_url": f"{base_url}/",
        "project_url": f"{base_url}/projects/{project}/about",
        "traces_url": f"{base_url}/projects/{project}/traces",
        "datasets_url": f"{base_url}/datasets",
        "evaluations_url": f"{base_url}/projects/{project}/evals"
    }


def _run_time_iso(run) -> Optional[str]:
    """Return a stable timestamp for different LangSmith SDK Run shapes."""
    value = (
        getattr(run, "created_at", None)
        or getattr(run, "start_time", None)
        or getattr(run, "created_time", None)
        or getattr(run, "first_token_time", None)
    )
    return value.isoformat() if hasattr(value, "isoformat") else value


def _run_field(run, name: str, default=None):
    if hasattr(run, name):
        return getattr(run, name)
    if isinstance(run, dict):
        return run.get(name, default)
    return default


@router.get("/status", response_model=LangSmithStatusResponse)
async def get_langsmith_status(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取 LangSmith 集成状态
    
    返回 LangSmith 是否启用、配置状态和客户端状态
    """
    config = get_langsmith_config()
    tracer = get_tracer()
    
    return {
        "enabled": config.get("enabled", False),
        "api_key_configured": bool(config.get("api_key")),
        "project": config.get("project", "financial_rag"),
        "endpoint": config.get("endpoint", "https://api.smith.langchain.com"),
        "tracing_enabled": config.get("tracing", False),
        "client_initialized": tracer.client is not None,
        "last_check": datetime.now().isoformat()
    }


@router.get("/stats", response_model=LangSmithStatsResponse)
async def get_langsmith_stats(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取 LangSmith 统计信息
    
    返回追踪统计、LLM 调用统计和工具调用统计
    """
    uptime = time.time() - _stats_tracker["start_time"]
    total_traces = _stats_tracker["total_traces"]
    total_tool_calls = _stats_tracker["total_tool_calls"]
    active_runs = 0
    error_count = _stats_tracker["error_count"]
    last_trace_time = _stats_tracker["last_trace_time"]

    try:
        async with AsyncSessionLocal() as db:
            total_traces = await db.scalar(select(func.count()).select_from(AgentTrace)) or 0
            total_tool_calls = await db.scalar(select(func.count()).select_from(ToolCallTrace)) or 0
            active_runs = await db.scalar(
                select(func.count()).select_from(AgentTrace).where(AgentTrace.status == "running")
            ) or 0
            failed_traces = await db.scalar(
                select(func.count()).select_from(AgentTrace).where(AgentTrace.status == "failed")
            ) or 0
            failed_tools = await db.scalar(
                select(func.count()).select_from(ToolCallTrace).where(ToolCallTrace.status != "success")
            ) or 0
            error_count = int(failed_traces) + int(failed_tools)
            latest_trace = await db.scalar(select(func.max(AgentTrace.created_at)))
            if latest_trace:
                last_trace_time = latest_trace.isoformat()
    except Exception as e:
        logger.warning(f"[LangSmith] 读取本地追踪统计失败，回退到内存统计: {e}")

    return {
        "total_traces": total_traces,
        "total_llm_calls": _stats_tracker["total_llm_calls"],
        "total_tool_calls": total_tool_calls,
        "active_runs": active_runs,
        "error_count": error_count,
        "last_trace_time": last_trace_time,
        "uptime_seconds": round(uptime, 2)
    }


@router.get("/dashboard", response_model=LangSmithDashboardResponse)
async def get_langsmith_dashboard(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取 LangSmith Dashboard 链接
    
    返回指向 LangSmith Web 界面的各个页面链接
    """
    config = get_langsmith_config()
    project = config.get("project", "financial_rag")
    
    urls = get_dashboard_url(project)
    
    return urls


@router.get("/project")
async def get_langsmith_project_info(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取 LangSmith 项目信息
    
    返回当前项目的统计信息
    """
    config = get_langsmith_config()
    tracer = get_tracer()
    
    if not config.get("enabled") or not tracer.client:
        return {
            "project_name": config.get("project", "financial_rag"),
            "run_count": 0,
            "last_run_time": None,
            "trace_count": _stats_tracker["total_traces"],
            "warning": "LangSmith 未配置或未初始化，请配置 LANGSMITH_API_KEY 和 LANGSMITH_TRACING=true"
        }
    
    try:
        project_name = config.get("project", "financial_rag")
        
        runs = list(tracer.client.list_runs(
            project_name=project_name,
            limit=100
        ))
        
        last_run = runs[0] if runs else None
        
        return {
            "project_name": project_name,
            "run_count": len(runs),
            "last_run_time": _run_time_iso(last_run) if last_run else None,
            "trace_count": _stats_tracker["total_traces"]
        }
        
    except Exception as e:
        logger.error(f"[LangSmith] 获取项目信息失败: {e}")
        return {
            "project_name": config.get("project", "financial_rag"),
            "run_count": 0,
            "last_run_time": None,
            "trace_count": _stats_tracker["total_traces"],
            "error": f"获取项目信息失败: {str(e)}"
        }


@router.post("/config")
async def update_langsmith_config(
    config_request: LangSmithConfigRequest,
    current_user: User = Depends(deps.get_current_user)
):
    """
    更新 LangSmith 配置（内存中）
    
    注意：此配置仅在当前服务进程内有效，
    重启后需要重新配置。如需永久保存，请修改环境变量或 .env 文件
    """
    import os
    
    updates = {}
    
    if config_request.api_key is not None:
        os.environ["LANGSMITH_API_KEY"] = config_request.api_key
        updates["api_key"] = "已更新"
    
    if config_request.project is not None:
        os.environ["LANGSMITH_PROJECT"] = config_request.project
        updates["project"] = config_request.project
    
    if config_request.endpoint is not None:
        os.environ["LANGSMITH_ENDPOINT"] = config_request.endpoint
        updates["endpoint"] = config_request.endpoint
    
    if config_request.tracing is not None:
        os.environ["LANGSMITH_TRACING"] = "true" if config_request.tracing else "false"
        updates["tracing"] = config_request.tracing
    
    new_config = get_langsmith_config()
    
    if new_config.get("enabled"):
        try:
            tracer = LangSmithTracer(project_name=new_config.get("project"))
            global _tracer
            _tracer = tracer
            updates["client_status"] = "已重新初始化" if tracer.client else "初始化失败"
        except Exception as e:
            updates["client_status"] = f"初始化失败: {str(e)}"
    else:
        updates["client_status"] = "未启用"
    
    return {
        "message": "配置已更新",
        "updates": updates,
        "current_config": new_config
    }


@router.post("/test")
async def test_langsmith_connection(
    current_user: User = Depends(deps.get_current_user)
):
    """
    测试 LangSmith 连接
    
    执行一个简单的追踪测试，验证配置是否正确
    """
    tracer = get_tracer()
    config = get_langsmith_config()
    
    if not config.get("enabled"):
        return {
            "success": False,
            "message": "LangSmith 未启用",
            "details": {
                "api_key_configured": bool(config.get("api_key")),
                "tracing_enabled": config.get("tracing", False)
            }
        }
    
    if not tracer.client:
        return {
            "success": False,
            "message": "LangSmith 客户端未初始化",
            "details": {
                "project": config.get("project"),
                "endpoint": config.get("endpoint")
            }
        }
    
    try:
        test_run = tracer.client.create_run(
            name="connection_test",
            run_type="tool",
            project_name=config.get("project", "financial_rag"),
            inputs={"test": "LangSmith 连接测试"},
            outputs={"result": "连接成功"},
            tags=["test", "connection"]
        )
        
        return {
            "success": True,
            "message": "LangSmith 连接正常",
            "details": {
                "run_id": str(test_run.id),
                "project": config.get("project"),
                "endpoint": config.get("endpoint")
            }
        }
        
    except Exception as e:
        logger.error(f"[LangSmith] 连接测试失败: {e}")
        return {
            "success": False,
            "message": f"连接测试失败: {str(e)}",
            "details": {
                "project": config.get("project"),
                "endpoint": config.get("endpoint")
            }
        }


@router.get("/recent-traces")
async def get_recent_langsmith_traces(
    limit: int = 10,
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取最近的 LangSmith 追踪记录
    
    Args:
        limit: 返回的记录数量，默认 10 条
    """
    config = get_langsmith_config()
    tracer = get_tracer()
    
    if not config.get("enabled") or not tracer.client:
        return {
            "traces": [],
            "message": "LangSmith 未启用或客户端未初始化"
        }
    
    try:
        runs = list(tracer.client.list_runs(
            project_name=config.get("project", "financial_rag"),
            limit=limit
        ))
        
        traces = []
        for run in runs:
            traces.append({
                "run_id": str(_run_field(run, "id", "")),
                "name": _run_field(run, "name", ""),
                "run_type": _run_field(run, "run_type", ""),
                "created_at": _run_time_iso(run),
                "inputs": _run_field(run, "inputs", {}) or {},
                "outputs": _run_field(run, "outputs", {}) or {},
                "error": _run_field(run, "error"),
                "tags": _run_field(run, "tags", []) or []
            })
        
        return {
            "total": len(traces),
            "traces": traces
        }
        
    except Exception as e:
        logger.error(f"[LangSmith] 获取最近追踪失败: {e}")
        return {
            "traces": [],
            "error": str(e)
        }
