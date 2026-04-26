"""
税务报告服务层

负责税务报告的核心业务逻辑处理

PgBouncer Transaction 模式改造：
- 使用 Repository 层替代直接的 AsyncSessionLocal 调用
- 所有数据库操作通过 TaxReportRepository 进行
- 租户隔离通过显式传递 tenant_id 实现
"""

import uuid
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.tax_report import TaxReportRepository
from app.services.minio_service import minio_service


class TaxReportService:
    """
    税务报告服务
    
    核心功能：
    1. 税务报告处理流程编排
    2. 文件解析和内容提取
    3. PII脱敏处理
    4. Agent编排集成
    5. 状态管理和通知
    
    注意：
    - 使用 TaxReportRepository 进行数据库操作
    - 所有查询都需要显式传递 tenant_id
    - 不再依赖 SET LOCAL 会话变量
    """
    
    def __init__(self, db: AsyncSession):
        """
        初始化服务
        
        Args:
            db: AsyncSession 实例（必须传入）
        """
        self.db = db
        self.repository = TaxReportRepository(db)
        self.processing_stages = [
            "文件下载",
            "文件解析",
            "内容提取",
            "PII脱敏",
            "Agent处理",
            "税务逻辑验证",
            "结果汇总"
        ]
    
    async def check_duplicate_report(
        self,
        tenant_id: str,
        original_filename: str,
        file_hash: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        检测是否存在重复的报告
        
        Args:
            tenant_id: 租户ID（显式传递）
            original_filename: 原始文件名
            file_hash: 文件哈希（可选）
            
        Returns:
            如果存在重复返回报告信息，否则返回 None
        """
        try:
            normalized_filename = original_filename.strip()
            
            print(f"🔍 [重复检测] 租户ID: {tenant_id}")
            print(f"🔍 [重复检测] 原始文件名: '{original_filename}'")
            print(f"🔍 [重复检测] 标准化文件名: '{normalized_filename}'")
            
            # 使用 Repository 查找重复
            existing = await self.repository.find_duplicates(
                tenant_id=tenant_id,
                filename=normalized_filename,
                file_hash=file_hash
            )
            
            if existing:
                print(f"✅ [重复检测] 发现重复文件: {existing.original_filename}")
                return {
                    "is_duplicate": True,
                    "report_id": str(existing.id),
                    "original_filename": existing.original_filename,
                    "status": existing.status,
                    "created_at": existing.created_at.isoformat() if existing.created_at else None,
                    "confidence_score": float(existing.confidence_score) if existing.confidence_score else None,
                    "risk_level": existing.risk_level,
                    "message": f"已存在同名报告：{existing.original_filename}"
                }
            
            print("✅ [重复检测] 未发现重复文件")
            return None
            
        except Exception as e:
            print(f"⚠️ [税务报告服务] 检测重复报告失败: {str(e)}")
            return None
    
    async def create_tax_report(
        self,
        user_id: str,
        tenant_id: str,
        file,
        tax_type: str = None,
        tax_period_year: int = None,
        tax_period_month: int = None,
        description: str = None,
        file_validation_result: dict = None,
    ) -> dict:
        """
        创建税务报告记录
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID（显式传递）
            file: 上传的文件对象
            tax_type: 税种类型
            tax_period_year: 税务年度
            tax_period_month: 税务月份
            description: 报告描述
            file_validation_result: 文件验证结果
            
        Returns:
            创建的报告信息
        """
        try:
            # 确保 tenant_id 是字符串
            if not isinstance(tenant_id, str):
                tenant_id = str(tenant_id)
            
            # 确保 user_id 是字符串
            if not isinstance(user_id, str):
                user_id = str(user_id)
            
            report_id = str(uuid.uuid4())
            filename = f"{report_id}_{file.filename}"
            original_filename = file.filename
            
            # 获取文件大小
            file_content = await file.read()
            file_size = len(file_content)
            
            # 确定文件类型
            file_type = "unknown"
            if file.content_type:
                if "pdf" in file.content_type.lower():
                    file_type = "pdf"
                elif "excel" in file.content_type.lower() or "spreadsheet" in file.content_type.lower():
                    file_type = "excel"
                elif "csv" in file.content_type.lower():
                    file_type = "csv"
            
            # 生成MinIO路径
            minio_path = f"{tenant_id}/{user_id}/tax-report/{report_id}/{filename}"
            
            # 上传到MinIO
            try:
                await minio_service.upload_document_async(
                    file_bytes=file_content,
                    object_name=minio_path,
                    content_type=file.content_type
                )
            except (OSError, IOError) as e:
                print(f"⚠️ [税务报告服务] MinIO上传IO错误: {str(e)}")
            except ConnectionError as e:
                print(f"⚠️ [税务报告服务] MinIO连接失败: {str(e)}")
            except Exception as e:
                print(f"⚠️ [税务报告服务] MinIO上传失败: {str(e)}")
            
            # 从验证结果中提取信息
            confidence_score = None
            key_metrics = None
            tax_validation_result = None
            
            if file_validation_result:
                confidence_score = file_validation_result.get("confidence")
                extracted_info = file_validation_result.get("extracted_info", {})
                
                key_metrics = {
                    "currency_amounts": extracted_info.get("currency_amounts", []),
                    "invoice_numbers": extracted_info.get("invoice_numbers", []),
                    "tax_ids": extracted_info.get("tax_ids", []),
                    "tax_rates": extracted_info.get("tax_rates", []),
                    "dates": extracted_info.get("dates", []),
                    "descriptions": extracted_info.get("descriptions", []),
                    "tax_type_hints": extracted_info.get("tax_type_hints", []),
                    "found_keywords": file_validation_result.get("found_keywords", []),
                }
                
                tax_validation_result = {
                    "confidence": confidence_score,
                    "found_keywords": file_validation_result.get("found_keywords", []),
                    "missing_indicators": file_validation_result.get("missing_indicators", []),
                    "extracted_info": extracted_info,
                }
            
            # 使用 Repository 创建报告
            report = await self.repository.create_report(
                user_id=user_id,
                tenant_id=tenant_id,
                filename=filename,
                original_filename=original_filename,
                file_type=file_type,
                file_size=file_size,
                minio_path=minio_path,
                tax_type=tax_type,
                tax_period_year=tax_period_year,
                tax_period_month=tax_period_month,
                status="pending",
                processing_message="文件已上传，等待处理",
                needs_human_review="false",
                pii_anonymized="false",
                confidence_score=str(confidence_score) if confidence_score else None,
                key_metrics=key_metrics,
                tax_validation_result=tax_validation_result,
            )
            
            print(f"✅ [税务报告服务] 创建报告成功: {report_id}")
            
            return {
                "id": str(report.id),
                "tenant_id": str(report.tenant_id),
                "user_id": str(report.user_id),
                "filename": report.filename,
                "original_filename": report.original_filename,
                "file_size": report.file_size,
                "file_size_mb": report.file_size_mb,
                "file_type": report.file_type,
                "tax_type": report.tax_type,
                "status": report.status,
                "created_at": report.created_at,
                "updated_at": report.updated_at,
                "message": "文件上传成功，等待处理",
            }
            
        except (ValueError, KeyError) as e:
            print(f"❌ [税务报告服务] 创建报告数据错误: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"创建税务报告数据错误: {str(e)}")
        except (OSError, IOError) as e:
            print(f"❌ [税务报告服务] 创建报告IO错误: {str(e)}")
            await self.db.rollback()
            raise IOError(f"创建税务报告IO错误: {str(e)}")
        except Exception as e:
            print(f"❌ [税务报告服务] 创建报告失败: {str(e)}")
            await self.db.rollback()
            raise ValueError(f"创建税务报告失败: {str(e)}")
    
    async def list_tax_reports(
        self,
        tenant_id: str,
        user_id: str = None,
        skip: int = 0,
        limit: int = 20,
        status: str = None,
        tax_type: str = None,
        start_date: str = None,
        end_date: str = None,
    ) -> tuple:
        """
        获取税务报告列表
        
        Args:
            tenant_id: 租户ID（显式传递）
            user_id: 用户ID（可选）
            skip: 跳过的记录数
            limit: 返回的记录数
            status: 状态过滤
            tax_type: 税种类型过滤
            start_date: 开始日期 (YYYY-MM-DD格式)
            end_date: 结束日期 (YYYY-MM-DD格式)
            
        Returns:
            (报告列表, 总数)
        """
        try:
            from datetime import datetime
            from sqlalchemy import and_, between
            
            # 构建查询条件
            filters = {}
            if user_id:
                filters['user_id'] = user_id
            if status:
                filters['status'] = status
            if tax_type:
                filters['tax_type'] = tax_type
            
            # 使用 Repository 获取列表
            reports = await self.repository.list(
                tenant_id=tenant_id,
                skip=skip,
                limit=limit,
                order_by='created_at',
                order_desc=True,
                **filters
            )
            
            # 应用日期过滤（如果提供了日期参数）
            if start_date or end_date:
                filtered_reports = []
                for report in reports:
                    report_date = report.created_at.date()
                    
                    # 检查是否在日期范围内
                    in_range = True
                    if start_date:
                        start = datetime.strptime(start_date, "%Y-%m-%d").date()
                        if report_date < start:
                            in_range = False
                    if end_date:
                        end = datetime.strptime(end_date, "%Y-%m-%d").date()
                        if report_date > end:
                            in_range = False
                    
                    if in_range:
                        filtered_reports.append(report)
                
                reports = filtered_reports
            
            # 获取总数（考虑日期过滤）
            total = await self.repository.count(
                tenant_id=tenant_id,
                **filters
            )
            
            # 如果应用了日期过滤，需要重新计算总数
            if start_date or end_date:
                total = len(reports)
            
            # 转换为字典列表
            report_list = []
            for report in reports:
                report_dict = {
                    "id": str(report.id),
                    "tenant_id": report.tenant_id,
                    "user_id": str(report.user_id),
                    "filename": report.filename,
                    "original_filename": report.original_filename,
                    "file_type": report.file_type,
                    "file_size": report.file_size,
                    "file_size_mb": report.file_size_mb,
                    "tax_type": report.tax_type,
                    "tax_period_year": report.tax_period_year,
                    "tax_period_month": report.tax_period_month,
                    "status": report.status,
                    "processing_message": report.processing_message,
                    "confidence_score": float(report.confidence_score) if report.confidence_score else None,
                    "risk_score": report.risk_score,
                    "risk_level": report.risk_level,
                    "needs_human_review": report.needs_human_review == "true",
                    "key_metrics": report.key_metrics,
                    "created_at": report.created_at,
                    "updated_at": report.updated_at,
                }
                report_list.append(report_dict)
            
            return report_list, total
            
        except Exception as e:
            print(f"❌ [税务报告服务] 查询列表失败: {str(e)}")
            return [], 0
    
    async def get_tax_report(self, report_id: str, tenant_id: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """
        获取单个税务报告详情（租户隔离）
        
        Args:
            report_id: 报告ID
            tenant_id: 租户ID（显式传递）
            user_id: 用户ID（可选）
            
        Returns:
            报告详情或 None
        """
        try:
            report = await self.repository.get_by_id(report_id, tenant_id=tenant_id)
            
            if not report:
                return None
            
            # 可选：验证用户权限
            if user_id and str(report.user_id) != user_id:
                print(f"⚠️ [税务报告服务] 用户 {user_id} 无权访问报告 {report_id}")
                return None
            
            return {
                "id": str(report.id),
                "tenant_id": report.tenant_id,
                "user_id": str(report.user_id),
                "filename": report.filename,
                "original_filename": report.original_filename,
                "file_type": report.file_type,
                "file_size": report.file_size,
                "file_size_mb": report.file_size_mb,
                "tax_type": report.tax_type,
                "tax_period_year": report.tax_period_year,
                "tax_period_month": report.tax_period_month,
                "status": report.status,
                "processing_message": report.processing_message,
                "confidence_score": float(report.confidence_score) if report.confidence_score else None,
                "risk_score": report.risk_score,
                "risk_level": report.risk_level,
                "needs_human_review": report.needs_human_review == "true",
                "review_request_id": str(report.review_request_id) if report.review_request_id else None,
                "key_metrics": report.key_metrics,
                "tax_validation_result": report.tax_validation_result,
                "processing_result": report.processing_result,
                "created_at": report.created_at,
                "updated_at": report.updated_at,
                "completed_at": report.completed_at,
            }
            
        except Exception as e:
            print(f"❌ [税务报告服务] 获取报告失败: {str(e)}")
            return None
    
    async def update_tax_report_status(
        self,
        report_id: str,
        tenant_id: str,
        status: str,
        message: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        更新税务报告状态
        
        Args:
            report_id: 报告ID
            tenant_id: 租户ID（显式传递）
            status: 新状态
            message: 状态消息
            
        Returns:
            更新后的报告或 None
        """
        try:
            report = await self.repository.update_status(
                report_id=report_id,
                tenant_id=tenant_id,
                status=status,
                message=message
            )
            
            if report:
                return {
                    "id": str(report.id),
                    "status": report.status,
                    "processing_message": report.processing_message,
                    "updated_at": report.updated_at,
                }
            
            return None
            
        except Exception as e:
            print(f"❌ [税务报告服务] 更新状态失败: {str(e)}")
            return None
    
    async def get_statistics(self, tenant_id: str, user_id: str = None) -> Dict[str, Any]:
        """
        获取税务报告统计信息
        
        Args:
            tenant_id: 租户ID（显式传递）
            user_id: 用户ID（可选）
            
        Returns:
            统计信息字典，包含：
            - total_reports: 总报告数
            - by_status: 按状态统计
            - by_tax_type: 按税种类型统计
            - by_risk_level: 按风险等级统计
            - needs_review_count: 需要审核的报告数
            - recent_activity: 最近活动统计
        """
        try:
            from datetime import datetime, timedelta, timezone
            
            # 获取所有报告
            filters = {}
            if user_id:
                filters['user_id'] = user_id
            
            reports = await self.repository.list(
                tenant_id=tenant_id,
                skip=0,
                limit=1000,  # 获取足够多的报告进行统计
                order_by='created_at',
                order_desc=True,
                **filters
            )
            
            if not reports:
                return {
                    "total_reports": 0,
                    "by_status": {},
                    "by_tax_type": {},
                    "by_risk_level": {},
                    "needs_review_count": 0,
                    "recent_activity": {
                        "last_7_days": 0,
                        "last_30_days": 0,
                        "today": 0
                    }
                }
            
            # 计算统计信息
            total_reports = len(reports)
            
            # 按状态统计
            by_status = {}
            for report in reports:
                status = report.status or "unknown"
                by_status[status] = by_status.get(status, 0) + 1
            
            # 按税种类型统计
            by_tax_type = {}
            for report in reports:
                tax_type = report.tax_type or "unknown"
                by_tax_type[tax_type] = by_tax_type.get(tax_type, 0) + 1
            
            # 按风险等级统计
            by_risk_level = {}
            for report in reports:
                risk_level = report.risk_level or "unknown"
                by_risk_level[risk_level] = by_risk_level.get(risk_level, 0) + 1
            
            # 需要审核的报告数
            needs_review_count = sum(
                1 for report in reports 
                if report.needs_human_review == "true"
            )
            
            # 最近活动统计 - 使用 timezone-aware datetime 以匹配数据库字段
            now = datetime.now(timezone.utc)
            last_7_days = now - timedelta(days=7)
            last_30_days = now - timedelta(days=30)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            recent_7_days = 0
            recent_30_days = 0
            today_count = 0
            
            for report in reports:
                if report.created_at:
                    report_date = report.created_at
                    
                    # 确保 report_date 也是 offset-aware
                    if report_date.tzinfo is None:
                        report_date = report_date.replace(tzinfo=timezone.utc)
                    
                    if report_date >= last_7_days:
                        recent_7_days += 1
                    
                    if report_date >= last_30_days:
                        recent_30_days += 1
                    
                    if report_date >= today_start:
                        today_count += 1
            
            return {
                "total_reports": total_reports,
                "by_status": by_status,
                "by_tax_type": by_tax_type,
                "by_risk_level": by_risk_level,
                "needs_review_count": needs_review_count,
                "recent_activity": {
                    "last_7_days": recent_7_days,
                    "last_30_days": recent_30_days,
                    "today": today_count
                }
            }
            
        except Exception as e:
            print(f"❌ [税务报告服务] 获取统计信息失败: {str(e)}")
            return {
                "total_reports": 0,
                "by_status": {},
                "by_tax_type": {},
                "by_risk_level": {},
                "needs_review_count": 0,
                "recent_activity": {
                    "last_7_days": 0,
                    "last_30_days": 0,
                    "today": 0
                },
                "error": str(e)
            }
    
    async def create_manual_tax_report(
        self,
        user_id: str,
        tenant_id: str,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        创建手动录入的税务报告
        
        支持管理员直接录入财务数据创建税务报告
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            input_data: 手动录入的数据
            
        Returns:
            创建的报告信息
        """
        try:
            report_id = str(uuid.uuid4())
            
            tax_type = input_data.get("tax_type", "vat")
            fiscal_year = input_data.get("fiscal_year", datetime.now().year)
            fiscal_period = input_data.get("fiscal_period")
            
            revenue = input_data.get("revenue", 0)
            taxable_sales = input_data.get("taxable_sales", 0)
            input_tax = input_data.get("input_tax", 0)
            output_tax = input_data.get("output_tax", 0)
            vat_rate = input_data.get("vat_rate", 0.13)
            
            key_metrics = {
                "revenue": revenue,
                "taxable_sales": taxable_sales,
                "input_tax": input_tax,
                "output_tax": output_tax,
                "vat_rate": vat_rate,
                "total_invoices": input_data.get("total_invoices", 0),
            }
            
            report = await self.repository.create_report(
                user_id=user_id,
                tenant_id=tenant_id,
                filename=f"manual_{report_id}.json",
                original_filename=f"手动录入_{fiscal_year}_{fiscal_period or ''}.json",
                file_type="manual",
                file_size=len(str(input_data)),
                minio_path=f"{tenant_id}/{user_id}/tax-report/{report_id}/manual.json",
                tax_type=tax_type,
                tax_period_year=fiscal_year,
                tax_period_month=int(fiscal_period.split("-")[1]) if fiscal_period and "-" in fiscal_period else None,
                status="pending",
                processing_message="手动录入税务报告，待处理",
                needs_human_review="false",
                pii_anonymized="true",
                key_metrics=key_metrics,
            )
            
            print(f"✅ [税务报告服务] 手动录入报告创建成功: {report_id}")
            
            return {
                "id": str(report.id),
                "tenant_id": str(report.tenant_id),
                "user_id": str(report.user_id),
                "filename": report.filename,
                "original_filename": report.original_filename,
                "file_type": report.file_type,
                "tax_type": report.tax_type,
                "status": report.status,
                "key_metrics": key_metrics,
                "created_at": report.created_at,
            }
            
        except Exception as e:
            print(f"❌ [税务报告服务] 手动录入报告创建失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def process_tax_report_background(
        self,
        report_id: str,
        user_id: str,
        tenant_id: str
    ):
        """
        后台处理税务报告（占位方法）
        
        注意：实际处理逻辑已移至 _process_tax_report_async
        此方法保留用于兼容现有调用
        
        Args:
            report_id: 报告ID
            user_id: 用户ID
            tenant_id: 租户ID
        """
        print(f"ℹ️ [税务报告服务] process_tax_report_background 被调用，但实际处理已在 _process_tax_report_async 中完成")
    
    async def delete_tax_report(
        self,
        report_id: str,
        tenant_id: str,
        user_id: str = None
    ) -> bool:
        """
        删除税务报告（租户+用户双重隔离）
        
        同时删除数据库记录和物理文件
        
        Args:
            report_id: 报告ID
            tenant_id: 租户ID
            user_id: 用户ID（可选，如果提供则仅删除自己的报告）
            
        Returns:
            bool: 是否成功删除
        """
        import os
        from pathlib import Path
        
        try:
            existing = await self.repository.get_by_id(report_id, tenant_id=tenant_id)
            
            if not existing:
                print(f"⚠️ [税务报告服务] 报告不存在: {report_id}")
                return False
            
            if user_id and str(existing.user_id) != user_id:
                print(f"⚠️ [税务报告服务] 用户无权删除此报告: {report_id}")
                return False
            
            file_path = Path("uploads/tax_reports") / existing.filename
            
            if file_path.exists():
                try:
                    os.remove(str(file_path))
                    print(f"✅ [税务报告服务] 删除物理文件: {file_path}")
                except OSError as e:
                    print(f"⚠️ [税务报告服务] 删除物理文件失败: {e}")
            
            deleted = await self.repository.delete(
                id=report_id,
                tenant_id=tenant_id
            )
            
            if deleted:
                print(f"✅ [税务报告服务] 删除报告成功: {report_id}")
                
                try:
                    from app.models.review_request import ReviewRequest
                    from sqlalchemy import delete, and_
                    from uuid import UUID
                    import logging
                    logger = logging.getLogger(__name__)
                    
                    try:
                        report_uuid = UUID(report_id)
                    except ValueError:
                        logger.error(f"❌ [税务报告服务] report_id格式无效: {report_id}")
                        return True
                    
                    delete_stmt = delete(ReviewRequest).where(
                        and_(
                            ReviewRequest.task_id == report_uuid,
                            ReviewRequest.tenant_id == tenant_id
                        )
                    )
                    
                    result = await self.db.execute(delete_stmt)
                    await self.db.commit()
                    
                    if result.rowcount > 0:
                        logger.info(f"✅ [税务报告服务] 删除审核请求成功: {result.rowcount}条, report_id={report_id}")
                        print(f"✅ [税务报告服务] 同步删除审核请求完成: {report_id}")
                    else:
                        logger.warning(f"⚠️ [税务报告服务] 未找到对应审核请求: {report_id}")
                except Exception as review_error:
                    logger.error(f"❌ [税务报告服务] 同步删除审核请求失败: {review_error}", exc_info=True)
                    print(f"⚠️ [税务报告服务] 同步删除审核请求失败: {review_error}")
            else:
                print(f"⚠️ [税务报告服务] 删除报告失败: {report_id}")
            
            return deleted
            
        except Exception as e:
            print(f"❌ [税务报告服务] 删除报告失败: {str(e)}")
            return False
