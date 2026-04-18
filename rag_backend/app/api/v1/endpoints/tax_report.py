from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from typing import Optional
from pathlib import Path
import logging
import io
import os
import uuid
import asyncio
from datetime import datetime

from app.api.deps import get_current_user, get_db, CurrentUser
from app.models.tax_report import TaxReport
from app.schemas.tax_report import (
    TaxReportResponse,
    TaxReportStatusResponse,
    TaxReportListResponse,
    TaxReportProcessingCallback,
    TaxTypeEnum,
    TaxReportStatusEnum,
    ManualTaxReportCreate,
)
from app.services.tax_report_service import TaxReportService
from app.services.tax_file_validator import tax_file_validator

router = APIRouter(tags=["税务报告"])
logger = logging.getLogger(__name__)


def _read_file_sync(file_path: str) -> bytes:
    """同步读取文件（用于 asyncio.to_thread）"""
    with open(file_path, "rb") as f:
        return f.read()


def _save_file_sync(file_path, content: bytes):
    """同步保存文件（用于 asyncio.to_thread）"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)


async def _extract_file_content(content: bytes, content_type: str, filename: str) -> str:
    """
    从上传的文件中提取文本内容用于验证
    
    Args:
        content: 文件字节内容
        content_type: 文件的MIME类型
        filename: 文件名
        
    Returns:
        str: 提取的文本内容
    """
    try:
        if content_type == "text/csv" or filename.lower().endswith(".csv"):
            return content.decode("utf-8", errors="ignore")
        
        elif "pdf" in content_type.lower() or filename.lower().endswith(".pdf"):
            try:
                try:
                    from pypdf import PdfReader
                    logger.info("使用 pypdf 库提取 PDF 文本")
                except ImportError:
                    import PyPDF2
                    PdfReader = PyPDF2.PdfReader
                    logger.info("使用 PyPDF2 库提取 PDF 文本")
                
                pdf_file = io.BytesIO(content)
                pdf_reader = PdfReader(pdf_file)
                text_parts = []
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text())
                return "\n".join(text_parts)
            except ImportError:
                logger.warning("pypdf/PyPDF2未安装，尝试使用pdfplumber")
                try:
                    import pdfplumber
                    with pdfplumber.open(io.BytesIO(content)) as pdf:
                        text_parts = [page.extract_text() for page in pdf.pages]
                    return "\n".join(text_parts)
                except ImportError:
                    logger.error("无法提取PDF内容：缺少pypdf/PyPDF2或pdfplumber库")
                    return ""
                except (ValueError, KeyError) as e:
                    logger.error(f"pdfplumber提取PDF数据错误: {str(e)}")
                    return ""
                except (OSError, IOError) as e:
                    logger.error(f"pdfplumber提取PDF IO错误: {str(e)}")
                    return ""
                except Exception as e:
                    logger.error(f"pdfplumber提取PDF失败: {str(e)}")
                    return ""
        
        elif "excel" in content_type.lower() or "spreadsheet" in content_type.lower() or \
             filename.lower().endswith((".xlsx", ".xls")):
            try:
                import pandas as pd
                excel_file = io.BytesIO(content)
                if filename.lower().endswith(".xlsx"):
                    df = pd.read_excel(excel_file, engine="openpyxl", header=None)
                else:
                    df = pd.read_excel(excel_file, engine="xlrd", header=None)
                return df.to_string(index=False, header=False)
            except ImportError:
                logger.warning("pandas未安装，尝试使用openpyxl直接读取")
                try:
                    from openpyxl import load_workbook
                    excel_file = io.BytesIO(content)
                    wb = load_workbook(excel_file, read_only=True, data_only=True)
                    text_parts = []
                    for ws in wb.worksheets:
                        for row in ws.iter_rows(values_only=True):
                            row_text = " ".join(str(cell) for cell in row if cell is not None)
                            if row_text.strip():
                                text_parts.append(row_text)
                    return "\n".join(text_parts)
                except ImportError:
                    logger.error("无法提取Excel内容：缺少pandas或openpyxl库")
                    return ""
                except (ValueError, KeyError) as e:
                    logger.error(f"openpyxl提取Excel数据错误: {str(e)}")
                    return ""
                except (OSError, IOError) as e:
                    logger.error(f"openpyxl提取Excel IO错误: {str(e)}")
                    return ""
                except (ValueError, KeyError) as e:
                    raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
                except (OSError, IOError) as e:
                    raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
                except Exception as e:
                    logger.error(f"openpyxl提取Excel失败: {str(e)}")
                    return ""
        
        else:
            # 尝试直接解码为文本
            return content.decode("utf-8", errors="ignore")
    
    except (ValueError, KeyError) as e:
        logger.error(f"提取文件内容数据错误: {str(e)}")
        return ""
    except (OSError, IOError) as e:
        logger.error(f"提取文件内容IO错误: {str(e)}")
        return ""
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"提取文件内容失败: {str(e)}")
        return ""


async def get_tax_report_service(db: AsyncSession = Depends(get_db)) -> TaxReportService:
    return TaxReportService(db)


UPLOAD_DIR = Path("uploads/tax_reports")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def _process_tax_report_async(
    report_id: str,
    file_path: str,
    user_id: str,
    tenant_id: str,
    tax_type: str,
    minio_path: str,
    original_filename: str,
    content_type: str,
):
    """
    后台异步处理税务报告
    
    在后台执行文件验证、AI分析和数据库更新
    """
    import time
    from app.db.session import AsyncSessionLocal
    from app.services.minio_service import minio_service
    
    start_time = time.time()
    
    try:
        logger.info(f"🔄 [TaxReport] 开始后台处理报告: {report_id}")
        
        logger.info(f"⏱️ [Background] Step 1: 读取文件内容... ({time.time() - start_time:.2f}s)")
        file_content = await asyncio.to_thread(_read_file_sync, file_path)
        logger.info(f"⏱️ [Background] 文件读取完成: {len(file_content)} bytes ({time.time() - start_time:.2f}s)")
        
        file_type = "pdf" if file_path.endswith(".pdf") else "excel" if file_path.endswith((".xlsx", ".xls")) else "csv"
        
        validation_result_dict = None
        try:
            logger.info(f"⏱️ [Background] Step 2: 提取文件文本... ({time.time() - start_time:.2f}s)")
            file_text = await _extract_file_content(file_content, f"application/{file_type}", os.path.basename(file_path))
            logger.info(f"⏱️ [Background] 文本提取完成: {len(file_text)} 字符 ({time.time() - start_time:.2f}s)")
            
            logger.info(f"⏱️ [Background] Step 3: 验证文件内容... ({time.time() - start_time:.2f}s)")
            validation_result = await tax_file_validator.validate_with_ocr_fallback(
                file_text, 
                file_bytes=file_content,
                file_type=f"application/{file_type}"
            )
            
            if validation_result and validation_result.is_valid:
                validation_result_dict = {
                    "confidence": validation_result.confidence,
                    "is_valid": validation_result.is_valid,
                    "found_keywords": validation_result.found_keywords,
                    "missing_indicators": validation_result.missing_indicators,
                    "extracted_info": validation_result.extracted_info,
                    "suggestions": validation_result.suggestions,
                }
                
        except Exception as e:
            logger.warning(f"⚠️ [Background] 后台验证失败: {str(e)}")
            validation_result_dict = None
        
        try:
            logger.info(f"⏱️ [Background] Step 4: 上传到MinIO... ({time.time() - start_time:.2f}s)")
            await minio_service.upload_document_async(
                file_bytes=file_content,
                object_name=minio_path,
                content_type=content_type
            )
            logger.info(f"☁️ [Background] MinIO上传完成: {minio_path} ({time.time() - start_time:.2f}s)")
        except Exception as e:
            logger.warning(f"⚠️ [Background] MinIO上传失败: {str(e)}")
        
        logger.info(f"⏱️ [Background] Step 5: 更新数据库状态为processing... ({time.time() - start_time:.2f}s)")
        async with AsyncSessionLocal() as db:
            service = TaxReportService(db)
            
            await db.execute(
                update(TaxReport)
                .where(TaxReport.id == report_id)
                .values(
                    status="processing",
                    tax_validation_result=validation_result_dict,
                    updated_at=datetime.utcnow()
                )
            )
            await db.commit()
            
            logger.info(f"⏱️ [Background] Step 6: 开始AI分析... ({time.time() - start_time:.2f}s)")
            await service.process_tax_report_background(report_id, user_id, tenant_id)
            logger.info(f"⏱️ [Background] AI分析完成 ({time.time() - start_time:.2f}s)")
        
        logger.info(f"✅ [Background] 后台处理完成: {report_id}, 总耗时: {time.time() - start_time:.2f}s")
        
    except Exception as e:
        logger.error(f"❌ [Background] 后台处理失败: {report_id}, 错误: {str(e)}")
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(TaxReport)
                    .where(TaxReport.id == report_id)
                    .values(
                        status="failed",
                        error_message=str(e),
                        updated_at=datetime.utcnow()
                    )
                )
                await db.commit()
        except Exception:
            pass


@router.post("/upload", response_model=TaxReportResponse, status_code=201)
async def upload_tax_report(
    file: UploadFile = File(...),
    tax_type: str = Query(..., description="税种类型: VAT, INCOME, PERSONAL, CONSUMPTION, BEHAVIOR"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    上传税务报告文件进行自动处理

    - 支持文件类型: PDF, Excel (.xlsx, .xls), CSV
    - 最大文件大小: 50MB
    - 优化：快速保存文件，立即返回，后台异步处理验证和分析
    - 自动检测重复文件
    """
    import time
    start_time = time.time()
    
    logger.info(f"📤 [TaxUpload] 收到上传请求: {file.filename}, 大小: {file.size}")
    
    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过50MB")

    allowed_types = ["application/pdf", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     "application/vnd.ms-excel", "text/csv"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="不支持的文件类型，请上传PDF、Excel或CSV文件")

    try:
        # Step 0: 检测重复文件
        logger.info("⏱️ [TaxUpload] Step 0: 检测重复文件...")
        service = TaxReportService()
        duplicate_result = await service.check_duplicate_report(
            tenant_id=user.tenant_id,
            original_filename=file.filename
        )
        
        if duplicate_result:
            logger.warning(f"⚠️ [TaxUpload] 检测到重复文件: {file.filename}")
            return JSONResponse(
                status_code=409,
                content={
                    "success": False,
                    "error_type": "DUPLICATE_FILE",
                    "message": f"发现重复文件！您之前已上传过「{file.filename}」，上传时间为 {duplicate_result.get('created_at', '未知')}。",
                    "details": {
                        "original_filename": duplicate_result.get('original_filename'),
                        "existing_report_id": duplicate_result.get('report_id'),
                        "existing_status": duplicate_result.get('status'),
                        "existing_confidence_score": duplicate_result.get('confidence_score'),
                        "existing_risk_level": duplicate_result.get('risk_level'),
                        "created_at": duplicate_result.get('created_at'),
                        "suggestion": "如需重新分析，请先删除旧报告后再上传"
                    }
                }
            )
        report_id = str(uuid.uuid4())
        
        ext = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
        saved_filename = f"{report_id}{ext}"
        file_path = UPLOAD_DIR / saved_filename
        
        logger.info("⏱️ [TaxUpload] Step 1: 开始读取文件内容...")
        content = await file.read()
        logger.info(f"⏱️ [TaxUpload] 文件读取完成，耗时: {time.time() - start_time:.2f}s")
        
        logger.info("⏱️ [TaxUpload] Step 2: 开始保存文件到磁盘...")
        await asyncio.to_thread(_save_file_sync, file_path, content)
        logger.info(f"⏱️ [TaxUpload] 文件保存完成，耗时: {time.time() - start_time:.2f}s")
        
        file_size = len(content)
        
        file_type = "pdf"
        if "excel" in file.content_type.lower() or "spreadsheet" in file.content_type.lower():
            file_type = "excel"
        elif "csv" in file.content_type.lower():
            file_type = "csv"
        
        minio_path = f"{user.tenant_id}/{user.id}/tax-report/{report_id}/{saved_filename}"
        
        logger.info(f"💾 [TaxUpload] 文件已保存: {file_path}, 大小: {file_size} bytes")
        
        logger.info("⏱️ [TaxUpload] Step 3: 开始创建数据库记录...")
        report = TaxReport(
            id=report_id,
            user_id=user.id,
            tenant_id=user.tenant_id,
            filename=saved_filename,
            original_filename=file.filename,
            file_type=file_type,
            file_size=file_size,
            minio_path=minio_path,
            tax_type=tax_type.upper(),
            status="pending",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        db.add(report)
        
        logger.info("⏱️ [TaxUpload] Step 4: 开始提交数据库事务...")
        try:
            await db.commit()
            logger.info(f"⏱️ [TaxUpload] 数据库提交完成，耗时: {time.time() - start_time:.2f}s")
        except Exception as db_error:
            logger.error(f"❌ [TaxUpload] 数据库提交失败: {str(db_error)}")
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"数据库提交失败: {str(db_error)}")
        
        try:
            await db.refresh(report)
            logger.info(f"⏱️ [TaxUpload] 数据库刷新完成，耗时: {time.time() - start_time:.2f}s")
        except Exception as refresh_error:
            logger.warning(f"⚠️ [TaxUpload] 数据库刷新失败，使用缓存数据: {str(refresh_error)}")
        
        logger.info(f"✅ [TaxUpload] 数据库记录已创建: {report_id}")
        
        logger.info("⏱️ [TaxUpload] Step 5: 创建后台处理任务...")
        asyncio.create_task(
            _process_tax_report_async(
                report_id=report_id,
                file_path=str(file_path),
                user_id=user.id,
                tenant_id=user.tenant_id,
                tax_type=tax_type,
                minio_path=minio_path,
                original_filename=file.filename,
                content_type=file.content_type,
            )
        )
        
        total_time = time.time() - start_time
        logger.info(f"🚀 [TaxUpload] 快速返回: 报告ID={report_id}, 总耗时: {total_time:.2f}s")
        
        from app.services.operation_log_service import operation_logger, OperationType
        operation_logger.log_operation(
            operation_type=OperationType.TAX_REPORT_UPLOAD,
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            resource="tax_report",
            details={
                "user_id": str(user.id),
                "tenant_id": str(user.tenant_id),
                "filename": file.filename,
                "file_size": file_size,
                "file_type": file_type,
                "tax_type": tax_type,
                "report_id": report_id,
                "minio_path": minio_path,
                "result": "success",
                "processing_time": f"{total_time:.2f}s",
                "upload_timestamp": datetime.utcnow().isoformat()
            },
            risk_level="low"
        )
        
        response_data = {
            "id": str(report.id),
            "user_id": str(report.user_id),
            "tenant_id": str(report.tenant_id),
            "filename": report.filename,
            "original_filename": report.original_filename,
            "file_type": report.file_type,
            "file_size": report.file_size,
            "file_size_mb": round(report.file_size / (1024 * 1024), 2) if report.file_size else 0.0,
            "tax_type": TaxTypeEnum(report.tax_type.lower()) if report.tax_type else None,
            "status": TaxReportStatusEnum(report.status),
            "created_at": report.created_at,
            "updated_at": report.updated_at,
        }
        
        logger.info(f"📤 [TaxUpload] 响应数据预览: {response_data}")
        
        return TaxReportResponse(**response_data)

    except HTTPException:
        total_time = time.time() - start_time
        from app.services.operation_log_service import operation_logger, OperationType
        operation_logger.log_operation(
            operation_type=OperationType.TAX_REPORT_UPLOAD,
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            resource="tax_report",
            details={
                "user_id": str(user.id),
                "tenant_id": str(user.tenant_id),
                "filename": file.filename if file else "unknown",
                "tax_type": tax_type,
                "result": "failed",
                "error_type": "HTTPException",
                "processing_time": f"{total_time:.2f}s",
                "upload_timestamp": datetime.utcnow().isoformat()
            },
            risk_level="low"
        )
        raise
    except Exception as e:
        import traceback
        total_time = time.time() - start_time
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
            "report_data": {
                "report_id": report.id if 'report' in locals() else None,
                "user_id": user.id if 'user' in locals() else None,
                "tenant_id": user.tenant_id if 'user' in locals() else None,
                "tax_type": tax_type if 'tax_type' in locals() else None,
            }
        }
        logger.error(f"税务报告上传失败: {error_details}", exc_info=True)
        
        from app.services.operation_log_service import operation_logger, OperationType
        operation_logger.log_operation(
            operation_type=OperationType.TAX_REPORT_UPLOAD,
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            resource="tax_report",
            details={
                "user_id": str(user.id),
                "tenant_id": str(user.tenant_id),
                "filename": file.filename if file else "unknown",
                "tax_type": tax_type,
                "result": "failed",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "processing_time": f"{total_time:.2f}s",
                "upload_timestamp": datetime.utcnow().isoformat()
            },
            risk_level="medium"
        )
        
        if "validation errors" in str(e).lower() or "pydantic" in str(e).lower():
            logger.error("🔍 [TaxUpload] Pydantic 验证错误详情:")
            for key, value in error_details.items():
                logger.error(f"   {key}: {value}")
        
        raise HTTPException(
            status_code=500,
            detail=f"税务报告上传失败: {str(e)}"
        )


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
    获取当前用户的税务报告列表（租户+用户双重隔离）

    - 支持分页
    - 支持按状态、税种类型、日期范围过滤
    - 按创建时间倒序排列
    - 每个用户只能看到自己的税务报告
    """
    reports, total = await service.list_tax_reports(
        tenant_id=user.tenant_id,
        user_id=str(user.id),  # 用户级隔离：每个用户只能看到自己的提交记录
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
    - 支持用户级隔离：每个用户只能看到自己的统计数据
    """
    stats = await service.get_statistics(user.tenant_id, str(user.id))
    return stats


@router.get("/{report_id}", response_model=TaxReportResponse)
async def get_tax_report(
    report_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: TaxReportService = Depends(get_tax_report_service),
):
    """
    获取税务报告详情（租户+用户双重隔离）

    - 返回报告基本信息
    - 返回处理结果
    - 返回税务验证结果（如有）
    - 用户只能访问自己的报告
    """
    report = await service.get_tax_report(report_id, user.tenant_id, str(user.id))
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
    获取税务报告处理状态（租户+用户双重隔离）

    - 用于轮询查询处理进度
    - 返回当前状态和进度信息
    - 用户只能查看自己的报告状态
    """
    status = await service.get_processing_status(report_id, user.tenant_id, str(user.id))
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
    重试失败的税务报告处理（租户+用户双重隔离）

    - 仅在状态为 FAILED 时可用
    - 重新触发后台处理流程
    - 用户只能重试自己的报告
    """
    report = await service.get_tax_report(report_id, user.tenant_id, str(user.id))
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
    删除税务报告（租户+用户双重隔离）

    - 仅可删除自己上传的报告
    - 删除时会同时删除关联的文件和文档
    - 用户只能删除自己的报告
    """
    success = await service.delete_tax_report(report_id, user.tenant_id, str(user.id))
    if not success:
        raise HTTPException(status_code=404, detail="税务报告不存在或无权删除")
    return {"message": "税务报告已删除", "report_id": report_id}


@router.post("/manual", response_model=dict)
async def create_manual_tax_report(
    request: ManualTaxReportCreate,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    service: TaxReportService = Depends(get_tax_report_service),
):
    """
    手动录入税务报告
    
    - 管理员可直接录入财务数据创建税务报告
    - 支持关联已有财务数据
    - 可选择是否立即运行AI分析
    """
    try:
        input_data = request.input_data.model_dump()
        
        result = await service.create_manual_tax_report(
            user_id=str(user.id),
            tenant_id=user.tenant_id,
            input_data=input_data,
        )
        
        return {
            "success": True,
            "message": "税务报告录入成功",
            "data": result
        }
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


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
    except (ValueError, KeyError) as e:
        logger.error(f"处理回调数据错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"回调处理数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"处理回调IO错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"回调处理IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"处理回调失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="回调处理失败")


@router.get("/reviews/pending", response_model=TaxReportListResponse)
async def get_pending_tax_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    service: TaxReportService = Depends(get_tax_report_service),
):
    """
    获取待审核的税务报告列表（租户+用户双重隔离）

    - 只返回需要人工审核的报告
    - 支持分页
    - 按创建时间倒序排列
    - 每个用户只能看到自己的待审核报告
    """
    reports, total = await service.list_tax_reports(
        tenant_id=user.tenant_id,
        user_id=str(user.id),  # 用户级隔离
        skip=skip,
        limit=limit,
        status="pending_review",
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
