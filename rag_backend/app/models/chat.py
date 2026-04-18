# app/models/chat.py
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, func, Float, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid
from app.db.base import Base


class ChatSession(Base):
    """会话窗口（比如左侧列表的一个个对话）"""
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # 与数据库一致：nullable
    tenant_id = Column(String(50), nullable=True, index=True)  # 与数据库一致：nullable
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
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=True)  # 与数据库一致：nullable
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)

    # 注意：数据库中使用的是 json，不是 jsonb
    sources = Column(JSON, nullable=True)
    tenant_id = Column(String(50), nullable=True, index=True)  # 与数据库一致：nullable

    embedding = Column(Vector(1024), nullable=True)
    importance = Column(Float, default=0.5)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime(timezone=True), default=func.now())

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")

    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)

    model_name = Column(String(100), nullable=True)
    agent_name = Column(String(100), nullable=True)
    turn = Column(Integer, default=1)

    session_total_tokens = Column(Integer, nullable=True)

    def to_log_dict(self) -> dict:
        """转换为对话日志格式"""
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "role": self.role,
            "content": self.content,
            "sources": self.sources,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model_name": self.model_name,
            "agent_name": self.agent_name,
            "turn": self.turn,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def calculate_message_size(cls, message: "ChatMessage") -> int:
        """计算消息占用的存储空间（字节）"""
        import sys
        content_size = sys.getsizeof(message.content or "")
        embedding = message.embedding
        if embedding is not None and hasattr(embedding, '__len__'):
            embedding_size = sys.getsizeof(embedding) if hasattr(embedding, 'tolist') else sys.getsizeof(list(embedding))
        else:
            embedding_size = 0
        return content_size + embedding_size