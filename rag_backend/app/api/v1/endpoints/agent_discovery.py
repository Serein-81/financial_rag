"""
Agent 发现与追踪 API 接口

提供以下功能：
1. Agent 发现：列出所有已注册的 Agent 及其工具
2. 工具分类：区分本地工具、云端工具和 MCP 工具
3. Agent 追踪：记录和查询 Agent 执行过程
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.api import deps
from app.models.user import User
from app.services.agent_registry import (
    agent_discovery_registry,
    AgentType,
    ToolLocation
)
from app.services.agent_tracer import agent_tracer

router = APIRouter()


class AgentSummaryResponse(BaseModel):
    """Agent 摘要响应"""
    agent_id: str
    agent_name: str
    agent_type: str
    specialty: Optional[str]
    description: str
    tool_count: int
    tool_breakdown: dict
    enabled: bool
    capabilities: List[str]


class ToolSummaryResponse(BaseModel):
    """工具摘要响应"""
    name: str
    description: str
    location: str
    category: str
    tags: List[str]
    agent_id: str
    agent_name: str


class AgentDetailResponse(BaseModel):
    """Agent 详细信息响应"""
    agent_id: str
    agent_name: str
    agent_type: str
    specialty: Optional[str]
    description: str
    enabled: bool
    capabilities: List[str]
    tools: List[dict]
    tool_summary: dict
    created_at: str
    last_updated: str


class RegistrySummaryResponse(BaseModel):
    """注册中心摘要响应"""
    total_agents: int
    enabled_agents: int
    total_tools: int
    tool_breakdown: dict
    agents: List[AgentSummaryResponse]


@router.get("/summary", response_model=RegistrySummaryResponse)
async def get_registry_summary(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取 Agent 注册中心摘要

    返回所有已注册 Agent 的概览信息，包括工具统计
    """
    try:
        summary = agent_discovery_registry.get_summary()

        return {
            "total_agents": summary["total_agents"],
            "enabled_agents": summary["enabled_agents"],
            "total_tools": summary["total_tools"],
            "tool_breakdown": summary["tool_breakdown"],
            "agents": [
                {
                    "agent_id": a["agent_id"],
                    "agent_name": a["agent_name"],
                    "agent_type": a["agent_type"],
                    "specialty": a.get("specialty"),
                    "description": "",
                    "tool_count": a["tool_count"],
                    "tool_breakdown": a["tool_summary"],
                    "enabled": a["enabled"],
                    "capabilities": []
                }
                for a in summary["agents"]
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取注册中心摘要失败: {str(e)}")


@router.get("/agents", response_model=List[AgentSummaryResponse])
async def list_agents(
    agent_type: Optional[str] = None,
    enabled_only: bool = True,
    current_user: User = Depends(deps.get_current_user)
):
    """
    列出所有已注册的 Agent

    Args:
        agent_type: Agent 类型过滤 (specialist/general/router/utility)
        enabled_only: 仅返回已启用的 Agent
        current_user: 当前用户
    """
    try:
        at_filter = AgentType(agent_type) if agent_type else None
        agents = agent_discovery_registry.list_agents(
            agent_type=at_filter,
            enabled_only=enabled_only
        )

        return [
            {
                "agent_id": a.agent_id,
                "agent_name": a.agent_name,
                "agent_type": a.agent_type.value,
                "specialty": a.specialty,
                "description": a.description,
                "tool_count": len(a.tools),
                "tool_breakdown": a.get_tool_count_summary(),
                "enabled": a.enabled,
                "capabilities": a.capabilities
            }
            for a in agents
        ]
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的 Agent 类型: {agent_type}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"列出 Agent 失败: {str(e)}")


@router.get("/agents/{agent_id}", response_model=AgentDetailResponse)
async def get_agent_detail(
    agent_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取 Agent 详细信息

    Args:
        agent_id: Agent ID
        current_user: 当前用户
    """
    try:
        agent = agent_discovery_registry.get_agent(agent_id)

        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent 不存在: {agent_id}")

        return {
            "agent_id": agent.agent_id,
            "agent_name": agent.agent_name,
            "agent_type": agent.agent_type.value,
            "specialty": agent.specialty,
            "description": agent.description,
            "enabled": agent.enabled,
            "capabilities": agent.capabilities,
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "location": t.location.value,
                    "category": t.category,
                    "tags": t.tags,
                    "parameters": t.parameters,
                    "is_async": t.is_async,
                    "enabled": t.enabled
                }
                for t in agent.tools
            ],
            "tool_summary": agent.get_tool_count_summary(),
            "created_at": agent.created_at.isoformat(),
            "last_updated": agent.last_updated.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Agent 详情失败: {str(e)}")


@router.get("/tools", response_model=List[ToolSummaryResponse])
async def list_tools(
    location: Optional[str] = None,
    agent_id: Optional[str] = None,
    enabled_only: bool = True,
    current_user: User = Depends(deps.get_current_user)
):
    """
    列出所有工具

    Args:
        location: 工具位置过滤 (local/cloud/mcp)
        agent_id: Agent ID 过滤
        enabled_only: 仅返回已启用的工具
        current_user: 当前用户
    """
    try:
        loc_filter = ToolLocation(location) if location else None
        tools = agent_discovery_registry.list_all_tools(
            location=loc_filter,
            enabled_only=enabled_only
        )

        if agent_id:
            agent = agent_discovery_registry.get_agent(agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail=f"Agent 不存在: {agent_id}")
            tools = [t for t in tools if any(tool.name == t.name for tool in agent.tools)]

        result = []
        for tool in tools:
            agent_info = agent_discovery_registry.get_agent_by_tool(tool.name)
            result.append({
                "name": tool.name,
                "description": tool.description,
                "location": tool.location.value,
                "category": tool.category,
                "tags": tool.tags,
                "agent_id": agent_info.agent_id if agent_info else "unknown",
                "agent_name": agent_info.agent_name if agent_info else "Unknown"
            })

        return result
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的工具位置: {location}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"列出工具失败: {str(e)}")


@router.get("/tools/by-location")
async def get_tools_by_location(
    current_user: User = Depends(deps.get_current_user)
):
    """
    按位置分类获取工具

    返回按 local/cloud/mcp 分类的工具列表
    """
    try:
        local_tools = agent_discovery_registry.list_all_tools(location=ToolLocation.LOCAL)
        cloud_tools = agent_discovery_registry.list_all_tools(location=ToolLocation.CLOUD)
        mcp_tools = agent_discovery_registry.list_all_tools(location=ToolLocation.MCP)

        def format_tools(tools):
            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "category": t.category,
                    "tags": t.tags,
                    "agent_name": agent_discovery_registry.get_agent_by_tool(t.name).agent_name if agent_discovery_registry.get_agent_by_tool(t.name) else "Unknown"
                }
                for t in tools
            ]

        return {
            "local": {
                "count": len(local_tools),
                "tools": format_tools(local_tools)
            },
            "cloud": {
                "count": len(cloud_tools),
                "tools": format_tools(cloud_tools)
            },
            "mcp": {
                "count": len(mcp_tools),
                "tools": format_tools(mcp_tools)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取工具分类失败: {str(e)}")


@router.get("/traces/{session_id}")
async def get_session_traces(
    session_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取某个会话的所有 Agent 追踪记录

    Args:
        session_id: 会话 ID
        current_user: 当前用户
    """
    try:
        traces = await agent_tracer.get_session_traces(session_id)

        return {
            "session_id": session_id,
            "total_traces": len(traces),
            "traces": traces
        }
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询追踪记录失败: {str(e)}")


@router.get("/traces/{trace_id}/steps")
async def get_trace_steps(
    trace_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    获取某次追踪的详细步骤

    Args:
        trace_id: 追踪 ID
        current_user: 当前用户
    """
    try:
        trace_data = await agent_tracer.get_trace_with_steps(
            trace_id=trace_id,
            user_id=str(current_user.id),
            tenant_id=tenant_context["tenant_id"],
        )

        if not trace_data:
            raise HTTPException(status_code=404, detail="追踪记录不存在")

        return trace_data
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询追踪步骤失败: {str(e)}")


@router.get("/traces/{trace_id}/visualization")
async def get_trace_visualization(
    trace_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    获取追踪的可视化数据（用于前端绘制流程图）

    Args:
        trace_id: 追踪 ID
        current_user: 当前用户
    """
    try:
        trace_data = await agent_tracer.get_trace_with_steps(
            trace_id=trace_id,
            user_id=str(current_user.id),
            tenant_id=tenant_context["tenant_id"],
        )

        if not trace_data:
            raise HTTPException(status_code=404, detail="追踪记录不存在")

        nodes = []
        edges = []

        steps = trace_data.get("steps", [])

        for i, step in enumerate(steps):
            node = {
                "id": f"step_{i}",
                "type": step["step_type"],
                "label": _get_step_label(step["step_type"]),
                "content": step["content"][:100] + "..." if len(step["content"]) > 100 else step["content"],
                "tool": step.get("tool_name"),
                "duration": step.get("tool_duration"),
                "confidence": step.get("confidence")
            }
            nodes.append(node)

            if i < len(steps) - 1:
                edge = {
                    "from": f"step_{i}",
                    "to": f"step_{i+1}",
                    "source": f"step_{i}",
                    "target": f"step_{i+1}",
                    "label": f"{step.get('tool_duration', 0):.0f}ms" if step.get("tool_duration") else ""
                }
                edges.append(edge)

        return {
            "trace_id": trace_id,
            "nodes": nodes,
            "edges": edges,
            "summary": {
                "total_steps": trace_data.get("total_iterations", 0),
                "total_time": trace_data.get("total_time", 0),
                "tool_calls": trace_data.get("tool_calls_count", 0),
                "status": trace_data.get("status", "unknown")
            }
        }
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成可视化数据失败: {str(e)}")


@router.get("/traces")
async def list_recent_traces(
    limit: int = 50,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    获取当前用户/租户的追踪记录列表

    Args:
        limit: 返回的记录数量限制，默认50
        current_user: 当前用户
        tenant_context: 租户上下文
    """
    try:
        user_id = str(current_user.id)
        tenant_id = tenant_context['tenant_id']
        
        traces = await agent_tracer.get_recent_traces(
            user_id=user_id,
            tenant_id=tenant_id,
            limit=limit
        )

        return {
            "total": len(traces),
            "traces": traces
        }
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取追踪记录列表失败: {str(e)}")


@router.get("/traces/{trace_id}")
async def get_trace_detail(
    trace_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    获取单条追踪记录的详细信息（仅限本人）

    Args:
        trace_id: 追踪 ID
        current_user: 当前用户
    """
    try:
        user_id = str(current_user.id)
        
        trace_data = await agent_tracer.get_trace_with_steps(
            trace_id=trace_id,
            user_id=user_id,
            tenant_id=tenant_context["tenant_id"],
        )

        if not trace_data:
            raise HTTPException(status_code=404, detail="追踪记录不存在或无权访问")

        return trace_data
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取追踪详情失败: {str(e)}")


def _get_step_label(step_type: str) -> str:
    """获取步骤类型的显示标签"""
    labels = {
        "thought": "💭 思考",
        "action": "🔧 行动",
        "observation": "👁️ 观察",
        "final_answer": "✅ 答案"
    }
    return labels.get(step_type, step_type.upper())
