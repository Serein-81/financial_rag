"""
向量搜索服务

提供优化的 pgvector 向量搜索功能
支持：
- ANN 近似最近邻搜索 (IVFFlat/HNSW)
- 元数据过滤
- 混合检索与重排序
"""

from app.utils.json_compat import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class IndexType(Enum):
    """向量索引类型"""
    FLAT = "flat"
    IVFFLAT = "ivfflat"
    HNSW = "hnsw"


class DistanceMetric(Enum):
    """距离度量"""
    COSINE = "cosine"
    EUCLIDEAN = "l2"
    DOT_PRODUCT = "inner"


@dataclass
class VectorSearchResult:
    """向量搜索结果"""
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float
    distance: Optional[float] = None
    rank: int = 0


@dataclass
class SearchConfig:
    """搜索配置"""
    top_k: int = 10
    similarity_threshold: float = 0.7
    enable_reranking: bool = False
    rerank_top_k: int = 5
    min_relevant_score: float = 0.5
    index_type: IndexType = IndexType.HNSW
    ef_search: int = 40
    m: int = 16


@dataclass
class MetadataFilter:
    """元数据过滤器"""
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    user_id: Optional[str] = None
    content_type: Optional[str] = None
    min_importance: Optional[float] = None
    custom_filters: Optional[Dict[str, Any]] = None


class VectorSearchService:
    """
    向量搜索服务
    
    功能：
    1. 高性能 ANN 向量搜索
    2. 元数据过滤
    3. 混合检索
    4. 重排序优化
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        embedding_dimension: int = 1024,
        table_name: str = "semantic_memories",
        embedding_column: str = "embedding"
    ):
        self.db = db_session
        self.embedding_dimension = embedding_dimension
        self.table_name = table_name
        self.embedding_column = embedding_column
        self._index_status: Optional[Dict[str, Any]] = None
    
    async def search(
        self,
        query_embedding: List[float],
        config: Optional[SearchConfig] = None,
        filters: Optional[MetadataFilter] = None
    ) -> List[VectorSearchResult]:
        """
        向量搜索
        
        Args:
            query_embedding: 查询向量
            config: 搜索配置
            filters: 元数据过滤器
            
        Returns:
            搜索结果列表
        """
        config = config or SearchConfig()
        
        if config.enable_reranking:
            return await self._search_with_reranking(query_embedding, config, filters)
        
        return await self._ann_search(query_embedding, config, filters)
    
    async def _ann_search(
        self,
        query_embedding: List[float],
        config: SearchConfig,
        filters: Optional[MetadataFilter]
    ) -> List[VectorSearchResult]:
        """
        ANN 向量搜索
        
        使用 HNSW 或 IVFFlat 进行近似最近邻搜索
        """
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        
        where_clauses = ["1=1"]
        params: Dict[str, Any] = {"embedding": embedding_str, "limit": config.top_k}
        
        if filters:
            filter_sql, filter_params = self._build_filter_sql(filters)
            where_clauses.append(filter_sql)
            params.update(filter_params)
        
        if config.similarity_threshold > 0:
            similarity_col = self._get_similarity_column(config.index_type)
            where_clauses.append(f"{similarity_col} >= :threshold")
            params["threshold"] = config.similarity_threshold
        
        where_clause = " AND ".join(where_clauses)
        
        similarity_expr = self._get_similarity_expression(embedding_str, config.index_type)
        
        sql = f"""
        SELECT 
            id,
            content,
            metadata,
            {similarity_expr} as similarity_score,
            1 as rank
        FROM {self.table_name}
        WHERE {where_clause}
        ORDER BY similarity_score DESC
        LIMIT :limit
        """
        
        try:
            result = await self.db.execute(text(sql), params)
            rows = result.fetchall()
            
            return [
                VectorSearchResult(
                    id=row[0],
                    content=row[1],
                    metadata=json.loads(row[2]) if row[2] else {},
                    score=float(row[3]),
                    rank=idx + 1
                )
                for idx, row in enumerate(rows)
            ]
            
        except (ValueError, KeyError) as e:
            logger.error(f"[VectorSearch] ANN 搜索数据错误: {e}")
            return []
        except (OSError, IOError) as e:
            logger.error(f"[VectorSearch] ANN 搜索IO错误: {e}")
            return []
        except Exception as e:
            logger.error(f"[VectorSearch] ANN 搜索失败: {e}")
            return []
    
    async def _search_with_reranking(
        self,
        query_embedding: List[float],
        config: SearchConfig,
        filters: Optional[MetadataFilter]
    ) -> List[VectorSearchResult]:
        """
        带重排序的搜索
        
        1. ANN 搜索获取候选
        2. 使用交叉编码器重排序
        """
        initial_config = SearchConfig(
            top_k=config.rerank_top_k * 3,
            similarity_threshold=0.0
        )
        
        candidates = await self._ann_search(query_embedding, initial_config, filters)
        
        if not candidates:
            return []
        
        reranked = await self._rerank_candidates(
            query_embedding,
            candidates,
            config.rerank_top_k
        )
        
        return reranked
    
    async def _rerank_candidates(
        self,
        query_embedding: List[float],
        candidates: List[VectorSearchResult],
        top_k: int
    ) -> List[VectorSearchResult]:
        """
        重排序候选结果
        
        当前实现为简单的分数调整
        实际生产环境应使用专门的 rerank 模型
        """
        for candidate in candidates:
            candidate.score = candidate.score * 1.0
        
        reranked = sorted(candidates, key=lambda x: x.score, reverse=True)[:top_k]
        
        for idx, result in enumerate(reranked):
            result.rank = idx + 1
        
        return reranked
    
    def _build_filter_sql(self, filters: MetadataFilter) -> Tuple[str, Dict[str, Any]]:
        """
        构建过滤 SQL
        
        Returns:
            (WHERE 子句, 参数字典)
        """
        clauses = []
        params: Dict[str, Any] = {}
        
        if filters.source:
            clauses.append("source = :filter_source")
            params["filter_source"] = filters.source
        
        if filters.tags:
            clauses.append("metadata::jsonb ?| :filter_tags")
            params["filter_tags"] = filters.tags
        
        if filters.date_from:
            clauses.append("created_at >= :date_from")
            params["date_from"] = filters.date_from
        
        if filters.date_to:
            clauses.append("created_at <= :date_to")
            params["date_to"] = filters.date_to
        
        if filters.user_id:
            clauses.append("user_id = :filter_user_id")
            params["filter_user_id"] = filters.user_id
        
        if filters.content_type:
            clauses.append("(metadata::jsonb->>'content_type') = :content_type")
            params["content_type"] = filters.content_type
        
        if filters.min_importance is not None:
            clauses.append("(metadata::jsonb->>'importance')::float >= :min_importance")
            params["min_importance"] = filters.min_importance
        
        if filters.custom_filters:
            for key, value in filters.custom_filters.items():
                clauses.append("(metadata::jsonb->>:filter_key) = :filter_value")
                params["filter_key"] = key
                params["filter_value"] = str(value)
        
        return "(" + " AND ".join(clauses) + ")", params
    
    def _get_similarity_expression(self, embedding: str, index_type: IndexType) -> str:
        """获取相似度表达式"""
        if index_type == IndexType.HNSW:
            return f"1 - (embedding <=> '{embedding}')"
        elif index_type == IndexType.IVFFLAT:
            return f"1 - (embedding <=> '{embedding}')"
        else:
            return f"1 - (embedding <=> '{embedding}')"
    
    def _get_similarity_column(self, index_type: IndexType) -> str:
        """获取相似度列名"""
        return "similarity_score"
    
    async def batch_search(
        self,
        query_embeddings: List[List[float]],
        config: Optional[SearchConfig] = None,
        filters: Optional[MetadataFilter] = None
    ) -> List[List[VectorSearchResult]]:
        """
        批量向量搜索
        
        Args:
            query_embeddings: 查询向量列表
            config: 搜索配置
            filters: 元数据过滤器
            
        Returns:
            每个查询的结果列表
        """
        tasks = [
            self.search(embedding, config, filters)
            for embedding in query_embeddings
        ]
        
        import asyncio
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [
            result if not isinstance(result, Exception) else []
            for result in results
        ]
    
    async def get_index_status(self) -> Dict[str, Any]:
        """
        获取向量索引状态
        
        Returns:
            索引状态信息
        """
        sql = """
        SELECT 
            indexname,
            indexdef
        FROM pg_indexes
        WHERE tablename = :table_name
        AND indexname LIKE '%embedding%'
        """
        
        try:
            result = await self.db.execute(text(sql), {"table_name": self.table_name})
            rows = result.fetchall()
            
            indexes = []
            for row in rows:
                indexes.append({
                    "name": row[0],
                    "definition": row[1]
                })
            
            self._index_status = {
                "table": self.table_name,
                "embedding_column": self.embedding_column,
                "embedding_dimension": self.embedding_dimension,
                "indexes": indexes,
                "has_hnsw": any("hnsw" in idx["name"].lower() for idx in indexes),
                "has_ivfflat": any("ivfflat" in idx["name"].lower() for idx in indexes)
            }
            
            return self._index_status
            
        except (ValueError, KeyError) as e:
            logger.error(f"[VectorSearch] 获取索引状态数据错误: {e}")
            return {"error": str(e)}
        except (OSError, IOError) as e:
            logger.error(f"[VectorSearch] 获取索引状态IO错误: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"[VectorSearch] 获取索引状态失败: {e}")
            return {"error": str(e)}
    
    async def create_hnsw_index(
        self,
        m: int = 16,
        ef_construction: int = 64
    ) -> bool:
        """
        创建 HNSW 索引
        
        Args:
            m: 每个元素的连接数
            ef_construction: 构建时的 ef 参数
            
        Returns:
            是否成功
        """
        sql = f"""
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_embedding_hnsw
        ON {self.table_name} 
        USING hnsw ({self.embedding_column} vector_cosine_ops)
        WITH (m = {m}, ef_construction = {ef_construction});
        """
        
        try:
            await self.db.execute(text(sql))
            await self.db.commit()
            logger.info("[VectorSearch] HNSW 索引创建成功")
            return True
        except (ValueError, KeyError) as e:
            logger.error(f"[VectorSearch] HNSW 索引创建数据错误: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"[VectorSearch] HNSW 索引创建IO错误: {e}")
            return False
        except Exception as e:
            logger.error(f"[VectorSearch] HNSW 索引创建失败: {e}")
            return False
    
    async def create_ivfflat_index(
        self,
        lists: int = 100
    ) -> bool:
        """
        创建 IVFFlat 索引
        
        Args:
            lists: 倒排列表数量
            
        Returns:
            是否成功
        """
        sql = f"""
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_embedding_ivfflat
        ON {self.table_name} 
        USING ivfflat ({self.embedding_column} vector_cosine_ops)
        WITH (lists = {lists});
        """
        
        try:
            await self.db.execute(text(sql))
            await self.db.commit()
            logger.info("[VectorSearch] IVFFlat 索引创建成功")
            return True
        except (ValueError, KeyError) as e:
            logger.error(f"[VectorSearch] IVFFlat 索引创建数据错误: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"[VectorSearch] IVFFlat 索引创建IO错误: {e}")
            return False
        except Exception as e:
            logger.error(f"[VectorSearch] IVFFlat 索引创建失败: {e}")
            return False
    
    async def analyze_table_stats(self) -> Dict[str, Any]:
        """
        分析表统计信息
        
        Returns:
            统计信息
        """
        sql = f"""
        SELECT 
            pg_size_pretty(pg_total_relation_size('{self.table_name}')) as total_size,
            pg_size_pretty(pg_relation_size('{self.table_name}')) as table_size,
            pg_size_pretty(pg_indexes_size('{self.table_name}')) as index_size,
            (SELECT COUNT(*) FROM {self.table_name}) as row_count
        """
        
        try:
            result = await self.db.execute(text(sql))
            row = result.fetchone()
            
            return {
                "total_size": row[0],
                "table_size": row[1],
                "index_size": row[2],
                "row_count": row[3]
            }
        except (ValueError, KeyError) as e:
            logger.error(f"[VectorSearch] 统计信息获取数据错误: {e}")
            return {"error": str(e)}
        except (OSError, IOError) as e:
            logger.error(f"[VectorSearch] 统计信息获取IO错误: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"[VectorSearch] 统计信息获取失败: {e}")
            return {"error": str(e)}
    
    async def optimize_index(self, index_type: IndexType = IndexType.HNSW) -> bool:
        """
        优化向量索引
        
        Args:
            index_type: 索引类型
            
        Returns:
            是否成功
        """
        index_name = f"idx_{self.table_name}_embedding_{index_type.value}"
        
        sql = f"ALTER INDEX {index_name} ALTER COLUMN {self.embedding_column} SET STATISTICS 500;"
        
        try:
            await self.db.execute(text(sql))
            
            analyze_sql = f"ANALYZE {self.table_name};"
            await self.db.execute(text(analyze_sql))
            
            await self.db.commit()
            logger.info("[VectorSearch] 索引优化完成")
            return True
        except (ValueError, KeyError) as e:
            logger.error(f"[VectorSearch] 索引优化数据错误: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"[VectorSearch] 索引优化IO错误: {e}")
            return False
        except Exception as e:
            logger.error(f"[VectorSearch] 索引优化失败: {e}")
            return False


class HybridVectorSearch:
    """
    混合向量搜索
    
    结合向量搜索和关键词搜索
    """
    
    def __init__(
        self,
        vector_service: VectorSearchService,
        keyword_weight: float = 0.3,
        vector_weight: float = 0.7
    ):
        self.vector_service = vector_service
        self.keyword_weight = keyword_weight
        self.vector_weight = vector_weight
    
    async def search(
        self,
        query: str,
        query_embedding: List[float],
        config: Optional[SearchConfig] = None,
        filters: Optional[MetadataFilter] = None
    ) -> List[VectorSearchResult]:
        """
        混合搜索
        
        结合向量相似度和关键词匹配
        """
        vector_results = await self.vector_service.search(
            query_embedding, config, filters
        )
        
        keyword_scores = await self._keyword_match(query, vector_results)
        
        hybrid_scores: Dict[str, float] = {}
        for result in vector_results:
            vec_score = result.score
            kw_score = keyword_scores.get(result.id, 0.0)
            
            hybrid_score = (
                vec_score * self.vector_weight +
                kw_score * self.keyword_weight
            )
            hybrid_scores[result.id] = hybrid_score
            result.score = hybrid_score
        
        reranked = sorted(
            vector_results,
            key=lambda x: x.score,
            reverse=True
        )
        
        for idx, result in enumerate(reranked):
            result.rank = idx + 1
        
        return reranked
    
    async def _keyword_match(
        self,
        query: str,
        results: List[VectorSearchResult]
    ) -> Dict[str, float]:
        """
        关键词匹配
        
        返回每个结果的关键词匹配分数
        """
        query_terms = set(query.lower().split())
        scores: Dict[str, float] = {}
        
        for result in results:
            content_lower = result.content.lower()
            matches = sum(1 for term in query_terms if term in content_lower)
            
            if matches > 0:
                scores[result.id] = matches / len(query_terms)
            else:
                scores[result.id] = 0.0
        
        return scores
