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
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.tax_report import TaxReportRepository
from app.services.minio_service import minio_service
from app.services.pii_anonymizer import pii_anonymizer


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
            
        Returns:
            (报告列表, 总数)
        """
        try:
            # 使用 Repository 获取列表
            reports = await self.repository.list(
                tenant_id=tenant_id,
                skip=skip,
                limit=limit,
                order_by='created_at',
                order_desc=True,
                user_id=user_id if user_id else None,
                status=status if status else None,
                tax_type=tax_type if tax_type else None,
            )
            
            # 获取总数
            total = await self.repository.count(
                tenant_id=tenant_id,
                user_id=user_id if user_id else None,
                status=status if status else None,
                tax_type=tax_type if tax_type else None,
            )
            
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
