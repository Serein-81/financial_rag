"""
合同审核报告数据库模型
存储合同审核和分析报告数据
"""

import uuid
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey, Text, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum


class ContractType(str, enum.Enum):
    """合同类型"""
    PURCHASE = "purchase"  # 采购合同
    SALES = "sales"  # 销售合同
    SERVICE = "service"  # 服务合同
    LEASE = "lease"  # 租赁合同
    EMPLOYMENT = "employment"  # 劳动合同
    PARTNERSHIP = "partnership"  # 合作协议
    LOAN = "loan"  # 借款合同
    OTHER = "other"  # 其他


class ReviewStatus(str, enum.Enum):
    """审核状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class RiskLevel(str, enum.Enum):
    """风险级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ContractReviewReport(Base):
    """
    合同审核报告模型
    
    存储合同审核分析报告
    """
    __tablename__ = "contract_review_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)

    contract_name = Column(String(500), nullable=False)
    contract_type = Column(SQLEnum(ContractType), nullable=True)
    counterparty = Column(String(255), nullable=True)

    contract_value = Column(Float, nullable=True)
    currency = Column(String(10), default="CNY")

    original_text = Column(Text, nullable=True)

    review_status = Column(SQLEnum(ReviewStatus), nullable=False, default=ReviewStatus.PENDING)

    overall_risk_score = Column(Float, nullable=True)
    overall_risk_level = Column(SQLEnum(RiskLevel), nullable=True)

    basic_analysis = Column(JSONB, nullable=True)

    parties_info = Column(JSONB, nullable=True)
    effective_date = Column(DateTime(timezone=True), nullable=True)
    expiration_date = Column(DateTime(timezone=True), nullable=True)
    termination_conditions = Column(JSONB, nullable=True)

    clauses_analysis = Column(JSONB, nullable=True)
    risk_clauses = Column(JSONB, nullable=True)
    unfavorable_clauses = Column(JSONB, nullable=True)

    compliance_checks = Column(JSONB, nullable=True)

    comparison_result = Column(JSONB, nullable=True)

    suggestions = Column(JSONB, nullable=True)
    recommended_revisions = Column(JSONB, nullable=True)

    ai_analysis_summary = Column(Text, nullable=True)

    pdf_path = Column(String(1000), nullable=True)

    review_completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)

    expires_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<ContractReviewReport(id={self.id}, name={self.contract_name}, status={self.review_status})>"


class ContractClause(Base):
    """
    合同条款模型
    
    存储合同中的单个条款
    """
    __tablename__ = "contract_clauses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    report_id = Column(UUID(as_uuid=True), ForeignKey("contract_review_reports.id", ondelete="CASCADE"), nullable=False, index=True)

    clause_type = Column(String(50), nullable=False, index=True)
    clause_title = Column(String(255), nullable=True)
    clause_text = Column(Text, nullable=False)

    original_position = Column(Integer, nullable=True)
    page_number = Column(Integer, nullable=True)

    risk_level = Column(SQLEnum(RiskLevel), nullable=True)
    risk_score = Column(Float, nullable=True)

    is_standard = Column(Boolean, default=False)
    is_controversial = Column(Boolean, default=False)
    needs_attention = Column(Boolean, default=False)

    analysis = Column(JSONB, nullable=True)
    suggestions = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False)

    contract_report = relationship("ContractReviewReport", backref="clauses")

    def __repr__(self):
        return f"<ContractClause(id={self.id}, type={self.clause_type}, risk={self.risk_level})>"


class ContractComparisonHistory(Base):
    """
    合同对比历史模型
    
    存储合同对比记录
    """
    __tablename__ = "contract_comparison_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)

    comparison_name = Column(String(255), nullable=False)

    contract1_id = Column(UUID(as_uuid=True), ForeignKey("contract_review_reports.id", ondelete="CASCADE"), nullable=False)
    contract2_id = Column(UUID(as_uuid=True), ForeignKey("contract_review_reports.id", ondelete="CASCADE"), nullable=False)

    comparison_result = Column(JSONB, nullable=True)
    differences = Column(JSONB, nullable=True)

    similarity_score = Column(Float, nullable=True)

    summary = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f"<ContractComparisonHistory(id={self.id}, name={self.comparison_name})>"


class ContractTemplate(Base):
    """
    合同模板模型
    
    存储常用合同模板
    """
    __tablename__ = "contract_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(String(50), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    contract_type = Column(SQLEnum(ContractType), nullable=False)

    template_content = Column(Text, nullable=False)

    clauses_library = Column(JSONB, nullable=True)

    usage_count = Column(Integer, default=0)

    is_public = Column(Boolean, default=False)

    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_by = Column(UUID(as_uuid=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<ContractTemplate(id={self.id}, name={self.name}, type={self.contract_type})>"
