# app/schemas/log.py

"""
日志相关的Pydantic模式定义
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum

from app.models.system_log import LogLevel, LogCategory


class LogQueryParams(BaseModel):
    """日志查询参数"""
    level: Optional[LogLevel] = None
    category: Optional[LogCategory] = None
    action: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    order_by: str = Field(default="created_at")
    order_desc: bool = Field(default=True)


class SystemLogResponse(BaseModel):
    """系统日志响应模式"""
    id: str
    created_at: datetime
    level: str
    category: str
    action: str
    message: str
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    module: Optional[str] = None
    function: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None
    execution_time: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    is_sensitive: bool = False

    class Config:
        from_attributes = True


class UserActionLogResponse(BaseModel):
    """用户操作日志响应模式"""
    id: str
    created_at: datetime
    user_id: str
    user_email: Optional[str] = None
    action_type: str
    action_name: str
    description: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    success: bool
    result_message: Optional[str] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    user_agent: Optional[str] = None
    before_data: Optional[Dict[str, Any]] = None
    after_data: Optional[Dict[str, Any]] = None
    extra_info: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class LogStatisticsResponse(BaseModel):
    """日志统计响应模式"""
    period: str
    start_time: str
    end_time: str
    level_stats: Dict[str, int]
    category_stats: Dict[str, int]
    daily_stats: Dict[str, int]
    error_count: int
    total_logs: int

    class Config:
        from_attributes = True


class LogsListResponse(BaseModel):
    """日志列表响应模式"""
    logs: List[SystemLogResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

    class Config:
        from_attributes = True


class UserActionLogsListResponse(BaseModel):
    """用户操作日志列表响应模式"""
    logs: List[UserActionLogResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

    class Config:
        from_attributes = True