"""
税务报告模型
"""

import uuid
from sqlalchemy import Column, String, DateTime, Integer, BigInteger, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class TaxReport(Base):
    """
    税务报告模型
    
    存储税务报告的元数据和处理状态
    """
    __tablename__ = "tax_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 用户和租户信息（租户隔离）
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)
    
    # 关联的审计任务（可选）
    audit_task_id = Column(UUID(as_uuid=True), ForeignKey("audit_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # 文件信息
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf/excel/image
    file_size = Column(BigInteger, nullable=False)  # 文件大小（字节）
    minio_path = Column(String(1000), nullable=False)  # MinIO存储路径
    
    # 文件内容（可选，用于存储提取的文本）
    extracted_content = Column(Text, nullable=True)
    
    # 税务类型识别
    tax_type = Column(String(50), nullable=True)  # vat/income/personal/comprehensive
    tax_period_year = Column(Integer, nullable=True)
    tax_period_month = Column(Integer, nullable=True)
    
    # 处理状态
    status = Column(String(20), default="pending", index=True)  # pending/processing/completed/failed/pending_review
    processing_message = Column(String(500), nullable=True)  # 处理状态消息
    
    # 处理结果（JSONB格式存储）
    processing_result = Column(JSONB, nullable=True)  # 包含税务发现、风险评分等
    tax_validation_result = Column(JSONB, nullable=True)  # 税务逻辑验证结果
    
    # 置信度和风险评分
    confidence_score = Column(String(10), nullable=True)  # 0.0 - 1.0
    risk_score = Column(Integer, nullable=True)  # 0-100
    risk_level = Column(String(20), nullable=True)  # low/medium/high/critical
    
    # 是否需要人工审核
    needs_human_review = Column(String(5), default="false", index=True)
    review_request_id = Column(UUID(as_uuid=True), ForeignKey("review_requests.id", ondelete="SET NULL"), nullable=True)
    
    # PII脱敏标识
    pii_anonymized = Column(String(5), default="false")
    pii_mapping = Column(JSONB, nullable=True)
    
    # 关键指标（用于快速查询）
    key_metrics = Column(JSONB, nullable=True)  # {
        # "input_tax": 0,      # 进项税额
        # "output_tax": 0,     # 销项税额
        # "taxable_sales": 0,  # 应税销售额
        # "tax_amount": 0,     # 税额
        # "tax_rate": 0.13    # 税率
    # }
    
    # 发现的问题摘要
    issues_summary = Column(JSONB, nullable=True)  # 问题列表摘要
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # 过期时间（用于临时文件清理）
    
    # 关系
    task = relationship("AuditTask", foreign_keys=[audit_task_id], backref="tax_reports")
    review_request = relationship("ReviewRequest", foreign_keys=[review_request_id], backref="tax_report")
    
    def __repr__(self):
        return f"<TaxReport(id={self.id}, filename={self.filename}, status={self.status})>"
    
    @property
    def file_size_mb(self):
        """返回文件大小（MB）"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0
    
    @property
    def is_completed(self):
        """是否已完成"""
        return self.status == "completed"
    
    @property
    def needs_review(self):
        """是否需要人工审核"""
        return self.needs_human_review == "true" or self.status == "pending_review"


class TaxReportDocument(Base):
    """
    税务报告文档关联表
    
    用于处理批量上传的多个文档
    """
    __tablename__ = "tax_report_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联的税务报告
    tax_report_id = Column(UUID(as_uuid=True), ForeignKey("tax_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 文档信息
    filename = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    minio_path = Column(String(1000), nullable=False)
    
    # 处理状态
    status = Column(String(20), default="pending", index=True)  # pending/processed/failed
    processing_message = Column(String(500), nullable=True)
    
    # 提取的内容
    extracted_content = Column(Text, nullable=True)
    
    # OCR结果（如果适用）
    ocr_result = Column(JSONB, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # 关系
    tax_report = relationship("TaxReport", backref="documents")
    
    def __repr__(self):
        return f"<TaxReportDocument(id={self.id}, filename={self.filename})>"
