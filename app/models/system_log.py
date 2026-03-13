# app/models/system_log.py

"""
系统日志模型

记录用户操作、系统事件、错误信息等，支持分级权限查看
"""

from sqlalchemy import Column, String, DateTime, Text, Integer, Boolean, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey, func
import uuid
from enum import Enum
from app.db.base import Base


class LogLevel(str, Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(str, Enum):
    """日志分类"""
    USER_ACTION = "USER_ACTION"          # 用户操作
    SYSTEM_EVENT = "SYSTEM_EVENT"        # 系统事件
    API_REQUEST = "API_REQUEST"          # API请求
    DATABASE_OPERATION = "DATABASE_OPERATION"  # 数据库操作
    FILE_OPERATION = "FILE_OPERATION"    # 文件操作
    AUTHENTICATION = "AUTHENTICATION"    # 认证相关
    AGENT_EXECUTION = "AGENT_EXECUTION"  # Agent执行
    TOOL_CALL = "TOOL_CALL"             # 工具调用
    ERROR_TRACE = "ERROR_TRACE"         # 错误追踪
    SECURITY = "SECURITY"               # 安全相关


class SystemLog(Base):
    """
    系统日志表
    
    记录所有系统操作和事件，支持多维度查询和分析
    """
    __tablename__ = "system_logs"

    # 基础字段
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # 日志基本信息
    level = Column(String(20), nullable=False, index=True)  # 日志级别
    category = Column(String(50), nullable=False, index=True)  # 日志分类
    action = Column(String(100), nullable=False, index=True)  # 操作动作
    message = Column(Text, nullable=False)  # 日志消息
    
    # 关联信息
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(100), nullable=True, index=True)  # 会话ID
    request_id = Column(String(100), nullable=True, index=True)  # 请求ID
    
    # 详细信息
    module = Column(String(100), nullable=True)  # 模块名称
    function = Column(String(100), nullable=True)  # 函数名称
    line_number = Column(Integer, nullable=True)  # 行号
    
    # 请求相关
    ip_address = Column(String(45), nullable=True, index=True)  # IP地址
    user_agent = Column(Text, nullable=True)  # 用户代理
    endpoint = Column(String(200), nullable=True)  # API端点
    method = Column(String(10), nullable=True)  # HTTP方法
    status_code = Column(Integer, nullable=True)  # 响应状态码
    
    # 性能指标
    execution_time = Column(Integer, nullable=True)  # 执行时间(毫秒)
    memory_usage = Column(Integer, nullable=True)  # 内存使用(KB)
    
    # 扩展数据
    extra_data = Column(JSON, nullable=True)  # 额外数据(JSON格式)
    
    # 错误信息
    error_type = Column(String(100), nullable=True)  # 错误类型
    error_message = Column(Text, nullable=True)  # 错误消息
    stack_trace = Column(Text, nullable=True)  # 堆栈跟踪
    
    # 标记字段
    is_sensitive = Column(Boolean, default=False)  # 是否敏感信息
    is_archived = Column(Boolean, default=False)  # 是否已归档
    
    # 关联关系
    user = relationship("User", backref="system_logs")

    # 创建复合索引
    __table_args__ = (
        Index('idx_logs_user_time', 'user_id', 'created_at'),
        Index('idx_logs_category_level', 'category', 'level'),
        Index('idx_logs_session_time', 'session_id', 'created_at'),
        Index('idx_logs_action_time', 'action', 'created_at'),
    )

    def __repr__(self):
        return f"<SystemLog(id={self.id}, level={self.level}, action={self.action})>"

    def to_dict(self, include_sensitive: bool = False):
        """
        转换为字典格式
        
        Args:
            include_sensitive: 是否包含敏感信息
        """
        data = {
            "id": str(self.id),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "level": self.level,
            "category": self.category,
            "action": self.action,
            "message": self.message,
            "user_id": str(self.user_id) if self.user_id else None,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "module": self.module,
            "function": self.function,
            "endpoint": self.endpoint,
            "method": self.method,
            "status_code": self.status_code,
            "execution_time": self.execution_time,
            "is_sensitive": self.is_sensitive,
        }
        
        # 敏感信息只有管理员可以查看
        if include_sensitive or not self.is_sensitive:
            data.update({
                "ip_address": self.ip_address,
                "user_agent": self.user_agent,
                "extra_data": self.extra_data,
                "error_type": self.error_type,
                "error_message": self.error_message,
                "stack_trace": self.stack_trace,
            })
        
        return data


class UserActionLog(Base):
    """
    用户操作日志表
    
    专门记录用户的业务操作，便于审计和分析
    """
    __tablename__ = "user_action_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # 用户信息
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    user_email = Column(String(255), nullable=True)  # 冗余存储，防止用户删除后无法追踪
    
    # 操作信息
    action_type = Column(String(50), nullable=False, index=True)  # 操作类型
    action_name = Column(String(100), nullable=False)  # 操作名称
    description = Column(Text, nullable=True)  # 操作描述
    
    # 资源信息
    resource_type = Column(String(50), nullable=True)  # 资源类型
    resource_id = Column(String(100), nullable=True)  # 资源ID
    resource_name = Column(String(200), nullable=True)  # 资源名称
    
    # 操作结果
    success = Column(Boolean, nullable=False, default=True)
    result_message = Column(Text, nullable=True)
    
    # 请求信息
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(100), nullable=True)
    
    # 扩展信息
    before_data = Column(JSON, nullable=True)  # 操作前数据
    after_data = Column(JSON, nullable=True)   # 操作后数据
    extra_info = Column(JSON, nullable=True)   # 额外信息
    
    # 关联关系
    user = relationship("User", backref="action_logs")

    # 创建索引
    __table_args__ = (
        Index('idx_action_logs_user_time', 'user_id', 'created_at'),
        Index('idx_action_logs_type_time', 'action_type', 'created_at'),
        Index('idx_action_logs_resource', 'resource_type', 'resource_id'),
    )

    def __repr__(self):
        return f"<UserActionLog(id={self.id}, action={self.action_name}, user={self.user_email})>"