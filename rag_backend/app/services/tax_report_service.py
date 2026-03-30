"""
税务报告服务层

负责税务报告的核心业务逻辑处理
"""

import asyncio
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.tax_report import TaxReport
from app.services.minio_service import minio_service
from app.services.file_service import file_service
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
    
    async def create_tax_report(
        self,
        user_id: str,
        tenant_id: str,
        file,
        tax_type: str = None,
        tax_period_year: int = None,
        tax_period_month: int = None,
        description: str = None,
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
            
        Returns:
            创建的报告信息
        """
        async with AsyncSessionLocal() as db:
            try:
                import uuid
                from datetime import datetime
                
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
                
                # 生成MinIO路径
                minio_path = f"tax-reports/{tenant_id}/{report_id}/{filename}"
                
                # 上传到MinIO（如果服务可用）
                try:
                    minio_service.upload_document(
                        file_bytes=file_content,
                        object_name=minio_path,
                        content_type=file.content_type,
                        tenant_id=tenant_id
                    )
                except Exception as e:
                    print(f"⚠️ [税务报告服务] MinIO上传失败: {str(e)}")
                
                # 保存到数据库
                from app.models.tax_report import TaxReport
                from sqlalchemy.dialects.postgresql import UUID
                
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
                
            except Exception as e:
                print(f"❌ [税务报告服务] 创建报告失败: {str(e)}")
                await db.rollback()
                raise ValueError(f"创建税务报告失败: {str(e)}")
    
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
                        "created_at": report.created_at,
                        "updated_at": report.updated_at,
                        "completed_at": report.completed_at,
                    }
                    report_list.append(report_dict)
                
                return report_list, total
                
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
                    "processing_result": report.processing_result,
                    "tax_validation": report.tax_validation_result,
                    "issues": [],
                    "key_metrics": None,
                    "rag_references": [],
                    "indicators": [],
                    "created_at": report.created_at,
                    "updated_at": report.updated_at,
                    "completed_at": report.completed_at,
                }
                
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
                file_content = minio_service.download_document(report.minio_path, tenant_id)
                
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
            except Exception:
                pass  # Redis不可用不影响主流程
            
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
