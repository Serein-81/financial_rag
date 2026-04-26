"""
人工审核 API 端点

提供审核请求的管理和处理功能
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func, and_
import uuid
import json
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

from app.db.session import AsyncSessionLocal
from app.api import deps
from app.models.user import User
from app.schemas.human_review import (
    ReviewRequestCreate,
    ReviewRequestResponse,
    ReviewRequestListResponse,
    ReviewRequestUpdate,
    ReviewRequestAction,
    ReviewStatisticsResponse,
    ReviewCommentRequest,
    ReviewCommentResponse,
    ReviewActionResponse,
    ReviewPriorityEnum,
    ReviewStatusEnum,
    ReviewTypeEnum
)
from app.models.review_request import ReviewRequest, ReviewRequestComment, ReviewRequestAction
from app.services.redis_service import redis_service

router = APIRouter(prefix="/reviews", tags=["人工审核"])


async def get_db():
    """数据库会话依赖"""
    async with AsyncSessionLocal() as session:
        yield session


@router.post("", response_model=ReviewRequestResponse)
async def create_review_request(
    request_data: ReviewRequestCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    创建审核请求
    """
    try:
        review_id = str(uuid.uuid4())
        
        # 计算SLA截止时间
        sla_hours = {
            "low": 72,
            "normal": 48,
            "high": 24,
            "urgent": 4
        }
        deadline_hours = sla_hours.get(request_data.priority, 48)
        sla_deadline = datetime.utcnow().replace(microsecond=0)
        from datetime import timedelta
        sla_deadline = sla_deadline + timedelta(hours=deadline_hours)
        
        review_request = ReviewRequest(
            id=review_id,
            task_id=request_data.task_id,
            tenant_id=tenant_context['tenant_id'],
            user_id=current_user.id,
            review_type=request_data.review_type.value if request_data.review_type else "tax",
            priority=request_data.priority.value if request_data.priority else "normal",
            trigger_reason=request_data.trigger_reason,
            trigger_details=request_data.trigger_details,
            title=request_data.title,
            description=request_data.description,
            content=request_data.content,
            document_ids=request_data.document_ids,
            status="pending",
            sla_deadline=sla_deadline
        )
        
        db.add(review_request)
        await db.commit()
        await db.refresh(review_request)
        
        # 记录操作日志
        await _log_action(db, review_id, current_user.id, "create", {
            "task_id": str(request_data.task_id),
            "priority": request_data.priority.value if request_data.priority else "normal"
        })
        
        # 发布到Redis（用于实时通知）
        background_tasks.add_task(
            _publish_review_event,
            tenant_context['tenant_id'],
            "created",
            review_request
        )
        
        return ReviewRequestResponse(
            id=str(review_request.id),
            task_id=str(review_request.task_id),
            tenant_id=review_request.tenant_id,
            user_id=str(review_request.user_id),
            review_type=ReviewTypeEnum(review_request.review_type),
            priority=ReviewPriorityEnum(review_request.priority),
            trigger_reason=review_request.trigger_reason,
            title=review_request.title,
            description=review_request.description,
            status=ReviewStatusEnum(review_request.status),
            created_at=review_request.created_at,
            sla_deadline=review_request.sla_deadline,
            is_overdue=review_request.is_overdue,
            age_hours=review_request.age_hours
        )
        
    except (ValueError, KeyError) as e:
        import traceback
        logger.error(f"[HumanReview] list_review_requests ValueError: {str(e)}, trace: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建审核请求失败: {str(e)}")


@router.get("", response_model=ReviewRequestListResponse)
async def list_review_requests(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    review_type: Optional[str] = None,
    assigned_to_me: Optional[bool] = None,
    overdue_only: Optional[bool] = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    获取审核请求列表（租户隔离）
    """
    try:
        logger.info(f"[HumanReview] list_review_requests called, tenant={tenant_context.get('tenant_id')}, page={page}, page_size={page_size}")
        
        query = select(ReviewRequest).where(ReviewRequest.tenant_id == tenant_context['tenant_id'])
        
        if status:
            query = query.where(ReviewRequest.status == status)
        
        if priority:
            query = query.where(ReviewRequest.priority == priority)
        
        if review_type:
            query = query.where(ReviewRequest.review_type == review_type)
        
        if assigned_to_me:
            query = query.where(ReviewRequest.assigned_to == current_user.id)
        
        if overdue_only:
            query = query.where(
                and_(
                    ReviewRequest.sla_deadline < datetime.utcnow(),
                    ReviewRequest.status != 'completed'
                )
            )
        
        # 排序
        from sqlalchemy import case
        priority_order = case(
            (ReviewRequest.priority == 'urgent', 1),
            (ReviewRequest.priority == 'high', 2),
            (ReviewRequest.priority == 'normal', 3),
            else_=4
        )
        query = query.order_by(priority_order, ReviewRequest.created_at.desc())
        
        # 分页
        query = query.limit(page_size).offset((page - 1) * page_size)
        
        result = await db.execute(query)
        requests = result.scalars().all()
        
        # 获取总数
        count_query = select(ReviewRequest).where(ReviewRequest.tenant_id == tenant_context['tenant_id'])
        if status:
            count_query = count_query.where(ReviewRequest.status == status)
        if priority:
            count_query = count_query.where(ReviewRequest.priority == priority)
        if review_type:
            count_query = count_query.where(ReviewRequest.review_type == review_type)
        if assigned_to_me:
            count_query = count_query.where(ReviewRequest.assigned_to == current_user.id)
        if overdue_only:
            count_query = count_query.where(
                and_(
                    ReviewRequest.sla_deadline < datetime.utcnow(),
                    ReviewRequest.status != 'completed'
                )
            )
        count_result = await db.execute(
            select(func.count()).select_from(count_query.subquery())
        )
        total = count_result.scalar()
        
        items = []
        for req in requests:
            is_overdue = req.is_overdue if hasattr(req, 'is_overdue') else False
            age_hours = req.age_hours if hasattr(req, 'age_hours') else 0
            
            try:
                review_type_enum = ReviewTypeEnum(req.review_type)
            except (ValueError, KeyError):
                review_type_enum = ReviewTypeEnum.TAX
            
            try:
                priority_enum = ReviewPriorityEnum(req.priority)
            except (ValueError, KeyError):
                priority_enum = ReviewPriorityEnum.NORMAL
            
            try:
                status_enum = ReviewStatusEnum(req.status)
            except (ValueError, KeyError):
                status_enum = ReviewStatusEnum.PENDING
            
            items.append(ReviewRequestResponse(
                id=str(req.id),
                task_id=str(req.task_id),
                tenant_id=req.tenant_id,
                user_id=str(req.user_id),
                review_type=review_type_enum,
                priority=priority_enum,
                trigger_reason=req.trigger_reason,
                trigger_details=json.loads(req.trigger_details) if isinstance(req.trigger_details, str) and req.trigger_details else req.trigger_details,
                title=req.title,
                description=req.description,
                content=json.loads(req.content) if isinstance(req.content, str) and req.content else req.content,
                status=status_enum,
                assigned_to=str(req.assigned_to) if req.assigned_to else None,
                assigned_at=req.assigned_at,
                review_result=json.loads(req.review_result) if isinstance(req.review_result, str) else req.review_result,
                review_comments=req.review_comments,
                reviewed_at=req.reviewed_at,
                sla_deadline=req.sla_deadline,
                created_at=req.created_at,
                updated_at=req.updated_at,
                is_overdue=is_overdue,
                age_hours=age_hours
            ))
        
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        return ReviewRequestListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except (ValueError, KeyError) as e:
        import traceback
        logger.error(f"[HumanReview] list_review_requests ValueError: {str(e)}, trace: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/statistics", response_model=ReviewStatisticsResponse)
async def get_review_statistics(
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    获取审核统计信息
    """
    try:
        tenant_id = tenant_context['tenant_id']
        
        # 待处理数量
        pending_result = await db.execute(
            text("SELECT COUNT(*) FROM review_requests WHERE tenant_id = :tenant_id AND status = 'pending'"),
            {"tenant_id": tenant_id}
        )
        pending_count = pending_result.scalar()
        
        # 处理中数量
        in_progress_result = await db.execute(
            text("SELECT COUNT(*) FROM review_requests WHERE tenant_id = :tenant_id AND status = 'in_progress'"),
            {"tenant_id": tenant_id}
        )
        in_progress_count = in_progress_result.scalar()
        
        # 今日完成数量
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        completed_today_result = await db.execute(
            text("SELECT COUNT(*) FROM review_requests WHERE tenant_id = :tenant_id AND status = 'completed' AND reviewed_at >= :today"),
            {"tenant_id": tenant_id, "today": today_start}
        )
        completed_today = completed_today_result.scalar()
        
        # 逾期数量
        overdue_result = await db.execute(
            text("SELECT COUNT(*) FROM review_requests WHERE tenant_id = :tenant_id AND sla_deadline < :now AND status != 'completed'"),
            {"tenant_id": tenant_id, "now": datetime.utcnow()}
        )
        overdue_count = overdue_result.scalar()
        
        # 按优先级统计
        priority_stats = {}
        for priority in ["urgent", "high", "normal", "low"]:
            result = await db.execute(
                text("SELECT COUNT(*) FROM review_requests WHERE tenant_id = :tenant_id AND priority = :priority AND status != 'completed'"),
                {"tenant_id": tenant_id, "priority": priority}
            )
            priority_stats[priority] = result.scalar()
        
        # 平均处理时间（小时）
        avg_time_result = await db.execute(
            text("""
            SELECT AVG(EXTRACT(EPOCH FROM (reviewed_at - created_at)) / 3600) 
            FROM review_requests 
            WHERE tenant_id = :tenant_id AND status = 'completed' AND reviewed_at IS NOT NULL
            """),
            {"tenant_id": tenant_id}
        )
        avg_processing_hours = avg_time_result.scalar() or 0
        
        return ReviewStatisticsResponse(
            pending_count=pending_count,
            in_progress_count=in_progress_count,
            completed_today=completed_today,
            overdue_count=overdue_count,
            priority_breakdown=priority_stats,
            avg_processing_hours=round(avg_processing_hours, 1)
        )
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


@router.get("/{review_id}", response_model=ReviewRequestResponse)
async def get_review_request(
    review_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    获取审核请求详情
    """
    try:
        result = await db.execute(
            text("SELECT * FROM review_requests WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": review_id, "tenant_id": tenant_context['tenant_id']}
        )
        req = result.fetchone()
        
        if not req:
            raise HTTPException(status_code=404, detail="审核请求不存在")

        # 计算 is_overdue（手动计算，因为是属性而非数据库列）
        is_overdue = False
        if req.sla_deadline:
            now = datetime.now(timezone.utc)
            sla_deadline = req.sla_deadline
            if req.sla_deadline.tzinfo is None:
                sla_deadline = req.sla_deadline.replace(tzinfo=timezone.utc)
            is_overdue = now > sla_deadline

        # 计算 age_hours（手动计算，因为是属性而非数据库列）
        age_hours = 0
        if req.created_at:
            now = datetime.now(timezone.utc)
            created_at = req.created_at
            if req.created_at.tzinfo is None:
                created_at = req.created_at.replace(tzinfo=timezone.utc)
            delta = now - created_at
            age_hours = int(delta.total_seconds() / 3600)

        return ReviewRequestResponse(
            id=str(req.id),
            task_id=str(req.task_id),
            tenant_id=req.tenant_id,
            user_id=str(req.user_id),
            review_type=ReviewTypeEnum(req.review_type),
            priority=ReviewPriorityEnum(req.priority),
            trigger_reason=req.trigger_reason,
            trigger_details=json.loads(req.trigger_details) if isinstance(req.trigger_details, str) and req.trigger_details else req.trigger_details,
            title=req.title,
            description=req.description,
            content=json.loads(req.content) if isinstance(req.content, str) and req.content else req.content,
            status=ReviewStatusEnum(req.status),
            assigned_to=str(req.assigned_to) if req.assigned_to else None,
            assigned_at=req.assigned_at,
            review_result=json.loads(req.review_result) if isinstance(req.review_result, str) else req.review_result,
            review_comments=req.review_comments,
            reviewed_at=req.reviewed_at,
            sla_deadline=req.sla_deadline,
            created_at=req.created_at,
            updated_at=req.updated_at,
            is_overdue=is_overdue,
            age_hours=age_hours
        )
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.patch("/{review_id}")
async def update_review_request(
    review_id: str,
    update_data: ReviewRequestUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    更新审核请求（分配、开始处理等）
    """
    try:
        result = await db.execute(
            text("SELECT * FROM review_requests WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": review_id, "tenant_id": tenant_context['tenant_id']}
        )
        req = result.fetchone()
        
        if not req:
            raise HTTPException(status_code=404, detail="审核请求不存在")
        
        update_dict = {"updated_at": datetime.utcnow()}
        action_type = None
        
        status_str = update_data.status.value if update_data.status else None
        
        if status_str:
            update_dict["status"] = status_str
            if status_str == "in_progress" and req.status == "pending":
                action_type = "start"
            elif status_str == "completed":
                now = datetime.now(timezone.utc)
                created_at = req.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                update_dict["reviewed_at"] = now
                update_dict["reviewed_by"] = str(current_user.id)
                update_dict["processing_time_seconds"] = int((now - created_at).total_seconds())
                action_type = "complete"
            elif status_str == "rejected":
                action_type = "reject"
        
        if update_data.assigned_to:
            update_dict["assigned_to"] = update_data.assigned_to
            update_dict["assigned_at"] = datetime.utcnow()
            action_type = "assign"
        
        if update_data.review_result:
            import json
            update_dict["review_result"] = json.dumps(update_data.review_result)
        
        if update_data.review_comments:
            update_dict["review_comments"] = update_data.review_comments
        
        set_clause = ", ".join([f"{k} = :{k}" for k in update_dict.keys()])
        update_sql = f"UPDATE review_requests SET {set_clause} WHERE id = :id"
        update_dict["id"] = review_id
        
        await db.execute(text(update_sql), update_dict)
        await db.commit()
        
        task_id = str(req.task_id) if req.task_id else None
        
        if action_type == "complete" and task_id:
            try:
                from app.models.tax_report import TaxReport
                from sqlalchemy import update as sql_update
                await db.execute(
                    sql_update(TaxReport)
                    .where(TaxReport.id == task_id)
                    .values(
                        status="completed",
                        updated_at=datetime.utcnow()
                    )
                )
                await db.commit()
            except Exception as e:
                logger.warning(f"[HumanReview] 更新 TaxReport 状态失败: {e}")
                await db.rollback()
        
        elif action_type == "reject" and task_id:
            try:
                from app.models.tax_report import TaxReport
                from sqlalchemy import update as sql_update
                await db.execute(
                    sql_update(TaxReport)
                    .where(TaxReport.id == task_id)
                    .values(
                        status="failed",
                        processing_message=f"审核拒绝: {update_data.review_comments or '无'}",
                        updated_at=datetime.utcnow()
                    )
                )
                await db.commit()
            except Exception as e:
                logger.warning(f"[HumanReview] 更新 TaxReport 状态失败: {e}")
                await db.rollback()
        
        if action_type:
            try:
                import json
                old_status = req.status
                new_status = update_dict.get("status", old_status)
                
                action_details = {
                    "description": _get_action_description(action_type, update_data),
                    "comment": update_data.review_comments or req.review_comments,
                    "result": update_data.review_result,
                    "priority": update_data.priority.value if update_data.priority else None,
                    "action_type": action_type
                }
                
                old_value = {
                    "status": old_status,
                    "assigned_to": str(req.assigned_to) if req.assigned_to else None,
                    "review_comments": req.review_comments,
                    "review_result": json.loads(req.review_result) if req.review_result else None
                }
                
                new_value = {
                    "status": new_status,
                    "assigned_to": update_dict.get("assigned_to"),
                    "review_comments": update_dict.get("review_comments") or update_data.review_comments,
                    "review_result": update_dict.get("review_result") or (json.dumps(update_data.review_result) if update_data.review_result else None)
                }
                
                logger.info(f"[HumanReview] 记录操作日志: action={action_type}, details={action_details}, old={old_value}, new={new_value}")
                
                await _log_action(
                    db, 
                    review_id, 
                    current_user.id, 
                    action_type, 
                    action_details,
                    old_value=old_value,
                    new_value=new_value
                )
            except Exception as e:
                import traceback
                logger.error(f"[HumanReview] 记录操作日志失败: {str(e)}, trace: {traceback.format_exc()}")
        
        # 发布更新事件
        background_tasks.add_task(
            _publish_review_event,
            tenant_context['tenant_id'],
            "updated",
            {"id": review_id, "action": action_type}
        )
        
        return {"success": True, "message": "更新成功"}
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        import traceback
        logger.error(f"[HumanReview] update_review_request ValueError: {str(e)}, trace: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        import traceback
        logger.error(f"[HumanReview] update_review_request 500 error: {str(e)}, trace: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.post("/{review_id}/comments", response_model=ReviewCommentResponse)
async def add_review_comment(
    review_id: str,
    comment_data: ReviewCommentRequest,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    添加审核评论
    """
    try:
        # 验证审核请求存在
        result = await db.execute(
            text("SELECT id FROM review_requests WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": review_id, "tenant_id": tenant_context['tenant_id']}
        )
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="审核请求不存在")
        
        comment_id = str(uuid.uuid4())
        comment = ReviewRequestComment(
            id=comment_id,
            review_request_id=review_id,
            user_id=current_user.id,
            content=comment_data.content,
            comment_type=comment_data.comment_type.value if comment_data.comment_type else "comment",
            related_entity_type=comment_data.related_entity_type,
            related_entity_id=comment_data.related_entity_id,
            attachments=comment_data.attachments
        )
        
        db.add(comment)
        await db.commit()
        await db.refresh(comment)
        
        return ReviewCommentResponse(
            id=str(comment.id),
            review_request_id=str(comment.review_request_id),
            user_id=str(comment.user_id),
            user_name=current_user.user_name,
            content=comment.content,
            comment_type=comment.comment_type,
            created_at=comment.created_at
        )
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加评论失败: {str(e)}")


@router.get("/{review_id}/comments", response_model=List[ReviewCommentResponse])
async def list_review_comments(
    review_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    获取审核评论列表
    """
    try:
        # 验证审核请求存在
        result = await db.execute(
            text("SELECT id FROM review_requests WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": review_id, "tenant_id": tenant_context['tenant_id']}
        )
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="审核请求不存在")
        
        comments_result = await db.execute(
            text("""
            SELECT * FROM review_request_comments 
            WHERE review_request_id = :review_id 
            ORDER BY created_at ASC
            """),
            {"review_id": review_id}
        )
        comments = comments_result.fetchall()
        
        # 获取用户名（简化处理）
        items = []
        for comment in comments:
            items.append(ReviewCommentResponse(
                id=str(comment.id),
                review_request_id=str(comment.review_request_id),
                user_id=str(comment.user_id),
                user_name="用户",  # 实际应关联用户表获取
                content=comment.content,
                comment_type=comment.comment_type,
                attachments=comment.attachments,
                created_at=comment.created_at
            ))
        
        return items
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/{review_id}/actions", response_model=List[ReviewActionResponse])
async def list_review_actions(
    review_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    获取审核操作历史
    """
    try:
        result = await db.execute(
            text("SELECT id FROM review_requests WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": review_id, "tenant_id": tenant_context['tenant_id']}
        )
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="审核请求不存在")
        
        actions_result = await db.execute(
            text("""
            SELECT * FROM review_request_actions 
            WHERE review_request_id = :review_id 
            ORDER BY created_at ASC
            """),
            {"review_id": review_id}
        )
        actions = actions_result.fetchall()
        
        items = []
        for action in actions:
            items.append(ReviewActionResponse(
                id=str(action.id),
                review_request_id=str(action.review_request_id),
                user_id=str(action.user_id),
                action=action.action,
                action_details=action.action_details,
                old_value=action.old_value,
                new_value=action.new_value,
                created_at=action.created_at
            ))
        
        return items
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


def _get_action_description(action_type: str, update_data) -> str:
    """根据操作类型生成操作描述"""
    descriptions = {
        "start": "开始处理审核请求",
        "complete": "批准审核请求",
        "reject": "驳回审核请求",
        "assign": "分配审核请求",
        "cancel": "取消审核请求"
    }
    
    description = descriptions.get(action_type, f"执行了{action_type}操作")
    
    if update_data.review_comments:
        comment_preview = update_data.review_comments[:100] if len(update_data.review_comments) > 100 else update_data.review_comments
        description += f"：{comment_preview}"
    
    return description


async def _log_action(
    db: AsyncSession, 
    review_id: str, 
    user_id: str, 
    action: str, 
    details: dict,
    old_value: dict = None,
    new_value: dict = None
):
    """记录操作日志"""
    try:
        logger.info(f"[HumanReview] _log_action: 创建操作记录, action={action}, details={details}, old={old_value}, new={new_value}")
        
        action_record = ReviewRequestAction(
            id=str(uuid.uuid4()),
            review_request_id=review_id,
            user_id=user_id,
            action=action,
            action_details=details,
            old_value=old_value,
            new_value=new_value
        )
        db.add(action_record)
        await db.commit()
        logger.info(f"[HumanReview] _log_action: 操作记录创建成功")
    except (ValueError, KeyError) as e:
        import traceback
        logger.error(f"[HumanReview] _log_action 数据错误: {str(e)}, trace: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        import traceback
        logger.error(f"[HumanReview] _log_action IO错误: {str(e)}, trace: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        import traceback
        logger.error(f"[HumanReview] _log_action 失败: {str(e)}, trace: {traceback.format_exc()}")


async def _publish_review_event(tenant_id: str, event_type: str, data: dict):
    """发布审核事件到Redis"""
    try:
        import json
        event = {
            "tenant_id": tenant_id,
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        await redis_service.publish(
            f"review:events:{tenant_id}",
            json.dumps(event)
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        print(f"⚠️ 发布审核事件失败: {str(e)}")
