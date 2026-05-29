"""
Prompt 版本管理模型

支持 Prompt 的版本控制、A/B 测试和自动优化。
"""

import uuid
from sqlalchemy import Column, String, Boolean, Integer, Float, DateTime, Text, func, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base
from datetime import datetime
from enum import Enum


class PromptStatus(str, Enum):
    """Prompt 状态"""
    DRAFT = "draft"              # 草稿
    TESTING = "testing"          # 测试中（A/B测试）
    ACTIVE = "active"            # 已激活
    ARCHIVED = "archived"        # 已归档


class PromptType(str, Enum):
    """Prompt 类型"""
    RAG_GENERATION = "rag_generation"          # RAG 生成
    QUERY_REWRITE = "query_rewrite"            # 查询重写
    SUMMARY = "summary"                        # 摘要生成
    EXTRACTION = "extraction"                  # 信息提取
    CLASSIFICATION = "classification"          # 分类
    CUSTOM = "custom"                          # 自定义


class PromptVersion(Base):
    """
    Prompt 版本表

    每个 Prompt 可以有多个版本，支持 A/B 测试和版本回滚。
    """
    __tablename__ = "prompt_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 租户ID（多租户隔离）
    tenant_id = Column(String(50), nullable=False, index=True)

    # Prompt 基本信息
    prompt_name = Column(String(100), nullable=False, index=True)  # Prompt名称（如: "rag_generation_v1"）
    prompt_type = Column(String(50), nullable=False, index=True)   # Prompt类型
    version = Column(String(20), nullable=False)                   # 版本号（如: "1.0.0", "1.1.0"）

    # Prompt 内容
    template = Column(Text, nullable=False)                        # Prompt模板
    variables = Column(JSONB, default={})                          # 变量定义
    system_prompt = Column(Text, nullable=True)                    # 系统提示词（可选）

    # 状态
    status = Column(String(20), default=PromptStatus.DRAFT.value, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)    # 是否为默认版本

    # 配置参数
    temperature = Column(Float, default=0.7)                       # 温度
    max_tokens = Column(Integer, default=1000)                     # 最大token数
    top_p = Column(Float, default=1.0)                            # top_p
    frequency_penalty = Column(Float, default=0.0)                # 频率惩罚
    presence_penalty = Column(Float, default=0.0)                 # 存在惩罚

    # 性能指标（从实际使用中统计）
    total_uses = Column(Integer, default=0)                       # 总使用次数
    success_count = Column(Integer, default=0)                    # 成功次数
    failure_count = Column(Integer, default=0)                    # 失败次数
    avg_response_time_ms = Column(Float, default=0.0)             # 平均响应时间
    avg_token_usage = Column(Float, default=0.0)                  # 平均token使用

    # 用户反馈指标
    positive_feedback_count = Column(Integer, default=0)          # 正面反馈数
    negative_feedback_count = Column(Integer, default=0)          # 负面反馈数
    avg_rating = Column(Float, default=0.0)                       # 平均评分（1-5）

    # A/B 测试权重（0-100，表示百分比）
    ab_test_weight = Column(Integer, default=0)                   # A/B测试流量权重

    # 元数据
    description = Column(String(500), nullable=True)              # 版本描述
    created_by = Column(String(100), nullable=True)               # 创建者
    tags = Column(JSONB, default=[])                              # 标签

    # 审计字段
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    activated_at = Column(DateTime(timezone=True), nullable=True)  # 激活时间

    # 索引
    __table_args__ = (
        Index('idx_tenant_prompt_status', 'tenant_id', 'prompt_name', 'status'),
        UniqueConstraint('tenant_id', 'prompt_name', 'version', name='uq_tenant_prompt_version'),
    )

    def __init__(self, **kwargs):
        """初始化实例，设置默认值"""
        super().__init__(**kwargs)
        # 确保数值字段有默认值（用于测试和直接实例化）
        if self.total_uses is None:
            self.total_uses = 0
        if self.success_count is None:
            self.success_count = 0
        if self.failure_count is None:
            self.failure_count = 0
        if self.avg_response_time_ms is None:
            self.avg_response_time_ms = 0.0
        if self.avg_token_usage is None:
            self.avg_token_usage = 0.0
        if self.positive_feedback_count is None:
            self.positive_feedback_count = 0
        if self.negative_feedback_count is None:
            self.negative_feedback_count = 0
        if self.avg_rating is None:
            self.avg_rating = 0.0
        if self.ab_test_weight is None:
            self.ab_test_weight = 0
        if self.variables is None:
            self.variables = {}
        if self.tags is None:
            self.tags = []

    def to_dict(self):
        """转换为字典"""
        return {
            "id": str(self.id),
            "tenant_id": self.tenant_id,
            "prompt_name": self.prompt_name,
            "prompt_type": self.prompt_type,
            "version": self.version,
            "template": self.template,
            "variables": self.variables,
            "system_prompt": self.system_prompt,
            "status": self.status,
            "is_default": self.is_default,
            "config": {
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "top_p": self.top_p,
                "frequency_penalty": self.frequency_penalty,
                "presence_penalty": self.presence_penalty
            },
            "metrics": {
                "total_uses": self.total_uses,
                "success_rate": self.get_success_rate(),
                "avg_response_time_ms": self.avg_response_time_ms,
                "avg_token_usage": self.avg_token_usage,
                "avg_rating": self.avg_rating,
                "positive_feedback": self.positive_feedback_count,
                "negative_feedback": self.negative_feedback_count
            },
            "ab_test_weight": self.ab_test_weight,
            "description": self.description,
            "created_by": self.created_by,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None
        }

    def get_success_rate(self) -> float:
        """计算成功率"""
        if self.total_uses == 0:
            return 0.0
        return self.success_count / self.total_uses

    def get_satisfaction_rate(self) -> float:
        """计算满意度"""
        total_feedback = self.positive_feedback_count + self.negative_feedback_count
        if total_feedback == 0:
            return 0.0
        return self.positive_feedback_count / total_feedback

    def increment_usage(self, success: bool, response_time_ms: float, token_usage: int):
        """增加使用统计"""
        self.total_uses += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

        # 更新平均响应时间（滑动平均）
        if self.avg_response_time_ms == 0:
            self.avg_response_time_ms = response_time_ms
        else:
            self.avg_response_time_ms = (
                self.avg_response_time_ms * 0.9 + response_time_ms * 0.1
            )

        # 更新平均token使用（滑动平均）
        if self.avg_token_usage == 0:
            self.avg_token_usage = token_usage
        else:
            self.avg_token_usage = (
                self.avg_token_usage * 0.9 + token_usage * 0.1
            )

    def add_feedback(self, rating: int, is_positive: bool):
        """添加用户反馈"""
        if is_positive:
            self.positive_feedback_count += 1
        else:
            self.negative_feedback_count += 1

        # 更新平均评分（滑动平均）
        total_feedback = self.positive_feedback_count + self.negative_feedback_count
        if total_feedback == 1:
            self.avg_rating = rating
        else:
            self.avg_rating = (
                self.avg_rating * (total_feedback - 1) + rating
            ) / total_feedback


class ABTestExperiment(Base):
    """
    A/B 测试实验表

    管理多个 Prompt 版本的 A/B 测试。
    """
    __tablename__ = "ab_test_experiments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 租户ID
    tenant_id = Column(String(50), nullable=False, index=True)

    # 实验信息
    experiment_name = Column(String(100), nullable=False, index=True)
    prompt_name = Column(String(100), nullable=False, index=True)  # 关联的Prompt名称
    prompt_type = Column(String(50), nullable=False)

    # 实验状态
    status = Column(String(20), default="running", nullable=False)  # running/completed/stopped
    is_active = Column(Boolean, default=True, nullable=False)

    # 参与测试的版本ID列表（带权重）
    variant_weights = Column(JSONB, default={})  # {"version_id": weight}

    # 实验配置
    min_sample_size = Column(Integer, default=100)      # 最小样本量
    confidence_level = Column(Float, default=0.95)      # 置信水平
    auto_promote_winner = Column(Boolean, default=False)  # 自动提升获胜版本

    # 实验结果
    total_samples = Column(Integer, default=0)          # 总样本数
    winner_version_id = Column(UUID(as_uuid=True), nullable=True)  # 获胜版本

    # 统计显著性
    is_significant = Column(Boolean, default=False)     # 是否有统计显著性
    p_value = Column(Float, nullable=True)              # p值

    # 时间范围
    start_time = Column(DateTime(timezone=True), default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)

    # 审计字段
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    def __init__(self, **kwargs):
        """初始化实例，设置默认值"""
        super().__init__(**kwargs)
        # 确保字段有默认值
        if self.variant_weights is None:
            self.variant_weights = {}
        if self.total_samples is None:
            self.total_samples = 0

    def to_dict(self):
        """转换为字典"""
        return {
            "id": str(self.id),
            "tenant_id": self.tenant_id,
            "experiment_name": self.experiment_name,
            "prompt_name": self.prompt_name,
            "prompt_type": self.prompt_type,
            "status": self.status,
            "is_active": self.is_active,
            "variant_weights": self.variant_weights,
            "config": {
                "min_sample_size": self.min_sample_size,
                "confidence_level": self.confidence_level,
                "auto_promote_winner": self.auto_promote_winner
            },
            "results": {
                "total_samples": self.total_samples,
                "winner_version_id": str(self.winner_version_id) if self.winner_version_id else None,
                "is_significant": self.is_significant,
                "p_value": self.p_value
            },
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class PromptImprovementSuggestion(Base):
    """
    Prompt 改进建议表

    基于失败案例自动生成的改进建议。
    """
    __tablename__ = "prompt_improvement_suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 租户ID
    tenant_id = Column(String(50), nullable=False, index=True)

    # 关联的Prompt版本
    prompt_version_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    prompt_name = Column(String(100), nullable=False)

    # 问题识别
    issue_type = Column(String(50), nullable=False)  # incomplete/inaccurate/format_error/hallucination等
    issue_description = Column(Text, nullable=False)  # 问题描述
    failure_case_ids = Column(JSONB, default=[])     # 相关失败案例ID列表

    # 改进建议
    suggestion_type = Column(String(50), nullable=False)  # add_instruction/modify_format/add_example等
    suggestion_detail = Column(Text, nullable=False)      # 具体建议
    suggested_prompt = Column(Text, nullable=True)        # 建议的新Prompt

    # 置信度和优先级
    confidence_score = Column(Float, default=0.0)    # 置信度（0-1）
    priority = Column(String(20), default="medium")  # low/medium/high

    # 状态
    status = Column(String(20), default="pending")   # pending/accepted/rejected/applied
    reviewed_by = Column(String(100), nullable=True) # 审核人
    review_notes = Column(Text, nullable=True)       # 审核备注

    # 应用结果
    applied_version_id = Column(UUID(as_uuid=True), nullable=True)  # 应用后生成的新版本ID
    improvement_metric = Column(Float, nullable=True)                # 改进指标（如成功率提升）

    # 审计字段
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    applied_at = Column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs):
        """初始化实例，设置默认值"""
        super().__init__(**kwargs)
        # 确保列表字段有默认值
        if self.failure_case_ids is None:
            self.failure_case_ids = []

    def to_dict(self):
        """转换为字典"""
        return {
            "id": str(self.id),
            "tenant_id": self.tenant_id,
            "prompt_version_id": str(self.prompt_version_id),
            "prompt_name": self.prompt_name,
            "issue": {
                "type": self.issue_type,
                "description": self.issue_description,
                "failure_case_count": len(self.failure_case_ids or [])
            },
            "suggestion": {
                "type": self.suggestion_type,
                "detail": self.suggestion_detail,
                "suggested_prompt": self.suggested_prompt,
                "confidence_score": self.confidence_score,
                "priority": self.priority
            },
            "status": self.status,
            "reviewed_by": self.reviewed_by,
            "review_notes": self.review_notes,
            "applied_version_id": str(self.applied_version_id) if self.applied_version_id else None,
            "improvement_metric": self.improvement_metric,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None
        }
