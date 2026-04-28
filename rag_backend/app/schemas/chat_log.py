"""
对话日志 Schema 定义

提供对话日志相关的数据模型定义
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime


class ChatLogSessionItem(BaseModel):
    """会话列表项"""
    id: str
    user_id: str
    user_name: str
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int = 0
    last_message_preview: Optional[str] = None
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0


class ChatLogSessionListResponse(BaseModel):
    """会话列表响应"""
    total: int
    page: int
    page_size: int
    sessions: List[ChatLogSessionItem]


class ChatLogMessageItem(BaseModel):
    """对话消息项"""
    id: str
    session_id: str
    role: str
    content: str
    sources: Optional[Any] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    model_name: Optional[str] = None
    agent_name: Optional[str] = None
    turn: Optional[int] = None
    created_at: Optional[str] = None


class ChatLogSessionStatistics(BaseModel):
    """会话统计信息"""
    session_id: str
    title: Optional[str] = None
    user_name: str
    user_id: str
    created_at: Optional[str] = None
    message_count: int = 0
    total_turns: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    model_name: Optional[str] = None


class ChatLogUserStatistics(BaseModel):
    """用户统计信息"""
    user_id: str
    user_name: str
    chat_statistics: Dict[str, Any] = Field(default_factory=dict)
    action_statistics: Dict[str, Any] = Field(default_factory=dict)


class ChatLogTenantStatistics(BaseModel):
    """租户统计信息"""
    total_users: int = 0
    active_users: int = 0
    total_sessions: int = 0
    total_messages: int = 0
    total_turns: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0


class ChatLogListRequest(BaseModel):
    """对话日志列表请求"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    user_id: Optional[str] = None
    keyword: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class ChatLogDetailRequest(BaseModel):
    """对话日志详情请求"""
    session_id: str


class UserActionLogItem(BaseModel):
    """用户操作日志项"""
    id: str
    user_id: str
    user_email: Optional[str] = None
    tenant_id: Optional[str] = None
    action_type: str
    action_name: str
    description: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    success: bool = True
    result_message: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: Optional[str] = None
    level: Optional[str] = None
    risk_level: Optional[str] = None
    extra_info: Optional[Dict[str, Any]] = None


class UserActionLogListResponse(BaseModel):
    """用户操作日志列表响应"""
    logs: List[UserActionLogItem]
    total: int
    page: int
    page_size: int
