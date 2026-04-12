from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class KnowledgeVisibility(str):
    PRIVATE = "private"
    ENTERPRISE = "enterprise"


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    visibility: str = "private"


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None


class KnowledgeBaseOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    visibility: str
    user_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentOut(BaseModel):
    id: UUID
    kb_id: UUID
    user_id: UUID
    filename: str
    file_path: str
    file_type: Optional[str]
    file_size: Optional[int]
    hash: Optional[str]
    status: str
    error_msg: Optional[str]
    visibility: str
    meta_info: Optional[dict] = {}
    created_at: datetime
    chunk_count: int = 0

    class Config:
        from_attributes = True