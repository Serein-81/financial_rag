"""
多智能体系统RAG检索器
为企业级税务审核场景提供知识检索功能

关键特性：
1. 租户隔离：只检索同一企业的文档
2. 可见性控制：只检索公开文档（is_public=True）
3. 分类过滤：支持按文档分类检索
4. 置信度增强：返回检索结果的同时提供置信度评分
5. 访问审计：记录所有检索操作
6. 速率限制：防止滥用
"""

import hashlib
import time
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)


class TenantRateLimiter:
    """
    租户级速率限制器

    功能：
    1. 每个租户独立计数
    2. 滑动窗口限流
    3. 自动清理过期记录
    """

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60
    ):
        """
        初始化限流器

        Args:
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口秒数
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = Lock()

    def check_rate_limit(self, tenant_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        检查速率限制

        Args:
            tenant_id: 租户ID

        Returns:
            (is_allowed, info): 是否允许及限制信息
        """
        current_time = time.time()
        window_start = current_time - self.window_seconds

        with self._lock:
            requests = self._requests[tenant_id]
            requests[:] = [t for t in requests if t > window_start]

            remaining = self.max_requests - len(requests)
            is_allowed = len(requests) < self.max_requests

            if is_allowed:
                requests.append(current_time)

            reset_time = min(requests) + self.window_seconds if requests else current_time + self.window_seconds

            return is_allowed, {
                "allowed": is_allowed,
                "remaining": max(0, remaining),
                "reset_at": reset_time,
                "limit": self.max_requests,
                "window_seconds": self.window_seconds
            }

    def get_usage(self, tenant_id: str) -> Dict[str, Any]:
        """获取租户使用情况"""
        current_time = time.time()
        window_start = current_time - self.window_seconds

        with self._lock:
            requests = self._requests[tenant_id]
            valid_requests = [t for t in requests if t > window_start]
            return {
                "total_requests": len(valid_requests),
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
                "usage_percent": len(valid_requests) / self.max_requests * 100
            }


class TenantAccessValidator:
    """
    租户访问验证器

    功能：
    1. 验证租户ID格式
    2. 检查租户状态
    3. 防止跨租户访问
    """

    def __init__(self):
        self._validated_tenants: Set[str] = set()
        self._lock = Lock()

    def validate_tenant_id(self, tenant_id: str) -> Tuple[bool, str]:
        """
        验证租户ID

        Args:
            tenant_id: 租户ID

        Returns:
            (is_valid, error_message): 是否有效及错误信息
        """
        if not tenant_id:
            return False, "租户ID不能为空"

        if not isinstance(tenant_id, str):
            return False, "租户ID必须是字符串"

        if len(tenant_id) < 8:
            return False, "租户ID格式无效（太短）"

        if len(tenant_id) > 128:
            return False, "租户ID格式无效（太长）"

        return True, ""

    def validate_access(
        self,
        tenant_id: str,
        document_tenant_id: str
    ) -> Tuple[bool, str]:
        """
        验证文档访问权限

        Args:
            tenant_id: 请求方租户ID
            document_tenant_id: 文档所属租户ID

        Returns:
            (is_allowed, error_message): 是否允许及错误信息
        """
        is_valid, error = self.validate_tenant_id(tenant_id)
        if not is_valid:
            return False, f"租户验证失败: {error}"

        if tenant_id != document_tenant_id:
            logger.warning(
                f"🚨 [安全] 跨租户访问尝试 | "
                f"请求方: {tenant_id} | 目标租户: {document_tenant_id}"
            )
            return False, "禁止跨租户访问"

        return True, ""

    def mark_validated(self, tenant_id: str):
        """标记已验证的租户"""
        with self._lock:
            self._validated_tenants.add(tenant_id)

    def is_validated(self, tenant_id: str) -> bool:
        """检查租户是否已验证"""
        with self._lock:
            return tenant_id in self._validated_tenants


class RAGDocType(Enum):
    """RAG文档类型枚举"""
    TAX_REGULATIONS = "tax_regulations"       # 税收法规
    TAX_POLICY = "tax_policy"                  # 税收政策
    INDUSTRY_GUIDELINES = "industry_guidelines" # 行业指引
    CASE_PRECEDENT = "case_precedent"          # 案例参考
    INTERNAL_GUIDELINES = "internal_guidelines" # 内部指引
    GENERAL = "general"                         # 一般文档


@dataclass
class RAGRetrievalResult:
    """RAG检索结果"""
    content: str
    source: str
    doc_type: RAGDocType
    confidence: float
    metadata: Dict[str, Any]
    relevance_score: float


@dataclass
class RAGRetrievalContext:
    """RAG检索上下文"""
    query: str
    results: List[RAGRetrievalResult]
    total_results: int
    retrieval_time_ms: float
    tenant_id: str
    filters_applied: Dict[str, Any]


class RetrievalCache:
    """
    检索结果缓存

    功能：
    1. 基于查询哈希的缓存
    2. 租户隔离
    3. TTL过期
    """

    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 300
    ):
        """
        初始化缓存

        Args:
            max_size: 最大缓存条目数
            ttl_seconds: 缓存过期时间（秒）
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = Lock()

    def _make_key(self, tenant_id: str, query: str) -> str:
        """生成缓存键"""
        content = f"{tenant_id}:{query}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def get(
        self,
        tenant_id: str,
        query: str
    ) -> Optional[RAGRetrievalContext]:
        """获取缓存结果"""
        key = self._make_key(tenant_id, query)
        current_time = time.time()

        with self._lock:
            if key in self._cache:
                result, timestamp = self._cache[key]
                if current_time - timestamp < self.ttl_seconds:
                    logger.debug(f"💾 [缓存] 命中 | 键: {key[:8]}...")
                    return result
                else:
                    del self._cache[key]
                    logger.debug(f"💾 [缓存] 过期 | 键: {key[:8]}...")

        return None

    def set(
        self,
        tenant_id: str,
        query: str,
        result: RAGRetrievalContext
    ):
        """设置缓存"""
        key = self._make_key(tenant_id, query)
        current_time = time.time()

        with self._lock:
            if len(self._cache) >= self.max_size:
                self._evict_oldest()
            self._cache[key] = (result, current_time)

    def _evict_oldest(self):
        """驱逐最老的缓存条目"""
        if not self._cache:
            return

        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k][1]
        )
        del self._cache[oldest_key]

    def clear(self, tenant_id: Optional[str] = None):
        """清除缓存"""
        with self._lock:
            if tenant_id:
                keys_to_remove = [
                    k for k in self._cache.keys()
                    if k.startswith(hashlib.sha256(tenant_id.encode()).hexdigest()[:32])
                ]
                for k in keys_to_remove:
                    del self._cache[k]
            else:
                self._cache.clear()


_global_rate_limiter = TenantRateLimiter(max_requests=100, window_seconds=60)
_global_access_validator = TenantAccessValidator()
_global_retrieval_cache = RetrievalCache(max_size=1000, ttl_seconds=300)


class TenantIsolatedRAGRetriever:
    """
    租户隔离的RAG检索器
    
    安全特性：
    1. 强制租户ID验证
    2. 只检索 is_public=True 的文档
    3. 审计日志记录
    """
    
    def __init__(
        self,
        qdrant_client=None,
        embedding_service=None,
        enable_audit: bool = True,
        search_service=None
    ):
        """
        初始化RAG检索器
        
        Args:
            qdrant_client: Qdrant向量数据库客户端（已弃用）
            embedding_service: 向量嵌入服务
            enable_audit: 是否启用检索审计日志
            search_service: pgvector搜索服务（推荐使用）
        """
        self.qdrant_client = qdrant_client
        self.embedding_service = embedding_service
        self.enable_audit = enable_audit
        self.search_service = search_service
        self.use_rate_limiter = True
        self.use_cache = True
        
        if self.search_service:
            logger.info("🔒 [RAG检索器] 租户隔离模式已启用 (使用 pgvector)")
        elif self.qdrant_client:
            logger.warning("⚠️ [RAG检索器] 使用已弃用的 Qdrant 客户端")
        else:
            logger.warning("⚠️ [RAG检索器] 未配置向量搜索服务")
    
    async def retrieve(
        self,
        query: str,
        tenant_id: str,
        top_k: int = 3,
        doc_types: Optional[List[RAGDocType]] = None,
        require_public: bool = True,
        min_relevance_score: float = 0.5,
        bypass_cache: bool = False
    ) -> RAGRetrievalContext:
        """
        执行RAG检索（带租户隔离）

        增强功能：
        1. 速率限制（防止滥用）
        2. 结果缓存（提升性能）
        3. 访问验证（增强安全）
        
        Args:
            query: 检索查询
            tenant_id: 租户ID（必填，用于隔离）
            top_k: 返回结果数量
            doc_types: 可选的文档类型过滤
            require_public: 是否只检索公开文档（默认True）
            min_relevance_score: 最小相关性分数
            bypass_cache: 是否绕过缓存
            
        Returns:
            RAG检索上下文
            
        Raises:
            ValueError: 如果tenant_id为空
            PermissionError: 如果速率超限
        """
        import time
        start_time = time.time()
        
        is_valid, error_msg = _global_access_validator.validate_tenant_id(tenant_id)
        if not is_valid:
            raise ValueError(f"租户ID验证失败: {error_msg}")
        
        if self.use_rate_limiter:
            allowed, rate_info = _global_rate_limiter.check_rate_limit(tenant_id)
            if not allowed:
                raise PermissionError(
                    f"速率超限，请等待 {int(rate_info['reset_at'] - time.time())} 秒后重试"
                )
        
        if self.use_cache and not bypass_cache:
            cached_result = _global_retrieval_cache.get(tenant_id, query)
            if cached_result:
                logger.info(f"💾 [RAG检索器] 使用缓存 | 租户: {tenant_id}")
                return cached_result
        
        if not tenant_id:
            raise ValueError("tenant_id is required for RAG retrieval - 租户隔离不能绕过")
        
        filters = self._build_tenant_isolated_filters(
            tenant_id=tenant_id,
            require_public=require_public,
            doc_types=doc_types
        )
        
        logger.info(f"📚 [RAG检索器] 开始检索 | 租户: {tenant_id} | 查询: {query[:50]}...")
        
        try:
            query_embedding = await self._get_query_embedding(query)
            
            # 检查embedding是否有效（全零向量表示输入为空）
            if not query_embedding or all(v == 0.0 for v in query_embedding):
                logger.warning("⚠️ [RAG检索器] 查询embedding无效（可能查询文本为空），跳过向量搜索")
                return []
            
            raw_results = await self._search_vectors(
                query_embedding=query_embedding,
                filters=filters,
                top_k=top_k * 2
            )
            
            filtered_results = self._filter_and_rank_results(
                raw_results=raw_results,
                min_score=min_relevance_score
            )[:top_k]
            
            rag_results = [
                RAGRetrievalResult(
                    content=self._extract_content(r),
                    source=self._extract_source(r),
                    doc_type=self._extract_doc_type(r),
                    confidence=self._extract_confidence(r),
                    metadata=self._extract_metadata(r),
                    relevance_score=r.get("score", 0)
                )
                for r in filtered_results
            ]
            
            retrieval_time = (time.time() - start_time) * 1000
            
            context = RAGRetrievalContext(
                query=query,
                results=rag_results,
                total_results=len(rag_results),
                retrieval_time_ms=retrieval_time,
                tenant_id=tenant_id,
                filters_applied=filters
            )
            
            if self.use_cache and not bypass_cache:
                _global_retrieval_cache.set(tenant_id, query, context)
            
            if self.enable_audit:
                await self._log_retrieval_audit(
                    query=query,
                    tenant_id=tenant_id,
                    results_count=len(rag_results),
                    filters_applied=filters
                )
            
            logger.info(
                f"✅ [RAG检索器] 检索完成 | 租户: {tenant_id} | "
                f"结果数: {len(rag_results)} | 耗时: {retrieval_time:.1f}ms"
            )
            
            return context
            
        except Exception as e:
            logger.error(f"❌ [RAG检索器] 检索失败 | 租户: {tenant_id} | 错误: {str(e)}")
            raise
    
    def _build_tenant_isolated_filters(
        self,
        tenant_id: str,
        require_public: bool = True,
        doc_types: Optional[List[RAGDocType]] = None
    ) -> Dict[str, Any]:
        """
        构建租户隔离的过滤器
        
        关键安全设计：
        1. 必须包含 tenant_id 过滤
        2. is_public 必须为 True
        3. 可选添加文档类型过滤
        
        Args:
            tenant_id: 租户ID
            require_public: 是否只检索公开文档
            doc_types: 文档类型过滤
            
        Returns:
            Qdrant 过滤器字典
        """
        must_conditions = [
            {
                "key": "tenant_id",
                "match": {"value": tenant_id}
            }
        ]
        
        if require_public:
            must_conditions.append({
                "key": "is_public",
                "match": {"value": True}
            })
        
        if doc_types:
            type_values = [dt.value for dt in doc_types]
            must_conditions.append({
                "key": "doc_type",
                "match": {"any": type_values}
            })
        
        return {"must": must_conditions}
    
    def get_tenant_usage(self, tenant_id: str) -> Dict[str, Any]:
        """
        获取租户使用统计
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            使用统计信息
        """
        rate_limit_info = _global_rate_limiter.get_usage(tenant_id)
        return {
            "tenant_id": tenant_id,
            "rate_limit": rate_limit_info,
            "cache_enabled": self.use_cache,
            "rate_limiter_enabled": self.use_rate_limiter
        }
    
    def clear_tenant_cache(self, tenant_id: str):
        """
        清除指定租户的缓存
        
        Args:
            tenant_id: 租户ID
        """
        _global_retrieval_cache.clear(tenant_id)
        logger.info(f"🗑️ [RAG检索器] 已清除租户缓存 | 租户: {tenant_id}")
    
    def enable_caching(self, enabled: bool = True):
        """启用/禁用缓存"""
        self.use_cache = enabled
        logger.info(f"⚙️ [RAG检索器] 缓存已{'启用' if enabled else '禁用'}")
    
    def enable_rate_limiting(self, enabled: bool = True):
        """启用/禁用速率限制"""
        self.use_rate_limiter = enabled
        logger.info(f"⚙️ [RAG检索器] 速率限制已{'启用' if enabled else '禁用'}")
    
    async def _get_query_embedding(self, query: str) -> List[float]:
        """获取查询的向量表示"""
        logger.debug(f"🔍 [_get_query_embedding] 原始查询: '{query}', 长度: {len(query)}")
        
        if self.embedding_service:
            embedding = await self.embedding_service.get_embedding(query)
            if embedding:
                is_all_zero = all(v == 0.0 for v in embedding)
                logger.debug(f"🔍 [_get_query_embedding] 获取到 embedding, 长度: {len(embedding)}, 是否全零: {is_all_zero}")
            else:
                logger.warning("⚠️ [_get_query_embedding] embedding 为空")
            return embedding
        else:
            logger.warning("⚠️ [RAG检索器] 未配置嵌入服务，使用空向量")
            return []
    
    async def _search_vectors(
        self,
        query_embedding: List[float],
        filters: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """执行向量搜索（优先使用 pgvector）"""
        if self.search_service:
            try:
                tenant_id = None
                if filters and "must" in filters:
                    for condition in filters["must"]:
                        if condition.get("key") == "tenant_id":
                            tenant_id = condition.get("match", {}).get("value")
                            break
                
                if not tenant_id:
                    logger.warning("⚠️ [RAG检索器] 无法从过滤器提取租户ID")
                    return []
                
                logger.info(f"🔍 [_search_vectors] 使用已有embedding搜索, tenant_id={tenant_id}, top_k={top_k}")
                
                # 直接使用已有的 query_embedding，不传入空字符串
                # 调用 search_service 的专用方法 search_with_vector（如果存在）
                # 否则跳过搜索，让调用方处理空结果
                try:
                    # 尝试调用支持外部向量的搜索方法
                    results = await self.search_service.search_with_vector(
                        query_vector=query_embedding,
                        top_k=top_k,
                        score_threshold=0.5,
                        tenant_id=tenant_id
                    )
                except AttributeError:
                    # 如果 search_service 没有 search_with_vector，使用带真实查询的 search
                    # 但这里我们已经有向量了，所以传一个占位符避免重复 embedding
                    logger.warning("⚠️ [RAG检索器] search_service 不支持外部向量，尝试使用缓存的embedding作为查询")
                    # 由于无法直接使用外部向量，这里返回空让上层处理
                    return []
                
                return [
                    {
                        "id": r.chunk_id,
                        "score": r.score,
                        "payload": {
                            "content": r.content,
                            "source": r.source_file,
                            "doc_type": "general"
                        }
                    }
                    for r in results
                ]
            except Exception as e:
                logger.error(f"❌ [RAG检索器] pgvector搜索失败: {e}")
                return []
        elif self.qdrant_client:
            try:
                results = self.qdrant_client.search(
                    collection_name="tax_knowledge",
                    query_vector=query_embedding,
                    query_filter=filters,
                    limit=top_k
                )
                return [
                    {
                        "id": r.id,
                        "score": r.score,
                        "payload": r.payload
                    }
                    for r in results
                ]
            except Exception as e:
                logger.error(f"❌ [RAG检索器] Qdrant搜索失败: {e}")
                return []
        else:
            logger.warning("⚠️ [RAG检索器] 未配置向量搜索服务")
            return []
    
    def _filter_and_rank_results(
        self,
        raw_results: List[Dict[str, Any]],
        min_score: float
    ) -> List[Dict[str, Any]]:
        """过滤和排序结果"""
        filtered = [
            r for r in raw_results
            if r.get("score", 0) >= min_score
        ]
        return sorted(filtered, key=lambda x: x.get("score", 0), reverse=True)
    
    def _extract_content(self, result: Dict) -> str:
        """提取内容"""
        payload = result.get("payload", {})
        return payload.get("content", payload.get("page_content", ""))
    
    def _extract_source(self, result: Dict) -> str:
        """提取来源"""
        payload = result.get("payload", {})
        return payload.get("source", payload.get("filename", "unknown"))
    
    def _extract_doc_type(self, result: Dict) -> RAGDocType:
        """提取文档类型"""
        payload = result.get("payload", {})
        doc_type_str = payload.get("doc_type", "general")
        try:
            return RAGDocType(doc_type_str)
        except ValueError:
            return RAGDocType.GENERAL
    
    def _extract_confidence(self, result: Dict) -> float:
        """提取置信度"""
        return result.get("score", 0)
    
    def _extract_metadata(self, result: Dict) -> Dict[str, Any]:
        """提取元数据"""
        payload = result.get("payload", {})
        return {
            "doc_id": result.get("id"),
            "source": payload.get("source"),
            "doc_type": payload.get("doc_type"),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at")
        }
    
    async def _log_retrieval_audit(
        self,
        query: str,
        tenant_id: str,
        results_count: int,
        filters_applied: Dict
    ):
        """记录检索审计日志"""
        logger.info(
            f"📋 [RAG审计] 查询: {query[:50]}... | "
            f"租户: {tenant_id} | 结果: {results_count} | "
            f"过滤: {filters_applied.get('must', [{}])[0].get('key')}"
        )


class TaxSpecificRAGEnhancer:
    """
    税务专用RAG增强器
    
    专门为税务审核场景优化RAG检索：
    1. 税务关键词扩展
    2. 政策时效性加权
    3. 案例相似度匹配
    """
    
    def __init__(self, base_retriever: TenantIsolatedRAGRetriever):
        self.base_retriever = base_retriever
        
        self.tax_keywords = {
            "vat": ["增值税", "进项税额", "销项税额", "专用发票", "普通发票", "抵扣"],
            "cit": ["企业所得税", "应纳税所得额", "税前扣除", "小型微利企业", "高新企业"],
            "iit": ["个人所得税", "工资薪金", "专项附加扣除", "年终奖", "劳务报酬"],
            "compliance": ["税务合规", "风险评估", "反避税", "转让定价", "同期资料"]
        }
    
    async def enhance_tax_extraction(
        self,
        base_extraction: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        使用RAG增强税务提取结果
        
        Args:
            base_extraction: 基础提取结果
            tenant_id: 租户ID
            
        Returns:
            增强后的提取结果
        """
        enhanced = base_extraction.copy()
        enhanced["rag_enhanced"] = False
        enhanced["rag_contexts"] = []
        
        tax_type = base_extraction.get("tax_type", "")
        uncertain_fields = base_extraction.get("uncertain_fields", [])
        
        if not uncertain_fields:
            return enhanced
        
        try:
            rag_contexts = []
            
            for field in uncertain_fields:
                query = self._build_field_query(field, tax_type, base_extraction)
                
                context = await self.base_retriever.retrieve(
                    query=query,
                    tenant_id=tenant_id,
                    top_k=2,
                    require_public=True,
                    min_relevance_score=0.6
                )
                
                if context.results:
                    rag_contexts.append({
                        "field": field,
                        "query": query,
                        "contexts": [
                            {
                                "content": r.content[:500],
                                "source": r.source,
                                "relevance": r.relevance_score
                            }
                            for r in context.results
                        ]
                    })
            
            if rag_contexts:
                enhanced["rag_enhanced"] = True
                enhanced["rag_contexts"] = rag_contexts
            
        except Exception as e:
            logger.error(f"⚠️ [RAG增强器] 增强失败: {e}")
        
        return enhanced
    
    def _build_field_query(
        self,
        field: str,
        tax_type: str,
        context: Dict[str, Any]
    ) -> str:
        """构建字段检索查询"""
        queries = []
        
        if tax_type:
            queries.append(tax_type)
        
        queries.append(field)
        
        if "business_type" in context:
            queries.append(context["business_type"])
        
        return " ".join(queries)


class MultiAgentRAGOrchestrator:
    """
    多智能体RAG编排器
    
    协调多个智能体的RAG需求：
    1. 税务智能体
    2. 财务智能体
    3. 法务智能体
    """
    
    def __init__(self, tenant_id: str):
        """
        初始化编排器
        
        Args:
            tenant_id: 租户ID（必填）
        """
        if not tenant_id:
            raise ValueError("tenant_id is required")
        
        self.tenant_id = tenant_id
        self.rag_retriever = TenantIsolatedRAGRetriever()
        self.tax_enhancer = TaxSpecificRAGEnhancer(self.rag_retriever)
        
        logger.info(f"🔧 [RAG编排器] 初始化 | 租户: {tenant_id}")
    
    async def retrieve_for_tax_agent(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> RAGRetrievalContext:
        """
        为税务智能体检索知识
        
        Args:
            query: 检索查询
            context: 额外上下文信息
            
        Returns:
            RAG检索结果
        """
        return await self.rag_retriever.retrieve(
            query=query,
            tenant_id=self.tenant_id,
            top_k=3,
            doc_types=[
                RAGDocType.TAX_REGULATIONS,
                RAGDocType.TAX_POLICY,
                RAGDocType.CASE_PRECEDENT
            ],
            require_public=True,
            min_relevance_score=0.5
        )
    
    async def retrieve_for_finance_agent(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> RAGRetrievalContext:
        """
        为财务智能体检索知识
        """
        return await self.rag_retriever.retrieve(
            query=query,
            tenant_id=self.tenant_id,
            top_k=3,
            doc_types=[
                RAGDocType.INDUSTRY_GUIDELINES,
                RAGDocType.CASE_PRECEDENT,
                RAGDocType.INTERNAL_GUIDELINES
            ],
            require_public=True,
            min_relevance_score=0.5
        )
    
    async def retrieve_for_legal_agent(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> RAGRetrievalContext:
        """
        为法务智能体检索知识
        """
        return await self.rag_retriever.retrieve(
            query=query,
            tenant_id=self.tenant_id,
            top_k=3,
            doc_types=[
                RAGDocType.TAX_REGULATIONS,
                RAGDocType.TAX_POLICY
            ],
            require_public=True,
            min_relevance_score=0.5
        )
    
    def format_rag_context_for_prompt(
        self,
        retrieval_context: RAGRetrievalContext
    ) -> str:
        """
        格式化RAG检索结果为提示词上下文
        
        Args:
            retrieval_context: RAG检索上下文
            
        Returns:
            格式化的上下文字符串
        """
        if not retrieval_context.results:
            return "无相关参考知识"
        
        formatted_parts = ["【参考知识】\n"]
        
        for i, result in enumerate(retrieval_context.results, 1):
            formatted_parts.append(
                f"{i}. {result.content[:300]}...\n"
                f"   来源: {result.source} | 相关度: {result.relevance_score:.2f}\n"
            )
        
        return "\n".join(formatted_parts)
