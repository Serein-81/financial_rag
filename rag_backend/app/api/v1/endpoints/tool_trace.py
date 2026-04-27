# app/api/v1/endpoints/tool_trace.py

"""
Tool trace API endpoints.

Keeps the existing /tool_calls/* routes and adds a session-level compatibility
route used by the older frontend page.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.api import deps
from app.models.user import User
from app.services.agent_tracer import agent_tracer
from app.services.tool_call_tracer import tool_call_tracer

router = APIRouter()


def _call_to_legacy(call: dict) -> dict:
    return {
        "tool_id": call.get("call_id"),
        "trace_id": call.get("trace_id"),
        "tool_name": call.get("tool_name"),
        "input": call.get("input_params") or {},
        "output": call.get("output_result"),
        "error": call.get("error_message"),
        "start_time": call.get("start_time"),
        "end_time": None,
        "duration": call.get("duration"),
        "status": call.get("status"),
        "tool_type": call.get("tool_type"),
    }


async def _ensure_trace_access(trace_id: str, current_user: User, tenant_context: dict):
    trace_data = await agent_tracer.get_trace_with_steps(
        trace_id=trace_id,
        user_id=str(current_user.id),
        tenant_id=tenant_context["tenant_id"],
    )
    if not trace_data:
        raise HTTPException(status_code=404, detail="追踪记录不存在或无权访问")
    return trace_data


@router.get("/tool_calls/{trace_id}")
async def get_tool_calls(
    trace_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
):
    """Get all tool calls for a trace after checking tenant/user access."""
    try:
        await _ensure_trace_access(trace_id, current_user, tenant_context)
        calls = await tool_call_tracer.get_trace_calls(trace_id)
        return {
            "trace_id": trace_id,
            "total_calls": len(calls),
            "calls": calls,
        }
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tool_calls/{trace_id}/chain")
async def get_tool_call_chain(
    trace_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
):
    """Get the nested tool call chain for a trace after checking access."""
    try:
        await _ensure_trace_access(trace_id, current_user, tenant_context)
        return await tool_call_tracer.build_call_chain(trace_id)
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_session_tool_traces(
    session_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
):
    """Backward compatible endpoint: return tool traces for every trace in a session."""
    try:
        traces = await agent_tracer.get_session_traces(
            session_id=session_id,
            user_id=str(current_user.id),
            tenant_id=tenant_context["tenant_id"],
        )

        calls = []
        for trace in traces:
            trace_calls = await tool_call_tracer.get_trace_calls(trace["trace_id"])
            for call in trace_calls:
                call["trace_id"] = trace["trace_id"]
                calls.append(_call_to_legacy(call))

        return {
            "session_id": session_id,
            "total": len(calls),
            "traces": calls,
        }
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tool_stats")
async def get_tool_statistics(
    days: int = 7,
    current_user: User = Depends(deps.get_current_user),
):
    """Get aggregate tool usage statistics."""
    try:
        stats = await tool_call_tracer.get_tool_statistics(days)
        return {
            "period": f"最近 {days} 天",
            "tools": stats,
        }
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
