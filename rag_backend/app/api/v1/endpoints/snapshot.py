"""
会话快照 API

提供会话快照的创建、查询、恢复、对比等功能
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.services.snapshot_service import snapshot_service, SnapshotType
from app.api import deps
from app.models.user import User

router = APIRouter(prefix="/snapshots", tags=["Session Snapshots"])


class CreateSnapshotRequest(BaseModel):
    """创建快照请求"""
    session_id: str = Field(..., description="会话ID")
    snapshot_type: SnapshotType = Field(SnapshotType.MANUAL, description="快照类型")
    title: Optional[str] = Field(None, description="快照标题")
    metadata: Optional[Dict[str, Any]] = Field(None, description="额外元数据")


class RestoreSnapshotRequest(BaseModel):
    """恢复快照请求"""
    target_session_id: Optional[str] = Field(None, description="目标会话ID，不传则创建新会话")
    merge: bool = Field(False, description="是否合并到现有会话")


class CompareSnapshotsRequest(BaseModel):
    """对比快照请求"""
    snapshot_id1: str = Field(..., description="第一个快照ID")
    snapshot_id2: str = Field(..., description="第二个快照ID")


@router.post("/", response_model=Dict[str, Any])
async def create_snapshot(
    request: CreateSnapshotRequest,
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    创建会话快照
    
    Args:
        request: 创建请求
        
    Returns:
        Dict: 快照信息
    """
    snapshot = await snapshot_service.create_snapshot(
        session_id=request.session_id,
        snapshot_type=request.snapshot_type,
        title=request.title,
        metadata={
            **(request.metadata or {}),
            "user_id": str(current_user.id),
        }
    )
    
    return snapshot.to_dict()


@router.get("/", response_model=List[Dict[str, Any]])
async def list_snapshots(
    session_id: Optional[str] = Query(None, description="按会话ID过滤"),
    snapshot_type: Optional[SnapshotType] = Query(None, description="按类型过滤"),
    include_expired: bool = Query(False, description="是否包含已过期的"),
    current_user: User = Depends(deps.get_current_user)
) -> List[Dict[str, Any]]:
    """
    列出快照
    
    Args:
        session_id: 按会话ID过滤
        snapshot_type: 按类型过滤
        include_expired: 是否包含已过期的
        
    Returns:
        List[Dict]: 快照列表
    """
    return await snapshot_service.list_snapshots(
        session_id=session_id,
        snapshot_type=snapshot_type,
        include_expired=include_expired,
    )


@router.get("/{snapshot_id}", response_model=Dict[str, Any])
async def get_snapshot(
    snapshot_id: str,
    include_messages: bool = Query(False, description="是否包含消息内容"),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    获取快照详情
    
    Args:
        snapshot_id: 快照ID
        include_messages: 是否包含消息内容
        
    Returns:
        Dict: 快照详情
    """
    snapshot = await snapshot_service.get_snapshot(snapshot_id)
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="快照不存在或已过期")
    
    if include_messages:
        return snapshot.to_full_dict()
    else:
        return snapshot.to_dict()


@router.delete("/{snapshot_id}")
async def delete_snapshot(
    snapshot_id: str,
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, str]:
    """
    删除快照
    
    Args:
        snapshot_id: 快照ID
        
    Returns:
        Dict: 操作结果
    """
    success = await snapshot_service.delete_snapshot(snapshot_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="快照不存在")
    
    return {
        "status": "success",
        "message": f"快照 {snapshot_id} 已删除",
        "snapshot_id": snapshot_id,
    }


@router.post("/{snapshot_id}/restore")
async def restore_snapshot(
    snapshot_id: str,
    request: RestoreSnapshotRequest,
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    恢复快照
    
    Args:
        snapshot_id: 快照ID
        request: 恢复请求
        
    Returns:
        Dict: 恢复结果
    """
    try:
        target_session_id, restored_messages = await snapshot_service.restore_snapshot(
            snapshot_id=snapshot_id,
            target_session_id=request.target_session_id,
            merge=request.merge,
        )
        
        return {
            "status": "success",
            "message": "快照已恢复",
            "snapshot_id": snapshot_id,
            "target_session_id": target_session_id,
            "restored_messages_count": len(restored_messages),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/compare")
async def compare_snapshots(
    request: CompareSnapshotsRequest,
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    对比两个快照
    
    Args:
        request: 对比请求
        
    Returns:
        Dict: 差异信息
    """
    try:
        diff = await snapshot_service.compare_snapshots(
            snapshot_id1=request.snapshot_id1,
            snapshot_id2=request.snapshot_id2,
        )
        
        return {
            "snapshot_id1": request.snapshot_id1,
            "snapshot_id2": request.snapshot_id2,
            "added_count": diff.added_count,
            "removed_count": diff.removed_count,
            "modified_count": diff.modified_count,
            "summary": diff.summary,
            "added_messages": diff.added_messages,
            "removed_messages": diff.removed_messages,
            "modified_messages": diff.modified_messages,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/cleanup")
async def cleanup_expired_snapshots(
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    清理过期的快照
    
    Returns:
        Dict: 清理结果
    """
    await snapshot_service.cleanup_expired()
    
    return {
        "status": "success",
        "message": "过期的快照已清理",
    }


@router.get("/stats")
async def get_snapshot_stats(
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    获取快照统计
    
    Returns:
        Dict: 统计信息
    """
    return snapshot_service.get_stats()
