"""
税务报告服务层

负责税务报告的核心业务逻辑处理
"""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.tax_report import TaxReport
from app.services.minio_service import minio_service
from app.services.pii_anonymizer import pii_anonymizer
from app.multi_agent_system.coordinator import AgentCoordinator


class TaxReportService:
    """
    税务报告服务
    
    核心功能：
    1. 税务报告处理流程编排
    2. 文件解析和内容提取
    3. PII脱敏处理
    4. Agent编排集成
    5. 状态管理和通知
    """
    
    def __init__(self, db: AsyncSession = None):
        """初始化服务"""
        self.db = db
        self.processing_stages = [
            "文件下载",
            "文件解析",
            "内容提取",
            "PII脱敏",
            "Agent处理",
            "税务逻辑验证",
            "结果汇总"
        ]
        print("📄 [税务报告服务] 初始化完成")
    
    async def check_duplicate_report(
        self,
        tenant_id: str,
        original_filename: str,
        file_hash: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        检测是否存在重复的报告
        
        Args:
            tenant_id: 租户ID
            original_filename: 原始文件名
            file_hash: 文件哈希（可选）
            
        Returns:
            如果存在重复返回报告信息，否则返回 None
        """
        async with AsyncSessionLocal() as db:
            try:
                # 标准化文件名：去除首尾空格，不区分大小写
                normalized_filename = original_filename.strip()
                
                print(f"🔍 [重复检测] 租户ID: {tenant_id}")
                print(f"🔍 [重复检测] 原始文件名: '{original_filename}'")
                print(f"🔍 [重复检测] 标准化文件名: '{normalized_filename}'")
                
                # 检查相同文件名是否存在（不区分大小写）
                query = text("""
                    SELECT id, original_filename, status, created_at, 
                           confidence_score, risk_level
                    FROM tax_reports 
                    WHERE tenant_id = :tenant_id 
                    AND TRIM(original_filename) = TRIM(:filename)
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                result = await db.execute(query, {
                    "tenant_id": tenant_id,
                    "filename": normalized_filename
                })
                existing = result.fetchone()
                
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
            tenant_id: 租户ID
            file: 上传的文件对象
            tax_type: 税种类型
            tax_period_year: 税务年度
            tax_period_month: 税务月份
            description: 报告描述
            file_validation_result: 文件验证结果（来自TaxFileValidator）
            
        Returns:
            创建的报告信息
        """
        async with AsyncSessionLocal() as db:
            try:
                import uuid
                
                # 确保 tenant_id 是字符串（处理 asyncpg UUID 类型）
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
                
                # 生成MinIO路径（包含tenant_id/user_id/分类，与知识库模式一致）
                minio_path = f"{tenant_id}/{user_id}/tax-report/{report_id}/{filename}"
                
                # 上传到MinIO（如果服务可用）- 使用异步版本避免阻塞
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
                
                # 保存到数据库
                from app.models.tax_report import TaxReport
                
                # 从验证结果中提取置信度和关键指标
                confidence_score = None
                key_metrics = None
                tax_validation_result = None
                
                if file_validation_result:
                    confidence_score = file_validation_result.get("confidence")
                    extracted_info = file_validation_result.get("extracted_info", {})
                    
                    # 构建关键指标
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
                    
                    # 构建验证结果（不含is_valid和suggestions）
                    tax_validation_result = {
                        "confidence": confidence_score,
                        "found_keywords": file_validation_result.get("found_keywords", []),
                        "missing_indicators": file_validation_result.get("missing_indicators", []),
                        "extracted_info": extracted_info,
                    }
                
                report = TaxReport(
                    id=uuid.UUID(report_id),
                    user_id=uuid.UUID(user_id),
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
                    confidence_score=confidence_score,
                    key_metrics=key_metrics,
                    tax_validation_result=tax_validation_result,
                )
                
                db.add(report)
                await db.commit()
                await db.refresh(report)
                
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
                await db.rollback()
                raise ValueError(f"创建税务报告数据错误: {str(e)}")
            except (OSError, IOError) as e:
                print(f"❌ [税务报告服务] 创建报告IO错误: {str(e)}")
                await db.rollback()
                raise IOError(f"创建税务报告IO错误: {str(e)}")
            except Exception as e:
                print(f"❌ [税务报告服务] 创建报告失败: {str(e)}")
                await db.rollback()
                raise ValueError(f"创建税务报告失败: {str(e)}")
    
    async def create_manual_tax_report(
        self,
        user_id: str,
        tenant_id: str,
        input_data: dict,
    ) -> dict:
        """
        手动录入税务报告
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            input_data: 手动录入的数据
            
        Returns:
            创建的报告信息
        """
        async with AsyncSessionLocal() as db:
            try:
                import uuid
                from datetime import datetime
                
                if not isinstance(tenant_id, str):
                    tenant_id = str(tenant_id)
                if not isinstance(user_id, str):
                    user_id = str(user_id)
                
                report_id = str(uuid.uuid4())
                
                # 根据税种类型生成文件名
                tax_type = input_data.get("tax_type", "manual")
                fiscal_year = input_data.get("fiscal_year", datetime.now().year)
                fiscal_period = input_data.get("fiscal_period", "")
                filename = f"手动录入_{tax_type}_{fiscal_year}_{fiscal_period}.json"
                
                # 构建关键指标
                key_metrics = {
                    "revenue": input_data.get("revenue", 0),
                    "taxable_sales": input_data.get("taxable_sales", 0),
                    "tax_free_sales": input_data.get("tax_free_sales", 0),
                    "input_tax": input_data.get("input_tax", 0),
                    "output_tax": input_data.get("output_tax", 0),
                    "vat_rate": input_data.get("vat_rate", 0.13),
                    "total_expenses": input_data.get("total_expenses", 0),
                    "deductible_expenses": input_data.get("deductible_expenses", 0),
                    "taxable_income": input_data.get("taxable_income", 0),
                    "corporate_tax_rate": input_data.get("corporate_tax_rate", 0.25),
                    "total_payroll": input_data.get("total_payroll", 0),
                    "total_invoices": input_data.get("total_invoices", 0),
                    "input_invoice_count": input_data.get("input_invoice_count", 0),
                    "output_invoice_count": input_data.get("output_invoice_count", 0),
                }
                
                # 计算税额
                tax_amount = 0
                if tax_type == "vat":
                    tax_amount = (input_data.get("output_tax", 0) - input_data.get("input_tax", 0))
                elif tax_type == "income":
                    tax_amount = input_data.get("taxable_income", 0) * input_data.get("corporate_tax_rate", 0.25)
                
                report = TaxReport(
                    id=uuid.UUID(report_id),
                    user_id=uuid.UUID(user_id),
                    tenant_id=tenant_id,
                    filename=filename,
                    original_filename=filename,
                    file_type="manual",
                    file_size=0,
                    minio_path=None,
                    tax_type=tax_type,
                    tax_period_year=input_data.get("fiscal_year"),
                    tax_period_month=int(fiscal_period.split("-")[-1]) if fiscal_period and "-" in fiscal_period else None,
                    status="pending",
                    processing_message="手动录入完成，等待AI分析",
                    needs_human_review="false",
                    pii_anonymized="true",
                    confidence_score=1.0,
                    key_metrics=key_metrics,
                )
                
                db.add(report)
                await db.commit()
                await db.refresh(report)
                
                print(f"✅ [税务报告服务] 手动创建报告成功: {report_id}")
                
                result = {
                    "id": str(report.id),
                    "tenant_id": str(report.tenant_id),
                    "user_id": str(report.user_id),
                    "filename": report.filename,
                    "original_filename": report.original_filename,
                    "tax_type": report.tax_type,
                    "status": report.status,
                    "created_at": report.created_at,
                    "key_metrics": key_metrics,
                    "needs_analysis": input_data.get("run_analysis", True),
                }
                
                # 如果需要运行分析，触发后台处理
                if input_data.get("run_analysis", True):
                    try:
                        await self.process_tax_report(report_id, tenant_id)
                        result["analysis_triggered"] = True
                    except Exception as e:
                        print(f"⚠️ [税务报告服务] 手动报告分析触发失败: {str(e)}")
                        result["analysis_triggered"] = False
                        result["analysis_error"] = str(e)
                else:
                    result["analysis_triggered"] = False
                
                return result
                
            except (ValueError, KeyError) as e:
                print(f"❌ [税务报告服务] 手动创建数据错误: {str(e)}")
                await db.rollback()
                raise ValueError(f"手动创建税务报告数据错误: {str(e)}")
            except (OSError, IOError) as e:
                print(f"❌ [税务报告服务] 手动创建IO错误: {str(e)}")
                await db.rollback()
                raise IOError(f"手动创建税务报告IO错误: {str(e)}")
            except Exception as e:
                print(f"❌ [税务报告服务] 手动创建失败: {str(e)}")
                await db.rollback()
                raise ValueError(f"手动创建税务报告失败: {str(e)}")
    
    async def process_tax_report_background(
        self,
        report_id: str,
        user_id: str,
        tenant_id: str
    ):
        """
        后台处理税务报告
        
        Args:
            report_id: 报告ID
            user_id: 用户ID
            tenant_id: 租户ID
        """
        try:
            await self.process_tax_report(report_id, tenant_id)
        except (ValueError, KeyError) as e:
            print(f"❌ [税务报告服务] 后台处理数据错误: {report_id}, {str(e)}")
        except (OSError, IOError) as e:
            print(f"❌ [税务报告服务] 后台处理IO错误: {report_id}, {str(e)}")
        except Exception as e:
            print(f"❌ [税务报告服务] 后台处理失败: {report_id}, {str(e)}")
    
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
            tenant_id: 租户ID
            user_id: 用户ID（可选，用于过滤用户自己的报告）
            skip: 跳过的记录数
            limit: 返回的记录数
            status: 状态过滤
            tax_type: 税种类型过滤
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            (报告列表, 总数)
        """
        async with AsyncSessionLocal() as db:
            try:
                # 构建查询条件
                conditions = ["tenant_id = :tenant_id"]
                params = {"tenant_id": tenant_id, "skip": skip, "limit": limit}
                
                if user_id:
                    conditions.append("user_id = :user_id")
                    params["user_id"] = user_id
                
                if status:
                    conditions.append("status = :status")
                    params["status"] = status
                
                if tax_type:
                    conditions.append("tax_type = :tax_type")
                    params["tax_type"] = tax_type
                
                if start_date:
                    conditions.append("created_at >= :start_date")
                    params["start_date"] = start_date
                
                if end_date:
                    conditions.append("created_at <= :end_date")
                    params["end_date"] = end_date
                
                where_clause = " AND ".join(conditions)
                
                # 查询总数
                count_query = text(f"SELECT COUNT(*) FROM tax_reports WHERE {where_clause}")
                result = await db.execute(count_query, params)
                total = result.scalar() or 0
                
                # 查询列表
                list_query = text(f"""
                    SELECT * FROM tax_reports 
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    OFFSET :skip LIMIT :limit
                """)
                result = await db.execute(list_query, params)
                reports = result.fetchall()
                
                # 转换为字典列表
                report_list = []
                for report in reports:
                    # 手动计算 file_size_mb
                    file_size_mb = round(report.file_size / (1024 * 1024), 2) if report.file_size else 0
                    report_dict = {
                        "id": str(report.id),
                        "tenant_id": report.tenant_id,
                        "user_id": str(report.user_id),
                        "filename": report.filename,
                        "original_filename": report.original_filename,
                        "file_type": report.file_type,
                        "file_size": report.file_size,
                        "file_size_mb": file_size_mb,
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
                    report_list.append(report_dict)
                
                return report_list, total
                
            except (ValueError, KeyError) as e:
                print(f"❌ [税务报告服务] 查询列表数据错误: {str(e)}")
                return [], 0
            except (OSError, IOError) as e:
                print(f"❌ [税务报告服务] 查询列表IO错误: {str(e)}")
                return [], 0
            except Exception as e:
                print(f"❌ [税务报告服务] 查询列表失败: {str(e)}")
                return [], 0
    
    async def get_tax_report(self, report_id: str, tenant_id: str):
        """
        获取单个税务报告详情
        
        Args:
            report_id: 报告ID
            tenant_id: 租户ID
            
        Returns:
            报告详情
        """
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    text("""
                    SELECT * FROM tax_reports 
                    WHERE id = :id AND tenant_id = :tenant_id
                    """),
                    {"id": report_id, "tenant_id": tenant_id}
                )
                report = result.fetchone()
                
                if not report:
                    return None
                
                file_size_mb = round(report.file_size / (1024 * 1024), 2) if report.file_size else 0
                
                # 解析 processing_result JSON，提取 issues
                issues = []
                rag_references = []
                tax_validation_result = None
                
                # 将 risk_level 映射为 severity（TaxIssueSchema 要求 severity 字段）
                def map_severity(risk_level):
                    if risk_level == 'info':
                        return 'low'
                    return risk_level if risk_level in ['low', 'medium', 'high', 'critical'] else 'low'
                
                if report.processing_result:
                    try:
                        import json
                        proc_result = json.loads(report.processing_result) if isinstance(report.processing_result, str) else report.processing_result
                        
                        # 提取税务发现
                        tax_findings = proc_result.get('tax_findings', [])
                        for finding in tax_findings:
                            recs = finding.get('recommendations', [])
                            recommendations_str = '; '.join(recs) if recs else None
                            issues.append({
                                "id": finding.get('id', ''),
                                "severity": map_severity(finding.get('risk_level', 'info')),
                                "category": finding.get('category', '税务'),
                                "description": finding.get('description', ''),
                                "evidence": finding.get('evidence', []),
                                "legal_basis": finding.get('legal_basis'),
                                "recommendation": recommendations_str,
                                "confidence": finding.get('confidence', 0.0),
                            })
                        
                        # 提取财务发现
                        finance_findings = proc_result.get('finance_findings', [])
                        for finding in finance_findings:
                            recs = finding.get('recommendations', [])
                            recommendations_str = '; '.join(recs) if recs else None
                            issues.append({
                                "id": finding.get('id', ''),
                                "severity": map_severity(finding.get('risk_level', 'info')),
                                "category": finding.get('category', '财务'),
                                "description": finding.get('description', ''),
                                "evidence": finding.get('evidence', []),
                                "legal_basis": finding.get('legal_basis'),
                                "recommendation": recommendations_str,
                                "confidence": finding.get('confidence', 0.0),
                            })
                        
                        # 提取法务发现
                        legal_findings = proc_result.get('legal_findings', [])
                        for finding in legal_findings:
                            recs = finding.get('recommendations', [])
                            recommendations_str = '; '.join(recs) if recs else None
                            issues.append({
                                "id": finding.get('id', ''),
                                "severity": map_severity(finding.get('risk_level', 'info')),
                                "category": finding.get('category', '法务'),
                                "description": finding.get('description', ''),
                                "evidence": finding.get('evidence', []),
                                "legal_basis": finding.get('legal_basis'),
                                "recommendation": recommendations_str,
                                "confidence": finding.get('confidence', 0.0),
                            })
                        
                        # 提取 RAG 上下文
                        rag_contexts = proc_result.get('rag_contexts', [])
                        for ctx in rag_contexts:
                            rag_references.append({
                                "content": ctx.get('content', '')[:200],
                                "source": ctx.get('source', ''),
                                "relevance": ctx.get('relevance', 0.0)
                            })
                        
                        # 提取税务验证结果
                        tax_validation_result = proc_result.get('tax_validation')
                        
                    except (json.JSONDecodeError, Exception) as e:
                        print(f"⚠️ [税务报告服务] 解析 processing_result 失败: {str(e)}")
                
                return {
                    "id": str(report.id),
                    "tenant_id": report.tenant_id,
                    "user_id": str(report.user_id),
                    "filename": report.filename,
                    "original_filename": report.original_filename,
                    "file_type": report.file_type,
                    "file_size": report.file_size,
                    "file_size_mb": file_size_mb,
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
                    "processing_result": None,
                    "tax_validation_result": tax_validation_result,
                    "key_metrics": report.key_metrics,
                    "issues": issues,
                    "rag_references": rag_references,
                    "indicators": [],
                    "created_at": report.created_at,
                    "updated_at": report.updated_at,
                    "completed_at": report.completed_at,
                }
                
            except (ValueError, KeyError) as e:
                print(f"❌ [税务报告服务] 查询详情数据错误: {str(e)}")
                return None
            except (OSError, IOError) as e:
                print(f"❌ [税务报告服务] 查询详情IO错误: {str(e)}")
                return None
            except Exception as e:
                print(f"❌ [税务报告服务] 查询详情失败: {str(e)}")
                return None
    
    async def get_statistics(self, tenant_id: str) -> dict:
        """
        获取税务报告统计信息
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            统计信息
        """
        async with AsyncSessionLocal() as db:
            try:
                # 统计总数
                total_result = await db.execute(
                    text("SELECT COUNT(*) FROM tax_reports WHERE tenant_id = :tenant_id"),
                    {"tenant_id": tenant_id}
                )
                total = total_result.scalar() or 0
                
                # 按状态统计
                status_result = await db.execute(
                    text("""
                    SELECT status, COUNT(*) as count 
                    FROM tax_reports 
                    WHERE tenant_id = :tenant_id
                    GROUP BY status
                    """),
                    {"tenant_id": tenant_id}
                )
                status_counts = {row.status: row.count for row in status_result.fetchall()}
                
                # 按税种统计
                tax_type_result = await db.execute(
                    text("""
                    SELECT tax_type, COUNT(*) as count 
                    FROM tax_reports 
                    WHERE tenant_id = :tenant_id AND tax_type IS NOT NULL
                    GROUP BY tax_type
                    """),
                    {"tenant_id": tenant_id}
                )
                tax_type_counts = {row.tax_type: row.count for row in tax_type_result.fetchall()}
                
                # 需要审核的数量
                review_result = await db.execute(
                    text("""
                    SELECT COUNT(*) FROM tax_reports 
                    WHERE tenant_id = :tenant_id AND needs_human_review = 'true'
                    """),
                    {"tenant_id": tenant_id}
                )
                needs_review = review_result.scalar() or 0
                
                return {
                    "total": total,
                    "by_status": status_counts,
                    "by_tax_type": tax_type_counts,
                    "needs_review": needs_review,
                }
                
            except (ValueError, KeyError) as e:
                print(f"❌ [税务报告服务] 统计数据错误: {str(e)}")
                return {"total": 0, "by_status": {}, "by_tax_type": {}, "needs_review": 0}
            except (OSError, IOError) as e:
                print(f"❌ [税务报告服务] 统计IO错误: {str(e)}")
                return {"total": 0, "by_status": {}, "by_tax_type": {}, "needs_review": 0}
            except Exception as e:
                print(f"❌ [税务报告服务] 统计失败: {str(e)}")
                return {"total": 0, "by_status": {}, "by_tax_type": {}, "needs_review": 0}
    
    async def get_processing_status(self, report_id: str, tenant_id: str) -> dict:
        """
        获取报告处理状态
        
        Args:
            report_id: 报告ID
            tenant_id: 租户ID
            
        Returns:
            状态信息
        """
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    text("""
                    SELECT status, processing_message, needs_human_review, completed_at, created_at
                    FROM tax_reports 
                    WHERE id = :id AND tenant_id = :tenant_id
                    """),
                    {"id": report_id, "tenant_id": tenant_id}
                )
                report = result.fetchone()
                
                if not report:
                    return None
                
                # 计算进度百分比
                progress_percent = 0
                if report.status == "completed":
                    progress_percent = 100
                elif report.status == "processing":
                    if report.created_at and report.completed_at:
                        total_seconds = (report.completed_at - report.created_at).total_seconds()
                        if total_seconds > 0:
                            elapsed = (datetime.utcnow() - report.created_at).total_seconds()
                            progress_percent = min(int((elapsed / total_seconds) * 100), 95)
                    else:
                        progress_percent = 50
                
                return {
                    "id": report_id,
                    "status": report.status,
                    "processing_message": report.processing_message,
                    "needs_human_review": report.needs_human_review == "true",
                    "progress_percent": progress_percent,
                }
                
            except (ValueError, KeyError) as e:
                print(f"❌ [税务报告服务] 查询状态数据错误: {str(e)}")
                return None
            except (OSError, IOError) as e:
                print(f"❌ [税务报告服务] 查询状态IO错误: {str(e)}")
                return None
            except Exception as e:
                print(f"❌ [税务报告服务] 查询状态失败: {str(e)}")
                return None
    
    async def delete_tax_report(self, report_id: str, tenant_id: str) -> bool:
        """
        删除税务报告
        
        Args:
            report_id: 报告ID
            tenant_id: 租户ID
            
        Returns:
            是否成功
        """
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    text("""
                    DELETE FROM tax_reports 
                    WHERE id = :id AND tenant_id = :tenant_id
                    """),
                    {"id": report_id, "tenant_id": tenant_id}
                )
                await db.commit()
                return result.rowcount > 0
                
            except (ValueError, KeyError) as e:
                print(f"❌ [税务报告服务] 删除数据错误: {str(e)}")
                return False
            except (OSError, IOError) as e:
                print(f"❌ [税务报告服务] 删除IO错误: {str(e)}")
                return False
            except Exception as e:
                print(f"❌ [税务报告服务] 删除失败: {str(e)}")
                return False
    
    async def process_tax_report(self, report_id: str, tenant_id: str):
        """
        处理税务报告的完整流程
        
        Args:
            report_id: 报告ID
            tenant_id: 租户ID
        """
        print(f"📄 [税务报告服务] 开始处理报告 {report_id}")
        
        async with AsyncSessionLocal() as db:
            try:
                # 1. 获取报告记录
                result = await db.execute(
                    text("SELECT * FROM tax_reports WHERE id = :id"),
                    {"id": report_id}
                )
                report = result.fetchone()
                
                if not report:
                    print(f"❌ [税务报告服务] 报告不存在: {report_id}")
                    return
                
                # 更新状态为处理中
                await self._update_status(db, report_id, "processing", "开始处理税务报告")
                
                # 2. 下载文件
                await self._update_status(db, report_id, "processing", "正在下载文件...")
                file_content = await minio_service.download_document_async(report.minio_path)
                
                # 3. 解析文件
                await self._update_status(db, report_id, "processing", "正在解析文件...")
                content = await self._parse_file(report.filename, file_content, report.file_type)
                
                # 4. PII脱敏
                await self._update_status(db, report_id, "processing", "正在进行数据脱敏...")
                anonymized_content = pii_anonymizer.anonymize(content)
                pii_mapping = {}
                
                # 5. Agent处理（核心处理逻辑）
                await self._update_status(db, report_id, "processing", "正在进行AI分析...")
                processing_result = await self._process_with_agents(
                    report_id=report_id,
                    tenant_id=tenant_id,
                    content=anonymized_content,
                    file_type=report.file_type
                )
                
                # 6. 更新报告记录
                await self._update_report_result(db, report_id, processing_result, pii_mapping)
                
                # 7. 检查是否需要人工审核
                if processing_result.get('needs_human_review', False):
                    await self._update_status(db, report_id, "pending_review", "需要人工审核")
                    await self._create_review_request(db, report_id, tenant_id, processing_result)
                else:
                    await self._update_status(db, report_id, "completed", "处理完成")
                
                print(f"✅ [税务报告服务] 报告处理完成: {report_id}")
                
            except (ValueError, KeyError) as e:
                error_msg = str(e)[:497] + "..." if len(str(e)) > 500 else str(e)
                print(f"❌ [税务报告服务] 处理数据错误: {report_id}, 错误: {str(e)}")
                await self._update_status(db, report_id, "failed", f"处理失败: {error_msg}")
            except (OSError, IOError) as e:
                error_msg = str(e)[:497] + "..." if len(str(e)) > 500 else str(e)
                print(f"❌ [税务报告服务] 处理IO错误: {report_id}, 错误: {str(e)}")
                await self._update_status(db, report_id, "failed", f"处理失败: {error_msg}")
            except Exception as e:
                error_msg = str(e)[:497] + "..." if len(str(e)) > 500 else str(e)
                print(f"❌ [税务报告服务] 处理失败: {report_id}, 错误: {str(e)}")
                await self._update_status(db, report_id, "failed", f"处理失败: {error_msg}")
    
    async def _parse_file(self, filename: str, content: bytes, file_type: str) -> str:
        """
        解析文件内容
        
        Args:
            filename: 文件名
            content: 文件内容
            file_type: 文件类型
            
        Returns:
            解析后的文本内容
        """
        try:
            # 根据文件类型选择解析方式
            if file_type in ['pdf']:
                # PDF解析
                from app.parsers.pdf_parser import PDFParser
                parser = PDFParser()
                text = await parser.parse(content)
            elif file_type in ['xlsx', 'xls']:
                # Excel解析
                from app.parsers.excel_parser import ExcelParser
                parser = ExcelParser()
                text = await parser.parse(content)
            elif file_type in ['jpg', 'jpeg', 'png']:
                # 图片OCR
                from app.services.ocr_service import ocr_service
                text = await ocr_service.recognize(content)
            else:
                # 通用文本解析
                text = content.decode('utf-8', errors='ignore')
            
            return text
            
        except (UnicodeDecodeError, UnicodeEncodeError) as e:
            print(f"⚠️ [税务报告服务] 文件解码错误: {str(e)}")
            return content.decode('utf-8', errors='ignore')
        except (OSError, IOError) as e:
            print(f"⚠️ [税务报告服务] 文件IO错误: {str(e)}")
            return content.decode('utf-8', errors='ignore')
        except (ValueError, KeyError) as e:
            print(f"⚠️ [税务报告服务] 文件解析数据错误: {str(e)}")
            return content.decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"⚠️ [税务报告服务] 文件解析失败: {str(e)}")
            return content.decode('utf-8', errors='ignore')
    
    async def _process_with_agents(
        self,
        report_id: str,
        tenant_id: str,
        content: str,
        file_type: str
    ) -> Dict[str, Any]:
        """
        使用Agent编排器处理税务报告
        
        Args:
            report_id: 报告ID
            tenant_id: 租户ID
            content: 处理后的内容
            file_type: 文件类型
            
        Returns:
            处理结果
        """
        try:
            # 初始化Agent协调器（租户隔离）
            coordinator = AgentCoordinator(
                tenant_id=tenant_id,
                user_id="system"  # 系统处理
            )
            
            # 构建文档对象
            documents = [{
                "id": report_id,
                "filename": f"report_{report_id}.{file_type}",
                "content": content,
                "type": file_type
            }]
            
            # 准备初始状态
            from app.multi_agent_system.state import create_initial_state
            initial_state = create_initial_state(
                task_id=report_id,
                tenant_id=tenant_id,
                user_id="system",
                audit_type="tax",
                documents=documents
            )
            
            # 执行审查流程
            result = await coordinator.execute_audit(initial_state)
            
            # 提取结果
            processing_result = {
                "status": "success",
                "report_id": report_id,
                "tax_findings": result.get('tax_findings', []),
                "finance_findings": result.get('finance_findings', []),
                "legal_findings": result.get('legal_findings', []),
                "tax_validation": result.get('tax_validation'),
                "confidence_scores": result.get('confidence_scores', {}),
                "conflicts": result.get('conflicts', []),
                "evidence_gaps": result.get('evidence_gaps', []),
                "rag_contexts": result.get('rag_contexts', []),
                "needs_human_review": result.get('needs_human_review', False),
                "review_trigger_reason": result.get('review_trigger_reason'),
                "overall_risk_score": self._calculate_risk_score(result),
                "risk_level": self._determine_risk_level(result)
            }
            
            return processing_result
            
        except (ValueError, KeyError) as e:
            print(f"❌ [税务报告服务] Agent处理数据错误: {str(e)}")
            return {
                "status": "error",
                "error_message": str(e),
                "needs_human_review": True,
                "review_trigger_reason": "agent_processing_data_error"
            }
        except (OSError, IOError) as e:
            print(f"❌ [税务报告服务] Agent处理IO错误: {str(e)}")
            return {
                "status": "error",
                "error_message": str(e),
                "needs_human_review": True,
                "review_trigger_reason": "agent_processing_io_error"
            }
        except Exception as e:
            print(f"❌ [税务报告服务] Agent处理失败: {str(e)}")
            return {
                "status": "error",
                "error_message": str(e),
                "needs_human_review": True,
                "review_trigger_reason": "agent_processing_failed"
            }
    
    def _calculate_risk_score(self, result: Dict[str, Any]) -> float:
        """
        计算综合风险评分
        
        Args:
            result: Agent处理结果
            
        Returns:
            风险评分 (0-100)
        """
        score = 0.0
        
        # 基于发现数量
        tax_findings = result.get('tax_findings', [])
        score += min(len(tax_findings) * 5, 30)  # 最多30分
        
        # 基于税务验证错误
        tax_validation = result.get('tax_validation', {})
        errors = tax_validation.get('errors', [])
        high_severity = tax_validation.get('high_severity', 0)
        score += high_severity * 20  # 每个高严重错误20分
        score += len(errors) * 5  # 每个错误5分
        
        # 基于冲突
        conflicts = result.get('conflicts', [])
        score += len(conflicts) * 10  # 每个冲突10分
        
        # 基于置信度
        confidence_scores = result.get('confidence_scores', {})
        if confidence_scores:
            avg_confidence = sum(confidence_scores.values()) / len(confidence_scores)
            score += (1 - avg_confidence) * 20  # 低置信度增加风险
        
        return min(score, 100)
    
    def _determine_risk_level(self, result: Dict[str, Any]) -> str:
        """
        确定风险等级
        
        Args:
            result: Agent处理结果
            
        Returns:
            风险等级 (low/medium/high/critical)
        """
        score = self._calculate_risk_score(result)
        
        if score >= 80:
            return "critical"
        elif score >= 60:
            return "high"
        elif score >= 30:
            return "medium"
        else:
            return "low"
    
    async def _update_status(
        self,
        db: AsyncSession,
        report_id: str,
        status: str,
        message: str
    ):
        """
        更新报告状态
        
        Args:
            db: 数据库会话
            report_id: 报告ID
            status: 新状态
            message: 状态消息
        """
        try:
            await db.execute(
                text("""
                UPDATE tax_reports 
                SET status = :status,
                    processing_message = :message,
                    updated_at = :updated_at
                WHERE id = :id
                """),
                {
                    "id": report_id,
                    "status": status,
                    "message": message,
                    "updated_at": datetime.utcnow()
                }
            )
            await db.commit()
            
            # 发布状态更新到Redis（用于WebSocket推送）
            try:
                from app.services.redis_service import redis_service
                import json
                
                status_data = {
                    "report_id": report_id,
                    "status": status,
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                await redis_service.publish(
                    f"tax_report:status:{report_id}",
                    json.dumps(status_data)
                )
            except (OSError, IOError):
                print("⚠️ [税务报告服务] Redis连接失败，跳过状态发布")
            except (ValueError, KeyError) as e:
                print(f"⚠️ [税务报告服务] Redis数据错误，跳过状态发布: {e}")
            except RuntimeError as e:
                print(f"⚠️ [税务报告服务] Redis运行时错误，跳过状态发布: {str(e)}")
            except Exception:
                print("⚠️ [税务报告服务] Redis发布失败，跳过状态发布")
            
        except (ValueError, KeyError) as e:
            print(f"⚠️ [税务报告服务] 更新状态数据错误: {str(e)}")
        except (OSError, IOError) as e:
            print(f"⚠️ [税务报告服务] 更新状态IO错误: {str(e)}")
        except Exception as e:
            print(f"⚠️ [税务报告服务] 更新状态失败: {str(e)}")
    
    async def _update_report_result(
        self,
        db: AsyncSession,
        report_id: str,
        result: Dict[str, Any],
        pii_mapping: Dict[str, str]
    ):
        """
        更新报告处理结果
        
        Args:
            db: 数据库会话
            report_id: 报告ID
            result: 处理结果
            pii_mapping: PII映射
        """
        try:
            import json
            await db.execute(
                text("""
                UPDATE tax_reports 
                SET 
                    processing_result = :processing_result,
                    confidence_score = :confidence_score,
                    risk_score = :risk_score,
                    risk_level = :risk_level,
                    needs_human_review = :needs_human_review,
                    pii_anonymized = :pii_anonymized,
                    pii_mapping = :pii_mapping,
                    completed_at = :completed_at,
                    updated_at = :updated_at
                WHERE id = :id
                """),
                {
                    "id": report_id,
                    "processing_result": json.dumps(result, ensure_ascii=False, default=str),
                    "confidence_score": str(result.get('confidence_scores', {}).get('tax', 0.0)),
                    "risk_score": int(result.get('overall_risk_score', 0)),
                    "risk_level": result.get('risk_level', 'low'),
                    "needs_human_review": "true" if result.get('needs_human_review') else "false",
                    "pii_anonymized": "true",
                    "pii_mapping": json.dumps(pii_mapping, ensure_ascii=False),
                    "completed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            )
            await db.commit()
            print(f"✅ [税务报告服务] 更新结果成功: {report_id}")
            
        except (ValueError, KeyError) as e:
            print(f"⚠️ [税务报告服务] 更新结果数据错误: {str(e)}")
        except (OSError, IOError) as e:
            print(f"⚠️ [税务报告服务] 更新结果IO错误: {str(e)}")
        except Exception as e:
            print(f"⚠️ [税务报告服务] 更新结果失败: {str(e)}")
    
    async def _create_review_request(
        self,
        db: AsyncSession,
        report_id: str,
        tenant_id: str,
        result: Dict[str, Any]
    ):
        """
        创建人工审核请求
        
        Args:
            db: 数据库会话
            report_id: 报告ID
            tenant_id: 租户ID
            result: 处理结果
        """
        try:
            # 导入审核模型（将在Phase 2创建）
            from app.models.review_request import ReviewRequest
            
            review_id = str(uuid.uuid4())
            
            review_request = ReviewRequest(
                id=review_id,
                task_id=report_id,
                tenant_id=tenant_id,
                user_id="system",
                review_type="tax",
                priority="high" if result.get('overall_risk_score', 0) > 60 else "normal",
                trigger_reason=result.get('review_trigger_reason', 'low_confidence'),
                description=f"税务报告处理后需要人工审核，风险评分：{result.get('overall_risk_score', 0)}",
                content=result,
                status="pending"
            )
            
            db.add(review_request)
            
            # 更新报告记录
            await db.execute(
                text("""
                UPDATE tax_reports 
                SET review_request_id = :review_id
                WHERE id = :id
                """),
                {"id": report_id, "review_id": review_id}
            )
            
            await db.commit()
            
            print(f"✅ [税务报告服务] 创建审核请求: {review_id}")
            
        except (ValueError, KeyError) as e:
            print(f"⚠️ [税务报告服务] 创建审核请求数据错误: {str(e)}")
        except (OSError, IOError) as e:
            print(f"⚠️ [税务报告服务] 创建审核请求IO错误: {str(e)}")
        except Exception as e:
            print(f"⚠️ [税务报告服务] 创建审核请求失败: {str(e)}")
    
    async def get_report_with_details(self, report_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        获取报告详情（包含所有处理结果）
        
        Args:
            report_id: 报告ID
            tenant_id: 租户ID
            
        Returns:
            报告详情
        """
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("""
                SELECT * FROM tax_reports 
                WHERE id = :id AND tenant_id = :tenant_id
                """),
                {"id": report_id, "tenant_id": tenant_id}
            )
            report = result.fetchone()
            
            if not report:
                return None
            
            return {
                "id": str(report.id),
                "filename": report.original_filename,
                "file_type": report.file_type,
                "status": report.status,
                "processing_message": report.processing_message,
                "confidence_score": float(report.confidence_score) if report.confidence_score else None,
                "risk_score": report.risk_score,
                "risk_level": report.risk_level,
                "needs_human_review": report.needs_human_review == "true",
                "result": report.processing_result,
                "tax_validation": report.tax_validation_result,
                "created_at": report.created_at.isoformat() if report.created_at else None,
                "completed_at": report.completed_at.isoformat() if report.completed_at else None
            }


# 单例实例
tax_report_service = TaxReportService()
