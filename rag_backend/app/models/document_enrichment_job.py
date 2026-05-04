"""
文档充血任务模型 (DLQ: Dead Letter Queue)

记录 Phase 2 中失败的 LLM 依赖任务，供定时任务重试。
与 Document 表解耦：文档本身已经是 'ready' 状态，不受任务失败影响。
"""

import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base


class EnrichmentJob(Base):
    """
    文档充血任务表

    记录需要异步 LLM 处理的 Phase 2 任务：
    - entity_resolve: 法务文档实体提取与替换
    - summary_generate: PARENT 节点摘要生成
    """
    __tablename__ = "enrichment_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 关联文档
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # 任务类型：entity_resolve / summary_generate
    job_type = Column(String(20), nullable=False, index=True)

    # 文档领域
    domain = Column(String(20), nullable=False)

    # 任务状态：pending / running / failed / completed / dead
    status = Column(String(20), default="pending", index=True)

    # 任务参数（如待处理的 chunk_id 列表、实体映射表等）
    payload = Column(JSONB, default={})

    # 错误信息
    error_message = Column(Text, nullable=True)

    # 重试控制
    retry_count = Column(Integer, default=0)                     # 已重试次数
    max_retries = Column(Integer, default=5)                     # 最大重试次数
    next_retry_at = Column(DateTime(timezone=True), nullable=True)  # 下一次重试时间

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    def __repr__(self):
        return (
            f"<EnrichmentJob(id={self.id}, document_id={self.document_id}, "
            f"job_type={self.job_type}, status={self.status}, "
            f"retry={self.retry_count}/{self.max_retries})>"
        )
