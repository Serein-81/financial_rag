"""
政策法规智能追踪 Pydantic Schema 定义
用于政策订阅、推送和追踪系统
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime, date
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


class SubscriptionStatus(str, Enum):
    """订阅状态"""
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class NotificationChannel(str, Enum):
    """通知渠道"""
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    WECHAT = "wechat"


class NotificationFrequency(str, Enum):
    """通知频率"""
    REAL_TIME = "real_time"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class PolicyCategory(str, Enum):
    """政策类别"""
    TAX = "tax"
    FINANCE = "finance"
    LEGAL = "legal"
    LABOR = "labor"
    ENVIRONMENT = "environment"
    INDUSTRY = "industry"
    TRADE = "trade"
    TECHNOLOGY = "technology"


class PolicyImpactLevel(str, Enum):
    """政策影响级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyUpdate(BaseModel):
    """政策更新"""
    update_id: str = Field(..., description="更新ID")
    policy_id: str = Field(..., description="政策ID")
    policy_name: str = Field(..., description="政策名称")
    policy_category: PolicyCategory = Field(..., description="政策类别")
    issuing_authority: str = Field(..., description="发布机构")
    issue_date: date = Field(..., description="发布日期")
    effective_date: Optional[date] = Field(None, description="生效日期")
    policy_summary: str = Field(..., description="政策摘要")
    impact_level: PolicyImpactLevel = Field(..., description="影响级别")
    affected_industries: List[str] = Field(default_factory=list, description="影响行业")
    key_changes: List[str] = Field(default_factory=list, description="主要变化")
    compliance_requirements: List[str] = Field(default_factory=list, description="合规要求")
    related_policies: List[str] = Field(default_factory=list, description="相关政策")
    source_url: Optional[str] = Field(None, description="原文链接")
    is_new: bool = Field(default=False, description="是否新增政策")
    is_amendment: bool = Field(default=False, description="是否修订")


class PolicySubscription(BaseModel):
    """政策订阅"""
    subscription_id: str = Field(..., description="订阅ID")
    tenant_id: str = Field(..., description="租户ID")
    user_id: str = Field(..., description="用户ID")
    policy_categories: List[PolicyCategory] = Field(..., description="订阅的政策类别")
    keywords: List[str] = Field(default_factory=list, description="关键词")
    notification_channels: List[NotificationChannel] = Field(
        default=[NotificationChannel.IN_APP],
        description="通知渠道"
    )
    notification_frequency: NotificationFrequency = Field(
        default=NotificationFrequency.DAILY,
        description="通知频率"
    )
    notification_email: Optional[str] = Field(None, description="通知邮箱")
    notification_webhook: Optional[str] = Field(None, description="Webhook URL")
    notification_phone: Optional[str] = Field(None, description="通知手机")
    status: SubscriptionStatus = Field(default=SubscriptionStatus.ACTIVE, description="订阅状态")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    expires_at: Optional[datetime] = Field(None, description="过期时间")


class PolicySubscriptionRequest(BaseModel):
    """政策订阅请求"""
    tenant_id: Optional[str] = Field(None, description="租户ID")
    user_id: Optional[str] = Field(None, description="用户ID")
    enterprise_id: Optional[str] = Field(None, description="企业ID")
    industry: Optional[str] = Field(None, description="行业")
    region: Optional[str] = Field(None, description="地区")
    company_size: Optional[str] = Field(None, description="公司规模")
    funding_stage: Optional[str] = Field(None, description="融资阶段")
    
    categories: Optional[List[str]] = Field(None, description="订阅的政策类别(别名)")
    business_scope: Optional[List[str]] = Field(None, description="业务范围(别名)")
    policy_categories: Optional[List[str]] = Field(None, description="订阅的政策类别")
    
    keywords: List[str] = Field(default_factory=list, description="关键词")
    
    notification_methods: Optional[List[str]] = Field(None, description="通知方式(别名)")
    notification_channels: Optional[List[str]] = Field(None, description="通知渠道")
    
    notification_frequency: NotificationFrequency = Field(
        default=NotificationFrequency.DAILY,
        description="通知频率"
    )
    notification_email: Optional[str] = Field(None, description="通知邮箱")
    notification_webhook: Optional[str] = Field(None, description="Webhook URL")
    notification_phone: Optional[str] = Field(None, description="通知手机")
    
    severity_threshold: Optional[float] = Field(None, description="严重程度阈值")
    subscription_days: int = Field(default=365, ge=1, le=3650, description="订阅天数")
    
    @model_validator(mode='before')
    @classmethod
    def normalize_categories(cls, values):
        if isinstance(values, dict):
            cats = values.get('categories') or values.get('business_scope') or values.get('policy_categories')
            if cats:
                values['policy_categories'] = cats
            else:
                values['policy_categories'] = values.get('policy_categories', [])
            
            methods = values.get('notification_methods') or values.get('notification_channels')
            if methods:
                values['notification_channels'] = methods
        return values
    
    def get_categories(self) -> List[str]:
        return self.categories or self.business_scope or self.policy_categories or []
    
    def get_notification_methods(self) -> List[str]:
        return self.notification_methods or self.notification_channels or []

    class Config:
        json_schema_extra = {
            "example": {
                "enterprise_id": "ent-123",
                "industry": "technology",
                "region": "beijing",
                "company_size": "small",
                "business_scope": ["tax", "subsidy", "finance"],
                "notification_methods": ["email", "in_app"],
                "severity_threshold": 0.6
            }
        }


class PolicySubscriptionResponse(BaseModel):
    """政策订阅响应"""
    subscription_id: str = Field(..., description="订阅ID")
    status: SubscriptionStatus = Field(..., description="订阅状态")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
    message: str = Field(..., description="状态消息")


class PolicyUpdateNotification(BaseModel):
    """政策更新通知"""
    notification_id: str = Field(..., description="通知ID")
    subscription_id: str = Field(..., description="订阅ID")
    user_id: str = Field(..., description="用户ID")
    policy_updates: List[PolicyUpdate] = Field(default_factory=list, description="政策更新列表")
    new_policies_count: int = Field(0, description="新政策数量")
    amended_policies_count: int = Field(0, description="修订政策数量")
    high_impact_count: int = Field(0, description="高影响政策数量")
    sent_at: datetime = Field(default_factory=datetime.now, description="发送时间")
    notification_channel: NotificationChannel = Field(..., description="通知渠道")
    read_status: bool = Field(default=False, description="是否已读")


class PolicyTrendAnalysis(BaseModel):
    """政策趋势分析"""
    trend_id: str = Field(..., description="趋势ID")
    period_start: date = Field(..., description="分析期间开始")
    period_end: date = Field(..., description="分析期间结束")
    
    total_policies: int = Field(0, description="政策总数")
    new_policies: int = Field(0, description="新增政策数")
    amended_policies: int = Field(0, description="修订政策数")
    
    policies_by_category: Dict[str, int] = Field(default_factory=dict, description="各类别政策数量")
    policies_by_impact: Dict[str, int] = Field(default_factory=dict, description="各级别政策数量")
    
    key_themes: List[str] = Field(default_factory=list, description="关键主题")
    regulatory_focus: List[str] = Field(default_factory=list, description="监管重点")
    
    upcoming_changes: List[str] = Field(default_factory=list, description="即将到来的变化")
    compliance_deadlines: List[Dict[str, str]] = Field(default_factory=list, description="合规截止日期")
    
    insights: List[str] = Field(default_factory=list, description="洞察")
    recommendations: List[str] = Field(default_factory=list, description="建议")


class PolicyQueryRequest(BaseModel):
    """政策查询请求"""
    tenant_id: str = Field(..., description="租户ID")
    keywords: Optional[List[str]] = Field(None, description="关键词")
    categories: Optional[List[PolicyCategory]] = Field(None, description="政策类别")
    impact_levels: Optional[List[PolicyImpactLevel]] = Field(None, description="影响级别")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    limit: int = Field(50, ge=1, le=200, description="返回数量")
    offset: int = Field(0, ge=0, description="偏移量")

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant-456",
                "keywords": ["增值税", "优惠政策"],
                "categories": ["tax"],
                "impact_levels": ["high", "critical"],
                "limit": 50
            }
        }


class PolicyQueryResponse(BaseModel):
    """政策查询响应"""
    total_count: int = Field(..., description="总数")
    policies: List[PolicyUpdate] = Field(default_factory=list, description="政策列表")
    has_more: bool = Field(..., description="是否有更多")


class NotificationPreferences(BaseModel):
    """通知偏好设置"""
    user_id: str = Field(..., description="用户ID")
    tenant_id: str = Field(..., description="租户ID")
    
    enable_in_app: bool = Field(default=True, description="启用应用内通知")
    enable_email: bool = Field(default=True, description="启用邮件通知")
    enable_sms: bool = Field(default=False, description="启用短信通知")
    enable_webhook: bool = Field(default=False, description="启用Webhook")
    
    email_address: Optional[str] = Field(None, description="邮箱地址")
    phone_number: Optional[str] = Field(None, description="手机号码")
    webhook_url: Optional[str] = Field(None, description="Webhook URL")
    
    quiet_hours_start: Optional[str] = Field(None, description="免打扰开始时间")
    quiet_hours_end: Optional[str] = Field(None, description="免打扰结束时间")
    
    min_impact_level: PolicyImpactLevel = Field(
        default=PolicyImpactLevel.MEDIUM,
        description="最低通知影响级别"
    )
    
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class ComplianceDeadline(BaseModel):
    """合规截止日期"""
    deadline_id: str = Field(..., description="截止日期ID")
    policy_name: str = Field(..., description="政策名称")
    requirement: str = Field(..., description="合规要求")
    deadline_date: date = Field(..., description="截止日期")
    days_remaining: int = Field(..., description="剩余天数")
    urgency_level: str = Field(..., description="紧急程度")
    status: str = Field(..., description="状态")
    action_items: List[str] = Field(default_factory=list, description="待办事项")
    responsible_person: Optional[str] = Field(None, description="负责人")


class ComplianceCalendar(BaseModel):
    """合规日历"""
    calendar_id: str = Field(..., description="日历ID")
    tenant_id: str = Field(..., description="租户ID")
    period_start: date = Field(..., description="期间开始")
    period_end: date = Field(..., description="期间结束")
    deadlines: List[ComplianceDeadline] = Field(default_factory=list, description="截止日期列表")
    upcoming_count: int = Field(0, description="即将到期数量")
    overdue_count: int = Field(0, description="已逾期数量")
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")
