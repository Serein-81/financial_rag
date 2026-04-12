# app/schemas/tenant_settings.py

"""
租户设置 Pydantic Schemas

提供租户设置的验证和序列化
"""

from pydantic import BaseModel, EmailStr, Field, field_validator, field_serializer
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from enum import Enum
from uuid import UUID


class FeatureToggle(str, Enum):
    """功能开关枚举"""
    ENABLED = "enabled"
    DISABLED = "disabled"


class TenantSettingsBase(BaseModel):
    """租户设置基础Schema"""
    company_name: str = Field(..., min_length=1, max_length=200, description="企业名称")
    company_logo: Optional[str] = Field(None, max_length=500, description="企业Logo URL")
    company_description: Optional[str] = Field(None, description="企业描述")
    company_website: Optional[str] = Field(None, max_length=500, description="企业网站")
    company_address: Optional[str] = Field(None, max_length=500, description="企业地址")
    company_phone: Optional[str] = Field(None, max_length=50, description="联系电话")
    company_email: Optional[EmailStr] = Field(None, description="联系邮箱")

    admin_name: Optional[str] = Field(None, max_length=100, description="管理员姓名")
    admin_email: Optional[EmailStr] = Field(None, description="管理员邮箱")
    admin_phone: Optional[str] = Field(None, max_length=50, description="管理员电话")

    # 企业画像（用于政策智能匹配）
    industry: Optional[str] = Field(None, max_length=100, description="企业所属行业")
    region: Optional[str] = Field(None, max_length=100, description="企业所在地区")
    scale: Optional[str] = Field(None, max_length=50, description="企业规模")
    tax_types: List[str] = Field(default=[], description="税种类型（可多选）")

    max_users: int = Field(default=10, ge=1, le=100000, description="最大用户数")
    max_storage_gb: int = Field(default=100, ge=1, le=100000, description="最大存储空间(GB)")
    max_knowledge_bases: int = Field(default=10, ge=1, le=10000, description="最大知识库数量")
    max_documents: int = Field(default=1000, ge=1, le=1000000, description="最大文档数量")
    max_monthly_requests: Optional[int] = Field(None, ge=1, description="最大月度请求次数")

    enable_group_chat: bool = Field(default=True, description="是否启用群聊")
    enable_multi_agent: bool = Field(default=True, description="是否启用多Agent")
    enable_knowledge_graph: bool = Field(default=False, description="是否启用知识图谱")
    enable_human_review: bool = Field(default=True, description="是否启用人工审核")
    enable_audit: bool = Field(default=False, description="是否启用审计功能")
    enable_tax_report: bool = Field(default=False, description="是否启用税务报表")
    enable_financial_data: bool = Field(default=False, description="是否启用财务数据")

    primary_color: str = Field(default="#1890ff", description="主色调")
    secondary_color: Optional[str] = Field(None, description="次要色调")
    custom_css: Optional[str] = Field(None, description="自定义CSS")
    custom_footer: Optional[str] = Field(None, description="自定义页脚")

    email_notification: bool = Field(default=True, description="是否启用邮件通知")
    system_notification: bool = Field(default=True, description="是否启用系统通知")
    notification_email: Optional[EmailStr] = Field(None, description="通知接收邮箱")

    @field_validator('primary_color', 'secondary_color')
    @classmethod
    def validate_color(cls, v):
        if v and not v.startswith('#'):
            raise ValueError('颜色值必须以#开头')
        if v and len(v) not in [4, 7, 9]:
            raise ValueError('颜色值格式不正确')
        return v


class TenantSettingsCreate(TenantSettingsBase):
    """创建租户设置的Schema"""
    tenant_id: str = Field(..., min_length=1, max_length=50, description="租户ID")


class TenantSettingsUpdate(BaseModel):
    """更新租户设置的Schema（所有字段可选）"""
    company_name: Optional[str] = Field(None, min_length=1, max_length=200, description="企业名称")
    company_logo: Optional[str] = Field(None, max_length=500, description="企业Logo URL")
    company_description: Optional[str] = Field(None, description="企业描述")
    company_website: Optional[str] = Field(None, max_length=500, description="企业网站")
    company_address: Optional[str] = Field(None, max_length=500, description="企业地址")
    company_phone: Optional[str] = Field(None, max_length=50, description="联系电话")
    company_email: Optional[EmailStr] = Field(None, description="联系邮箱")

    admin_name: Optional[str] = Field(None, max_length=100, description="管理员姓名")
    admin_email: Optional[EmailStr] = Field(None, description="管理员邮箱")
    admin_phone: Optional[str] = Field(None, max_length=50, description="管理员电话")

    # 企业画像（用于政策智能匹配）
    industry: Optional[str] = Field(None, max_length=100, description="企业所属行业")
    region: Optional[str] = Field(None, max_length=100, description="企业所在地区")
    scale: Optional[str] = Field(None, max_length=50, description="企业规模")
    tax_types: Optional[List[str]] = Field(None, description="税种类型（可多选）")

    max_users: Optional[int] = Field(None, ge=1, le=100000, description="最大用户数")
    max_storage_gb: Optional[int] = Field(None, ge=1, le=100000, description="最大存储空间(GB)")
    max_knowledge_bases: Optional[int] = Field(None, ge=1, le=10000, description="最大知识库数量")
    max_documents: Optional[int] = Field(None, ge=1, le=1000000, description="最大文档数量")
    max_monthly_requests: Optional[int] = Field(None, ge=1, description="最大月度请求次数")

    enable_group_chat: Optional[bool] = Field(None, description="是否启用群聊")
    enable_multi_agent: Optional[bool] = Field(None, description="是否启用多Agent")
    enable_knowledge_graph: Optional[bool] = Field(None, description="是否启用知识图谱")
    enable_human_review: Optional[bool] = Field(None, description="是否启用人工审核")
    enable_audit: Optional[bool] = Field(None, description="是否启用审计功能")
    enable_tax_report: Optional[bool] = Field(None, description="是否启用税务报表")
    enable_financial_data: Optional[bool] = Field(None, description="是否启用财务数据")

    primary_color: Optional[str] = Field(None, description="主色调")
    secondary_color: Optional[str] = Field(None, description="次要色调")
    custom_css: Optional[str] = Field(None, description="自定义CSS")
    custom_footer: Optional[str] = Field(None, description="自定义页脚")

    email_notification: Optional[bool] = Field(None, description="是否启用邮件通知")
    system_notification: Optional[bool] = Field(None, description="是否启用系统通知")
    notification_email: Optional[EmailStr] = Field(None, description="通知接收邮箱")

    @field_validator('primary_color', 'secondary_color')
    @classmethod
    def validate_color(cls, v):
        if v is not None and not v.startswith('#'):
            raise ValueError('颜色值必须以#开头')
        if v is not None and len(v) not in [4, 7, 9]:
            raise ValueError('颜色值格式不正确')
        return v


class TenantSettingsResponse(TenantSettingsBase):
    """租户设置响应Schema"""
    id: Union[str, UUID]
    tenant_id: str
    created_at: datetime
    updated_at: datetime
    is_active: bool
    is_trial: bool
    trial_expires_at: Optional[datetime] = None
    extra_settings: Optional[Dict[str, Any]] = None

    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    @field_serializer('id')
    def serialize_id(self, value: Union[str, UUID]) -> str:
        return str(value)

    class Config:
        from_attributes = True


class TenantSettingsPublicResponse(BaseModel):
    """公开的租户设置响应（不含敏感信息）"""
    tenant_id: str
    company_name: str
    company_logo: Optional[str] = None
    company_description: Optional[str] = None
    company_website: Optional[str] = None
    primary_color: str = "#1890ff"
    secondary_color: Optional[str] = None

    class Config:
        from_attributes = True


class FeatureToggleRequest(BaseModel):
    """功能开关请求Schema"""
    feature: str = Field(..., description="功能名称")
    enabled: bool = Field(..., description="是否启用")

    @field_validator('feature')
    @classmethod
    def validate_feature(cls, v):
        valid_features = [
            'enable_group_chat',
            'enable_multi_agent',
            'enable_knowledge_graph',
            'enable_human_review',
            'enable_audit',
            'enable_tax_report',
            'enable_financial_data'
        ]
        if v not in valid_features:
            raise ValueError(f'无效的功能名称。有效值: {", ".join(valid_features)}')
        return v


class TenantSettingsListResponse(BaseModel):
    """租户设置列表响应"""
    settings: List[TenantSettingsResponse]
    total: int
