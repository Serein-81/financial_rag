"""
用户反馈 API

提供用户反馈收集、失败案例管理、改进记录等功能。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.models.feedback import (
    UserFeedback,
    FailureCase,
    ImprovementRecord,
    FeedbackType,
    FailureType,
    FailureStatus,
    ImprovementType
)

router = APIRouter()


# ==================== Pydantic 模型 ====================

class FeedbackCreate(BaseModel):
    """创建反馈请求"""
    session_id: str = Field(..., description="会话 ID")
    message_id: Optional[UUID] = Field(None, description="消息 ID")
    query: str = Field(..., description="用户查询")
    response: str = Field(..., description="系统响应")
    feedback_type: FeedbackType = Field(..., description="反馈类型")
    rating: Optional[int] = Field(None, ge=1, le=5, description="评分 1-5")
    comment: Optional[str] = Field(None, description="用户评论")
    retrieval_method: Optional[str] = Field(None, description="检索方法")
    chunks_used: Optional[dict] = Field(None, description="使用的文档块")
    kb_id: Optional[str] = Field(None, description="知识库 ID")
    retrieval_time: Optional[int] = Field(None, description="检索时间(ms)")
    generation_time: Optional[int] = Field(None, description="生成时间(ms)")
    total_time: Optional[int] = Field(None, description="总时间(ms)")
    token_count: Optional[int] = Field(None, description="Token 消耗")


class FeedbackUpdate(BaseModel):
    """更新反馈请求"""
    feedback_type: Optional[FeedbackType] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    """反馈响应"""
    id: UUID
    session_id: str
    message_id: Optional[UUID]
    user_id: Optional[UUID]
    query: str
    response: str
    feedback_type: str
    rating: Optional[int]
    comment: Optional[str]
    retrieval_method: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class FailureCaseCreate(BaseModel):
    """创建失败案例请求"""
    feedback_id: UUID = Field(..., description="关联的反馈 ID")
    failure_type: FailureType = Field(..., description="失败类型")
    analysis: Optional[dict] = Field(None, description="分析结果")
    fix_suggestions: Optional[list] = Field(None, description="修复建议")


class FailureCaseUpdate(BaseModel):
    """更新失败案例请求"""
    failure_type: Optional[FailureType] = None
    analysis: Optional[dict] = None
    fix_suggestions: Optional[list] = None
    status: Optional[FailureStatus] = None


class ImprovementRecordCreate(BaseModel):
    """创建改进记录请求"""
    failure_case_id: UUID = Field(..., description="关联的失败案例 ID")
    improvement_type: ImprovementType = Field(..., description="改进类型")
    before_config: Optional[dict] = Field(None, description="改进前配置")
    after_config: Optional[dict] = Field(None, description="改进后配置")
    description: Optional[str] = Field(None, description="改进描述")


# ==================== 反馈管理 API ====================

@router.post("/feedbacks", response_model=dict)
async def create_feedback(
    feedback_data: FeedbackCreate = Body(...),
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_tenant_db)
):
    """
    创建用户反馈

    记录用户对 RAG 系统响应的反馈。
    """
    try:
        # 创建反馈记录
        feedback = UserFeedback(
            session_id=feedback_data.session_id,
            message_id=feedback_data.message_id,
            user_id=current_user.id,
            tenant_id=tenant_context.get("tenant_id"),
            query=feedback_data.query,
            response=feedback_data.response,
            feedback_type=feedback_data.feedback_type,
            rating=feedback_data.rating,
            comment=feedback_data.comment,
            retrieval_method=feedback_data.retrieval_method,
            chunks_used=feedback_data.chunks_used,
            kb_id=feedback_data.kb_id,
            retrieval_time=feedback_data.retrieval_time,
            generation_time=feedback_data.generation_time,
            total_time=feedback_data.total_time,
            token_count=feedback_data.token_count
        )

        db.add(feedback)
        await db.commit()
        await db.refresh(feedback)

        return {
            "success": True,
            "message": "反馈创建成功",
            "feedback": feedback.to_dict(),
            "tenant_id": tenant_context.get("tenant_id")
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"创建反馈失败: {str(e)}")


@router.get("/feedbacks/{feedback_id}", response_model=dict)
async def get_feedback(
    feedback_id: UUID,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_tenant_db)
):
    """
    获取反馈详情
    """
    try:
        # 查询反馈（租户隔离）
        stmt = select(UserFeedback).where(
            and_(
                UserFeedback.id == feedback_id,
                UserFeedback.tenant_id == tenant_context.get("tenant_id")
            )
        )
        result = await db.execute(stmt)
        feedback = result.scalar_one_or_none()

        if not feedback:
            raise HTTPException(status_code=404, detail="反馈不存在")

        return {
            "success": True,
            "feedback": feedback.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取反馈失败: {str(e)}")


@router.get("/feedbacks", response_model=dict)
async def list_feedbacks(
    session_id: Optional[str] = Query(None, description="会话 ID 过滤"),
    feedback_type: Optional[FeedbackType] = Query(None, description="反馈类型过滤"),
    rating_min: Optional[int] = Query(None, ge=1, le=5, description="最低评分"),
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_tenant_db)
):
    """
    获取反馈列表（支持过滤和分页）
    """
    try:
        # 构建查询条件
        conditions = [UserFeedback.tenant_id == tenant_context.get("tenant_id")]

        if session_id:
            conditions.append(UserFeedback.session_id == session_id)

        if feedback_type:
            conditions.append(UserFeedback.feedback_type == feedback_type)

        if rating_min:
            conditions.append(UserFeedback.rating >= rating_min)

        # 查询总数
        count_stmt = select(func.count(UserFeedback.id)).where(and_(*conditions))
        total = (await db.execute(count_stmt)).scalar()

        # 查询列表
        stmt = (
            select(UserFeedback)
            .where(and_(*conditions))
            .order_by(UserFeedback.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        feedbacks = result.scalars().all()

        return {
            "success": True,
            "feedbacks": [f.to_dict() for f in feedbacks],
            "total": total,
            "skip": skip,
            "limit": limit,
            "tenant_id": tenant_context.get("tenant_id")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取反馈列表失败: {str(e)}")


@router.patch("/feedbacks/{feedback_id}", response_model=dict)
async def update_feedback(
    feedback_id: UUID,
    feedback_data: FeedbackUpdate = Body(...),
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_tenant_db)
):
    """
    更新反馈
    """
    try:
        # 查询反馈（租户隔离）
        stmt = select(UserFeedback).where(
            and_(
                UserFeedback.id == feedback_id,
                UserFeedback.tenant_id == tenant_context.get("tenant_id")
            )
        )
        result = await db.execute(stmt)
        feedback = result.scalar_one_or_none()

        if not feedback:
            raise HTTPException(status_code=404, detail="反馈不存在")

        # 更新字段
        if feedback_data.feedback_type is not None:
            feedback.feedback_type = feedback_data.feedback_type
        if feedback_data.rating is not None:
            feedback.rating = feedback_data.rating
        if feedback_data.comment is not None:
            feedback.comment = feedback_data.comment

        await db.commit()
        await db.refresh(feedback)

        return {
            "success": True,
            "message": "反馈更新成功",
            "feedback": feedback.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"更新反馈失败: {str(e)}")


@router.delete("/feedbacks/{feedback_id}", response_model=dict)
async def delete_feedback(
    feedback_id: UUID,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_tenant_db)
):
    """
    删除反馈
    """
    try:
        # 查询反馈（租户隔离）
        stmt = select(UserFeedback).where(
            and_(
                UserFeedback.id == feedback_id,
                UserFeedback.tenant_id == tenant_context.get("tenant_id")
            )
        )
        result = await db.execute(stmt)
        feedback = result.scalar_one_or_none()

        if not feedback:
            raise HTTPException(status_code=404, detail="反馈不存在")

        await db.delete(feedback)
        await db.commit()

        return {
            "success": True,
            "message": "反馈删除成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"删除反馈失败: {str(e)}")


# ==================== 失败案例管理 API ====================

@router.post("/failure-cases", response_model=dict)
async def create_failure_case(
    case_data: FailureCaseCreate = Body(...),
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_tenant_db)
):
    """
    创建失败案例
    """
    try:
        # 验证反馈是否存在
        stmt = select(UserFeedback).where(
            and_(
                UserFeedback.id == case_data.feedback_id,
                UserFeedback.tenant_id == tenant_context.get("tenant_id")
            )
        )
        result = await db.execute(stmt)
        feedback = result.scalar_one_or_none()

        if not feedback:
            raise HTTPException(status_code=404, detail="关联的反馈不存在")

        # 创建失败案例
        failure_case = FailureCase(
            feedback_id=case_data.feedback_id,
            failure_type=case_data.failure_type,
            analysis=case_data.analysis,
            fix_suggestions=case_data.fix_suggestions,
            status=FailureStatus.PENDING
        )

        db.add(failure_case)
        await db.commit()
        await db.refresh(failure_case)

        return {
            "success": True,
            "message": "失败案例创建成功",
            "failure_case": failure_case.to_dict(),
            "tenant_id": tenant_context.get("tenant_id")
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"创建失败案例失败: {str(e)}")


@router.get("/failure-cases", response_model=dict)
async def list_failure_cases(
    failure_type: Optional[FailureType] = Query(None, description="失败类型过滤"),
    status: Optional[FailureStatus] = Query(None, description="状态过滤"),
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_tenant_db)
):
    """
    获取失败案例列表（支持过滤和分页）
    """
    try:
        # 构建查询条件（通过 feedback 进行租户隔离）
        conditions = [UserFeedback.tenant_id == tenant_context.get("tenant_id")]

        if failure_type:
            conditions.append(FailureCase.failure_type == failure_type)

        if status:
            conditions.append(FailureCase.status == status)

        # 查询总数
        count_stmt = (
            select(func.count(FailureCase.id))
            .join(UserFeedback, FailureCase.feedback_id == UserFeedback.id)
            .where(and_(*conditions))
        )
        total = (await db.execute(count_stmt)).scalar()

        # 查询列表
        stmt = (
            select(FailureCase)
            .join(UserFeedback, FailureCase.feedback_id == UserFeedback.id)
            .where(and_(*conditions))
            .order_by(FailureCase.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        cases = result.scalars().all()

        return {
            "success": True,
            "failure_cases": [c.to_dict() for c in cases],
            "total": total,
            "skip": skip,
            "limit": limit,
            "tenant_id": tenant_context.get("tenant_id")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取失败案例列表失败: {str(e)}")


@router.get("/failure-cases/{case_id}", response_model=dict)
async def get_failure_case(
    case_id: UUID,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_tenant_db)
):
    """
    获取失败案例详情
    """
    try:
        # 查询失败案例（通过 feedback 进行租户隔离）
        stmt = (
            select(FailureCase)
            .join(UserFeedback, FailureCase.feedback_id == UserFeedback.id)
            .where(
                and_(
                    FailureCase.id == case_id,
                    UserFeedback.tenant_id == tenant_context.get("tenant_id")
                )
            )
        )
        result = await db.execute(stmt)
        case = result.scalar_one_or_none()

        if not case:
            raise HTTPException(status_code=404, detail="失败案例不存在")

        return {
            "success": True,
            "failure_case": case.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取失败案例失败: {str(e)}")


@router.patch("/failure-cases/{case_id}", response_model=dict)
async def update_failure_case(
    case_id: UUID,
    case_data: FailureCaseUpdate = Body(...),
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_tenant_db)
):
    """
    更新失败案例
    """
    try:
        # 查询失败案例（通过 feedback 进行租户隔离）
        stmt = (
            select(FailureCase)
            .join(UserFeedback, FailureCase.feedback_id == UserFeedback.id)
            .where(
                and_(
                    FailureCase.id == case_id,
                    UserFeedback.tenant_id == tenant_context.get("tenant_id")
                )
            )
        )
        result = await db.execute(stmt)
        case = result.scalar_one_or_none()

        if not case:
            raise HTTPException(status_code=404, detail="失败案例不存在")

        # 更新字段
        if case_data.failure_type is not None:
            case.failure_type = case_data.failure_type
        if case_data.analysis is not None:
            case.analysis = case_data.analysis
        if case_data.fix_suggestions is not None:
            case.fix_suggestions = case_data.fix_suggestions
        if case_data.status is not None:
            case.status = case_data.status
            if case_data.status == FailureStatus.ANALYZING:
                case.analyzed_at = datetime.now()

        await db.commit()
        await db.refresh(case)

        return {
            "success": True,
            "message": "失败案例更新成功",
            "failure_case": case.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败案例失败: {str(e)}")


# ==================== 改进记录管理 API ====================

@router.post("/improvement-records", response_model=dict)
async def create_improvement_record(
    record_data: ImprovementRecordCreate = Body(...),
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_tenant_db)
):
    """
    创建改进记录
    """
    try:
        # 验证失败案例是否存在
        stmt = (
            select(FailureCase)
            .join(UserFeedback, FailureCase.feedback_id == UserFeedback.id)
            .where(
                and_(
                    FailureCase.id == record_data.failure_case_id,
                    UserFeedback.tenant_id == tenant_context.get("tenant_id")
                )
            )
        )
        result = await db.execute(stmt)
        failure_case = result.scalar_one_or_none()

        if not failure_case:
            raise HTTPException(status_code=404, detail="关联的失败案例不存在")

        # 创建改进记录
        improvement = ImprovementRecord(
            failure_case_id=record_data.failure_case_id,
            improvement_type=record_data.improvement_type,
            before_config=record_data.before_config,
            after_config=record_data.after_config,
            description=record_data.description
        )

        db.add(improvement)
        await db.commit()
        await db.refresh(improvement)

        return {
            "success": True,
            "message": "改进记录创建成功",
            "improvement_record": improvement.to_dict(),
            "tenant_id": tenant_context.get("tenant_id")
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"创建改进记录失败: {str(e)}")


@router.get("/improvement-records", response_model=dict)
async def list_improvement_records(
    improvement_type: Optional[ImprovementType] = Query(None, description="改进类型过滤"),
    deployed: Optional[bool] = Query(None, description="是否已部署"),
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_tenant_db)
):
    """
    获取改进记录列表（支持过滤和分页）
    """
    try:
        # 构建查询条件（通过 feedback 进行租户隔离）
        conditions = [UserFeedback.tenant_id == tenant_context.get("tenant_id")]

        if improvement_type:
            conditions.append(ImprovementRecord.improvement_type == improvement_type)

        if deployed is not None:
            conditions.append(ImprovementRecord.deployed == deployed)

        # 查询总数
        count_stmt = (
            select(func.count(ImprovementRecord.id))
            .join(FailureCase, ImprovementRecord.failure_case_id == FailureCase.id)
            .join(UserFeedback, FailureCase.feedback_id == UserFeedback.id)
            .where(and_(*conditions))
        )
        total = (await db.execute(count_stmt)).scalar()

        # 查询列表
        stmt = (
            select(ImprovementRecord)
            .join(FailureCase, ImprovementRecord.failure_case_id == FailureCase.id)
            .join(UserFeedback, FailureCase.feedback_id == UserFeedback.id)
            .where(and_(*conditions))
            .order_by(ImprovementRecord.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        records = result.scalars().all()

        return {
            "success": True,
            "improvement_records": [r.to_dict() for r in records],
            "total": total,
            "skip": skip,
            "limit": limit,
            "tenant_id": tenant_context.get("tenant_id")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取改进记录列表失败: {str(e)}")


# ==================== 统计分析 API ====================

@router.get("/statistics/feedback-summary", response_model=dict)
async def get_feedback_summary(
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_tenant_db)
):
    """
    获取反馈统计摘要

    返回各类反馈的数量统计、平均评分等信息。
    """
    try:
        tenant_id = tenant_context.get("tenant_id")

        # 总反馈数
        total_stmt = select(func.count(UserFeedback.id)).where(
            UserFeedback.tenant_id == tenant_id
        )
        total_feedbacks = (await db.execute(total_stmt)).scalar()

        # 各类型反馈数
        positive_stmt = select(func.count(UserFeedback.id)).where(
            and_(
                UserFeedback.tenant_id == tenant_id,
                UserFeedback.feedback_type == FeedbackType.POSITIVE
            )
        )
        positive_count = (await db.execute(positive_stmt)).scalar()

        negative_stmt = select(func.count(UserFeedback.id)).where(
            and_(
                UserFeedback.tenant_id == tenant_id,
                UserFeedback.feedback_type == FeedbackType.NEGATIVE
            )
        )
        negative_count = (await db.execute(negative_stmt)).scalar()

        # 平均评分
        avg_rating_stmt = select(func.avg(UserFeedback.rating)).where(
            and_(
                UserFeedback.tenant_id == tenant_id,
                UserFeedback.rating.isnot(None)
            )
        )
        avg_rating = (await db.execute(avg_rating_stmt)).scalar()

        # 失败案例统计
        failure_stmt = (
            select(func.count(FailureCase.id))
            .join(UserFeedback, FailureCase.feedback_id == UserFeedback.id)
            .where(UserFeedback.tenant_id == tenant_id)
        )
        total_failures = (await db.execute(failure_stmt)).scalar()

        # 已修复案例
        fixed_stmt = (
            select(func.count(FailureCase.id))
            .join(UserFeedback, FailureCase.feedback_id == UserFeedback.id)
            .where(
                and_(
                    UserFeedback.tenant_id == tenant_id,
                    FailureCase.status == FailureStatus.FIXED
                )
            )
        )
        fixed_count = (await db.execute(fixed_stmt)).scalar()

        return {
            "success": True,
            "summary": {
                "total_feedbacks": total_feedbacks,
                "positive_count": positive_count,
                "negative_count": negative_count,
                "neutral_count": total_feedbacks - positive_count - negative_count,
                "avg_rating": round(float(avg_rating), 2) if avg_rating else None,
                "total_failures": total_failures,
                "fixed_count": fixed_count,
                "fix_rate": round(fixed_count / total_failures * 100, 2) if total_failures > 0 else 0
            },
            "tenant_id": tenant_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取反馈统计失败: {str(e)}")


@router.get("/statistics/failure-types", response_model=dict)
async def get_failure_types_distribution(
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_tenant_db)
):
    """
    获取失败类型分布统计
    """
    try:
        tenant_id = tenant_context.get("tenant_id")

        # 按失败类型统计
        distribution = {}
        for failure_type in FailureType:
            stmt = (
                select(func.count(FailureCase.id))
                .join(UserFeedback, FailureCase.feedback_id == UserFeedback.id)
                .where(
                    and_(
                        UserFeedback.tenant_id == tenant_id,
                        FailureCase.failure_type == failure_type
                    )
                )
            )
            count = (await db.execute(stmt)).scalar()
            distribution[failure_type.value] = count

        return {
            "success": True,
            "distribution": distribution,
            "tenant_id": tenant_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取失败类型分布失败: {str(e)}")
