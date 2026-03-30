from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import json
import logging

from app.api.deps import get_current_user, get_db, CurrentUser, PaginatedParams
from app.models.tax_report import TaxReport, TaxReportDocument
from app.schemas.tax_report import (
    TaxReportCreate,
    TaxReportResponse,
    TaxReportStatusResponse,
    TaxReportListResponse,
    TaxReportProcessingCallback,
)
from app.services.tax_report_service import TaxReportService

router = APIRouter(tags=["税务报告"])
logger = logging.getLogger(__name__)


async def get_tax_report_service(db: AsyncSession = Depends(get_db)) -> TaxReportService:
    return TaxReportService(db)


@router.post("/upload", response_model=TaxReportResponse, status_code=201)
async def upload_tax_report(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tax_type: str = Query(..., description="税种类型: VAT, INCOME, PERSONAL, CONSUMPTION, BEHAVIOR"),
    user: CurrentUser = Depends(get_current_user),
    service: TaxReportService = Depends(get_tax_report_service),
):
    """
    上传税务报告文件进行自动处理

    - 支持文件类型: PDF, Excel (.xlsx, .xls), CSV
    - 最大文件大小: 50MB
    - 自动触发税务逻辑验证
    - 需要人工审核时自动加入审核队列
    """
    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过50MB")

    allowed_types = ["application/pdf", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     "application/vnd.ms-excel", "text/csv"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="不支持的文件类型，请上传PDF、Excel或CSV文件")

    try:
        result = await service.create_tax_report(
            user_id=user.id,
            tenant_id=user.tenant_id,
            file=file,
            tax_type=tax_type,
        )

        background_tasks.add_task(
            service.process_tax_report_background,
            result["id"],
            user.id,
            user.tenant_id,
        )

        return TaxReportResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"税务报告上传失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="税务报告上传失败")


@router.get("", response_model=TaxReportListResponse)
async def list_tax_reports(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="过滤状态: PENDING, PROCESSING, COMPLETED, FAILED, NEEDS_REVIEW"),
    tax_type: Optional[str] = Query(None, description="过滤税种类型"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    user: CurrentUser = Depends(get_current_user),
    service: TaxReportService = Depends(get_tax_report_service),
):
    """
    获取当前用户的税务报告列表

    - 支持分页
    - 支持按状态、税种类型、日期范围过滤
    - 按创建时间倒序排列
    """
    reports, total = await service.list_tax_reports(
        tenant_id=user.tenant_id,
        user_id=user.id,
        skip=skip,
        limit=limit,
        status=status,
        tax_type=tax_type,
        start_date=start_date,
        end_date=end_date,
    )

    # 计算分页信息
    page = (skip // limit) + 1 if limit > 0 else 1
    total_pages = (total + limit - 1) // limit if limit > 0 else 1
    
    return TaxReportListResponse(
        items=[TaxReportResponse.model_validate(r) for r in reports],
        total=total,
        page=page,
        page_size=limit,
        total_pages=total_pages,
    )


@router.get("/statistics")
async def get_tax_report_statistics(
    user: CurrentUser = Depends(get_current_user),
    service: TaxReportService = Depends(get_tax_report_service),
):
    """
    获取税务报告统计信息

    - 按状态统计数量
    - 按税种类型统计数量
    - 总处理时长统计
    """
    stats = await service.get_statistics(user.tenant_id)
    return stats


@router.get("/{report_id}", response_model=TaxReportResponse)
async def get_tax_report(
    report_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: TaxReportService = Depends(get_tax_report_service),
):
    """
    获取税务报告详情

    - 返回报告基本信息
    - 返回处理结果
    - 返回税务验证结果（如有）
    """
    report = await service.get_tax_report(report_id, user.tenant_id)
    if not report:
        raise HTTPException(status_code=404, detail="税务报告不存在")
    return TaxReportResponse.model_validate(report)


@router.get("/{report_id}/status", response_model=TaxReportStatusResponse)
async def get_report_status(
    report_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: TaxReportService = Depends(get_tax_report_service),
):
    """
    获取税务报告处理状态

    - 用于轮询查询处理进度
    - 返回当前状态和进度信息
    """
    status = await service.get_processing_status(report_id, user.tenant_id)
    if not status:
        raise HTTPException(status_code=404, detail="税务报告不存在")
    return TaxReportStatusResponse(**status)


@router.post("/{report_id}/retry")
async def retry_processing(
    report_id: str,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    service: TaxReportService = Depends(get_tax_report_service),
):
    """
    重试失败的税务报告处理

    - 仅在状态为 FAILED 时可用
    - 重新触发后台处理流程
    """
    report = await service.get_tax_report(report_id, user.tenant_id)
    if not report:
        raise HTTPException(status_code=404, detail="税务报告不存在")

    if report.status != "FAILED":
        raise HTTPException(status_code=400, detail="只能重试失败的报告")

    background_tasks.add_task(
        service.process_tax_report_background,
        report_id,
        user.id,
        user.tenant_id,
    )

    return {"message": "重试任务已提交", "report_id": report_id}


@router.delete("/{report_id}")
async def delete_tax_report(
    report_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: TaxReportService = Depends(get_tax_report_service),
):
    """
    删除税务报告

    - 仅可删除自己上传的报告
    - 删除时会同时删除关联的文件和文档
    """
    success = await service.delete_tax_report(report_id, user.tenant_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="税务报告不存在或无权删除")
    return {"message": "税务报告已删除", "report_id": report_id}


@router.post("/callback/processing")
async def processing_callback(
    callback: TaxReportProcessingCallback,
    service: TaxReportService = Depends(get_tax_report_service),
):
    """
    处理完成回调（内部接口，供Agent系统调用）

    - 更新报告状态
    - 保存处理结果
    - 自动判断是否需要人工审核
    """
    try:
        await service.update_processing_result(
            report_id=callback.report_id,
            status=callback.status,
            processing_result=callback.processing_result,
            tax_validation_result=callback.tax_validation_result,
            needs_human_review=callback.needs_human_review,
            key_metrics=callback.key_metrics,
            issues=callback.issues,
        )
        return {"message": "回调处理成功"}
    except Exception as e:
        logger.error(f"处理回调失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="回调处理失败")
