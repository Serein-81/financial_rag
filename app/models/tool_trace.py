# app/models/tool_trace.py

"""
工具调用追踪数据模型

用于记录工具调用链路，支持嵌套调用和性能分析
"""

from sqlalchemy import Column, String, Text, Float, JSON, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.db.base import Base


class ToolCallTrace(Base):
    """
    工具调用追踪记录
    
    记录每次工具调用的详细信息，支持嵌套调用
    """
    __tablename__ = "tool_call_traces"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联信息
    trace_id = Column(UUID, ForeignKey("agent_traces.id"), nullable=True)  # 关联到 Agent 追踪
    parent_call_id = Column(UUID, ForeignKey("tool_call_traces.id"), nullable=True)  # 父调用（支持嵌套）
    
    # 工具信息
    tool_name = Column(String, nullable=False)
    tool_type = Column(String, default="function")  # function, langchain, api
    
    # 调用信息
    input_params = Column(JSON, nullable=True)  # 输入参数
    output_result = Column(Text, nullable=True)  # 输出结果
    
    # 性能指标
    start_time = Column(Float, nullable=False)  # Unix 时间戳
    end_time = Column(Float, nullable=True)
    duration = Column(Float, nullable=True)  # 毫秒
    
    # 状态
    status = Column(String, default="running")  # running, success, error, timeout
    error_message = Column(Text, nullable=True)
    
    # 元数据
    tool_metadata = Column(JSON, nullable=True)  # 额外信息（如 API 调用次数、token 消耗等）
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    children = relationship("ToolCallTrace", backref="parent", remote_side=[id])
    
    def __repr__(self):
        return f"<ToolCallTrace(id={self.id}, tool_name={self.tool_name}, status={self.status})>"
