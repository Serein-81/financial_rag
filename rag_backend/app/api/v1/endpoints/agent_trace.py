# app/api/v1/endpoints/agent_trace.py

"""
Agent 追踪 API 接口

提供查询 Agent 执行追踪的 REST API
"""

from fastapi import APIRouter, Depends, HTTPException
from app.api import deps
from app.models.user import User
from app.services.agent_tracer import agent_tracer

router = APIRouter()


def _step_to_event(step: dict) -> dict:
    event_type_map = {
        "thought": "thinking",
        "action": "tool_call",
        "observation": "tool_result",
        "final_answer": "response",
    }
    return {
        "timestamp": step.get("timestamp"),
        "event_type": event_type_map.get(step.get("step_type"), step.get("step_type", "response")),
        "content": step.get("content", ""),
        "metadata": {
            "step_number": step.get("step_number"),
            "step_type": step.get("step_type"),
            "tool_name": step.get("tool_name"),
            "tool_input": step.get("tool_input"),
            "tool_output": step.get("tool_output"),
            "tool_duration": step.get("tool_duration"),
            "confidence": step.get("confidence"),
        },
    }


def _trace_to_legacy(trace: dict) -> dict:
    steps = trace.get("steps", [])
    return {
        "trace_id": trace.get("trace_id"),
        "session_id": trace.get("session_id") or "",
        "query": trace.get("user_query") or trace.get("query") or "",
        "events": [_step_to_event(step) for step in steps],
        "total_time": trace.get("total_time") or 0,
        "created_at": trace.get("created_at"),
        "status": trace.get("status"),
        "agent_type": trace.get("agent_type"),
        "user_query": trace.get("user_query"),
        "final_answer": trace.get("final_answer"),
        "steps": steps,
        "total_iterations": trace.get("total_iterations"),
        "tool_calls_count": trace.get("tool_calls_count"),
    }


@router.get("/traces/{session_id}")
async def get_session_traces(
    session_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    获取某个会话的 Agent 追踪记录（仅限当前用户）
    
    Args:
        session_id: 会话 ID
        current_user: 当前用户
        tenant_context: 租户上下文
        
    Returns:
        追踪记录列表
    """
    try:
        user_id = str(current_user.id)
        tenant_id = tenant_context['tenant_id']
        
        traces = await agent_tracer.get_session_traces(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id
        )
        
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


@router.get("/session/{session_id}")
async def get_session_traces_legacy(
    session_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """Backward compatible session trace endpoint for older frontend clients."""
    response = await get_session_traces(session_id, current_user, tenant_context)
    return [_trace_to_legacy(trace) for trace in response.get("traces", [])]


@router.get("/traces/{trace_id}/steps")
async def get_trace_steps(
    trace_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    获取某次追踪的详细步骤（仅限本人）
    
    Args:
        trace_id: 追踪 ID
        current_user: 当前用户
        
    Returns:
        包含所有步骤的完整追踪信息
    """
    try:
        user_id = str(current_user.id)
        
        trace_data = await agent_tracer.get_trace_with_steps(
            trace_id=trace_id,
            user_id=user_id,
            tenant_id=tenant_context["tenant_id"]
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
        raise HTTPException(status_code=500, detail=f"查询追踪步骤失败: {str(e)}")


@router.get("/{trace_id}")
async def get_trace_legacy(
    trace_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """Backward compatible trace detail endpoint for older frontend clients."""
    trace_data = await get_trace_steps(trace_id, current_user, tenant_context)
    return _trace_to_legacy(trace_data)


@router.get("/traces/{trace_id}/visualization")
async def get_trace_visualization(
    trace_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    获取追踪的可视化数据（用于前端绘制流程图，仅限本人）
    
    Args:
        trace_id: 追踪 ID
        current_user: 当前用户
        
    Returns:
        可视化数据（节点和边）
    """
    try:
        user_id = str(current_user.id)
        
        trace_data = await agent_tracer.get_trace_with_steps(
            trace_id=trace_id,
            user_id=user_id,
            tenant_id=tenant_context["tenant_id"]
        )
        
        if not trace_data:
            raise HTTPException(status_code=404, detail="追踪记录不存在或无权访问")
        
        # 构建可视化节点和边
        nodes = []
        edges = []
        
        steps = trace_data.get("steps", [])
        
        for i, step in enumerate(steps):
            # 创建节点
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
            
            # 创建边（连接到下一个节点）
            if i < len(steps) - 1:
                edge = {
                    "from": f"step_{i}",
                    "to": f"step_{i+1}",
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


def _get_step_label(step_type: str) -> str:
    """获取步骤类型的显示标签"""
    labels = {
        "thought": "💭 思考",
        "action": "🔧 行动",
        "observation": "👁️ 观察",
        "final_answer": "✅ 答案"
    }
    return labels.get(step_type, step_type.upper())
