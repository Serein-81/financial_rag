"""
人工介入（Human-in-the-Loop）模块

提供人工审核队列和状态管理功能
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class ReviewStatus(str, Enum):
    """审核状态"""
    PENDING = "pending"  # 待审核
    IN_PROGRESS = "in_progress"  # 审核中
    APPROVED = "approved"  # 已通过
    REJECTED = "rejected"  # 已拒绝
    ESCALATED = "escalated"  # 已升级
    EXPIRED = "expired"  # 已过期


class ReviewPriority(str, Enum):
    """审核优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ReviewTrigger(str, Enum):
    """触发审核的原因"""
    LOW_CONFIDENCE = "low_confidence"  # 置信度过低
    MISSING_MANDATORY_FIELDS = "missing_mandatory_fields"  # 关键字段缺失
    AUDIT_FAILED = "audit_failed"  # 审计失败
    ANOMALY_DETECTED = "anomaly_detected"  # 检测到异常
    SECURITY_FLAG = "security_flag"  # 安全标记
    TRIAGE_UNCERTAIN = "triage_uncertain"  # 门卫无法确定
    MANUAL_REQUEST = "manual_request"  # 手动请求


@dataclass
class ReviewRequest:
    """审核请求"""
    id: str
    task_id: str
    tenant_id: str
    user_id: str
    review_type: str
    priority: ReviewPriority
    trigger_reason: ReviewTrigger
    description: str
    content: Dict[str, Any]
    original_document: Optional[str] = None
    anonymized_content: Optional[str] = None
    pii_mapping: Optional[Dict[str, str]] = None
    status: ReviewStatus = ReviewStatus.PENDING
    assigned_reviewer: Optional[str] = None
    review_notes: Optional[List[str]] = None
    reviewer_decision: Optional[str] = None
    reviewer_feedback: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "review_type": self.review_type,
            "priority": self.priority.value if isinstance(self.priority, ReviewPriority) else self.priority,
            "trigger_reason": self.trigger_reason.value if isinstance(self.trigger_reason, ReviewTrigger) else self.trigger_reason,
            "description": self.description,
            "content": self.content,
            "original_document": self.original_document,
            "anonymized_content": self.anonymized_content,
            "pii_mapping": self.pii_mapping,
            "status": self.status.value if isinstance(self.status, ReviewStatus) else self.status,
            "assigned_reviewer": self.assigned_reviewer,
            "review_notes": self.review_notes,
            "reviewer_decision": self.reviewer_decision,
            "reviewer_feedback": self.reviewer_feedback,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }
    
    def update_status(self, new_status: ReviewStatus, reviewer_feedback: Optional[str] = None):
        """更新状态"""
        self.status = new_status
        self.updated_at = datetime.utcnow()
        if reviewer_feedback:
            self.reviewer_feedback = reviewer_feedback


class HumanReviewQueue:
    """
    人工审核队列管理器
    
    负责：
    1. 创建审核请求
    2. 分配审核任务
    3. 跟踪审核状态
    4. 处理审核结果
    """
    
    def __init__(self):
        """初始化审核队列"""
        self._queue: Dict[str, ReviewRequest] = {}
        self._pending_by_tenant: Dict[str, List[str]] = {}
        self._assigned_by_reviewer: Dict[str, List[str]] = {}
        
        print("📋 [人工审核队列] 初始化完成")
    
    def create_review_request(
        self,
        task_id: str,
        tenant_id: str,
        user_id: str,
        review_type: str,
        trigger_reason: ReviewTrigger,
        description: str,
        content: Dict[str, Any],
        priority: ReviewPriority = ReviewPriority.NORMAL,
        original_document: Optional[str] = None,
        anonymized_content: Optional[str] = None,
        pii_mapping: Optional[Dict[str, str]] = None
    ) -> ReviewRequest:
        """
        创建审核请求
        
        Args:
            task_id: 任务ID
            tenant_id: 租户ID
            user_id: 用户ID
            review_type: 审核类型
            trigger_reason: 触发原因
            description: 描述
            content: 内容
            priority: 优先级
            original_document: 原始文档
            anonymized_content: 脱敏后的内容
            pii_mapping: PII映射
            
        Returns:
            审核请求对象
        """
        request_id = f"review_{uuid.uuid4().hex[:12]}"
        
        request = ReviewRequest(
            id=request_id,
            task_id=task_id,
            tenant_id=tenant_id,
            user_id=user_id,
            review_type=review_type,
            priority=priority,
            trigger_reason=trigger_reason,
            description=description,
            content=content,
            original_document=original_document,
            anonymized_content=anonymized_content,
            pii_mapping=pii_mapping
        )
        
        self._queue[request_id] = request
        
        if tenant_id not in self._pending_by_tenant:
            self._pending_by_tenant[tenant_id] = []
        self._pending_by_tenant[tenant_id].append(request_id)
        
        print(f"📋 [人工审核队列] 创建审核请求: {request_id}")
        print(f"   - 任务ID: {task_id}")
        print(f"   - 触发原因: {trigger_reason.value}")
        print(f"   - 优先级: {priority.value}")
        
        return request
    
    def get_pending_reviews(
        self,
        tenant_id: Optional[str] = None,
        reviewer_id: Optional[str] = None
    ) -> List[ReviewRequest]:
        """
        获取待审核列表
        
        Args:
            tenant_id: 租户ID（可选）
            reviewer_id: 审核员ID（可选）
            
        Returns:
            审核请求列表
        """
        if reviewer_id:
            assigned_ids = self._assigned_by_reviewer.get(reviewer_id, [])
            return [self._queue[rid] for rid in assigned_ids if rid in self._queue]
        
        if tenant_id:
            pending_ids = self._pending_by_tenant.get(tenant_id, [])
            return [self._queue[rid] for rid in pending_ids if rid in self._queue]
        
        return [
            req for req in self._queue.values()
            if req.status == ReviewStatus.PENDING
        ]
    
    def assign_reviewer(
        self,
        request_id: str,
        reviewer_id: str
    ) -> bool:
        """
        分配审核员
        
        Args:
            request_id: 审核请求ID
            reviewer_id: 审核员ID
            
        Returns:
            是否成功
        """
        if request_id not in self._queue:
            print(f"❌ [人工审核队列] 审核请求不存在: {request_id}")
            return False
        
        request = self._queue[request_id]
        request.assigned_reviewer = reviewer_id
        request.status = ReviewStatus.IN_PROGRESS
        request.updated_at = datetime.utcnow()
        
        if reviewer_id not in self._assigned_by_reviewer:
            self._assigned_by_reviewer[reviewer_id] = []
        self._assigned_by_reviewer[reviewer_id].append(request_id)
        
        if request_id in self._pending_by_tenant.get(request.tenant_id, []):
            self._pending_by_tenant[request.tenant_id].remove(request_id)
        
        print(f"👤 [人工审核队列] 分配审核员: {request_id} -> {reviewer_id}")
        return True
    
    def complete_review(
        self,
        request_id: str,
        decision: str,
        feedback: Optional[str] = None,
        notes: Optional[List[str]] = None
    ) -> bool:
        """
        完成审核
        
        Args:
            request_id: 审核请求ID
            decision: 决定（approved/rejected/escalated）
            feedback: 反馈
            notes: 备注
            
        Returns:
            是否成功
        """
        if request_id not in self._queue:
            print(f"❌ [人工审核队列] 审核请求不存在: {request_id}")
            return False
        
        request = self._queue[request_id]
        
        if decision == "approved":
            request.status = ReviewStatus.APPROVED
        elif decision == "rejected":
            request.status = ReviewStatus.REJECTED
        elif decision == "escalated":
            request.status = ReviewStatus.ESCALATED
        else:
            print(f"❌ [人工审核队列] 无效的决定: {decision}")
            return False
        
        request.reviewer_decision = decision
        request.reviewer_feedback = feedback
        request.updated_at = datetime.utcnow()
        
        if notes:
            request.review_notes = notes
        
        if request.assigned_reviewer:
            assigned_list = self._assigned_by_reviewer.get(request.assigned_reviewer, [])
            if request_id in assigned_list:
                assigned_list.remove(request_id)
        
        print(f"✅ [人工审核队列] 审核完成: {request_id} -> {decision}")
        return True
    
    def get_review_by_id(self, request_id: str) -> Optional[ReviewRequest]:
        """根据ID获取审核请求"""
        return self._queue.get(request_id)
    
    def get_stats(self, tenant_id: Optional[str] = None) -> Dict[str, int]:
        """获取统计信息"""
        requests = self.get_pending_reviews(tenant_id) if tenant_id else list(self._queue.values())
        
        stats = {
            "total": len(self._queue),
            "pending": 0,
            "in_progress": 0,
            "approved": 0,
            "rejected": 0,
            "escalated": 0,
            "urgent": 0
        }
        
        for req in self._queue.values():
            if tenant_id and req.tenant_id != tenant_id:
                continue
            
            status = req.status.value
            if status in stats:
                stats[status] += 1
            
            if req.priority == ReviewPriority.URGENT:
                stats["urgent"] += 1
        
        return stats


human_review_queue = HumanReviewQueue()


def create_review_request(
    task_id: str,
    tenant_id: str,
    user_id: str,
    review_type: str,
    trigger_reason: ReviewTrigger,
    description: str,
    content: Dict[str, Any],
    priority: ReviewPriority = ReviewPriority.NORMAL,
    original_document: Optional[str] = None,
    anonymized_content: Optional[str] = None,
    pii_mapping: Optional[Dict[str, str]] = None
) -> ReviewRequest:
    """
    便捷函数：创建审核请求
    """
    return human_review_queue.create_review_request(
        task_id=task_id,
        tenant_id=tenant_id,
        user_id=user_id,
        review_type=review_type,
        trigger_reason=trigger_reason,
        description=description,
        content=content,
        priority=priority,
        original_document=original_document,
        anonymized_content=anonymized_content,
        pii_mapping=pii_mapping
    )


def get_pending_reviews(
    tenant_id: Optional[str] = None,
    reviewer_id: Optional[str] = None
) -> List[ReviewRequest]:
    """
    便捷函数：获取待审核列表
    """
    return human_review_queue.get_pending_reviews(tenant_id, reviewer_id)


def assign_reviewer(request_id: str, reviewer_id: str) -> bool:
    """
    便捷函数：分配审核员
    """
    return human_review_queue.assign_reviewer(request_id, reviewer_id)


def complete_review(
    request_id: str,
    decision: str,
    feedback: Optional[str] = None,
    notes: Optional[List[str]] = None
) -> bool:
    """
    便捷函数：完成审核
    """
    return human_review_queue.complete_review(request_id, decision, feedback, notes)


def get_review_stats(tenant_id: Optional[str] = None) -> Dict[str, int]:
    """
    便捷函数：获取统计信息
    """
    return human_review_queue.get_stats(tenant_id)
