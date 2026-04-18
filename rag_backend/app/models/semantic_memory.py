# app/models/semantic_memory.py
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, func, Float, Integer, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid
from app.db.base import Base


class SemanticMemory(Base):
    """语义记忆数据表 - 存储用户的长期知识"""
    __tablename__ = "semantic_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 核心内容
    content = Column(Text, nullable=False)
    role = Column(String, default="system")  # system, user, assistant
    
    # 向量嵌入（1024维，适配BAAI/bge-m3模型）
    embedding = Column(Vector(1024), nullable=True)
    
    # 记忆属性
    importance = Column(Float, default=0.5)  # 重要性 0.0-1.0
    access_count = Column(Integer, default=0)  # 访问次数
    decay_factor = Column(Float, default=1.0)  # 衰减因子 0.0-1.0
    
    # 分类和标签
    memory_type = Column(String, default="knowledge")  # knowledge, preference, skill, fact
    tags = Column(ARRAY(String), nullable=True)  # 标签数组（使用 ARRAY 类型）
    
    # 元数据
    memory_metadata = Column(JSONB, nullable=True)  # 扩展信息（使用 JSONB 提升查询性能）
    source_session_id = Column(UUID(as_uuid=True), nullable=True)  # 来源会话
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_accessed = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user = relationship("User", back_populates="semantic_memories")

    def __repr__(self):
        return f"<SemanticMemory(id={self.id}, user_id={self.user_id}, type={self.memory_type})>"
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "content": self.content,
            "role": self.role,
            "importance": self.importance,
            "access_count": self.access_count,
            "decay_factor": self.decay_factor,
            "memory_type": self.memory_type,
            "tags": self.tags,
            "metadata": self.metadata,
            "source_session_id": str(self.source_session_id) if self.source_session_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None
        }