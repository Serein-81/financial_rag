# app/models/prompt_optimization.py

"""
Prompt 优化数据模型

用于 Prompt 模板管理、执行记录和 A/B 测试
"""

from sqlalchemy import Column, String, Text, Integer, Float, Boolean, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from app.db.base import Base


class PromptTemplate(Base):
    """
    Prompt 模板
    
    存储不同版本的 Prompt 模板，支持版本管理和 A/B 测试
    """
    __tablename__ = "prompt_templates"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 模板信息
    name = Column(String, unique=True, nullable=False)  # 模板名称（唯一）
    version = Column(String, nullable=False)  # 版本号（如 v1.0, v2.0）
    template_text = Column(Text, nullable=False)  # 模板内容
    
    # 分类信息
    agent_type = Column(String, nullable=False)  # react, plan, reflect
    use_case = Column(String, default="general")  # general, search, analysis, etc.
    
    # 状态
    is_active = Column(Boolean, default=True)  # 是否启用
    is_baseline = Column(Boolean, default=False)  # 是否为基准版本
    
    # 变量定义（使用 JSONB 提升查询性能）
    variables = Column(JSONB, nullable=True)  # 模板中的变量定义
    
    # 描述
    description = Column(Text, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    executions = relationship("PromptExecution", back_populates="template")
    
    def __repr__(self):
        return f"<PromptTemplate(name={self.name}, version={self.version}, active={self.is_active})>"


class PromptExecution(Base):
    """
    Prompt 执行记录
    
    记录每次使用 Prompt 模板的执行结果，用于分析和优化
    """
    __tablename__ = "prompt_executions"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联信息
    template_id = Column(UUID, ForeignKey("prompt_templates.id"), nullable=False)
    trace_id = Column(UUID, ForeignKey("agent_traces.id"), nullable=True)
    
    # 执行信息
    user_query = Column(Text, nullable=False)
    final_answer = Column(Text, nullable=True)
    
    # 性能指标
    execution_time = Column(Float, nullable=True)  # 秒
    iterations_count = Column(Integer, nullable=True)
    tool_calls_count = Column(Integer, nullable=True)
    
    # 结果评估
    success = Column(Boolean, nullable=False)  # 是否成功完成
    user_feedback = Column(Integer, nullable=True)  # 用户评分（1-5）
    auto_score = Column(Float, nullable=True)  # 自动评分（0-1）
    
    # 错误信息
    error_type = Column(String, nullable=True)  # timeout, tool_error, llm_error
    error_message = Column(Text, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    template = relationship("PromptTemplate", back_populates="executions")
    
    def __repr__(self):
        return f"<PromptExecution(id={self.id}, success={self.success}, score={self.auto_score})>"


class PromptABTest(Base):
    """
    Prompt A/B 测试
    
    管理 Prompt 模板的 A/B 测试，比较不同版本的效果
    """
    __tablename__ = "prompt_ab_tests"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 测试信息
    test_name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # 测试模板
    template_a_id = Column(UUID, ForeignKey("prompt_templates.id"), nullable=False)
    template_b_id = Column(UUID, ForeignKey("prompt_templates.id"), nullable=False)
    
    # 流量分配
    traffic_split = Column(Float, default=0.5)  # A 版本的流量比例（0-1）
    
    # 测试状态
    status = Column(String, default="running")  # running, completed, cancelled
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True), nullable=True)
    
    # 统计信息
    total_executions = Column(Integer, default=0)
    winner_template_id = Column(UUID, nullable=True)  # 获胜的模板 ID
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<PromptABTest(name={self.test_name}, status={self.status})>"
