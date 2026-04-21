"""
混合搜索服务

集成向量搜索、同义词扩展、PostgreSQL全文搜索的混合检索服务
用于提升检索的召回率和精确率
"""
import time
import logging
import re
from typing import List, Optional, Dict, Any
from sqlalchemy import text, select, func
from app.db import AsyncSessionLocal
from app.services.embedding_service import embedding_service
from app.services.synonym_service import synonym_service
from app.schemas.chat import SearchResultItem
from app.models.search_log import SearchLog
from app.models.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


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
        enable_fulltext: bool = True
    ):
        """
        初始化混合搜索服务
        
        Args:
            vector_weight: 向量搜索权重
            synonym_weight: 同义词搜索权重
            fulltext_weight: 全文搜索权重
            enable_synonym: 是否启用同义词扩展
            enable_fulltext: 是否启用全文搜索
        """
        self.vector_weight = vector_weight
        self.synonym_weight = synonym_weight
        self.fulltext_weight = fulltext_weight
        self.enable_synonym = enable_synonym
        self.enable_fulltext = enable_fulltext
        
        self._normalize_weights()
        
        logger.info(
            f"🔧 混合搜索配置: "
            f"向量={self.vector_weight}, "
            f"同义词={self.synonym_weight}, "
            f"全文={self.fulltext_weight}, "
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

            final_results = []
            for r in results:
                if r['combined_score'] >= score_threshold:
                    final_results.append(SearchResultItem(
                        chunk_id=str(r['chunk_id']),
                        document_id=str(r['document_id']),
                        score=round(r['combined_score'], 4),
                        content=r['content'],
                        source_file=r['source_file'],
                        page_number=r.get('page_number')
                    ))

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
    
    def _merge_results(
        self,
        vector_results: List[Dict],
        synonym_results: List[Dict],
        fulltext_results: List[Dict]
    ) -> Dict[str, Dict[str, Any]]:
        """合并搜索结果"""
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
        sorted_results = sorted(
            merged.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )
        
        return sorted_results[:top_k]
    
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
