from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Optional, Dict, Any

# ==========================================
# 1. 基础模型 (Base)
# ==========================================
# 这里定义所有 Document 模型通用的字段。
# 无论是创建还是返回，都有这些东西。
class DocumentBase(BaseModel):
    filename: str = Field(..., description="文件的原始名称")
    file_type: Optional[str] = Field(None, description="文件类型，如 application/pdf")
    file_size: Optional[int] = Field(None, description="文件大小(字节)")
    status: str = Field("pending", description="当前状态: pending/parsing/completed/failed")
    meta_info: Dict[str, Any] = Field(default=dict, description="额外的元数据，如作者、页数等")

# ==========================================
# 2. 创建模型 (Create) - 暂时留空
# ==========================================
# 通常用于接收前端传来的 JSON 数据。
# 但文件上传比较特殊（用的是 Form Data），所以这里暂时不需要额外的字段。
class DocumentCreate(DocumentBase):
    pass

# ==========================================
# 3. 响应模型 (Response)
# ==========================================
# 这是核心！这是真正返回给前端看到的 JSON 结构。
# 它必须包含数据库生成的 id 和 created_at。
class DocumentResponse(DocumentBase):
    id: UUID
    created_at: datetime
    error_msg: Optional[str] = None

    # 【关键配置】
    # 告诉 Pydantic："请允许我直接从 SQLAlchemy 的数据库对象里读取数据"
    # 如果没有这行，你把数据库对象传给它，它会报错说"这不是一个字典"。
    class Config:
        from_attributes = True