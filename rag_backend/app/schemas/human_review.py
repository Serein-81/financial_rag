"""
人工审核相关 Pydantic Schemas

定义审核请求的请求/响应模型
"""

from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field,ConfigDict
from enum import Enum


class ReviewStatusEnum(str, Enum):
    """审核状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ReviewPriorityEnum(str, Enum):
    """审核优先级枚举"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ReviewTypeEnum(str, Enum):
    """审核类型枚举"""
    TAX = "tax"
    FINANCE = "finance"
    LEGAL = "legal"
    COMPLIANCE = "compliance"


class CommentTypeEnum(str, Enum):
    """评论类型枚举"""
    COMMENT = "comment"
    REPLY = "reply"
    APPROVAL = "approval"
    REJECTION = "rejection"
    MODIFICATION = "modification"


class ReviewRequestCreate(BaseModel):
    """创建审核请求"""
    task_id: Optional[str] = Field(None, description="关联的任务ID")
    title: Optional[str] = Field(None, max_length=200, description="审核标题")
    description: Optional[str] = Field(None, description="审核描述")
    review_type: ReviewTypeEnum = Field(ReviewTypeEnum.TAX, description="审核类型")
    priority: ReviewPriorityEnum = Field(ReviewPriorityEnum.NORMAL, description="优先级")
    trigger_reason: Optional[str] = Field(None, description="触发原因")
    trigger_details: Optional[Dict[str, Any]] = Field(None, description="触发详情")
    content: Optional[Dict[str, Any]] = Field(None, description="审核内容（AI分析结果等）")
    document_ids: Optional[List[str]] = Field(None, description="关联文档ID列表")


class ReviewRequestUpdate(BaseModel):
    """更新审核请求"""
    title: Optional[str] = Field(None, max_length=200, description="审核标题")
    description: Optional[str] = Field(None, description="审核描述")
    priority: Optional[ReviewPriorityEnum] = Field(None, description="优先级")
    assigned_to: Optional[str] = Field(None, description="分配给的用户ID")
    status: Optional[ReviewStatusEnum] = Field(None, description="状态")
    review_result: Optional[Dict[str, Any]] = Field(None, description="审核结果")
    review_comments: Optional[str] = Field(None, description="审核意见")


class ReviewResultSchema(BaseModel):
    """审核结果"""
    decision: str = Field(..., description="决定: approved, rejected, needs_modification")
    details: Optional[str] = Field(None, description="详情")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="置信度")


class ReviewRequestResponse(BaseModel):
    """审核请求响应"""
    id: str
    task_id: Optional[str] = None
    tenant_id: str
    user_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    review_type: ReviewTypeEnum
    priority: ReviewPriorityEnum
    status: ReviewStatusEnum
    trigger_reason: Optional[str] = None
    trigger_details: Optional[Dict[str, Any]] = None
    content: Optional[Dict[str, Any]] = None
    document_ids: Optional[List[str]] = None
    assigned_to: Optional[str] = None
    assigned_at: Optional[datetime] = None
    review_result: Optional[Dict[str, Any]] = None
    review_comments: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    sla_deadline: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_overdue: bool = False
    age_hours: float = 0

    class Config:
        from_attributes = True


class ReviewRequestListResponse(BaseModel):
    """审核请求列表响应"""
    items: List[ReviewRequestResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ReviewRequestFilter(BaseModel):
    """审核请求过滤条件"""
    status: Optional[ReviewStatusEnum] = None
    priority: Optional[ReviewPriorityEnum] = None
    review_type: Optional[ReviewTypeEnum] = None
    assigned_to_me: Optional[bool] = None
    overdue_only: Optional[bool] = None
    keyword: Optional[str] = None
    page: int = 1
    page_size: int = 20


class PriorityBreakdownSchema(BaseModel):
    """优先级分布"""
    urgent: int = 0
    high: int = 0
    normal: int = 0
    low: int = 0


class ReviewStatisticsResponse(BaseModel):
    """审核统计响应"""
    pending_count: int = 0
    in_progress_count: int = 0
    completed_today: int = 0
    completed_this_week: int = 0
    overdue_count: int = 0
    avg_processing_hours: float = 0
    priority_breakdown: PriorityBreakdownSchema = PriorityBreakdownSchema()


class ReviewCommentRequest(BaseModel):
    """添加评论请求"""
    content: str = Field(..., min_length=1, description="评论内容")
    comment_type: CommentTypeEnum = Field(CommentTypeEnum.COMMENT, description="评论类型")
    related_entity_type: Optional[str] = Field(None, description="关联实体类型")
    related_entity_id: Optional[str] = Field(None, description="关联实体ID")
    attachments: Optional[List[Dict[str, Any]]] = Field(None, description="附件")


class ReviewCommentResponse(BaseModel):
    """评论响应"""
    id: str
    review_request_id: str
    user_id: str
    user_name: Optional[str] = None
    content: str
    comment_type: str
    attachments: Optional[List[Dict[str, Any]]] = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class ReviewActionRequest(BaseModel):
    """记录操作请求"""
    action: str = Field(..., description="操作类型")
    details: Optional[Dict[str, Any]] = Field(None, description="操作详情")


class ReviewActionResponse(BaseModel):
    """操作历史响应"""
    id: str
    review_request_id: str
    user_id: str
    user_name: Optional[str] = None
    action: str
    action_details: Optional[Dict[str, Any]] = None
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class ReviewRequestAction(BaseModel):
    """审核操作记录（内部使用）"""
    id: str
    review_request_id: str
    user_id: str
    action: str
    action_details: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class BatchUpdateStatusRequest(BaseModel):
    """批量更新状态请求"""
    ids: List[str] = Field(..., min_items=1, description="审核请求ID列表")
    status: ReviewStatusEnum = Field(..., description="目标状态")


class TransferReviewRequest(BaseModel):
    """转交审核请求"""
    target_user_id: str = Field(..., description="目标用户ID")
    reason: Optional[str] = Field(None, description="转交原因")


class ClaimReviewRequest(BaseModel):
    """认领审核请求"""
    pass


class ExportReviewRequest(BaseModel):
    """导出审核请求"""
    format: str = Field("csv", description="导出格式: csv, excel")
    filter: Optional[ReviewRequestFilter] = None
