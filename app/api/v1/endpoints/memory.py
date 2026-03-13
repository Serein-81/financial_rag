# app/api/v1/endpoints/memory.py

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.api import deps
from app.models.user import User
from app.memory_system.memory_manager import MemoryManager

router = APIRouter()


@router.post("/search")
async def search_current_conversation(
    keywords: List[str],
    session_id: str,
    role: Optional[str] = Query(None, description="角色过滤 (user/assistant/system)"),
    importance_min: Optional[float] = Query(None, ge=0.0, le=1.0, description="最小重要性"),
    top_k: int = Query(10, ge=1, le=50, description="返回结果数量"),
    current_user: User = Depends(deps.get_current_user)
):
    """
    在当前对话中搜索记忆
    
    Args:
        keywords: 关键词列表
        session_id: 会话ID
        role: 角色过滤
        importance_min: 最小重要性
        top_k: 返回结果数量
    """
    try:
        # 创建记忆管理器
        memory_manager = MemoryManager(session_id, str(current_user.id))
        
        # 搜索记忆
        results = await memory_manager.search_current_conversation(
            keywords=keywords,
            role=role,
            importance_min=importance_min,
            top_k=top_k
        )
        
        # 格式化结果
        formatted_results = []
        for memory in results:
            formatted_results.append({
                "id": memory.id,
                "content": memory.content,
                "role": memory.role,
                "timestamp": memory.timestamp.isoformat(),
                "importance": memory.importance,
                "access_count": memory.access_count,
                "decay_factor": memory.decay_factor,
                "metadata": memory.metadata
            })
        
        return {
            "success": True,
            "results": formatted_results,
            "total": len(formatted_results),
            "keywords": keywords,
            "session_id": session_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"记忆搜索失败: {str(e)}")


@router.get("/statistics/{session_id}")
async def get_memory_statistics(
    session_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取记忆系统统计信息
    
    Args:
        session_id: 会话ID
    """
    try:
        # 创建记忆管理器
        memory_manager = MemoryManager(session_id, str(current_user.id))
        
        # 获取统计信息
        stats = await memory_manager.get_memory_statistics()
        
        return {
            "success": True,
            "statistics": stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/summary/{session_id}")
async def export_session_summary(
    session_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """
    导出会话摘要
    
    Args:
        session_id: 会话ID
    """
    try:
        # 创建记忆管理器
        memory_manager = MemoryManager(session_id, str(current_user.id))
        
        # 导出摘要
        summary = await memory_manager.export_session_summary()
        
        return {
            "success": True,
            "summary": summary
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出摘要失败: {str(e)}")