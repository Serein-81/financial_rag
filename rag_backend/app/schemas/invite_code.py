"""
邀请码相关的Pydantic模型
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID


# =======================
# 邀请码创建相关
# =======================

class InviteCodeCreate(BaseModel):
    """创建邀请码的请求模型"""
    max_uses: int = Field(default=1, ge=1, le=100, description="最大使用次数")
    expires_hours: int = Field(default=24, ge=1, le=8760, description="过期时间(小时)")
    description: Optional[str] = Field(None, max_length=200, description="邀请描述")
    role: str = Field(default="member", description="被邀请用户角色")


class InviteCodeUpdate(BaseModel):
    """更新邀请码的请求模型"""
    is_active: Optional[bool] = Field(None, description="是否激活")
    description: Optional[str] = Field(None, max_length=200, description="邀请描述")


# =======================
# 邀请码响应相关
# =======================

class InviteCodeOut(BaseModel):
    """邀请码输出模型"""
    id: UUID
    code: str
    tenant_id: str
    created_by: UUID
    
    # 配置信息
    max_uses: int
    used_count: int
    expires_at: Optional[datetime]
    description: Optional[str]
    role: str
    
    # 状态信息
    is_active: bool
    is_expired: bool
    is_exhausted: bool
    is_valid: bool
    remaining_uses: int
    
    # 时间信息
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# 为了兼容性和统一命名，提供别名
InviteCodeResponse = InviteCodeOut


class InviteCodeSummary(BaseModel):
    """邀请码摘要信息"""
    id: UUID
    code: str
    description: Optional[str]
    max_uses: int
    used_count: int
    remaining_uses: int
    is_valid: bool
    expires_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


# =======================
# 邀请码验证相关
# =======================

class InviteCodeValidation(BaseModel):
    """邀请码验证请求"""
    code: str = Field(..., min_length=8, max_length=32, description="邀请码")


class InviteCodeValidationResult(BaseModel):
    """邀请码验证结果"""
    valid: bool
    message: str
    tenant_id: Optional[str] = None
    company_name: Optional[str] = None
    creator_name: Optional[str] = None
    description: Optional[str] = None
    expires_at: Optional[datetime] = None
    remaining_uses: Optional[int] = None


# =======================
# 邀请码使用记录
# =======================

class InviteCodeUsageOut(BaseModel):
    """邀请码使用记录输出"""
    id: UUID
    invite_code_id: UUID
    user_id: UUID
    used_at: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]
    
    # 关联信息
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    
    class Config:
        from_attributes = True


# =======================
# 邀请码统计
# =======================

class InviteCodeStats(BaseModel):
    """邀请码统计信息"""
    total_codes: int
    active_codes: int
    expired_codes: int
    exhausted_codes: int
    total_uses: int
    total_invited_users: int


# =======================
# 批量操作
# =======================

class InviteCodeBatchCreate(BaseModel):
    """批量创建邀请码"""
    count: int = Field(..., ge=1, le=50, description="创建数量")
    max_uses: int = Field(default=1, ge=1, le=100, description="每个邀请码的最大使用次数")
    expires_hours: int = Field(default=24, ge=1, le=8760, description="过期时间(小时)")
    description_template: Optional[str] = Field(None, max_length=200, description="描述模板")
    role: str = Field(default="member", description="被邀请用户角色")


class InviteCodeBatchResult(BaseModel):
    """批量创建结果"""
    success: bool
    created_count: int
    codes: list[str]
    message: str