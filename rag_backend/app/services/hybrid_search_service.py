"""
混合搜索服务

集成向量搜索、同义词扩展、PostgreSQL全文搜索的混合检索服务
用于提升检索的召回率和精确率

融合策略：
- RRF（倒数排名融合）：默认推荐，只依赖排名不依赖绝对分数
- 加权融合：需要分数归一化后才能使用
"""
import time
import logging
import re
import os
from typing import List, Optional, Dict, Any
from enum import Enum
from collections import defaultdict
from sqlalchemy import text, select, func
from app.db import AsyncSessionLocal
from app.services.embedding_service import embedding_service
from app.services.synonym_service import synonym_service
from app.services.rerank_service import rerank_service
from app.schemas.chat import SearchResultItem
from app.models.search_log import SearchLog
from app.models.knowledge_base import KnowledgeBase
from app.core.config import settings

logger = logging.getLogger(__name__)


class FusionStrategy(Enum):
    """融合策略枚举"""
    RRF = "rrf"           # 倒数排名融合（默认）
    WEIGHTED = "weighted"  # 加权融合（需要归一化）


class HybridSearchService:
    """混合搜索服务"""

    async def _get_tenant_id_from_kb(self, kb_id: str) -> Optional[str]:
        """从知识库ID获取租户ID"""
        if not kb_id:
            return None
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(KnowledgeBase.tenant_id).where(KnowledgeBase.id == kb_id)
            )
            row = result.scalar_one_or_none()
            return row

    def __init__(
        self,
        vector_weight: float = 0.5,
        synonym_weight: float = 0.3,
        fulltext_weight: float = 0.2,
        enable_synonym: bool = True,
        enable_fulltext: bool = True,
        fusion_strategy: str = None,
        rrf_k: int = 60,
        enable_rerank: bool = None,
        rerank_top_k: int = None
    ):
        """
        初始化混合搜索服务
        
        Args:
            vector_weight: 向量搜索权重
            synonym_weight: 同义词搜索权重
            fulltext_weight: 全文搜索权重
            enable_synonym: 是否启用同义词扩展
            enable_fulltext: 是否启用全文搜索
            fusion_strategy: 融合策略，"rrf"（默认）或 "weighted"
            rrf_k: RRF 融合参数（默认60），越大各路结果越均衡
            enable_rerank: 是否启用 Cross-Encoder Rerank，None 使用配置默认值
            rerank_top_k: Rerank 返回结果数量
        """
        self.vector_weight = vector_weight
        self.synonym_weight = synonym_weight
        self.fulltext_weight = fulltext_weight
        self.enable_synonym = enable_synonym
        self.enable_fulltext = enable_fulltext
        self.rrf_k = rrf_k
        
        if enable_rerank is None:
            enable_rerank = settings.ENABLE_RERANK
        self.enable_rerank = enable_rerank and bool(settings.SILICONFLOW_API_KEY)
        
        if rerank_top_k is None:
            rerank_top_k = settings.RERANK_TOP_K
        self.rerank_top_k = rerank_top_k
        
        if fusion_strategy is None:
            fusion_strategy = os.getenv('HYBRID_FUSION_STRATEGY', 'rrf')
        
        self.fusion_strategy = FusionStrategy(fusion_strategy)
        
        if self.fusion_strategy == FusionStrategy.RRF:
            self.vector_weight = 0.0
            self.synonym_weight = 0.0
            self.fulltext_weight = 0.0
        
        logger.info(
            f"🔧 混合搜索配置: "
            f"融合策略={self.fusion_strategy.value}, "
            f"向量={self.vector_weight}, "
            f"同义词={self.synonym_weight}, "
            f"全文={self.fulltext_weight}, "
            f"RRF_k={self.rrf_k}, "
            f"Rerank={'开启' if self.enable_rerank else '关闭'}, "
            f"Rerank_top_k={self.rerank_top_k}, "
            f"同义词扩展={'开启' if enable_synonym else '关闭'}, "
            f"全文搜索={'开启' if enable_fulltext else '关闭'}"
        )
    
    def _normalize_weights(self):
        """归一化权重"""
        total = self.vector_weight + self.synonym_weight + self.fulltext_weight
        if total > 0:
            self.vector_weight /= total
            self.synonym_weight /= total
            self.fulltext_weight /= total
    
    async def search(
        self,
        query: str,
        kb_id: Optional[str] = None,
        top_k: int = 10,
        score_threshold: float = 0.3,
        tenant_id: str = None,
        user_id: str = None
    ) -> List[SearchResultItem]:
        """
        混合搜索主方法
        🔐 租户隔离：必须传入 tenant_id 进行过滤
        🔐 可见性过滤：私人知识库只有创建者可见，企业知识库整个租户可见

        Args:
            query: 用户查询
            kb_id: 知识库ID
            top_k: 返回结果数量
            score_threshold: 分数阈值
            tenant_id: 租户ID（必须）
            user_id: 用户ID（用于可见性过滤）

        Returns:
            搜索结果列表
        """
        start_time = time.time()
        results = []

        if not tenant_id:
            if kb_id:
                tenant_id = await self._get_tenant_id_from_kb(kb_id)
                print(f"🔍 [HybridSearch] 自动从KB获取tenant_id: {tenant_id}")
            if not tenant_id:
                raise ValueError("租户隔离失败：缺少 tenant_id")

        try:
            vector_results = []
            synonym_results = []
            fulltext_results = []

            query_vector = await embedding_service.get_embedding(query)
            if query_vector:
                vector_results = await self._vector_search(
                    query_vector, kb_id, top_k * 2, score_threshold, tenant_id, user_id
                )
                logger.info(f"📊 向量搜索: {len(vector_results)} 个结果")

            if self.enable_synonym:
                synonym_queries = synonym_service.expand_query(query)
                logger.info(f"🔄 同义词扩展: {len(synonym_queries)} 个查询 | 查询: {synonym_queries}")

                for syn_query in synonym_queries[:5]:
                    logger.info(f"🔍 处理同义词查询: '{syn_query}' | 类型: {type(syn_query)}")
                    syn_vector = await embedding_service.get_embedding(syn_query)
                    logger.info(f"🔍 同义词向量类型: {type(syn_vector)} | 长度: {len(syn_vector) if isinstance(syn_vector, list) and syn_vector else 0}")
                    if syn_vector and isinstance(syn_vector, list) and len(syn_vector) > 0:
                        if isinstance(syn_vector[0], (int, float)):
                            syn_results = await self._vector_search(
                                syn_vector, kb_id, top_k, score_threshold, tenant_id, user_id
                            )
                            synonym_results.extend(syn_results)
                        else:
                            logger.warning(f"⚠️ 向量格式错误，首元素类型: {type(syn_vector[0])}")
                    else:
                        logger.warning("⚠️ 向量为空或格式错误")

            if self.enable_fulltext:
                fulltext_results = await self._fulltext_search(
                    query, kb_id, top_k * 2, tenant_id, user_id
                )
                logger.info(f"📝 全文搜索: {len(fulltext_results)} 个结果")

            merged = self._merge_results(
                vector_results,
                synonym_results,
                fulltext_results
            )

            results = self._rerank_results(merged, query_vector, top_k)
            
            if self.enable_rerank and results:
                try:
                    rerank_candidates = [r.get('content', '') for r in results[:self.rerank_top_k * 3]]
                    if rerank_candidates:
                        reranked = await rerank_service.rerank(
                            query=query,
                            documents=rerank_candidates,
                            top_k=self.rerank_top_k,
                            max_chars_per_doc=settings.RERANK_MAX_CHARS
                        )
                        
                        if reranked:
                            rerank_map = {r.index: r for r in reranked}
                            reranked_results = []
                            
                            for i, result in enumerate(results):
                                rrf_score = result.get('combined_score', 0)
                                rerank_score = rerank_map[i].relevance_score if i in rerank_map else rrf_score
                                
                                combined_score = self._compute_hybrid_score(rrf_score, rerank_score)
                                
                                reranked_result = result.copy()
                                reranked_result['combined_score'] = combined_score
                                reranked_result['rerank_score'] = rerank_score
                                reranked_result['rrf_score'] = rrf_score
                                reranked_results.append(reranked_result)
                            
                            reranked_results.sort(key=lambda x: x['combined_score'], reverse=True)
                            results = reranked_results
                            
                            top_score = reranked[0].relevance_score if reranked else 0
                            logger.info(f"🎯 Cross-Encoder Rerank 完成: {len(reranked)} 个结果 | 最高分: {top_score:.4f}")
                except Exception as e:
                    logger.warning(f"⚠️ Rerank 失败，使用融合结果: {e}")

            final_results = self._apply_adaptive_threshold(results, score_threshold)
            
            return final_results

        except Exception as e:
            logger.error(f"❌ 混合搜索失败: {e}", exc_info=True)
            return []
        finally:
            latency = time.time() - start_time
            logger.info(f"🔍 混合搜索完成 | 耗时: {latency:.4f}s | 结果: {len(results)}")
    
    async def _vector_search(
        self,
        query_vector: List[float],
        kb_id: Optional[str],
        top_k: int,
        score_threshold: float,
        tenant_id: str,
        user_id: str = None
    ) -> List[Dict[str, Any]]:
        """向量搜索 🔐 租户隔离 + 可见性过滤"""
        results = []

        try:
            async with AsyncSessionLocal() as db:
                where_clauses = [
                    "(1 - (CAST(c.embedding AS vector) <=> CAST(:vector AS vector))) >= :threshold"
                ]
                where_clauses.append("d.tenant_id = :tenant_id")
                params = {
                    "vector": "[" + ",".join(map(str, query_vector)) + "]",
                    "threshold": float(score_threshold),
                    "limit": int(top_k),
                    "tenant_id": str(tenant_id)
                }

                if user_id:
                    where_clauses.append("""
                        (
                            (UPPER(kb.visibility) = 'ENTERPRISE' OR (UPPER(kb.visibility) = 'PRIVATE' AND kb.user_id = CAST(:user_id AS UUID)))
                        )
                        AND
                        (
                            (UPPER(d.visibility) = 'PUBLIC' OR (UPPER(d.visibility) = 'PRIVATE' AND d.user_id = CAST(:user_id AS UUID)))
                        )
                    """)
                    params["user_id"] = str(user_id)

                if kb_id:
                    where_clauses.append("d.kb_id = CAST(:kb_id AS UUID)")
                    params["kb_id"] = str(kb_id)

                where_sql = " AND ".join(where_clauses)

                logger.info(f"🔎 向量搜索参数: kb_id={kb_id}, tenant_id={tenant_id}, user_id={user_id}, threshold={score_threshold}, top_k={top_k}")
                
                chunk_count_result = await db.execute(text("SELECT COUNT(*) FROM document_chunks c JOIN documents d ON c.document_id = d.id WHERE d.tenant_id = :tenant_id"), {"tenant_id": str(tenant_id)})
                total_chunks = chunk_count_result.scalar()
                logger.info(f"🔎 数据库中该租户共有 {total_chunks} 个 chunks")

                if kb_id:
                    kb_chunk_result = await db.execute(text("SELECT COUNT(*) FROM document_chunks c JOIN documents d ON c.document_id = d.id WHERE d.tenant_id = :tenant_id AND d.kb_id = CAST(:kb_id AS UUID)"), {"tenant_id": str(tenant_id), "kb_id": str(kb_id)})
                    kb_chunks = kb_chunk_result.scalar()
                    logger.info(f"🔎 该知识库中共有 {kb_chunks} 个 chunks")

                sql = text(f"""
                    SELECT
                        c.id,
                        c.document_id,
                        c.content,
                        c.meta_info,
                        d.filename,
                        kb.name as kb_name,
                        (1 - (CAST(c.embedding AS vector) <=> CAST(:vector AS vector))) AS similarity
                    FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    JOIN knowledge_bases kb ON d.kb_id = kb.id
                    WHERE {where_sql}
                    ORDER BY similarity DESC
                    LIMIT :limit
                """)
                
                db_res = await db.execute(sql, params)
                rows = db_res.mappings().all()
                
                for row in rows:
                    meta = row["meta_info"] or {}
                    results.append({
                        "chunk_id": str(row["id"]),
                        "document_id": str(row["document_id"]),
                        "content": row["content"],
                        "source_file": row["filename"],
                        "page_number": meta.get("page_number"),
                        "vector_score": float(row["similarity"]),
                        "synonym_score": 0.0,
                        "fulltext_score": 0.0,
                        "combined_score": float(row["similarity"])
                    })
                    
        except Exception as e:
            logger.error(f"❌ 向量搜索失败: {e}")
        
        return results
    
    async def _fulltext_search(
        self,
        query: str,
        kb_id: Optional[str],
        top_k: int,
        tenant_id: str,
        user_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        PostgreSQL全文搜索 - 优化版
        🔐 租户隔离：必须传入 tenant_id 进行过滤
        🔐 可见性过滤：私人知识库只有创建者可见，企业知识库整个租户可见

        使用 GIN 索引 + to_tsvector/to_tsquery 实现千万级数据高性能检索
        不再使用 ILIKE '%phrase%' 这种会导致全表扫描的低效查询
        """
        results = []

        try:
            async with AsyncSessionLocal() as db:
                where_clauses = []
                params = {
                    "limit": int(top_k),
                    "tenant_id": str(tenant_id)
                }

                # 检查是否已迁移到新架构（fts_vector 列存在）
                check_fts_column = await db.execute(text("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'document_chunks' 
                        AND column_name = 'fts_vector'
                    ) as exists
                """))
                has_fts_column = check_fts_column.scalar()

                if has_fts_column:
                    # 使用优化的全文检索
                    return await self._fts_search_optimized(
                        query, kb_id, top_k, tenant_id, user_id
                    )
                else:
                    # 回退到传统方式（仅警告，不使用 ILIKE）
                    logger.warning("⚠️ 未检测到 fts_vector 列，使用基本全文检索")
                    return await self._fts_search_basic(
                        query, kb_id, top_k, tenant_id, user_id
                    )

        except Exception as e:
            logger.error(f"❌ 全文搜索失败: {e}", exc_info=True)

        return results

    async def _fts_search_optimized(
        self,
        query: str,
        kb_id: Optional[str],
        top_k: int,
        tenant_id: str,
        user_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        优化的全文检索 - 使用 GIN 索引 + to_tsvector/to_tsquery
        性能特征：O(log n) 级别，支持千万级数据
        """
        results = []

        try:
            # 使用 pg_catalog.simple 配置，支持中英文混合
            # to_tsquery 在 SQL 中调用，这里准备查询字符串
            search_query = query

            async with AsyncSessionLocal() as db:
                where_clauses = []
                params = {
                    "query": search_query,
                    "limit": int(top_k),
                    "tenant_id": str(tenant_id)
                }

                # 🔐 租户隔离
                where_clauses.append("d.tenant_id = :tenant_id")

                # 🔐 两层可见性过滤
                if user_id:
                    where_clauses.append("""
                        (
                            (UPPER(kb.visibility) = 'ENTERPRISE' OR (UPPER(kb.visibility) = 'PRIVATE' AND kb.user_id = CAST(:user_id AS UUID)))
                        )
                        AND
                        (
                            (UPPER(d.visibility) = 'PUBLIC' OR (UPPER(d.visibility) = 'PRIVATE' AND d.user_id = CAST(:user_id AS UUID)))
                        )
                    """)
                    params["user_id"] = str(user_id)

                if kb_id:
                    where_clauses.append("d.kb_id = CAST(:kb_id AS UUID)")
                    params["kb_id"] = str(kb_id)

                where_sql = " AND ".join(where_clauses)

                # 使用 ts_rank_cd 进行相关性排序，支持权重
                sql = text(f"""
                    SELECT
                        c.id,
                        c.document_id,
                        c.content,
                        c.meta_info,
                        d.filename,
                        kb.name as kb_name,
                        ts_rank_cd(c.fts_vector, to_tsquery('pg_catalog.simple', :query)) AS rank,
                        ts_headline(
                            'pg_catalog.simple',
                            c.content,
                            to_tsquery('pg_catalog.simple', :query),
                            'MaxWords=50, MinWords=20, StartSel=<mark>, StopSel=</mark>'
                        ) AS highlight
                    FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    JOIN knowledge_bases kb ON d.kb_id = kb.id
                    WHERE {where_sql}
                    AND c.fts_vector @@ to_tsquery('pg_catalog.simple', :query)
                    ORDER BY rank DESC
                    LIMIT :limit
                """)

                logger.info(f"🔍 全文检索查询: {search_query}")
                db_res = await db.execute(sql, params)
                rows = db_res.mappings().all()

                for row in rows:
                    meta = row["meta_info"] or {}
                    rank = float(row["rank"]) if row["rank"] else 0

                    # 归一化分数到 [0, 1] 范围
                    normalized_score = min(rank / 10.0, 1.0) if rank > 0 else 0

                    results.append({
                        "chunk_id": str(row["id"]),
                        "document_id": str(row["document_id"]),
                        "content": row["content"],
                        "source_file": row["filename"],
                        "page_number": meta.get("page_number"),
                        "vector_score": 0.0,
                        "synonym_score": 0.0,
                        "fulltext_score": normalized_score,
                        "combined_score": normalized_score
                    })

                logger.info(f"📝 优化全文检索: {len(results)} 个结果")

        except Exception as e:
            logger.error(f"❌ 优化全文检索失败: {e}", exc_info=True)

        return results

    async def _fts_search_basic(
        self,
        query: str,
        kb_id: Optional[str],
        top_k: int,
        tenant_id: str,
        user_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        基本全文检索 - 当 fts_vector 列不存在时的回退方案
        注意：此方法不使用 GIN 索引，仅用于迁移期间
        """
        results = []

        try:
            async with AsyncSessionLocal() as db:
                where_clauses = []
                params = {
                    "query": query,
                    "limit": int(top_k),
                    "tenant_id": str(tenant_id)
                }

                # 🔐 租户隔离
                where_clauses.append("d.tenant_id = :tenant_id")

                # 🔐 两层可见性过滤
                if user_id:
                    where_clauses.append("""
                        (
                            (UPPER(kb.visibility) = 'ENTERPRISE' OR (UPPER(kb.visibility) = 'PRIVATE' AND kb.user_id = CAST(:user_id AS UUID)))
                        )
                        AND
                        (
                            (UPPER(d.visibility) = 'PUBLIC' OR (UPPER(d.visibility) = 'PRIVATE' AND d.user_id = CAST(:user_id AS UUID)))
                        )
                    """)
                    params["user_id"] = str(user_id)

                if kb_id:
                    where_clauses.append("d.kb_id = CAST(:kb_id AS UUID)")
                    params["kb_id"] = str(kb_id)

                where_sql = " AND ".join(where_clauses)

                # 使用 to_tsvector/to_tsquery 但不使用索引
                sql = text(f"""
                    SELECT
                        c.id,
                        c.document_id,
                        c.content,
                        c.meta_info,
                        d.filename,
                        kb.name as kb_name,
                        ts_rank_cd(
                            to_tsvector('pg_catalog.simple', c.content),
                            to_tsquery('pg_catalog.simple', :query)
                        ) AS rank
                    FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    JOIN knowledge_bases kb ON d.kb_id = kb.id
                    WHERE {where_sql}
                    AND to_tsvector('pg_catalog.simple', c.content) @@ to_tsquery('pg_catalog.simple', :query)
                    ORDER BY rank DESC
                    LIMIT :limit
                """)

                logger.warning("⚠️ 使用基本全文检索（无索引）")
                db_res = await db.execute(sql, params)
                rows = db_res.mappings().all()

                for row in rows:
                    meta = row["meta_info"] or {}
                    rank = float(row["rank"]) if row["rank"] else 0
                    normalized_score = min(rank / 10.0, 1.0) if rank > 0 else 0

                    results.append({
                        "chunk_id": str(row["id"]),
                        "document_id": str(row["document_id"]),
                        "content": row["content"],
                        "source_file": row["filename"],
                        "page_number": meta.get("page_number"),
                        "vector_score": 0.0,
                        "synonym_score": 0.0,
                        "fulltext_score": normalized_score,
                        "combined_score": normalized_score
                    })

        except Exception as e:
            logger.error(f"❌ 基本全文检索失败: {e}", exc_info=True)

        return results
    
    def _extract_phrases(self, query: str) -> List[str]:
        """
        从查询中提取短语
        
        支持：
        1. 中文短语（连续中文字符）
        2. 英文词组（用引号括起来的）
        3. 常见短语模式
        """
        phrases = []
        
        quoted_phrases = re.findall(r'"([^"]+)"', query)
        phrases.extend(quoted_phrases)
        
        chinese_phrases = re.findall(r'[\u4e00-\u9fa5]{4,}', query)
        phrases.extend(chinese_phrases)
        
        english_phrases = re.findall(r'\b[a-zA-Z]{4,}\b', query.lower())
        phrases.extend(english_phrases)
        
        return list(set(phrases))
    
    def _normalize_scores(self, results: List[Dict], score_key: str) -> List[Dict]:
        """
        归一化分数到 [0, 1] 范围
        
        Args:
            results: 结果列表
            score_key: 分数字段名
            
        Returns:
            归一化后的结果
        """
        if not results:
            return results
        
        scores = [r.get(score_key, 0) for r in results]
        max_score = max(scores) if scores else 1
        min_score = min(scores) if scores else 0
        score_range = max_score - min_score
        
        if score_range > 0:
            for r in results:
                raw_score = r.get(score_key, 0)
                r[score_key] = (raw_score - min_score) / score_range
        else:
            for r in results:
                r[score_key] = 0.0 if max_score == 0 else 1.0
        
        return results
    
    def _rrf_fusion(
        self,
        vector_results: List[Dict],
        synonym_results: List[Dict],
        fulltext_results: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """
        RRF（倒数排名融合）
        
        RRF_score(d) = Σ 1/(k + rank_i(d))
        
        优点：
        - 只依赖排名，不依赖绝对分数
        - 自然归一化，无需处理不同量纲问题
        - 简单高效，无需调参
        
        Args:
            vector_results: 向量检索结果
            synonym_results: 同义词检索结果
            fulltext_results: 全文检索结果
            top_k: 返回结果数量
            
        Returns:
            融合后的结果
        """
        scores: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "rrf_score": 0.0,
            "source": None,
            "best_rank": float('inf')
        })
        
        all_results = [
            (vector_results, "vector"),
            (synonym_results, "synonym"),
            (fulltext_results, "fulltext")
        ]
        
        for result_list, source_name in all_results:
            for rank, result in enumerate(result_list, start=1):
                chunk_id = result["chunk_id"]
                rrf_contribution = 1.0 / (self.rrf_k + rank)
                
                scores[chunk_id]["rrf_score"] += rrf_contribution
                scores[chunk_id]["best_rank"] = min(scores[chunk_id]["best_rank"], rank)
                scores[chunk_id]["source"] = result
        
        sorted_scores = sorted(
            scores.items(),
            key=lambda x: (x[1]["rrf_score"], -x[1]["best_rank"]),
            reverse=True
        )
        
        final_results = []
        for chunk_id, score_info in sorted_scores[:top_k]:
            result = score_info["source"].copy()
            result["combined_score"] = score_info["rrf_score"]
            result["best_rank"] = score_info["best_rank"]
            result["fusion_method"] = "rrf"
            final_results.append(result)
        
        logger.info(f"🔄 RRF 融合: 向量={len(vector_results)}, 同义词={len(synonym_results)}, 全文={len(fulltext_results)} → {len(final_results)}")
        return final_results
    
    def _merge_results(
        self,
        vector_results: List[Dict],
        synonym_results: List[Dict],
        fulltext_results: List[Dict]
    ) -> Dict[str, Dict[str, Any]]:
        """合并搜索结果（支持 RRF 和加权两种策略）"""
        
        if self.fusion_strategy == FusionStrategy.RRF:
            merged = {}
            all_results = vector_results + synonym_results + fulltext_results
            for result in all_results:
                chunk_id = result["chunk_id"]
                if chunk_id not in merged:
                    merged[chunk_id] = result
                    merged[chunk_id]["source_list"] = []
                merged[chunk_id]["source_list"].append(result)
            return merged
        
        merged = {}
        
        for result in vector_results:
            chunk_id = result["chunk_id"]
            if chunk_id not in merged:
                merged[chunk_id] = result
            else:
                merged[chunk_id]["vector_score"] = max(
                    merged[chunk_id]["vector_score"],
                    result["vector_score"]
                )
        
        for result in synonym_results:
            chunk_id = result["chunk_id"]
            if chunk_id not in merged:
                merged[chunk_id] = result
            else:
                merged[chunk_id]["synonym_score"] = max(
                    merged[chunk_id]["synonym_score"],
                    result["vector_score"]
                )
        
        for result in fulltext_results:
            chunk_id = result["chunk_id"]
            if chunk_id not in merged:
                merged[chunk_id] = result
            else:
                merged[chunk_id]["fulltext_score"] = max(
                    merged[chunk_id]["fulltext_score"],
                    result["fulltext_score"]
                )
        
        for chunk_id in merged:
            r = merged[chunk_id]
            r["combined_score"] = (
                r["vector_score"] * self.vector_weight +
                r["synonym_score"] * self.synonym_weight +
                r["fulltext_score"] * self.fulltext_weight
            )
        
        return merged
    
    def _rerank_results(
        self,
        merged: Dict[str, Dict],
        query_vector: Optional[List[float]],
        top_k: int
    ) -> List[Dict]:
        """重排序结果"""
        
        if self.fusion_strategy == FusionStrategy.RRF:
            vector_results = []
            synonym_results = []
            fulltext_results = []
            
            for chunk_id, result in merged.items():
                source_list = result.get("source_list", [])
                for src in source_list:
                    src_copy = src.copy()
                    src_copy["chunk_id"] = chunk_id
                    if src_copy.get("vector_score", 0) > 0:
                        vector_results.append(src_copy)
                    elif src_copy.get("synonym_score", 0) > 0:
                        synonym_results.append(src_copy)
                    elif src_copy.get("fulltext_score", 0) > 0:
                        fulltext_results.append(src_copy)
            
            vector_results.sort(key=lambda x: x.get("vector_score", 0), reverse=True)
            synonym_results.sort(key=lambda x: x.get("synonym_score", 0), reverse=True)
            fulltext_results.sort(key=lambda x: x.get("fulltext_score", 0), reverse=True)
            
            return self._rrf_fusion(vector_results, synonym_results, fulltext_results, top_k)
        
        sorted_results = sorted(
            merged.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )
        
        return sorted_results[:top_k]
    
    def _compute_hybrid_score(self, rrf_score: float, rerank_score: float) -> float:
        """
        计算混合分数：RRF分数 + Rerank分数加权融合
        
        融合策略：
        - RRF分数代表多路召回的排名信息（0.0 ~ 0.05）
        - Rerank分数代表语义相关性（0.0 ~ 1.0）
        - 当Rerank分数过低时，更信任RRF的排名结果
        
        Args:
            rrf_score: RRF融合分数
            rerank_score: Rerank相关性分数
            
        Returns:
            混合分数 [0, 1]
        """
        if rerank_score <= 0 and rrf_score <= 0:
            return 0.0
        
        if rerank_score <= 0:
            return min(rrf_score * 20, 1.0)
        
        if rrf_score <= 0:
            return rerank_score
        
        rrf_normalized = min(rrf_score * 20, 1.0)
        
        if rerank_score >= 0.5:
            hybrid_score = rrf_normalized * 0.3 + rerank_score * 0.7
        elif rerank_score >= 0.2:
            hybrid_score = rrf_normalized * 0.5 + rerank_score * 0.5
        else:
            hybrid_score = rrf_normalized * 0.8 + rerank_score * 0.2
        
        return min(hybrid_score, 1.0)
    
    def _apply_adaptive_threshold(
        self,
        results: List[Dict],
        base_threshold: float
    ) -> List[SearchResultItem]:
        """
        自适应阈值过滤：根据结果质量动态调整阈值
        
        策略：
        1. 如果 top 结果分数都很低（< 0.4），降低阈值确保召回
        2. 如果有高质量结果（> 0.6），使用严格阈值
        3. 始终返回至少 1 个结果（如果有候选的话）
        
        Args:
            results: 排序后的结果列表
            base_threshold: 基础阈值
            
        Returns:
            过滤后的 SearchResultItem 列表
        """
        if not results:
            return []
        
        final_results = []
        top_scores = [r.get('combined_score', 0) for r in results[:5]]
        top_score = max(top_scores) if top_scores else 0
        
        if top_score >= 0.6:
            effective_threshold = max(base_threshold, 0.5)
            logger.info(f"📊 自适应阈值: 高质量结果(top={top_score:.4f})，使用严格阈值 {effective_threshold}")
        elif top_score >= 0.4:
            effective_threshold = max(base_threshold, 0.35)
            logger.info(f"📊 自适应阈值: 中等质量结果(top={top_score:.4f})，使用适中阈值 {effective_threshold}")
        elif top_score > 0:
            effective_threshold = max(base_threshold, 0.25)
            logger.info(f"📊 自适应阈值: 低质量结果(top={top_score:.4f})，降低阈值 {effective_threshold}")
        else:
            effective_threshold = base_threshold
            logger.warning(f"⚠️ 所有结果分数接近0，可能检索失败")
        
        for r in results:
            if r['combined_score'] >= effective_threshold:
                final_results.append(SearchResultItem(
                    chunk_id=str(r['chunk_id']),
                    document_id=str(r['document_id']),
                    score=round(r['combined_score'], 4),
                    content=r['content'],
                    source_file=r['source_file'],
                    page_number=r.get('page_number')
                ))
        
        if not final_results and results:
            logger.warning(f"⚠️ 阈值{effective_threshold}过滤后无结果，强制返回top候选")
            top_candidates = min(len(results), 3)
            for r in results[:top_candidates]:
                final_results.append(SearchResultItem(
                    chunk_id=str(r['chunk_id']),
                    document_id=str(r['document_id']),
                    score=round(r['combined_score'], 4),
                    content=r['content'],
                    source_file=r['source_file'],
                    page_number=r.get('page_number')
                ))
        
        logger.info(f"📊 最终结果: {len(final_results)} 条 (阈值: {effective_threshold})")
        return final_results
    
    async def _save_search_log(
        self,
        query: str,
        result_count: int,
        latency: float
    ):
        """保存搜索日志"""
        try:
            async with AsyncSessionLocal() as db:
                log = SearchLog(
                    query=query,
                    result_count=result_count,
                    latency=latency
                )
                db.add(log)
                await db.commit()
        except Exception as e:
            logger.error(f"❌ 保存搜索日志失败: {e}")


hybrid_search_service = HybridSearchService()
