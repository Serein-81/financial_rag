"""
多智能体会话数据库模型
"""

import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func, Index, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base


class MultiAgentSession(Base):
    """多智能体会话"""
    __tablename__ = "multi_agent_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    
    tenant_id = Column(String(100), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    user_query = Column(Text, nullable=False)
    primary_intent = Column(String(50))
    routing_strategy = Column(String(50))
    complexity = Column(String(20))
    
    enable_reflection = Column(Boolean, default=True)
    confidence_threshold = Column(Float, default=0.7)
    max_specialists = Column(Integer, default=3)
    
    status = Column(String(20), default="active")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    extra_metadata = Column(JSONB, nullable=True)
    
    specialist_results = relationship("MultiAgentSpecialistResult", back_populates="session", cascade="all, delete-orphan")
    reports = relationship("MultiAgentReport", back_populates="session", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_ma_session_tenant_created', 'tenant_id', 'created_at'),
        Index('idx_ma_session_user', 'user_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<MultiAgentSession(id={self.session_id}, status={self.status})>"


class MultiAgentSpecialistResult(Base):
    """多智能体专家结果"""
    __tablename__ = "multi_agent_specialist_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    session_id = Column(UUID(as_uuid=True), ForeignKey("multi_agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    
    specialist_type = Column(String(50), nullable=False)
    specialist_name = Column(String(100), nullable=True)
    
    query = Column(Text)
    analysis = Column(JSONB)
    raw_response = Column(Text)
    
    confidence = Column(Float, default=0.0)
    processing_time = Column(Float, default=0.0)
    
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    execution_order = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    session = relationship("MultiAgentSession", back_populates="specialist_results")
    
    __table_args__ = (
        Index('idx_ma_specialist_session', 'session_id', 'execution_order'),
    )
    
    def __repr__(self):
        return f"<MultiAgentSpecialistResult(specialist={self.specialist_type}, success={self.success})>"


class MultiAgentIntentAnalysis(Base):
    """多智能体意图分析记录"""
    __tablename__ = "multi_agent_intent_analyses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    session_id = Column(UUID(as_uuid=True), ForeignKey("multi_agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    
    primary_intent = Column(String(50), nullable=False)
    sub_intents = Column(JSONB, nullable=True)
    
    routing_strategy = Column(String(50), nullable=False)
    required_specialists = Column(JSONB)
    
    complexity = Column(String(20))
    confidence = Column(Float)
    
    raw_query = Column(Text)
    interpreted_query = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_ma_intent_session', 'session_id'),
    )
    
    def __repr__(self):
        return f"<MultiAgentIntentAnalysis(intent={self.primary_intent}, strategy={self.routing_strategy})>"


class MultiAgentReflectionRecord(Base):
    """多智能体反思记录"""
    __tablename__ = "multi_agent_reflection_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    session_id = Column(UUID(as_uuid=True), ForeignKey("multi_agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    
    quality_score = Column(Float)
    quality_level = Column(String(20))
    
    needs_revision = Column(Boolean, default=False)
    revision_reason = Column(Text, nullable=True)
    
    suggestions = Column(JSONB)
    improvement_summary = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_ma_reflection_session', 'session_id'),
    )
    
    def __repr__(self):
        return f"<MultiAgentReflectionRecord(score={self.quality_score}, needs_revision={self.needs_revision})>"
