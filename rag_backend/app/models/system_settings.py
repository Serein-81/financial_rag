# app/models/system_settings.py

"""
系统级（部署级）配置表

用于存储不适合按租户隔离的全局配置，例如 Embedding / Rerank 模型配置
（向量列维度固定 + 服务为全局单例，故这类配置是部署级而非租户级）。
键值结构：key 唯一，value 存 JSON。
"""

from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class SystemSetting(Base):
    """部署级键值配置"""
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(JSONB, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SystemSetting(key={self.key})>"
