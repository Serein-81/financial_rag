# app/models/chat.py
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, func, JSON, Float, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid
from app.db.base import Base


class ChatSession(Base):
    """会话窗口（比如左侧列表的一个个对话）"""
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    title = Column(String, default="New Chat")  # 会话标题
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="chat_sessions")
    # 💡 修复点：加上级联删除。这样当你删 session 时，它名下的 messages 也会被自动删干净。
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    """具体的每一条对话记录"""
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"))
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)

    # 存放引用来源，JSON格式，方便以后前端回显
    sources = Column(JSON, nullable=True)

    # 🆕 情景记忆增强字段
    embedding = Column(Vector(2048), nullable=True)  # 向量嵌入（2048维）
    importance = Column(Float, default=0.5)  # 重要性评分（0.0-1.0）
    access_count = Column(Integer, default=0)  # 访问次数
    last_accessed = Column(DateTime(timezone=True), default=func.now())  # 最后访问时间

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")