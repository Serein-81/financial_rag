# app/models/agent_trace.py

"""
Agent 追踪数据模型

用于记录 Agent 的执行过程，包括每一步的思考、行动和观察
"""

from sqlalchemy import Column, String, Text, Integer, Float, Boolean, JSON, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.db.base import Base


class AgentTrace(Base):
    """
    Agent 执行追踪记录
    
    记录一次完整的 Agent 执行过程，包括基本信息和统计数据
    """
    __tablename__ = "agent_traces"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联信息
    session_id = Column(UUID, ForeignKey("chat_sessions.id"), nullable=True)
    message_id = Column(UUID, ForeignKey("chat_messages.id"), nullable=True)
    
    # Agent 基本信息
    agent_type = Column(String, nullable=False)  # react, plan, reflect
    user_query = Column(Text, nullable=False)
    final_answer = Column(Text, nullable=True)
    
    # 执行统计
    total_iterations = Column(Integer, default=0)
    total_time = Column(Float, default=0.0)  # 秒
    tool_calls_count = Column(Integer, default=0)
    
    # 执行状态
    status = Column(String, default="running")  # running, completed, failed
    error_message = Column(Text, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # 关系
    steps = relationship("AgentStep", back_populates="trace", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AgentTrace(id={self.id}, agent_type={self.agent_type}, status={self.status})>"


class AgentStep(Base):
    """
    Agent 单步执行记录
    
    记录 Agent 执行过程中的每一步详细信息
    """
    __tablename__ = "agent_steps"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联到追踪记录
    trace_id = Column(UUID, ForeignKey("agent_traces.id"), nullable=False)
    
    # 步骤信息
    step_number = Column(Integer, nullable=False)  # 第几步（从 1 开始）
    step_type = Column(String, nullable=False)  # thought, action, observation, final_answer
    
    # 内容
    content = Column(Text, nullable=False)  # 该步骤的主要内容
    
    # 工具调用信息（仅 action 类型有值）
    tool_name = Column(String, nullable=True)
    tool_input = Column(JSON, nullable=True)
    tool_output = Column(Text, nullable=True)
    tool_duration = Column(Float, nullable=True)  # 毫秒
    
    # 置信度评分（可选）
    confidence = Column(Float, nullable=True)  # 0-1 之间
    
    # 元数据
    step_metadata = Column(JSON, nullable=True)  # 额外的元数据
    
    # 时间戳
    timestamp = Column(Float, nullable=False)  # Unix 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    trace = relationship("AgentTrace", back_populates="steps")
    
    def __repr__(self):
        return f"<AgentStep(id={self.id}, step_number={self.step_number}, step_type={self.step_type})>"
