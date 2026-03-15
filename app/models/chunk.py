import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, func, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from app.db.base import Base


class DocumentChunk(Base):
    """
    文档切片模型
    存储从文档中提取出来的文本片段
    """
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 外键：关联到 Document 表
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)

    # 序号：这是第几段
    chunk_index = Column(Integer, nullable=False)

    # 内容：切分后的文本
    content = Column(Text, nullable=False)

    # 元数据：可以存这段文字所在的页码等信息
    meta_info = Column(JSONB, default={})

    # ✅ 重点修改：使用标准数组类型 ARRAY(Float)
    # 这对应数据库里的 FLOAT8[]
    embedding = Column(ARRAY(Float), nullable=True)
    
    # 新增字段：支持智能切块元数据
    heading_path = Column(String, nullable=True)  # 标题路径(如: "第一章 > 1.1节")
    chunk_start = Column(Integer, nullable=True)  # 在原文中的起始位置
    chunk_end = Column(Integer, nullable=True)    # 在原文中的结束位置
    token_count = Column(Integer, nullable=True)  # Token 数量

    created_at = Column(DateTime(timezone=True), default=func.now(),server_default=func.now())

    # 建立关系：方便以后通过 chunk.document 访问父文档
    # document = relationship("Document", back_populates="chunks")
    # (暂时先注释掉关系反向引用，避免要修改 document.py，保持简单)