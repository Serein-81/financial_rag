"""
情景记忆模型

与 ChatMessage 解耦，情景记忆独立存储。
chat_messages 表只由 persist_chat_message (chat.py) 写入，用于聊天历史显示。
episodic_memories 表只由 EpisodicMemory.add() 写入，用于记忆检索和向量匹配。
两表互不干扰，从根源上杜绝重复记录。
"""

import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, func, Float, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.db.base import Base


class EpisodicMemoryRecord(Base):
    """
    情景记忆持久化记录

    用途：存储对话的向量化记忆，供情景记忆系统检索相似对话。
    与 ChatMessage 的区别：
    - ChatMessage：聊天历史展示，由 persist_chat_message 写入
    - EpisodicMemoryRecord：记忆检索，由 EpisodicMemory.add() 写入
    """
    __tablename__ = "episodic_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)

    sources = Column(JSON, nullable=True)

    # 记忆管理专用字段
    embedding = Column(Vector(1024), nullable=True)   # 向量嵌入（用于相似度检索）
    importance = Column(Float, default=0.5)            # 重要性评分
    access_count = Column(Integer, default=0)          # 访问次数
    last_accessed = Column(DateTime(timezone=True), default=func.now())  # 最后访问时间

    created_at = Column(DateTime(timezone=True), server_default=func.now())
