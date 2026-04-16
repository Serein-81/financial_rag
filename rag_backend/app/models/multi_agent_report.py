"""
多智能体报告数据库模型
"""

import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func, Index, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class MultiAgentReport(Base):
    """多智能体生成的报告"""
    __tablename__ = "multi_agent_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    session_id = Column(UUID(as_uuid=True), ForeignKey("multi_agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    report_type = Column(String(50), nullable=False)
    format = Column(String(20), default="markdown")
    
    title = Column(String(500))
    summary = Column(Text)
    content = Column(Text)
    
    sections = Column(JSONB)
    extra_metadata = Column(JSONB)
    
    version = Column(Integer, default=1)
    is_latest = Column(Boolean, default=True)
    parent_report_id = Column(UUID(as_uuid=True), ForeignKey("multi_agent_reports.id"), nullable=True)
    
    quality_score = Column(Float, nullable=True)
    quality_level = Column(String(20), nullable=True)
    
    generated_by = Column(String(100))
    generation_time = Column(Float)
    
    word_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    session = relationship("MultiAgentSession", back_populates="reports")
    previous_versions = relationship("MultiAgentReport", remote_side=[id])
    
    __table_args__ = (
        Index('idx_ma_report_session_latest', 'session_id', 'is_latest'),
        Index('idx_ma_report_tenant_created', 'tenant_id', 'created_at'),
        Index('idx_ma_report_type', 'report_type', 'created_at'),
    )
    
    def __repr__(self):
        return f"<MultiAgentReport(type={self.report_type}, format={self.format}, version={self.version})>"


class MultiAgentReportVersion(Base):
    """多智能体报告版本历史"""
    __tablename__ = "multi_agent_report_versions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    report_id = Column(UUID(as_uuid=True), ForeignKey("multi_agent_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    
    version = Column(Integer, nullable=False)
    
    content_snapshot = Column(Text)
    metadata_snapshot = Column(JSONB)
    
    change_reason = Column(String(200))
    changed_by = Column(String(100))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_ma_report_version_report', 'report_id', 'version'),
    )
    
    def __repr__(self):
        return f"<MultiAgentReportVersion(report_id={self.report_id}, version={self.version})>"


class MultiAgentReportAccessLog(Base):
    """多智能体报告访问日志"""
    __tablename__ = "multi_agent_report_access_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    report_id = Column(UUID(as_uuid=True), ForeignKey("multi_agent_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    action = Column(String(50), nullable=False)
    access_type = Column(String(20))
    
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    
    duration_ms = Column(Integer)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_ma_report_access_report', 'report_id', 'created_at'),
        Index('idx_ma_report_access_user', 'user_id', 'created_at'),
        Index('idx_ma_report_access_tenant', 'tenant_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<MultiAgentReportAccessLog(report_id={self.report_id}, action={self.action})>"
