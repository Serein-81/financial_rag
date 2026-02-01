# app/models/user.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关联关系
    knowledge_bases = relationship("KnowledgeBase", back_populates="owner")
    chat_sessions = relationship("ChatSession", back_populates="user")

# class KnowledgeBase(Base):
#     __tablename__ = "knowledge_bases"
#
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
#     name = Column(String, nullable=False)
#     description = Column(String, nullable=True)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#
#     owner = relationship("User", back_populates="knowledge_bases")
#     # 注意：你需要在 Document 模型里加一个 kb_id 外键来关联这里
#     # documents = relationship("Document", back_populates="knowledge_base")