"""
Agent 任务状态 Schema

用于前端状态水合 (Hydration) API
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class SpecialistProgress(BaseModel):
    """专家进度"""
    specialist_type: str
    status: str  # pending, running, completed, failed
    confidence: Optional[float] = None
    completed_at: Optional[str] = None


class CheckpointInfo(BaseModel):
    """检查点信息"""
    checkpoint_id: str
    parent_checkpoint_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TaskStatusResponse(BaseModel):
    """任务状态响应 (用于前端水合)"""
    task_id: str
    thread_id: str
    status: str  # pending, running, completed, failed, cancelled, interrupted
    
    task_type: str
    task_name: Optional[str] = None
    
    current_node: Optional[str] = None
    progress_percent: int = 0
    progress_message: Optional[str] = None
    
    specialist_progress: Optional[Dict[str, Dict[str, Any]]] = None
    
    user_query: Optional[str] = None
    final_response: Optional[str] = None
    
    checkpoints: Optional[List[CheckpointInfo]] = None
    latest_checkpoint_id: Optional[str] = None
    
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time_ms: Optional[float] = None
    
    error_message: Optional[str] = None
    retry_count: int = 0
    
    can_resume: bool = False
    needs_hydration: bool = True
    
    needs_clarification: bool = False
    clarification_request: Optional[Dict[str, Any]] = None
    intent_analysis: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "lgwf_abc123def456",
                "thread_id": "session_xyz789",
                "status": "running",
                "task_type": "langgraph_workflow",
                "current_node": "finance_specialist",
                "progress_percent": 40,
                "progress_message": "正在执行 finance 专家...",
                "specialist_progress": {
                    "finance": {"completed": False, "confidence": 0.85}
                },
                "created_at": "2025-04-23T10:00:00Z",
                "can_resume": True,
                "needs_hydration": True
            }
        }


class TaskSubmitRequest(BaseModel):
    """任务提交请求"""
    user_query: str
    thread_id: Optional[str] = None
    priority: int = Field(default=5, ge=1, le=10)
    enable_reflection: bool = True
    max_specialists: int = Field(default=3, ge=1, le=5)
    context: Optional[Dict[str, Any]] = None


class TaskSubmitResponse(BaseModel):
    """任务提交响应"""
    task_id: str
    thread_id: str
    status: str = "submitted"
    message: str
    estimated_completion_seconds: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "lgwf_abc123def456",
                "thread_id": "session_xyz789",
                "status": "submitted",
                "message": "任务已提交到队列，请使用 GET /status/{thread_id} 查询进度"
            }
        }


class ThreadHydrationResponse(BaseModel):
    """线程水合响应 (前端切回页面时使用)"""
    thread_id: str
    needs_hydration: bool
    
    task_info: Optional[TaskStatusResponse] = None
    
    last_checkpoint: Optional[CheckpointInfo] = None
    checkpoint_history: List[CheckpointInfo] = []
    
    recovered_state: Optional[Dict[str, Any]] = None
    
    recommendations: List[str] = []
    
    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": "session_xyz789",
                "needs_hydration": True,
                "task_info": {
                    "task_id": "lgwf_abc123def456",
                    "status": "running",
                    "current_node": "finance_specialist",
                    "progress_percent": 40
                },
                "recommendations": [
                    "任务正在后台执行，可以继续等待",
                    "或刷新页面查看最新进度"
                ]
            }
        }


class TaskEventResponse(BaseModel):
    """任务事件响应"""
    task_id: str
    events: List[Dict[str, Any]]
    total_count: int


class WorkflowSnapshot(BaseModel):
    """工作流快照"""
    thread_id: str
    checkpoint_id: str
    node_name: str
    state_summary: Dict[str, Any]
    timestamp: str
    is_recovery_point: bool = False