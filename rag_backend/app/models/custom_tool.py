from enum import Enum

from sqlalchemy import Boolean, Column, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base
from app.models.mixins import FullMixin


class CustomToolStatus(str, Enum):
    DRAFT = "draft"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    PUBLISHED = "published"
    DISABLED = "disabled"
    REJECTED = "rejected"


class CustomToolKind(str, Enum):
    ECHO = "echo"
    HTTP = "http"
    RAG_QUERY = "rag_query"
    PYTHON_CODE = "python_code"


class CustomTool(Base, FullMixin):
    __tablename__ = "custom_tools"
    __table_args__ = (
        Index("ix_custom_tools_tenant_name_version", "tenant_id", "name", "version", unique=True),
    )

    name = Column(String(80), nullable=False, index=True)
    display_name = Column(String(120), nullable=False)
    description = Column(Text, nullable=False)
    purpose = Column(Text, nullable=True)
    kind = Column(String(32), nullable=False, default=CustomToolKind.ECHO.value, index=True)
    status = Column(String(32), nullable=False, default=CustomToolStatus.DRAFT.value, index=True)
    version = Column(String(32), nullable=False, default="1.0.0")

    input_schema = Column(JSONB, nullable=False, default=dict)
    output_schema = Column(JSONB, nullable=False, default=dict)
    runtime_config = Column(JSONB, nullable=False, default=dict)
    safety_policy = Column(JSONB, nullable=False, default=dict)
    generated_code = Column(Text, nullable=True)

    agent_id = Column(String(100), nullable=True, index=True)
    created_by = Column(String(64), nullable=True, index=True)
    approved_by = Column(String(64), nullable=True)
    enabled = Column(Boolean, nullable=False, default=False, index=True)
