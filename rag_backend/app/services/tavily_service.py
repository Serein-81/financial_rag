"""
Web检索服务 - 基于Tavily API
提供实时网络搜索能力，补充知识库检索
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class TavilyService:
    """
    Tavily Web检索服务
    
    功能：
    - 实时网络搜索
    - 支持自定义搜索深度
    - 自动去重和相关性过滤
    """
    
    def __init__(self):
        self.api_key = settings.TAVILY_API_KEY
        self.max_results = getattr(settings, 'TAVILY_MAX_RESULTS', 5)
        self.client = None
        
        if self.api_key and TavilyClient:
            try:
                self.client = TavilyClient(api_key=self.api_key)
                logger.info(f"✅ Tavily服务初始化成功 (max_results={self.max_results})")
            except Exception as e:
                logger.error(f"❌ Tavily客户端初始化失败: {e}")
                self.client = None
        else:
            logger.warning("⚠️ Tavily API未配置或tavily库未安装")
    
    def is_available(self) -> bool:
        """检查服务是否可用"""
        return self.client is not None
    
    async def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        search_depth: str = "basic",
        include_answer: bool = False,
        include_raw_content: bool = False,
        include_images: bool = False
    ) -> Dict[str, Any]:
        """
        执行Web搜索
        
        Args:
            query: 搜索查询
            max_results: 最大结果数，默认使用配置值
            search_depth: 搜索深度，"basic" 或 "advanced"
            include_answer: 是否包含AI生成的答案
            include_raw_content: 是否包含原始内容
            include_images: 是否包含图片
            
        Returns:
            搜索结果字典
        """
        if not self.is_available():
            logger.warning("⚠️ Tavily服务不可用，返回空结果")
            return self._empty_result()
        
        try:
            results = self.client.search(
                query=query,
                max_results=max_results or self.max_results,
                search_depth=search_depth,
                include_answer=include_answer,
                include_raw_content=include_raw_content,
                include_images=include_images
            )
            
            logger.info(f"🔍 Tavily搜索完成 | 查询: {query[:30]}... | 结果: {len(results.get('results', []))}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Tavily搜索失败: {e}", exc_info=True)
            return self._empty_result()
    
    async def search_with_callback(
        self,
        query: str,
        callback: Optional[Callable] = None,
        max_results: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        带回调的Web搜索
        
        Args:
            query: 搜索查询
            callback: 进度回调函数
            max_results: 最大结果数
            
        Returns:
            搜索结果字典
        """
        await self._emit_callback(callback, "🌐 正在发起Web搜索...", "info")
        
        if not self.is_available():
            await self._emit_callback(callback, "⚠️ Web搜索服务不可用", "warning")
            return self._empty_result()
        
        try:
            start_time = datetime.now()
            results = await self.search(query, max_results=max_results)
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            result_count = len(results.get('results', []))
            
            if result_count > 0:
                await self._emit_callback(
                    callback,
                    f"✅ Web搜索完成 | 耗时: {elapsed_ms:.0f}ms | 找到 {result_count} 条结果",
                    "success"
                )
            else:
                await self._emit_callback(callback, "⚠️ Web搜索未找到相关结果", "warning")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Web搜索失败: {e}", exc_info=True)
            await self._emit_callback(callback, f"❌ Web搜索失败: {str(e)}", "error")
            return self._empty_result()
    
    async def retrieve_chunks(
        self,
        query: str,
        top_k: int = 5,
        callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """
        获取格式化的搜索片段，用于RAG上下文
        
        Args:
            query: 搜索查询
            top_k: 返回前k个结果
            callback: 进度回调
            
        Returns:
            格式化的文档片段列表
        """
        results = await self.search_with_callback(query, callback, max_results=top_k)
        
        chunks = []
        for idx, result in enumerate(results.get('results', [])[:top_k]):
            chunk = {
                "chunk_id": f"web_{result.get('url', '')}_{idx}",
                "document_id": f"web_doc_{idx}",
                "score": result.get('score', 0.0),
                "content": self._clean_content(result.get('content', '')),
                "source_file": result.get('url', ''),
                "title": result.get('title', ''),
                "page_number": None,
                "source": "web"
            }
            chunks.append(chunk)
        
        if chunks:
            await self._emit_callback(
                callback,
                f"📄 已格式化 {len(chunks)} 个Web文档片段",
                "info"
            )
        
        return chunks
    
    def _clean_content(self, content: str, max_length: int = 2000) -> str:
        """
        清理和截断内容
        
        Args:
            content: 原始内容
            max_length: 最大长度
            
        Returns:
            清理后的内容
        """
        if not content:
            return ""
        
        cleaned = content.strip()
        
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length] + "..."
        
        return cleaned
    
    def _empty_result(self) -> Dict[str, Any]:
        """返回空结果"""
        return {
            "query": "",
            "follow_up_questions": None,
            "answer": None,
            "results": []
        }
    
    async def _emit_callback(
        self,
        callback: Optional[Callable],
        message: str,
        status: str = "info"
    ):
        """发送回调消息"""
        if callback:
            try:
                data = {
                    "status": status,
                    "message": message,
                    "timestamp": datetime.now().isoformat(),
                    "source": "tavily"
                }
                
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
                    
            except Exception as e:
                logger.warning(f"⚠️ 回调发送失败: {e}")


import asyncio

tavily_service = TavilyService()
