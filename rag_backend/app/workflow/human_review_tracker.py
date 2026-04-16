# app/workflow/human_review_tracker.py

"""
人工审核追踪模块

增强人工审核节点的可观测性：
- 审核生命周期追踪
- 审核时效性监控
- 审核结果与工作流的关联
- 审核操作的完整审计日志
"""

import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ReviewAction(str, Enum):
    """审核操作类型"""
    ASSIGN = "assign"
    START_REVIEW = "start_review"
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    ESCALATE = "escalate"
    COMMENT = "comment"
    COMPLETE = "complete"


class ReviewPriority(str, Enum):
    """审核优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ReviewTrackingRecord:
    """审核追踪记录"""
    review_request_id: uuid.UUID
    workflow_trace_id: Optional[uuid.UUID]
    node_execution_id: Optional[uuid.UUID]
    
    workflow_type: str
    node_name: str
    
    review_type: str
    priority: ReviewPriority
    
    trigger_reason: str
    trigger_details: Optional[Dict[str, Any]] = None
    
    status: str = "pending"
    assigned_to: Optional[uuid.UUID] = None
    assigned_at: Optional[datetime] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    sla_deadline: Optional[datetime] = None
    sla_breached: bool = False
    
    actions: List[Dict[str, Any]] = field(default_factory=list)


class HumanReviewTracker:
    """
    人工审核追踪器
    
    提供完整的人工审核可观测性，与WorkflowMonitor紧密集成
    """
    
    SLA_HOURS = {
        ReviewPriority.URGENT: 1,
        ReviewPriority.HIGH: 4,
        ReviewPriority.NORMAL: 24,
        ReviewPriority.LOW: 72,
    }
    
    def __init__(self, db_session: Session):
        """
        初始化人工审核追踪器
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session
    
    def create_review_tracking(
        self,
        review_request_id: uuid.UUID,
        workflow_trace_id: Optional[uuid.UUID],
        node_execution_id: Optional[uuid.UUID],
        workflow_type: str,
        node_name: str,
        review_type: str,
        priority: ReviewPriority = ReviewPriority.NORMAL,
        trigger_reason: str = "",
        trigger_details: Optional[Dict[str, Any]] = None,
        content_for_review: Optional[Dict[str, Any]] = None
    ) -> ReviewTrackingRecord:
        """
        创建审核追踪记录
        
        Args:
            review_request_id: 审核请求ID
            workflow_trace_id: 工作流追踪ID
            node_execution_id: 节点执行ID
            workflow_type: 工作流类型
            node_name: 节点名称
            review_type: 审核类型
            priority: 审核优先级
            trigger_reason: 触发原因
            trigger_details: 触发详情
            content_for_review: 审核内容
            
        Returns:
            ReviewTrackingRecord: 审核追踪记录
        """
        try:
            
            sla_hours = self.SLA_HOURS.get(priority, 24)
            sla_deadline = datetime.utcnow() + timedelta(hours=sla_hours)
            
            tracking_record = ReviewTrackingRecord(
                review_request_id=review_request_id,
                workflow_trace_id=workflow_trace_id,
                node_execution_id=node_execution_id,
                workflow_type=workflow_type,
                node_name=node_name,
                review_type=review_type,
                priority=priority,
                trigger_reason=trigger_reason,
                trigger_details=trigger_details,
                sla_deadline=sla_deadline,
                status="pending"
            )
            
            if content_for_review:
                self._update_review_request_content(
                    review_request_id,
                    content_for_review,
                    workflow_trace_id,
                    node_execution_id
                )
            
            logger.info(
                f"人工审核追踪创建: review_request={review_request_id}, "
                f"workflow={workflow_trace_id}, node={node_name}, "
                f"priority={priority.value}, sla={sla_hours}h"
            )
            
            return tracking_record
            
        except Exception as e:
            logger.error(f"创建审核追踪记录失败: {e}", exc_info=True)
            raise
    
    def _update_review_request_content(
        self,
        review_request_id: uuid.UUID,
        content: Dict[str, Any],
        workflow_trace_id: Optional[uuid.UUID],
        node_execution_id: Optional[uuid.UUID]
    ) -> None:
        """
        更新审核请求内容
        
        Args:
            review_request_id: 审核请求ID
            content: 审核内容
            workflow_trace_id: 工作流追踪ID
            node_execution_id: 节点执行ID
        """
        try:
            from app.models.review_request import ReviewRequest
            
            review_request = self.db.query(ReviewRequest).filter(
                ReviewRequest.id == review_request_id
            ).first()
            
            if review_request:
                if review_request.content is None:
                    review_request.content = {}
                
                review_request.content["workflow_trace_id"] = str(workflow_trace_id) if workflow_trace_id else None
                review_request.content["node_execution_id"] = str(node_execution_id) if node_execution_id else None
                review_request.content["review_data"] = content
                
                self.db.flush()
                
        except Exception as e:
            logger.warning(f"更新审核请求内容失败: {e}")
    
    def record_action(
        self,
        review_request_id: uuid.UUID,
        action: ReviewAction,
        user_id: uuid.UUID,
        action_details: Optional[Dict[str, Any]] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """
        记录审核操作
        
        Args:
            review_request_id: 审核请求ID
            action: 操作类型
            user_id: 用户ID
            action_details: 操作详情
            old_value: 旧值
            new_value: 新值
            ip_address: IP地址
        """
        try:
            from app.models.review_request import ReviewRequestAction
            
            review_action = ReviewRequestAction(
                id=uuid.uuid4(),
                review_request_id=review_request_id,
                user_id=user_id,
                action=action.value,
                action_details=action_details,
                old_value=old_value,
                new_value=new_value,
                ip_address=ip_address,
                created_at=datetime.utcnow()
            )
            
            self.db.add(review_action)
            self.db.flush()
            
            logger.info(
                f"审核操作记录: request={review_request_id}, "
                f"action={action.value}, user={user_id}"
            )
            
            self._update_review_request_status(review_request_id, action, user_id)
            
        except Exception as e:
            logger.error(f"记录审核操作失败: {e}", exc_info=True)
            raise
    
    def _update_review_request_status(
        self,
        review_request_id: uuid.UUID,
        action: ReviewAction,
        user_id: uuid.UUID
    ) -> None:
        """
        更新审核请求状态
        
        Args:
            review_request_id: 审核请求ID
            action: 操作类型
            user_id: 用户ID
        """
        try:
            from app.models.review_request import ReviewRequest
            
            review_request = self.db.query(ReviewRequest).filter(
                ReviewRequest.id == review_request_id
            ).first()
            
            if not review_request:
                return
            
            if action == ReviewAction.ASSIGN:
                review_request.status = "in_progress"
                review_request.assigned_to = user_id
                review_request.assigned_at = datetime.utcnow()
            
            elif action == ReviewAction.START_REVIEW:
                review_request.status = "in_progress"
            
            elif action == ReviewAction.APPROVE:
                review_request.status = "completed"
                review_request.reviewed_at = datetime.utcnow()
                review_request.reviewed_by = user_id
                review_request.review_result = {"action": "approve"}
            
            elif action == ReviewAction.REJECT:
                review_request.status = "rejected"
                review_request.reviewed_at = datetime.utcnow()
                review_request.reviewed_by = user_id
                review_request.review_result = {"action": "reject"}
            
            elif action == ReviewAction.ESCALATE:
                review_request.priority = ReviewPriority.URGENT.value
                review_request.review_result = {"action": "escalated"}
            
            if review_request.assigned_at:
                processing_seconds = (datetime.utcnow() - review_request.assigned_at).total_seconds()
                review_request.processing_time_seconds = int(processing_seconds)
            
            self.db.flush()
            
        except Exception as e:
            logger.error(f"更新审核请求状态失败: {e}", exc_info=True)
    
    def complete_review_and_resume_workflow(
        self,
        review_request_id: uuid.UUID,
        review_result: Dict[str, Any],
        resume_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        完成审核并恢复工作流执行
        
        这个方法会：
        1. 完成审核追踪
        2. 更新工作流状态
        3. 触发工作流继续执行
        
        Args:
            review_request_id: 审核请求ID
            review_result: 审核结果
            resume_data: 恢复执行所需的数据
        """
        try:
            from app.models.review_request import ReviewRequest
            from app.workflow.workflow_monitor import WorkflowMonitor
            
            review_request = self.db.query(ReviewRequest).filter(
                ReviewRequest.id == review_request_id
            ).first()
            
            if not review_request:
                logger.warning(f"审核请求不存在: {review_request_id}")
                return
            
            workflow_trace_id = None
            node_execution_id = None
            
            if review_request.content:
                workflow_trace_id_str = review_request.content.get("workflow_trace_id")
                node_execution_id_str = review_request.content.get("node_execution_id")
                
                if workflow_trace_id_str:
                    workflow_trace_id = uuid.UUID(workflow_trace_id_str)
                if node_execution_id_str:
                    node_execution_id = uuid.UUID(node_execution_id_str)
            
            if workflow_trace_id and node_execution_id:
                monitor = WorkflowMonitor(self.db)
                monitor.complete_human_review(
                    node_execution_id=node_execution_id,
                    review_result=review_result,
                    workflow_trace_id=workflow_trace_id
                )
            
            review_request.review_result = review_result
            
            if resume_data:
                logger.info(f"工作流恢复数据: {resume_data}")
            
            logger.info(
                f"人工审核完成并恢复工作流: "
                f"review_request={review_request_id}, "
                f"workflow={workflow_trace_id}, "
                f"action={review_result.get('action', 'unknown')}"
            )
            
        except Exception as e:
            logger.error(f"完成审核并恢复工作流失败: {e}", exc_info=True)
            raise
    
    def get_review_tracking_stats(
        self,
        tenant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取审核追踪统计
        
        Args:
            tenant_id: 租户ID
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            统计信息
        """
        try:
            from app.models.review_request import ReviewRequest, ReviewRequestAction
            
            query = self.db.query(ReviewRequest)
            
            if tenant_id:
                query = query.filter(ReviewRequest.tenant_id == tenant_id)
            
            if start_date:
                query = query.filter(ReviewRequest.created_at >= start_date)
            
            if end_date:
                query = query.filter(ReviewRequest.created_at <= end_date)
            
            all_requests = query.all()
            
            stats = {
                "total": len(all_requests),
                "pending": 0,
                "in_progress": 0,
                "completed": 0,
                "rejected": 0,
                "overdue": 0,
                "avg_processing_time_seconds": 0,
                "by_priority": {
                    "urgent": 0,
                    "high": 0,
                    "normal": 0,
                    "low": 0,
                },
                "by_type": {},
                "action_counts": {}
            }
            
            total_processing_time = 0
            processing_count = 0
            
            for req in all_requests:
                status_key = req.status.replace("_", "")
                if status_key in stats:
                    stats[status_key] += 1
                
                priority_key = req.priority.lower()
                if priority_key in stats["by_priority"]:
                    stats["by_priority"][priority_key] += 1
                
                review_type = req.review_type
                if review_type not in stats["by_type"]:
                    stats["by_type"][review_type] = 0
                stats["by_type"][review_type] += 1
                
                if req.is_overdue:
                    stats["overdue"] += 1
                
                if req.processing_time_seconds:
                    total_processing_time += req.processing_time_seconds
                    processing_count += 1
            
            if processing_count > 0:
                stats["avg_processing_time_seconds"] = total_processing_time / processing_count
            
            actions = self.db.query(ReviewRequestAction).filter(
                ReviewRequestAction.review_request_id.in_([r.id for r in all_requests])
            ).all()
            
            for action in actions:
                action_type = action.action
                if action_type not in stats["action_counts"]:
                    stats["action_counts"][action_type] = 0
                stats["action_counts"][action_type] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"获取审核追踪统计失败: {e}", exc_info=True)
            return {}
    
    def get_pending_reviews(
        self,
        tenant_id: Optional[str] = None,
        priority: Optional[ReviewPriority] = None,
        assigned_to: Optional[uuid.UUID] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取待审核列表
        
        Args:
            tenant_id: 租户ID
            priority: 优先级筛选
            assigned_to: 分配给谁
            limit: 返回数量限制
            
        Returns:
            待审核列表
        """
        try:
            from app.models.review_request import ReviewRequest
            
            query = self.db.query(ReviewRequest).filter(
                ReviewRequest.status.in_(["pending", "in_progress"])
            )
            
            if tenant_id:
                query = query.filter(ReviewRequest.tenant_id == tenant_id)
            
            if priority:
                query = query.filter(ReviewRequest.priority == priority.value)
            
            if assigned_to:
                query = query.filter(ReviewRequest.assigned_to == assigned_to)
            
            query = query.order_by(
                ReviewRequest.created_at.desc()
            ).limit(limit)
            
            reviews = query.all()
            
            return [
                {
                    "id": str(r.id),
                    "task_id": str(r.task_id),
                    "title": r.title,
                    "review_type": r.review_type,
                    "priority": r.priority,
                    "status": r.status,
                    "trigger_reason": r.trigger_reason,
                    "assigned_to": str(r.assigned_to) if r.assigned_to else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "is_overdue": r.is_overdue,
                    "age_hours": r.age_hours,
                    "sla_deadline": r.sla_deadline.isoformat() if r.sla_deadline else None,
                    "content": {
                        "workflow_trace_id": r.content.get("workflow_trace_id") if r.content else None,
                        "node_execution_id": r.content.get("node_execution_id") if r.content else None,
                    } if r.content else None
                }
                for r in reviews
            ]
            
        except Exception as e:
            logger.error(f"获取待审核列表失败: {e}", exc_info=True)
            return []
