"""
统一检索服务 (Unified Retriever Service)

整合 Memory、RAG 和 Graph，根据智能路由结果执行相应的检索
增强支持知识图谱检索
"""

import logging
from typing import List, Dict, Any, Optional
from app.services.smart_router import smart_router, RouteMode
from app.services.search_service import search_service
from app.memory_system.memory_manager import MemoryManager
from app.memory_system.base_memory import MemoryItem
from app.core.config import settings

logger = logging.getLogger(__name__)


class UnifiedRetriever:
    """
    统一检索器
    
    根据智能路由结果，自动选择使用 Memory、RAG 或混合检索
    """
    
    def __init__(self):
        """初始化统一检索器"""
        pass
    
    async def retrieve(
        self,
        query: str,
        kb_id: str,
        session_id: str,
        user_id: str,
        top_k: int = 5,
        enable_routing: bool = True,
        enable_graph: bool = True,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        统一检索接口（增强版，支持图谱检索）
        
        Args:
            query: 用户查询
            kb_id: 知识库ID
            session_id: 会话ID
            user_id: 用户ID
            top_k: 返回结果数量
            enable_routing: 是否启用智能路由
            enable_graph: 是否启用图谱检索
            tenant_id: 租户ID（必需用于图谱检索）
            
        Returns:
            检索结果字典，包含：
            - mode: 使用的检索模式
            - rag_results: RAG 检索结果
            - memory_results: Memory 检索结果
            - graph_results: Graph 检索结果
            - combined_context: 合并后的上下文
            - use_graph: 是否使用了图谱
        """
        graph_results: Dict[str, Any] = {}
        use_graph = False
        
        if enable_routing:
            route_mode = await smart_router.route(query)
        else:
            route_mode = RouteMode.HYBRID
        
        rag_results = []
        memory_results: Dict[str, List[MemoryItem]] = {}
        
        if route_mode == RouteMode.GREETING:
            return {
                "mode": route_mode.value,
                "rag_results": [],
                "memory_results": {},
                "graph_results": {},
                "combined_context": "",
                "query": query,
                "use_graph": False
            }
        
        if route_mode == RouteMode.RAG_ONLY:
            rag_results = await self._retrieve_from_rag(query, kb_id, top_k)
        elif route_mode == RouteMode.MEMORY_ONLY:
            memory_results = await self._retrieve_from_memory(query, session_id, user_id, top_k)
        else:
            rag_results = await self._retrieve_from_rag(query, kb_id, top_k)
            memory_results = await self._retrieve_from_memory(query, session_id, user_id, top_k)
        
        if enable_graph and tenant_id and settings.ENABLE_KNOWLEDGE_GRAPH:
            try:
                from app.services.graph_query_classifier import graph_query_classifier, GraphQueryType
                
                query_type, need_graph = await graph_query_classifier.classify(query)
                
                if need_graph:
                    try:
                        from app.services.graph_retriever import graph_retriever
                        
                        graph_results = await graph_retriever.retrieve_context(
                            query=query,
                            tenant_id=tenant_id,
                            top_k=top_k
                        )
                        use_graph = graph_results.get("found", False)
                        logger.info(f"[统一检索] 图谱检索返回 {len(graph_results.get('entities', []))} 个实体")
                    except Exception as e:
                        logger.warning(f"[统一检索] 图谱检索失败: {e}")
                        graph_results = {}
                        use_graph = False
            except Exception as e:
                logger.warning(f"[统一检索] 图谱分类失败: {e}")
        
        combined_context = self._combine_context(rag_results, memory_results, graph_results, route_mode)
        
        return {
            "mode": route_mode.value,
            "rag_results": rag_results,
            "memory_results": memory_results,
            "graph_results": graph_results,
            "combined_context": combined_context,
            "query": query,
            "use_graph": use_graph
        }
    
    async def _retrieve_from_rag(
        self, query: str, kb_id: str, top_k: int
    ) -> List[Any]:
        """从 RAG 检索"""
        try:
            results = await search_service.search(
                query=query,
                top_k=top_k,
                kb_id=kb_id
            )
            return results if results else []
        except Exception as e:
            print(f"⚠️ [RAG 检索] 失败: {e}")
            return []
    
    async def _retrieve_from_memory(
        self, query: str, session_id: str, user_id: str, top_k: int
    ) -> Dict[str, List[MemoryItem]]:
        """从 Memory 检索"""
        try:
            memory_manager = MemoryManager(session_id, user_id)
            results = await memory_manager.retrieve_context(
                query=query,
                use_working=True,
                use_episodic=True,
                use_semantic=True,
                top_k=top_k
            )
            return results
        except Exception as e:
            print(f"⚠️ [Memory 检索] 失败: {e}")
            return {"working": [], "episodic": [], "semantic": []}
    
    def _combine_context(
        self,
        rag_results: List[Any],
        memory_results: Dict[str, List[MemoryItem]],
        graph_results: Dict[str, Any],
        mode: RouteMode
    ) -> str:
        """
        合并 RAG、Memory 和 Graph 的上下文
        
        优先级：Memory > Graph > RAG
        
        Args:
            rag_results: RAG 检索结果
            memory_results: Memory 检索结果
            graph_results: Graph 检索结果
            mode: 路由模式
            
        Returns:
            格式化的上下文字符串
        """
        context_parts = []
        
        if memory_results:
            if memory_results.get("working"):
                working_context = "【当前对话】\n"
                for item in memory_results["working"]:
                    working_context += f"{item.role}: {item.content}\n"
                context_parts.append(working_context)
            
            if memory_results.get("semantic"):
                semantic_context = "\n【个人知识库】\n"
                for item in memory_results["semantic"][:3]:
                    semantic_context += f"- {item.content}\n"
                context_parts.append(semantic_context)
            
            if memory_results.get("episodic"):
                episodic_context = "\n【相关历史】\n"
                for item in memory_results["episodic"][:2]:
                    episodic_context += f"{item.role}: {item.content[:100]}...\n"
                context_parts.append(episodic_context)
        
        if graph_results and graph_results.get("context"):
            context_parts.append(graph_results["context"])
        
        if rag_results:
            rag_context = "\n<KnowledgeBase>\n"
            for idx, result in enumerate(rag_results[:5], 1):
                rag_context += f"{idx}. {result.content[:200]}...\n"
                rag_context += f"   来源: {result.source_file}\n\n"
            rag_context += "</KnowledgeBase>\n"
            context_parts.append(rag_context)
        
        if mode == RouteMode.HYBRID:
            context_parts.insert(0, "<ContextSource type='hybrid'>以下内容包含知识库文档和个人对话记忆\n")
        elif mode == RouteMode.MEMORY_ONLY:
            context_parts.insert(0, "<ContextSource type='memory'>以下内容来自个人对话记忆\n")
        elif mode == RouteMode.RAG_ONLY:
            context_parts.insert(0, "<ContextSource type='rag'>以下内容来自知识库文档\n")
        
        return "\n".join(context_parts)
    
    async def get_formatted_context_for_llm(
        self,
        query: str,
        kb_id: str,
        session_id: str,
        user_id: str,
        max_tokens: int = 2000
    ) -> str:
        """
        获取格式化的上下文，用于传递给 LLM
        
        Args:
            query: 用户查询
            kb_id: 知识库ID
            session_id: 会话ID
            user_id: 用户ID
            max_tokens: 最大 token 数（粗略估算）
            
        Returns:
            格式化的上下文字符串
        """
        result = await self.retrieve(
            query=query,
            kb_id=kb_id,
            session_id=session_id,
            user_id=user_id,
            top_k=5
        )
        
        context = result["combined_context"]
        
        # 简单的长度控制（1 token ≈ 1.5 字符）
        max_chars = max_tokens * 1.5
        if len(context) > max_chars:
            context = context[:int(max_chars)] + "\n...(内容过长，已截断)"
        
        return context


# 全局单例
unified_retriever = UnifiedRetriever()
