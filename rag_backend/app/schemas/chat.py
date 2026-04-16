# app/schemas/chat.py
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Annotated
# 假设 SearchResultItem 定义在 app.schemas.search 里
# 如果找不到，请检查 app/schemas/search.py 是否存在
from app.schemas.search import SearchResultItem


# --- 基础请求体 (V1 无状态接口使用) ---
class ChatRequest(BaseModel):
    query: str  # 用户的问题

    top_k: int = 5  # 引用几段资料

    # 📝 新增：指定知识库 ID (可选)
    # 如果不传，默认搜索所有库，或者根据业务逻辑处理
    kb_id: Optional[str] = None

    # 历史对话
    # 使用 default_factory=list 防止“可变默认参数”陷阱
    history: Annotated[List[Dict[str, Any]], Field(default_factory=list)]


# --- 进阶请求体 (V2 持久化接口使用) ---
class ChatRequestPersistent(ChatRequest):
    """
    V2 接口专用：继承自 ChatRequest，但多了一个 session_id
    """
    # 如果传了 session_id，后端会去查数据库恢复上下文
    # 如果没传 (null)，后端会新建一个会话
    session_id: Optional[str] = None


# --- 响应体 (非流式接口使用) ---
class ChatResponse(BaseModel):
    answer: str  # AI 生成的回答
    sources: List[SearchResultItem]  # 你的回答参考了哪些文件 (证据)
    total_time: float  # 总耗时
    model_used: str  # 告诉你到底用了哪个模型


class ChatMessageSchema(BaseModel):
    """ChatMessage 的序列化 schema（不包含 embedding 等不可序列化的字段）"""
    id: str
    session_id: str
    role: str
    content: str
    sources: Optional[Any] = None
    created_at: str
    sender_name: Optional[str] = None
    sender_avatar: Optional[str] = None

    class Config:
        from_attributes = True


class ChatSessionSchema(BaseModel):
    """ChatSession 的序列化 schema（确保时间字段格式正确）"""
    id: str
    title: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True