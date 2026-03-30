import uuid
from sqlalchemy import Column, Text, Integer, Float, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class SearchLog(Base):
    """
    搜索日志模型
    记录用户的每一次搜索行为
    """
    __tablename__ = "search_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query = Column(Text, nullable=False)
    result_count = Column(Integer, default=0)
    latency = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())