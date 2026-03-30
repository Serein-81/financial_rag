from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class KnowledgeVisibility(str):
    PRIVATE = "private"
    ENTERPRISE = "enterprise"


# 1. 用于接收创建请求的 Schema (入参)
class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    visibility: str = "private"  # private 或 enterprise


# 2. (可选) 用于更新请求的 Schema
class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None  # 允许修改可见性


# 3. (可选) 用于返回给前端的 Schema (出参)
# 如果你想规范返回字段，可以用这个，而不是直接返回 ORM 对象
class KnowledgeBaseOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    visibility: str
    user_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True  # 允许从 ORM 对象读取数据