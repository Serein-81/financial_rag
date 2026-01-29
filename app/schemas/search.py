from pydantic import BaseModel
from typing import List, Optional, Any

# 用户搜索时的请求体
class SearchRequest(BaseModel):
    query: str              # 用户的问题
    top_k: int = 5          # 返回几条结果
    kb_id: Optional[str] = None # (可选) 指定在哪个知识库搜

# 单个搜索结果的结构
class SearchResultItem(BaseModel):
    chunk_id: str
    document_id: str
    score: float            # 相似度分数 (0~1之间)
    content: str            # 查到的正文
    source_file: str        # 来源文件名 (方便告诉用户出自哪里)
    page_number: Optional[int] = None

# 接口返回的整体结构
class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    total_time: float       # 搜索耗时 (秒)