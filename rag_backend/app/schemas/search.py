from pydantic import BaseModel
from typing import List, Optional, Any, Literal, Callable, Union
from datetime import datetime

# 用户搜索时的请求体
class SearchRequest(BaseModel):
    query: str              # 用户的问题
    top_k: int = 5          # 返回几条结果
    kb_id: Optional[str] = None # (可选) 指定在哪个知识库搜
    score_threshold: float = 0.3  # 相似度阈值


# 🆕 同义词混合搜索请求
class HybridSynonymSearchRequest(BaseModel):
    """支持同义词扩展的混合搜索请求"""
    query: str
    top_k: int = 10
    kb_id: Optional[str] = None
    enable_synonym: bool = True  # 启用同义词扩展
    enable_fulltext: bool = True  # 启用全文搜索
    vector_weight: float = 0.5  # 向量搜索权重
    synonym_weight: float = 0.3  # 同义词搜索权重
    fulltext_weight: float = 0.2  # 全文搜索权重
    score_threshold: float = 0.3  # 相似度阈值


# 🆕 回调消息Schema
class CallbackMessage(BaseModel):
    """回调消息结构"""
    status: Literal["info", "success", "warning", "error"]  # 消息状态
    message: str  # 消息内容
    progress: Optional[float] = None  # 进度 (0.0 - 1.0)
    timestamp: datetime = datetime.now()  # 时间戳
    source: Optional[str] = None  # 来源 (tavily, search, etc.)


# 🆕 带回调的搜索请求
class SearchWithCallbackRequest(BaseModel):
    """支持Web检索和回调的搜索请求"""
    query: str
    top_k: int = 5
    kb_id: Optional[str] = None
    enable_web: bool = False  # 是否启用Web检索
    enable_callback: bool = True  # 是否启用回调
    score_threshold: float = 0.3  # 相似度阈值


# 🆕 Web搜索结果Schema
class WebSearchResult(BaseModel):
    """Web搜索结果项"""
    chunk_id: str
    score: float
    content: str
    source_file: str  # URL
    title: Optional[str] = None
    source: str = "web"


# 🆕 混合搜索响应
class HybridSearchResponse(BaseModel):
    """混合搜索响应（知识库 + Web）"""
    kb_results: List[Any] = []  # 知识库结果 (SearchResultItem)
    web_results: List[WebSearchResult] = []  # Web搜索结果
    total_kb: int = 0
    total_web: int = 0
    search_time: float = 0.0  # 搜索耗时
    web_available: bool = True  # Web服务是否可用

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