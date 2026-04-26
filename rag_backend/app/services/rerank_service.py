"""
Rerank 服务

使用硅基流动的 Cross-Encoder Rerank 模型进行重排序

Rerank 模型特点：
- 基于注意力机制的交叉编码器，逐字比对 Query 和 Document
- 比 Bi-Encoder 的向量相似度更精确
- 适合作为 RAG 检索的最后一道精准排序关卡
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """Rerank 结果"""
    index: int
    document: str
    relevance_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "document": self.document,
            "relevance_score": self.relevance_score
        }


class RerankService:
    """
    Rerank 服务（单例）
    
    使用硅基流动的 Cross-Encoder Rerank 模型进行重排序
    
    使用示例：
    ```python
    rerank_service = RerankService()
    
    # 批量重排序
    results = await rerank_service.rerank(
        query="什么是增值税专用发票？",
        documents=[
            "增值税专用发票是...",
            "普通发票与专用发票...",
            "企业所得税计算方法..."
        ],
        top_k=5
    )
    ```
    """
    
    _instance = None
    _client: Optional[httpx.AsyncClient] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.api_key = settings.SILICONFLOW_API_KEY
        self.model_name = getattr(settings, 'SILICONFLOW_RERANK_MODEL', 'Pro/BAAI/bge-reranker-v2-m3')
        self.base_url = "https://api.siliconflow.cn/v1/rerank"
        self.top_n = settings.RERANK_TOP_K
        self.return_documents = True
        self.score_threshold = getattr(settings, 'RERANK_SCORE_THRESHOLD', 0.5)
        
        self._initialized = True
        
        if not self.api_key:
            logger.warning("⚠️ 硅基流动 API Key 未配置，Rerank 服务将不可用")
        else:
            logger.info(f"✅ Rerank 服务初始化完成")
            logger.info(f"   - 模型: {self.model_name}")
            logger.info(f"   - Base URL: {self.base_url}")
            logger.info(f"   - API Key: {self.api_key[:8]}...{self.api_key[-4:]}")
    
    def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._client
    
    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
        max_chars_per_doc: int = 512
    ) -> List[RerankResult]:
        """
        使用 Cross-Encoder Rerank 模型对文档进行重排序
        
        Args:
            query: 查询字符串
            documents: 文档列表
            top_k: 返回前 k 个结果，None 则返回所有
            max_chars_per_doc: 每个文档最大字符数（防止超长）
            
        Returns:
            按相关性分数降序排列的 RerankResult 列表
        """
        if not self.api_key:
            logger.error("❌ 硅基流动 API Key 未配置")
            return []
        
        if not documents:
            logger.warning("⚠️ 文档列表为空")
            return []
        
        top_k = top_k or self.top_n
        
        truncated_docs = []
        for doc in documents:
            if len(doc) > max_chars_per_doc:
                truncated_docs.append(doc[:max_chars_per_doc])
            else:
                truncated_docs.append(doc)
        
        payload = {
            "model": self.model_name,
            "query": query,
            "documents": truncated_docs,
            "top_n": min(top_k, len(truncated_docs)),
            "return_documents": self.return_documents
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            client = self._get_client()
            response = await client.post(
                self.base_url,
                headers=headers,
                json=payload
            )
            
            response.raise_for_status()
            result = response.json()
            
            rerank_results = []
            for item in result.get("results", []):
                score = item.get("relevance_score", 0)
                rerank_results.append(RerankResult(
                    index=item["index"],
                    document=item["document"],
                    relevance_score=score
                ))
            
            rerank_results.sort(key=lambda x: x.relevance_score, reverse=True)
            
            logger.info(f"🎯 Rerank 完成: {len(documents)} → {len(rerank_results)} 个结果 | 最高分: {rerank_results[0].relevance_score if rerank_results else 0:.4f}")
            return rerank_results
            
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            try:
                error_json = e.response.json()
                error_message = error_json.get("message", error_detail)
                error_code = error_json.get("code", "unknown")
            except Exception:
                error_message = error_detail
                error_code = "unknown"
            
            logger.error(f"❌ Rerank API 错误: {error_code} - {error_message}")
            raise Exception(f"Rerank API 请求失败: {error_code} - {error_message}")
            
        except httpx.RequestError as e:
            logger.error(f"❌ Rerank 请求错误: {str(e)}")
            raise Exception(f"Rerank HTTP 请求错误: {str(e)}")
            
        except Exception as e:
            logger.error(f"❌ Rerank 失败: {str(e)}")
            raise
    
    async def rerank_with_metadata(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None,
        content_key: str = "content",
        max_chars_per_doc: int = 512
    ) -> List[Dict[str, Any]]:
        """
        带元数据的 Rerank
        
        保留原始文档的所有元数据信息
        
        Args:
            query: 查询字符串
            documents: 文档列表（包含 content 和其他元数据）
            top_k: 返回前 k 个结果
            content_key: 内容字段的键名
            max_chars_per_doc: 每个文档最大字符数
            
        Returns:
            带元数据的重排序结果
        """
        if not documents:
            return []
        
        contents = [doc.get(content_key, str(doc)) for doc in documents]
        original_order = list(range(len(documents)))
        
        rerank_results = await self.rerank(
            query=query,
            documents=contents,
            top_k=top_k,
            max_chars_per_doc=max_chars_per_doc
        )
        
        results_with_metadata = []
        for result in rerank_results:
            original_idx = result.index
            if 0 <= original_idx < len(documents):
                doc_with_metadata = documents[original_idx].copy()
                doc_with_metadata["rerank_score"] = result.relevance_score
                doc_with_metadata["rerank_rank"] = len(results_with_metadata) + 1
                results_with_metadata.append(doc_with_metadata)
        
        return results_with_metadata
    
    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None


rerank_service = RerankService()
