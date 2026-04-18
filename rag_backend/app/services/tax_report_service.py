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
    
    async def get_tax_report(self, report_id: str, tenant_id: str, user_id: str = None):
        """
        获取单个税务报告详情（租户+用户双重隔离）
        
        Args:
            report_id: 报告ID
            tenant_id: 租户ID
            user_id: 用户ID（可选，用于用户级隔离）
            
        Returns:
            报告详情
        """
        async with AsyncSessionLocal() as db:
            try:
                # 构建查询条件
                conditions = ["id = :id", "tenant_id = :tenant_id"]
                params = {"id": report_id, "tenant_id": tenant_id}
                
                # 添加用户级隔离
                if user_id:
                    conditions.append("user_id = :user_id")
                    params["user_id"] = user_id
                
                query = text(f"""
                    SELECT * FROM tax_reports 
                    WHERE {' AND '.join(conditions)}
                """)
                
                result = await db.execute(query, params)
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
                        
                        # 提取RAG上下文
                        rag_contexts = proc_result.get('rag_contexts', [])
                        for ctx in rag_contexts:
                            rag_references.append({
                                "source": ctx.get('source', ''),
                                "content": ctx.get('content', ''),
                                "relevance": ctx.get('relevance', 0.0),
                            })
                        
                        # 提取税务验证结果
                        tax_validation = proc_result.get('tax_validation')
                        if tax_validation:
                            tax_validation_result = {
                                "is_valid": tax_validation.get('is_valid', False),
                                "confidence": tax_validation.get('confidence', 0.0),
                                "issues": tax_validation.get('issues', []),
                                "suggestions": tax_validation.get('suggestions', []),
                            }
                        
                    except (json.JSONDecodeError, ValueError, KeyError) as e:
                        print(f"⚠️ [税务报告服务] 解析处理结果失败: {str(e)}")
                
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
                    "key_metrics": report.key_metrics,
                    "tax_validation_result": tax_validation_result,
                    "processing_result": report.processing_result,
                    "issues": issues,
                    "rag_references": rag_references,
                    "created_at": report.created_at,
                    "updated_at": report.updated_at,
                    "completed_at": report.completed_at,
                }
                
            except (ValueError, KeyError) as e:
                print(f"❌ [税务报告服务] 获取详情数据错误: {str(e)}")
                return None
            except (OSError, IOError) as e:
                print(f"❌ [税务报告服务] 获取详情IO错误: {str(e)}")
                return None
            except Exception as e:
                print(f"❌ [税务报告服务] 获取详情失败: {str(e)}")
                return None
    
    async def get_statistics(self, tenant_id: str, user_id: str = None) -> dict:
        """
        获取税务报告统计信息
        
        Args:
            tenant_id: 租户ID
            user_id: 用户ID（可选，用于用户级隔离）
            
        Returns:
            统计信息
        """
        async with AsyncSessionLocal() as db:
            try:
                # 构建基础查询条件
                base_conditions = "tenant_id = :tenant_id"
                params = {"tenant_id": tenant_id}
                
                if user_id:
                    base_conditions += " AND user_id = :user_id"
                    params["user_id"] = user_id
                
                # 按状态统计
                status_query = text(f"""
                    SELECT status, COUNT(*) as count
                    FROM tax_reports
                    WHERE {base_conditions}
                    GROUP BY status
                """)
                result = await db.execute(status_query, params)
                status_counts = {row.status: row.count for row in result}
                
                # 按税种类型统计
                tax_type_query = text(f"""
                    SELECT tax_type, COUNT(*) as count
                    FROM tax_reports
                    WHERE {base_conditions}
                    GROUP BY tax_type
                """)
                result = await db.execute(tax_type_query, params)
                tax_type_counts = {row.tax_type: row.count for row in result}
                
                # 计算需要审核的数量
                needs_review = status_counts.get('pending_review', 0)
                
                # 总数
                total_query = text(f"SELECT COUNT(*) as total FROM tax_reports WHERE {base_conditions}")
                result = await db.execute(total_query, params)
                total = result.scalar() or 0
                
                return {
                    "total": total,
                    "by_status": status_counts,
                    "by_tax_type": tax_type_counts,
                    "needs_review": needs_review
                }
                
            except (ValueError, KeyError) as e:
                print(f"❌ [税务报告服务] 统计数据错误: {str(e)}")
                return {"total": 0, "by_status": {}, "by_tax_type": {}, "needs_review": 0}
            except (OSError, IOError) as e:
                print(f"❌ [税务报告服务] 统计数据IO错误: {str(e)}")
                return {"total": 0, "by_status": {}, "by_tax_type": {}, "needs_review": 0}
            except Exception as e:
                print(f"❌ [税务报告服务] 统计失败: {str(e)}")
                return {"total": 0, "by_status": {}, "by_tax_type": {}, "needs_review": 0}
    
    async def get_processing_status(self, report_id: str, tenant_id: str, user_id: str = None) -> dict:
        """
        获取报告处理状态（租户+用户双重隔离）
        
        Args:
            report_id: 报告ID
            tenant_id: 租户ID
            user_id: 用户ID（可选，用于用户级隔离）
            
        Returns:
            状态信息
        """
        async with AsyncSessionLocal() as db:
            try:
                # 构建查询条件
                conditions = ["id = :id", "tenant_id = :tenant_id"]
                params = {"id": report_id, "tenant_id": tenant_id}
                
                # 添加用户级隔离
                if user_id:
                    conditions.append("user_id = :user_id")
                    params["user_id"] = user_id
                
                query = text(f"""
                    SELECT status, processing_message, needs_human_review, completed_at, created_at
                    FROM tax_reports 
                    WHERE {' AND '.join(conditions)}
                """)
                
                result = await db.execute(query, params)
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
    
    async def delete_tax_report(self, report_id: str, tenant_id: str, user_id: str = None) -> bool:
        """
        删除税务报告（租户+用户双重隔离）
        
        Args:
            report_id: 报告ID
            tenant_id: 租户ID
            user_id: 用户ID（可选，用于用户级隔离）
            
        Returns:
            是否成功
        """
        async with AsyncSessionLocal() as db:
            try:
                # 构建查询条件
                conditions = ["id = :id", "tenant_id = :tenant_id"]
                params = {"id": report_id, "tenant_id": tenant_id}
                
                # 添加用户级隔离
                if user_id:
                    conditions.append("user_id = :user_id")
                    params["user_id"] = user_id
                
                query = text(f"""
                    DELETE FROM tax_reports 
                    WHERE {' AND '.join(conditions)}
                """)
                
                result = await db.execute(query, params)
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
                
                # 5. 重复发票检测
                await self._update_status(db, report_id, "processing", "正在检测重复发票...")
                duplicate_invoice_issues = await self._detect_duplicate_invoices(
                    db, tenant_id, report.key_metrics, report_id
                )
                
                # 5. Agent处理（核心处理逻辑）
                await self._update_status(db, report_id, "processing", "正在进行AI分析...")
                processing_result = await self._process_with_agents(
                    report_id=report_id,
                    tenant_id=tenant_id,
                    content=anonymized_content,
                    file_type=report.file_type
                )
                
                # 6. 合并重复发票问题到处理结果
                if duplicate_invoice_issues:
                    if not processing_result.get('tax_findings'):
                        processing_result['tax_findings'] = []
                    processing_result['tax_findings'].extend(duplicate_invoice_issues)
                    processing_result['needs_human_review'] = True
                    processing_result['review_trigger_reason'] = 'duplicate_invoices_detected'
                
                # 7. 更新报告记录
                await self._update_report_result(db, report_id, processing_result, pii_mapping)
                
                # 8. 检查是否需要人工审核
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
    
    async def _detect_duplicate_invoices(
        self,
        db: AsyncSession,
        tenant_id: str,
        key_metrics: dict,
        current_report_id: str
    ) -> list:
        """
        检测重复发票（同一发票号在同一租户内多次出现）
        
        Args:
            db: 数据库会话
            tenant_id: 租户ID
            key_metrics: 当前报告的关键指标（包含提取的发票号）
            current_report_id: 当前报告ID
            
        Returns:
            重复发票问题列表
        """
        duplicate_issues = []
        
        try:
            # 获取当前报告提取的发票号
            invoice_numbers = key_metrics.get('invoice_numbers', []) if key_metrics else []
            
            if not invoice_numbers:
                print("📋 [重复发票检测] 当前报告未提取到发票号")
                return duplicate_issues
            
            print(f"🔍 [重复发票检测] 当前报告包含 {len(invoice_numbers)} 个发票号")
            
            # 查询同一租户内其他报告的发票号
            for invoice_number in invoice_numbers:
                query = text("""
                    SELECT tr.id, tr.original_filename, tr.created_at, tr.key_metrics
                    FROM tax_reports tr
                    WHERE tr.tenant_id = :tenant_id
                    AND tr.id != :current_report_id
                    AND tr.status IN ('completed', 'processing')
                    AND tr.key_metrics IS NOT NULL
                """)
                
                result = await db.execute(query, {
                    "tenant_id": tenant_id,
                    "current_report_id": current_report_id
                })
                
                other_reports = result.fetchall()
                
                # 检查每个报告中是否包含相同的发票号
                duplicate_details = []
                for other_report in other_reports:
                    other_key_metrics = other_report.key_metrics
                    if other_key_metrics and isinstance(other_key_metrics, dict):
                        other_invoice_numbers = other_key_metrics.get('invoice_numbers', [])
                        if invoice_number in other_invoice_numbers:
                            duplicate_details.append({
                                "report_id": str(other_report.id),
                                "filename": other_report.original_filename,
                                "created_at": other_report.created_at.isoformat() if other_report.created_at else None
                            })
                
                # 如果发现重复，添加问题记录
                if duplicate_details:
                    issue = {
                        "type": "duplicate_invoice",
                        "severity": "high",
                        "title": f"检测到重复发票号码: {invoice_number}",
                        "description": f"发票号码 {invoice_number} 在本租户内出现 {len(duplicate_details) + 1} 次",
                        "evidence": {
                            "invoice_number": invoice_number,
                            "occurrences": len(duplicate_details) + 1,
                            "duplicate_reports": duplicate_details
                        },
                        "recommendation": "请核实发票真实性，确认是否为重复报销或发票重复使用",
                        "auto_fixable": False
                    }
                    duplicate_issues.append(issue)
                    print(f"⚠️ [重复发票检测] 发现重复发票: {invoice_number}, 出现在 {len(duplicate_details) + 1} 个报告中")
            
            if not duplicate_issues:
                print("✅ [重复发票检测] 未发现重复发票")
            
            return duplicate_issues
            
        except Exception as e:
            print(f"⚠️ [重复发票检测] 检测失败: {str(e)}")
            return []
    