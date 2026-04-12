# app/api/v1/endpoints/tool_trace.py

"""
工具调用追踪 API 接口
"""

from fastapi import APIRouter, Depends, HTTPException
from app.api import deps
from app.models.user import User
from app.services.tool_call_tracer import tool_call_tracer

router = APIRouter()


@router.get("/tool_calls/{trace_id}")
async def get_tool_calls(
    trace_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """获取某次追踪的所有工具调用"""
    try:
        calls = await tool_call_tracer.get_trace_calls(trace_id)
        return {
            "trace_id": trace_id,
            "total_calls": len(calls),
            "calls": calls
        }
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tool_calls/{trace_id}/chain")
async def get_tool_call_chain(
    trace_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """获取工具调用链（树状结构）"""
    try:
        chain_data = await tool_call_tracer.build_call_chain(trace_id)
        return chain_data
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tool_stats")
async def get_tool_statistics(
    days: int = 7,
    current_user: User = Depends(deps.get_current_user)
):
    """获取工具使用统计"""
    try:
        stats = await tool_call_tracer.get_tool_statistics(days)
        return {
            "period": f"最近 {days} 天",
            "tools": stats
        }
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
