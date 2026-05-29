"""
用户反馈数据模型

用于记录用户对 RAG 系统的反馈，支持失败案例分析和自我改进。
"""

from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean, ForeignKey, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
import enum
from app.db.base import Base


class FeedbackType(str, enum.Enum):
    """反馈类型"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class FailureType(str, enum.Enum):
    """失败类型"""
    RETRIEVAL = "retrieval"  # 检索失败（没找到相关文档）
    GENERATION = "generation"  # 生成失败（理解错误、格式错误）
    HALLUCINATION = "hallucination"  # 幻觉（编造信息）
    INCOMPLETE = "incomplete"  # 不完整
    IRRELEVANT = "irrelevant"  # 不相关
    OTHER = "other"


class FailureStatus(str, enum.Enum):
    """失败案例状态"""
    PENDING = "pending"  # 待分析
    ANALYZING = "analyzing"  # 分析中
    FIXED = "fixed"  # 已修复
    IGNORED = "ignored"  # 已忽略


class ImprovementType(str, enum.Enum):
    """改进类型"""
    PROMPT = "prompt"  # Prompt 优化
    RETRIEVAL = "retrieval"  # 检索策略优化
    CHUNKING = "chunking"  # 分块策略优化
    PARAMETER = "parameter"  # 参数调优
    OTHER = "other"


class UserFeedback(Base):
    """
    用户反馈记录

    记录用户对每次对话的反馈，用于质量评估和改进。
    """
    __tablename__ = "user_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(100), nullable=False, index=True, comment="会话 ID")
    message_id = Column(UUID(as_uuid=True), nullable=True, comment="消息 ID")

    # 用户信息
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    tenant_id = Column(String(50), nullable=True, index=True)

    # 查询和响应
    query = Column(Text, nullable=False, comment="用户查询")
    response = Column(Text, nullable=False, comment="系统响应")

    # 反馈内容
    feedback_type = Column(
        SQLEnum(FeedbackType, name="feedback_type_enum"),
        nullable=False,
        default=FeedbackType.NEUTRAL,
        comment="反馈类型"
    )
    rating = Column(
        Integer,
        nullable=True,
        comment="评分 1-5"
    )
    comment = Column(Text, nullable=True, comment="用户评论")

    # RAG 元数据
    retrieval_method = Column(
        String(50),
        nullable=True,
        comment="检索方法 (simple/graphrag/agentic)"
    )
    chunks_used = Column(JSONB, nullable=True, comment="使用的文档块")
    kb_id = Column(String(100), nullable=True, comment="知识库 ID")

    # 性能指标
    retrieval_time = Column(Integer, nullable=True, comment="检索时间(ms)")
    generation_time = Column(Integer, nullable=True, comment="生成时间(ms)")
    total_time = Column(Integer, nullable=True, comment="总时间(ms)")
    token_count = Column(Integer, nullable=True, comment="Token 消耗")

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user = relationship("User", backref="feedbacks")
    failure_cases = relationship(
        "FailureCase",
        back_populates="feedback",
        cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": str(self.id),
            "session_id": self.session_id,
            "message_id": str(self.message_id) if self.message_id else None,
            "user_id": str(self.user_id) if self.user_id else None,
            "tenant_id": self.tenant_id,
            "query": self.query,
            "response": self.response,
            "feedback_type": self.feedback_type.value if self.feedback_type else None,
            "rating": self.rating,
            "comment": self.comment,
            "retrieval_method": self.retrieval_method,
            "chunks_used": self.chunks_used,
            "kb_id": self.kb_id,
            "retrieval_time": self.retrieval_time,
            "generation_time": self.generation_time,
            "total_time": self.total_time,
            "token_count": self.token_count,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class FailureCase(Base):
    """
    失败案例记录

    对负面反馈进行深入分析，识别问题根因。
    """
    __tablename__ = "failure_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feedback_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_feedback.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # 失败分类
    failure_type = Column(
        SQLEnum(FailureType, name="failure_type_enum"),
        nullable=False,
        comment="失败类型"
    )

    # 分析结果
    analysis = Column(JSONB, nullable=True, comment="分析结果（根因、缺失信息等）")
    fix_suggestions = Column(JSONB, nullable=True, comment="修复建议列表")

    # 状态
    status = Column(
        SQLEnum(FailureStatus, name="failure_status_enum"),
        nullable=False,
        default=FailureStatus.PENDING,
        comment="处理状态"
    )

    # 自动分析元数据
    auto_analyzed = Column(Boolean, default=False, comment="是否已自动分析")
    confidence_score = Column(Integer, nullable=True, comment="分析置信度 0-100")

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    analyzed_at = Column(DateTime(timezone=True), nullable=True, comment="分析时间")

    # 关系
    feedback = relationship("UserFeedback", back_populates="failure_cases")
    improvements = relationship(
        "ImprovementRecord",
        back_populates="failure_case",
        cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": str(self.id),
            "feedback_id": str(self.feedback_id),
            "failure_type": self.failure_type.value if self.failure_type else None,
            "analysis": self.analysis,
            "fix_suggestions": self.fix_suggestions,
            "status": self.status.value if self.status else None,
            "auto_analyzed": self.auto_analyzed,
            "confidence_score": self.confidence_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None
        }


class ImprovementRecord(Base):
    """
    改进记录

    记录针对失败案例的改进措施，包括 A/B 测试结果。
    """
    __tablename__ = "improvement_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    failure_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("failure_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # 改进类型
    improvement_type = Column(
        SQLEnum(ImprovementType, name="improvement_type_enum"),
        nullable=False,
        comment="改进类型"
    )

    # 改进配置
    before_config = Column(JSONB, nullable=True, comment="改进前配置")
    after_config = Column(JSONB, nullable=True, comment="改进后配置")

    # A/B 测试结果
    ab_test_result = Column(JSONB, nullable=True, comment="A/B 测试结果")

    # 部署状态
    deployed = Column(Boolean, default=False, comment="是否已部署")
    deployed_at = Column(DateTime(timezone=True), nullable=True, comment="部署时间")

    # 效果评估
    success_rate_before = Column(Integer, nullable=True, comment="改进前成功率 %")
    success_rate_after = Column(Integer, nullable=True, comment="改进后成功率 %")
    user_satisfaction_before = Column(Integer, nullable=True, comment="改进前用户满意度 0-100")
    user_satisfaction_after = Column(Integer, nullable=True, comment="改进后用户满意度 0-100")

    # 描述
    description = Column(Text, nullable=True, comment="改进描述")
    notes = Column(Text, nullable=True, comment="备注")

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    failure_case = relationship("FailureCase", back_populates="improvements")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": str(self.id),
            "failure_case_id": str(self.failure_case_id),
            "improvement_type": self.improvement_type.value if self.improvement_type else None,
            "before_config": self.before_config,
            "after_config": self.after_config,
            "ab_test_result": self.ab_test_result,
            "deployed": self.deployed,
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
            "success_rate_before": self.success_rate_before,
            "success_rate_after": self.success_rate_after,
            "user_satisfaction_before": self.user_satisfaction_before,
            "user_satisfaction_after": self.user_satisfaction_after,
            "description": self.description,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


# 数据库迁移 SQL（供参考）
"""
-- 创建枚举类型
CREATE TYPE feedback_type_enum AS ENUM ('positive', 'negative', 'neutral');
CREATE TYPE failure_type_enum AS ENUM ('retrieval', 'generation', 'hallucination', 'incomplete', 'irrelevant', 'other');
CREATE TYPE failure_status_enum AS ENUM ('pending', 'analyzing', 'fixed', 'ignored');
CREATE TYPE improvement_type_enum AS ENUM ('prompt', 'retrieval', 'chunking', 'parameter', 'other');

-- 创建用户反馈表
CREATE TABLE user_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) NOT NULL,
    message_id UUID,
    user_id UUID REFERENCES users(id),
    tenant_id VARCHAR(50),
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    feedback_type feedback_type_enum NOT NULL DEFAULT 'neutral',
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    retrieval_method VARCHAR(50),
    chunks_used JSONB,
    kb_id VARCHAR(100),
    retrieval_time INTEGER,
    generation_time INTEGER,
    total_time INTEGER,
    token_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_user_feedback_session ON user_feedback(session_id);
CREATE INDEX idx_user_feedback_tenant ON user_feedback(tenant_id);
CREATE INDEX idx_user_feedback_type ON user_feedback(feedback_type);

-- 创建失败案例表
CREATE TABLE failure_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feedback_id UUID NOT NULL REFERENCES user_feedback(id) ON DELETE CASCADE,
    failure_type failure_type_enum NOT NULL,
    analysis JSONB,
    fix_suggestions JSONB,
    status failure_status_enum NOT NULL DEFAULT 'pending',
    auto_analyzed BOOLEAN DEFAULT FALSE,
    confidence_score INTEGER CHECK (confidence_score >= 0 AND confidence_score <= 100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    analyzed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_failure_cases_feedback ON failure_cases(feedback_id);
CREATE INDEX idx_failure_cases_status ON failure_cases(status);
CREATE INDEX idx_failure_cases_type ON failure_cases(failure_type);

-- 创建改进记录表
CREATE TABLE improvement_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    failure_case_id UUID NOT NULL REFERENCES failure_cases(id) ON DELETE CASCADE,
    improvement_type improvement_type_enum NOT NULL,
    before_config JSONB,
    after_config JSONB,
    ab_test_result JSONB,
    deployed BOOLEAN DEFAULT FALSE,
    deployed_at TIMESTAMP WITH TIME ZONE,
    success_rate_before INTEGER,
    success_rate_after INTEGER,
    user_satisfaction_before INTEGER,
    user_satisfaction_after INTEGER,
    description TEXT,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_improvement_records_failure_case ON improvement_records(failure_case_id);
CREATE INDEX idx_improvement_records_deployed ON improvement_records(deployed);
"""
