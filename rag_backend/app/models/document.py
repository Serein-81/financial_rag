import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base
from pgvector.sqlalchemy import Vector


class DocumentVisibility(str):
    PRIVATE = "private"   # 私人文档：仅上传者可见
    PUBLIC = "public"      # 公开文档：整个企业可见


class Document(Base):
    """
    文档数据模型
    """
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 🟢 租户隔离字段
    tenant_id = Column(String(50), nullable=True, index=True)  # 与数据库一致：nullable

    # 🌟 [关键修复 1] 绑定到 knowledge_bases 表，加上级联删除和索引！
    kb_id = Column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=True,  # 与数据库一致：nullable
        index=True
    )

    # 🔐 上传者ID（用于文档可见性控制）
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,  # 与数据库一致：nullable
        index=True
    )

    # 🔐 文档可见性：private（仅上传者）/ public（企业可见）
    visibility = Column(
        String(20),
        default=DocumentVisibility.PRIVATE,
        nullable=False,
        index=True
    )

    filename = Column(String(255), nullable=False)
    hash = Column(String(32), index=True, nullable=True)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(200), nullable=True)
    file_size = Column(Integer, nullable=True)

    status = Column(String(20), default="pending")
    error_msg = Column(Text, nullable=True)
    meta_info = Column(JSONB, default={})

    # 🔢 文档向量嵌入（使用 halfvec 类型，768维，适配 bge-m3 模型）
    embedding = Column(Vector(768), nullable=True)

    # 🌟 [关键修复 2] 彻底解决创建时间为空的报错
    created_at = Column(DateTime(timezone=True), default=func.now(), server_default=func.now())

    def __repr__(self):
        return f"<Document(id={self.id}, filename='{self.filename}', status='{self.status}', visibility='{self.visibility}')>"