# app/models/knowledge_base.py
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func  # 👈 引入 func 用于数据库时间的默认值
from sqlalchemy.orm import relationship
import uuid
from app.db import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    # 1. 对应数据库里的 id (UUID)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # 2. 多租户字段
    tenant_id = Column(String(50), nullable=False, index=True)  # 租户ID，用于多租户隔离

    # 3. 对应 name (varchar 255)
    name = Column(String(255), nullable=False)

    # 4. 对应 description (text)
    description = Column(Text, nullable=True)

    # 4. 对应 created_at
    # 🌟 [修复] 加上 default=func.now()，让 Python 在生成 INSERT 语句时主动带上当前时间
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())

    # 5. 对应 updated_at
    # 🌟 [修复] 加上 default=func.now()，确保首次创建时也有时间！
    updated_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())

    # 5. 对应 user_id (uuid) - 外键关联到 users 表
    # 🌟 [升级] 加上 ondelete="CASCADE" 级联删除，并加上 index=True 提升鉴权查询速度
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # 6. 定义反向关系，方便以后 user.knowledge_bases 这样查
    owner = relationship("User", back_populates="knowledge_bases")