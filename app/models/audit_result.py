"""
审查结果模型
"""

import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class AuditResult(Base):
    """审查结果"""
    __tablename__ = "audit_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联任务
    task_id = Column(UUID(as_uuid=True), ForeignKey("audit_tasks.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(50), nullable=False, index=True)
    
    # Agent 信息
    agent_name = Column(String(50), index=True)  # finance/tax/legal
    
    # 审查结果
    findings = Column(JSONB)  # 发现的问题列表
    risk_score = Column(Float)  # 风险评分 0-100
    confidence = Column(Float)  # 置信度 0-1
    recommendations = Column(JSONB)  # 改进建议
    legal_basis = Column(JSONB)  # 法律依据
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    
    # 关系
    task = relationship("AuditTask", back_populates="results")
    
    # 多租户复合索引
    __table_args__ = (
        Index('idx_audit_results_tenant_task', 'tenant_id', 'task_id'),
    )
    
    def __repr__(self):
        return f"<AuditResult(agent={self.agent_name}, risk_score={self.risk_score})>"
