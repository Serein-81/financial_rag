# app/models/knowledge_base.py
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from sqlalchemy.orm import relationship
from app.db import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    # 1. 对应数据库里的 id (UUID)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 2. 对应 name (varchar 255)
    name = Column(String(255), nullable=False)

    # 3. 对应 description (text)
    description = Column(Text, nullable=True)

    # 4. 对应 created_at (timestamptz)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 5. 对应 user_id (uuid) - 外键关联到 users 表
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # (可选) 定义反向关系，方便以后 user.knowledge_bases 这样查
    # owner = relationship("User", back_populates="knowledge_bases")