# app/models/tenant_settings.py

"""
租户设置模型

存储企业/租户的配置信息，包括企业名称、Logo、主题设置等
"""

from sqlalchemy import Column, String, DateTime, Text, Boolean, Integer, Index, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import func
import uuid
from app.db.base import Base


class TenantSettings(Base):
    """
    租户设置表

    存储企业的配置信息
    """
    __tablename__ = "tenant_settings"

    # 基础字段
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 租户标识
    tenant_id = Column(String(50), unique=True, nullable=False, index=True)

    # 企业基本信息
    company_name = Column(String(200), nullable=False, index=True)  # 企业名称
    company_logo = Column(String(500), nullable=True)  # 企业Logo URL
    company_description = Column(Text, nullable=True)  # 企业描述
    company_website = Column(String(500), nullable=True)  # 企业网站
    company_address = Column(String(500), nullable=True)  # 企业地址
    company_phone = Column(String(50), nullable=True)  # 联系电话
    company_email = Column(String(255), nullable=True)  # 联系邮箱

    # 企业管理员信息
    admin_name = Column(String(100), nullable=True)  # 管理员姓名
    admin_email = Column(String(255), nullable=True)  # 管理员邮箱
    admin_phone = Column(String(50), nullable=True)  # 管理员电话

    # 企业画像（用于政策智能匹配）
    industry = Column(String(100), nullable=True, index=True)  # 企业所属行业
    region = Column(String(100), nullable=True, index=True)  # 企业所在地区
    scale = Column(String(50), nullable=True, index=True)  # 企业规模
    tax_types = Column(ARRAY(String), default=[])  # 税种类型（可多选）

    # 系统设置
    max_users = Column(Integer, default=10)  # 最大用户数
    max_storage_gb = Column(Integer, default=100)  # 最大存储空间(GB)
    max_knowledge_bases = Column(Integer, default=10)  # 最大知识库数量
    max_documents = Column(Integer, default=1000)  # 最大文档数量
    max_monthly_requests = Column(Integer, nullable=True)  # 最大月度请求次数

    # 功能开关
    enable_group_chat = Column(Boolean, default=True)  # 是否启用群聊
    enable_multi_agent = Column(Boolean, default=True)  # 是否启用多Agent
    enable_knowledge_graph = Column(Boolean, default=False)  # 是否启用知识图谱
    enable_human_review = Column(Boolean, default=True)  # 是否启用人工审核
    enable_audit = Column(Boolean, default=False)  # 是否启用审计功能
    enable_tax_report = Column(Boolean, default=False)  # 是否启用税务报表
    enable_financial_data = Column(Boolean, default=False)  # 是否启用财务数据

    # 主题和界面设置
    primary_color = Column(String(20), default="#1890ff")  # 主色调
    secondary_color = Column(String(20), nullable=True)  # 次要色调
    custom_css = Column(Text, nullable=True)  # 自定义CSS
    custom_footer = Column(Text, nullable=True)  # 自定义页脚

    # 通知设置
    email_notification = Column(Boolean, default=True)  # 是否启用邮件通知
    system_notification = Column(Boolean, default=True)  # 是否启用系统通知
    notification_email = Column(String(255), nullable=True)  # 通知接收邮箱

    # 状态
    is_active = Column(Boolean, default=True)  # 是否启用
    is_trial = Column(Boolean, default=True)  # 是否试用版
    trial_expires_at = Column(DateTime(timezone=True), nullable=True)  # 试用过期时间

    # 扩展数据（使用 JSONB 提升查询性能）
    extra_settings = Column(JSONB, nullable=True)  # 额外设置(JSON)

    # 创建索引
    __table_args__ = (
        Index('idx_tenant_settings_tenant_id', 'tenant_id'),
    )

    def __repr__(self):
        return f"<TenantSettings(tenant_id={self.tenant_id}, company_name={self.company_name})>"
