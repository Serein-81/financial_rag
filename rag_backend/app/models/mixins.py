"""
SQLAlchemy Model Mixins

提供可复用的模型功能组件

使用方式：
    from app.models.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
    
    class MyModel(Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin):
        __tablename__ = "my_table"
        
        # 自定义字段...
        name = Column(String(100))
"""

from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid


class TenantMixin:
    """
    租户隔离 Mixin
    
    为模型添加 tenant_id 字段，用于多租户数据隔离
    
    使用场景：
        - 所有需要租户隔离的数据表
        - 与 BaseRepository 配合使用
        
    注意：
        - tenant_id 字段会自动添加索引
        - 所有 CRUD 操作都会自动添加 tenant_id 过滤
    """
    tenant_id = Column(
        String(50),
        nullable=False,
        index=True,
        doc="租户ID，用于多租户隔离"
    )


class TimestampMixin:
    """
    时间戳 Mixin
    
    自动管理 created_at 和 updated_at 字段
    
    使用场景：
        - 需要审计追踪的数据表
        - 需要知道记录创建和修改时间
        
    注意：
        - created_at 在创建时自动设置
        - updated_at 在每次修改时自动更新
    """
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="记录创建时间"
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="记录最后更新时间"
    )


class UUIDPrimaryKeyMixin:
    """
    UUID 主键 Mixin
    
    提供标准化的 UUID 主键
    
    使用场景：
        - 需要全局唯一 ID 的数据表
        - 分布式环境下的主键生成
        
    优点：
        - 全局唯一，无冲突风险
        - 无法通过 ID 猜测其他记录
        - URL 中不暴露真实 ID 顺序
    """
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="UUID 主键"
    )


class TenantTimestampMixin(TenantMixin, TimestampMixin):
    """
    组合 Mixin：租户 + 时间戳
    
    使用场景：
        - 大多数业务数据表
        - 需要同时支持租户隔离和审计追踪
        
    等同于同时继承 TenantMixin 和 TimestampMixin
    """
    pass


class FullMixin(TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin):
    """
    完整 Mixin：租户 + 时间戳 + UUID 主键
    
    使用场景：
        - 标准的业务数据表
        - 需要完整元数据支持的场景
        
    推荐用于：
        - 文档、报告等核心业务实体
        - 需要完整审计追踪的数据表
    """
    pass


class SoftDeleteMixin:
    """
    软删除 Mixin
    
    提供 is_deleted 字段用于软删除
    
    使用场景：
        - 需要保留删除记录的数据表
        - 需要审计删除操作的数据表
        
    注意：
        - 删除操作会设置 is_deleted = True
        - 查询会自动过滤已删除的记录
        - 可以通过 BaseRepository.include_deleted() 包含已删除记录
    """
    is_deleted = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="软删除时间，为 NULL 表示未删除"
    )
    
    @property
    def is_soft_deleted(self) -> bool:
        """检查记录是否已软删除"""
        return self.is_deleted is not None


class TenantSoftDeleteMixin(TenantMixin, SoftDeleteMixin):
    """
    组合 Mixin：租户 + 软删除
    
    使用场景：
        - 需要同时支持租户隔离和软删除的数据表
        - 核心业务实体，需要数据恢复能力
    """
    pass
