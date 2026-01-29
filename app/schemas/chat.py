from pydantic import BaseModel, Field
from typing import List, Optional, Any, Annotated
# 复用之前定义的 SearchResultItem，这样前端可以直接看到引用来源
from app.schemas.search import SearchResultItem


class ChatRequest(BaseModel):
    query: str  # 用户的问题
    top_k: int = 5  # 引用几段资料 (GLM-4.7窗口很大，可以适当多传一点，比如3-5段)

    # 预留历史对话字段 (本期先不做多轮对话，但留个口子)
    # ❌ 错误写法: history: List[dict] = []
    history: Annotated[List[dict], Field(default_factory=list)]


class ChatResponse(BaseModel):
    answer: str  # AI 生成的回答
    sources: List[SearchResultItem]  # 你的回答参考了哪些文件 (证据)
    total_time: float  # 总耗时
    model_used: str  # 告诉你到底用了哪个模型