"""
统一检索服务 (Unified Retriever Service)

整合 Memory、RAG 和 Graph，根据智能路由结果执行相应的检索
增强支持知识图谱检索
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import select

from app.core.config import settings
from app.db import AsyncSessionLocal
from app.models.chunk import DocumentChunk
from app.services.smart_router import smart_router, RouteMode
from app.services.search_service import search_service
from app.services.query_analyzer import query_analyzer
from app.services.hybrid_search import hybrid_search_engine
from app.services.rerank_service import rerank_service
from app.services.embedding_service import embedding_service
from app.services.cliff_pruner import cliff_prune
from app.services.context_assembler import context_assembler
from app.memory_system.memory_manager import MemoryManager
from app.memory_system.base_memory import MemoryItem

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
        tenant_id: Optional[str] = None,
        _skip_metric_filter: bool = False,
    ) -> Dict[str, Any]:
        """
        统一检索接口 (v3: Hybrid Search + Reranker + Domain Assembly)

        完整链路：
        QueryAnalyzer -> Hybrid Search (Dense+BM25+RRF) -> Reranker
        -> Cliff Prune -> Temporal Dedup -> Relationship Expansion
        -> Auto-Merging -> Domain-Aware Prompt Assembly
        """
        graph_results: Dict[str, Any] = {}
        use_graph = False

        if enable_routing:
            route_mode = await smart_router.route(query)
        else:
            route_mode = RouteMode.HYBRID

        memory_results: Dict[str, List[MemoryItem]] = {}

        # ── Step 1: 查询解析 ──
        query_meta = query_analyzer.analyze(query)

        if route_mode == RouteMode.GREETING:
            return {
                "mode": route_mode.value, "rag_results": [],
                "memory_results": {}, "graph_results": {},
                "combined_context": "", "query": query, "use_graph": False,
            }

        # ── Step 2: 构建过滤条件 ──
        metadata_filter = query_analyzer.build_metadata_filter(query_meta)

        # 时效过滤仅限 tax 领域（finance/legal 没有 effective_date 字段）
        domain = query_meta.get("domain")
        if domain == "tax":
            temporal_filter = query_analyzer.build_temporal_filter(query_meta)
            if temporal_filter:
                metadata_filter = {**(metadata_filter or {}), **temporal_filter}

        # 财务指标 JSONB 数组过滤（评估模式下可跳过）
        jsonb_array_filter = None
        if not _skip_metric_filter:
            metric = query_meta.get("filters", {}).get("metric")
            jsonb_array_filter = {"metrics": metric} if metric else None

        # ── Step 3: 混合检索 (Hybrid Search + RRF) ──
        candidates = await hybrid_search_engine.search(
            query=query,
            tenant_id=tenant_id,
            domain=domain,
            metadata_filter=metadata_filter,
            jsonb_array_filter=jsonb_array_filter,
        )

        # ── Step 4: Reranker + Cliff Prune ──
        pruned = await self._rerank_and_prune(query, candidates)

        # ── Step 4.5: 时序去重 ──
        deduped = await hybrid_search_engine.temporal_dedup(
            chunks=pruned, query_meta=query_meta,
        )

        # ── Step 5: 关系展开 ──
        enriched = await self._enrich_results(deduped)

        # ── Step 6: Auto-Merging (仅 general) ──
        if domain in (None, "general"):
            enriched = await hybrid_search_engine.auto_merge(enriched)

        # ── Step 7: 多态 Prompt 组装 ──
        combined_context = await context_assembler.assemble(
            chunks=enriched, domain=domain, query=query,
        )

        # ── 图谱检索（独立于主链路） ──
        if enable_graph and settings.ENABLE_KNOWLEDGE_GRAPH:
            graph_results = await self._graph_retrieval(query, kb_id, tenant_id)
            use_graph = graph_results.get("found", False)

        return {
            "mode": route_mode.value,
            "rag_results": enriched,
            "memory_results": memory_results,
            "graph_results": graph_results,
            "combined_context": combined_context,
            "query": query,
            "use_graph": use_graph,
        }

    async def _rerank_and_prune(
        self, query: str, candidates: List[Dict],
    ) -> List[Dict]:
        """Reranker + MMR 多样性 + Cliff Prune 精排截断"""
        if not candidates:
            return []

        try:
            reranked = await rerank_service.rerank(
                query=query,
                documents=[c["content"] for c in candidates],
                top_k=20, max_chars_per_doc=1000,
            )
        except Exception as e:
            logger.warning(f"[Reranker] 失败，降级为 RRF 排序: {e}")
            return candidates[:20]

        for rr in reranked:
            if rr.index < len(candidates):
                candidates[rr.index]["rerank_score"] = rr.relevance_score

        # MMR 多样性重排
        mmr_result = await self._mmr_rerank(
            query=query, candidates=candidates,
            top_k=15, lambda_param=0.6,
        )

        return cliff_prune(
            items=mmr_result, score_key="rerank_score",
            min_results=3, max_results=20, cliff_threshold=0.15,
        )

    async def _mmr_rerank(
        self, query: str, candidates: List[Dict],
        top_k: int = 15, lambda_param: float = 0.6,
    ) -> List[Dict]:
        """
        MMR (Maximal Marginal Relevance) 多样性重排。
        选出的结果既相关又不多样化，避免多个相似 chunk 同时进入上下文。
        """
        scored = [c for c in candidates if c.get("rerank_score") is not None]
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)

        if len(scored) <= top_k:
            return scored

        selected = [scored[0]]
        candidates_pool = scored[1:]

        try:
            query_emb = await embedding_service.get_embedding(query)
            if not query_emb:
                return scored[:top_k]

            selected_embs = [query_emb]
            for _ in range(min(top_k - 1, len(candidates_pool))):
                best_idx = -1
                best_score = -float("inf")

                for i, cand in enumerate(candidates_pool):
                    cand_emb = await embedding_service.get_embedding(
                        cand["content"][:500]
                    )
                    if not cand_emb:
                        continue

                    sim_to_query = self._cosine_sim(query_emb, cand_emb)
                    max_sim_to_sel = max(
                        self._cosine_sim(cand_emb, se) for se in selected_embs
                    )
                    mmr_score = lambda_param * sim_to_query - (1 - lambda_param) * max_sim_to_sel

                    if mmr_score > best_score:
                        best_score = mmr_score
                        best_idx = i

                if best_idx >= 0:
                    selected.append(candidates_pool.pop(best_idx))
                    selected_embs.append(query_emb)

        except Exception as e:
            logger.warning(f"[MMR] 失败，跳过: {e}")
            return scored[:top_k]

        return selected

    @staticmethod
    def _cosine_sim(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        return dot / (na * nb) if na and nb else 0.0

    async def _graph_retrieval(
        self, query: str, kb_id: str, tenant_id: Optional[str],
    ) -> Dict[str, Any]:
        """图谱检索（独立分支）"""
        resolved_tenant_id = tenant_id
        if not resolved_tenant_id and kb_id:
            try:
                from app.db.session import AsyncSessionLocal as _ASL
                from app.models.knowledge_base import KnowledgeBase
                async with _ASL() as db:
                    result = await db.execute(
                        select(KnowledgeBase.tenant_id).where(KnowledgeBase.id == kb_id)
                    )
                    row = result.scalar_one_or_none()
                    if row:
                        resolved_tenant_id = str(row)
            except Exception:
                pass

        if not resolved_tenant_id:
            return {"entities": [], "relations": [], "context": "", "found": False}

        try:
            from app.services.graph_query_classifier import graph_query_classifier
            _, need_graph = await graph_query_classifier.classify(query)
            if need_graph:
                from app.services.graph_retriever import graph_retriever
                return await graph_retriever.retrieve_context(
                    query=query, tenant_id=resolved_tenant_id, top_k=5,
                )
        except Exception as e:
            logger.warning(f"[Graph] 检索失败: {e}")

        return {"entities": [], "relations": [], "context": "", "found": False}

    async def _enrich_results(self, results: List[Dict]) -> List[Dict]:
        """富化结果：PARENT 摘要 + PREVIOUS/NEXT 展开"""
        if not results:
            return results
        enriched = []
        for chunk in results:
            chunk_id = chunk.get("id")
            if chunk_id:
                parent_summary = await self._resolve_parent_summary(str(chunk_id))
                if parent_summary:
                    chunk["parent_summary"] = parent_summary
                domain = chunk.get("domain")
                if domain == "tax":
                    pn = await self._resolve_prev_next(str(chunk_id))
                    if pn.get("previous"):
                        chunk["prev_content"] = pn["previous"]
                    if pn.get("next"):
                        chunk["next_content"] = pn["next"]
            enriched.append(chunk)
        return enriched

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
                # PARENT 摘要（含 Phase 2 降级兜底）
                parent_summary = getattr(result, "parent_summary", None)
                if parent_summary:
                    rag_context += f"[上下文概况]: {parent_summary}\n"
                rag_context += f"{idx}. {result.content[:200]}...\n"
                rag_context += f"   来源: {result.source_file}"
                if hasattr(result, "score") and result.score is not None:
                    rag_context += f" | 相似度: {float(result.score):.2%}"
                if getattr(result, "answerability_score", None) is not None:
                    rag_context += f" | 可回答性: {float(result.answerability_score):.2%}"
                flags = getattr(result, "evidence_flags", None) or {}
                if flags:
                    quality_notes = []
                    if flags.get("has_process_steps"):
                        quality_notes.append("包含流程步骤")
                    elif flags.get("asks_process"):
                        quality_notes.append("缺少明确流程步骤")
                    if flags.get("is_code_or_plan_fragment"):
                        quality_notes.append("偏代码/方案片段")
                    if not flags.get("enough_context", True):
                        quality_notes.append("上下文不足")
                    if flags.get("top_gap_clear"):
                        quality_notes.append("top1分差明显")
                    if quality_notes:
                        rag_context += f" | 证据质量: {'、'.join(quality_notes)}"
                rag_context += "\n\n"
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

    async def _resolve_parent_summary(
        self,
        chunk_id: str,
    ) -> str | None:
        """
        通过 PARENT 关系获取父节点摘要（语义锚点）。

        优先级：
        1. parent.summary（50 字摘要，最优方案）
        2. parent.content[:300]（降级方案）
        3. None（无 PARENT）
        """
        if not chunk_id:
            return None

        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(DocumentChunk).where(DocumentChunk.id == chunk_id)
                )
                chunk = result.scalar_one_or_none()
                if not chunk or not chunk.relationships:
                    return None

                parent_id = chunk.relationships.get("PARENT")
                if not parent_id:
                    return None

                try:
                    parent_uuid = uuid.UUID(str(parent_id))
                except (ValueError, AttributeError):
                    return None

                parent_result = await db.execute(
                    select(DocumentChunk).where(DocumentChunk.id == parent_uuid)
                )
                parent = parent_result.scalar_one_or_none()
                if not parent:
                    return None

                # 一级：summary（50 字摘要）
                if parent.summary and len(parent.summary) > 5:
                    return parent.summary

                # 二级降级：content 前 300 字符
                return parent.content[:300]

        except Exception as e:
            logger.warning(f"[UnifiedRetriever] 解析 PARENT 摘要失败: {e}")
            return None

    async def _resolve_prev_next(
        self,
        chunk_id: str,
        max_chars: int = 200,
    ) -> dict:
        """
        通过 PREVIOUS/NEXT 关系获取相邻条款。

        Args:
            chunk_id: 当前 chunk 的 ID
            max_chars: 相邻条款最大字符数

        Returns:
            {"previous": str | None, "next": str | None}
        """
        if not chunk_id:
            return {"previous": None, "next": None}

        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(DocumentChunk).where(DocumentChunk.id == chunk_id)
                )
                chunk = result.scalar_one_or_none()
                if not chunk or not chunk.relationships:
                    return {"previous": None, "next": None}

                prev_content = None
                next_content = None

                prev_id = chunk.relationships.get("PREVIOUS")
                if prev_id:
                    try:
                        prev_uuid = uuid.UUID(str(prev_id))
                        prev_result = await db.execute(
                            select(DocumentChunk).where(DocumentChunk.id == prev_uuid)
                        )
                        prev = prev_result.scalar_one_or_none()
                        if prev:
                            prev_content = prev.content[:max_chars]
                    except (ValueError, AttributeError):
                        pass

                next_id = chunk.relationships.get("NEXT")
                if next_id:
                    try:
                        next_uuid = uuid.UUID(str(next_id))
                        next_result = await db.execute(
                            select(DocumentChunk).where(DocumentChunk.id == next_uuid)
                        )
                        nxt = next_result.scalar_one_or_none()
                        if nxt:
                            next_content = nxt.content[:max_chars]
                    except (ValueError, AttributeError):
                        pass

                return {"previous": prev_content, "next": next_content}

        except Exception as e:
            logger.warning(f"[UnifiedRetriever] 解析 PREVIOUS/NEXT 失败: {e}")
            return {"previous": None, "next": None}


# 全局单例
unified_retriever = UnifiedRetriever()
