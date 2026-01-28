import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base


class Document(Base):
    """
    文档数据模型
    对应数据库中的 documents 表
    """
    # 1. 表名 (必须与数据库完全一致)
    __tablename__ = "documents"

    # 2. 字段定义
    # 主键: UUID 类型，自动生成
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ➕ 新增：必须匹配数据库里的字段！
    # 注意：如果数据库里这个字段允许为空，这里就写 nullable=True
    # 如果数据库里是必填的，我们在代码里先设为 nullable=True 防止报错，
    # 或者我们在上传时必须给它一个假的值。
    kb_id = Column(UUID(as_uuid=True), nullable=True)

    # 基础信息
    filename = Column(String(255), nullable=False)  # 文件名
    file_path = Column(String(500), nullable=False)  # 物理存储路径
    file_type = Column(String(50), nullable=True)  # 文件类型 (pdf, docx)
    file_size = Column(Integer, nullable=True)  # 文件大小 (字节)

    # 状态 (pending -> parsing -> completed/failed)
    status = Column(String(20), default="pending")

    # 错误信息 (如果解析失败，记录原因)
    error_msg = Column(Text, nullable=True)

    # 元数据 (JSON格式，存作者、页数、标签等灵活数据)
    meta_info = Column(JSONB, default={})

    # 创建时间 (数据库自动记录当前时间)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 3. 打印对象时的显示 (方便调试)
    def __repr__(self):
        return f"<Document(id={self.id}, filename='{self.filename}', status='{self.status}')>"