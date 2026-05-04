# RAG 检索与召回机制重构方案

> 基于现有分块与入库机制（四个领域的节点关系体系+元数据注入），设计对应的检索与召回策略。
> 参考 LlamaIndex 的 Hybrid Search、RecursiveRetriever、AutoMergingRetriever 等核心机制。
> **先不出代码，方案定稿后再落地。**

---

## 目录

1. [整体架构：检索流水线](#1-整体架构检索流水线)
2. [通用底层召回算法基座](#2-通用底层召回算法基座)
3. [精排与断崖截断](#3-精排与断崖截断)
4. [领域感知的查询解析与前置过滤](#4-领域感知的查询解析与前置过滤)
5. [法务领域 Legal 的召回与展开](#5-法务领域-legal-的召回与展开)
6. [税务领域 Tax 的召回与展开](#6-税务领域-tax-的召回与展开)
7. [财务领域 Finance 的召回与展开](#7-财务领域-finance-的召回与展开)
8. [通用领域 General 的召回与展开](#8-通用领域-general-的召回与展开)
9. [多态 Prompt 组装总控](#9-多态-prompt-组装总控)
10. [与现有系统的集成方案](#10-与现有系统的集成方案)
11. [配置管理中心](#11-配置管理中心)
12. [监控与可观测性](#12-监控与可观测性)
13. [测试验证策略](#13-测试验证策略)

---

## 1. 整体架构：检索流水线

### 1.1 完整链路

```
用户查询: "2023年上海的高新企业所得税优惠是什么？"
  │
  ▼
┌─ Step 1: QueryAnalyzer ─────────────────────────────────────────┐
│  输入: query                                                     │
│  处理: 域路由 + 结构化条件提取                                    │
│  输出: {"domain": "tax", "filters": {"year":"2023",             │
│         "region":"上海市", "tax_type":"企业所得税"}}              │
│  耗时: < 5ms (纯正则, 无 LLM)                                     │
└─────────────────────────┬────────────────────────────────────────┘
  │
  ▼
┌─ Step 2: Pre-filtering + Hybrid Recall ─────────────────────────┐
│  并行执行两路检索：                                               │
│                                                                  │
│  Dense (pgvector HNSW):                                         │
│    SELECT ... FROM document_chunks                               │
│    WHERE domain='tax' AND meta_info->>'region'='上海市'           │
│      AND meta_info->>'tax_type'='企业所得税'                       │
│      AND meta_info->>'effective_date' <= '2023-12-31'             │
│      AND meta_info->>'expiry_date' >= '2023-01-01'                │
│    ORDER BY embedding <=> :vec LIMIT 100                          │
│                                                                  │
│  Sparse (tsvector BM25):                                        │
│    SELECT ... FROM document_chunks                               │
│    WHERE content_tsvector @@ plainto_tsquery('simple', :query)   │
│      AND domain='tax'  /* 同样做前置过滤 */                        │
│    ORDER BY ts_rank DESC LIMIT 100                                │
│                                                                  │
│  → RRF 融合两路结果 (k=60, w_dense=0.5, w_sparse=0.5)           │
│  → 输出 Top-50 候选                                               │
│  耗时: ~15ms                                                      │
└─────────────────────────┬────────────────────────────────────────┘
  │
  ▼
┌─ Step 3: Cross-Encoder Reranker ────────────────────────────────┐
│  输入: Top-50 候选                                                │
│  模型: bge-reranker-v2-m3 (SiliconFlow API)                      │
│  输出: 50 条重排得分 [0.92, 0.90, 0.45, 0.42, 0.10, ...]        │
│  耗时: ~200-800ms (取决于候选数量)                                  │
└─────────────────────────┬────────────────────────────────────────┘
  │
  ▼
┌─ Step 4: Cliff Pruning ─────────────────────────────────────────┐
│  输入: 重排得分列表                                                │
│  算法: 从第 min_results(3) 条开始检测 Δ>0.15 的断崖                 │
│  输出: 保留前 2 条 [0.92, 0.90] (3条后的 0.45 因 Δ=0.45 > 0.15)   │
│  耗时: < 1ms                                                      │
└─────────────────────────┬────────────────────────────────────────┘
  │
  ▼
┌─ Step 4.5: Temporal Dedup ─────────────────────────────────────┐
│  触发条件: query_meta.wants_latest=True                          │
│  算法: 按 heading_path/content 分组 → 组内按时间降序               │
│        → 每组只保留最新版本                                       │
│  输出: 2021/2022/2023 三版 → 仅保留 2023 版                     │
│  耗时: < 5ms                                                      │
└─────────────────────────┬────────────────────────────────────────┘
  │
  ▼
┌─ Step 5: Relationship Expansion ────────────────────────────────┐
│  按 domain='tax' 展开:                                           │
│  ├─ 读取 chunk.relationships["PREVIOUS"]  → 前一条法条 (200字符)   │
│  ├─ 读取 chunk.relationships["NEXT"]      → 后一条法条 (200字符)   │
│  └─ 附着到 chunk 对象上备用                                        │
│  耗时: ~10ms (2 次 DB 单行查询)                                    │
└─────────────────────────┬────────────────────────────────────────┘
  │
  ▼
┌─ Step 6: Prompt Assembly ───────────────────────────────────────┐
│  按 domain='tax' 模板组装:                                        │
│  [税法规定 1]                                                     │
│  【前一条款】: ...企业所得税税率为25%...                             │
│  【核心命中】: 第三条：高新技术企业减按15%的税率征收企业所得税。      │
│  【后一条款】: ...本优惠不包含已被列入异常名录的企业...              │
│  耗时: < 1ms                                                      │
└─────────────────────────┬────────────────────────────────────────┘
  │
  ▼
LLM 推理 → 最终回答
```

### 1.2 各步骤延迟预算

| 步骤 | 预期 P50 | 预期 P99 | 超时阈值 |
|------|----------|----------|----------|
| QueryAnalyzer | 2ms | 10ms | 100ms |
| Hybrid Recall (Dense+Sparse+RRF) | 15ms | 50ms | 200ms |
| Cross-Encoder Reranker | 300ms | 800ms | 2000ms |
| Cliff Pruning | <1ms | 2ms | 50ms |
| Temporal Dedup | <5ms | 10ms | 50ms |
| Relationship Expansion | 10ms | 30ms | 100ms |
| Prompt Assembly | <1ms | 2ms | 50ms |
| **总计** | **~335ms** | **~910ms** | **2500ms** |

---

## 2. 通用底层召回算法基座

### 2.1 设计原则

**第一条：只看排名，不看绝对分数。**
向量余弦相似度的得分分布在 0.6~0.95，BM25 得分分布在 0~30，量纲完全不同。禁止直接相加，必须通过 RRF 将排名转化为无量纲的平滑得分。

**第二条：前置过滤必须在向量距离计算之前。**
metadata 过滤（`WHERE meta_info->>'year' = '2023'`）是在 pgvector HNSW 索引扫描时一起下推的，不是在拿到结果后再 filter。这确保了过滤掉的文档根本不参与距离计算，性能不受影响。

**第三条：Dense 和 Sparse 各自取 Top-100，融合后取 Top-50。**
两路各自的 Top-100 通过 RRF 融合后取 Top-50 送入 Reranker。太少的候选（如各取 Top-20）会导致 RRF 融合后有效候选不足；太多则 Reranker 延迟不可控。

### 2.2 Dense 稠密向量检索

#### 2.2.1 现有基础

`SearchService.search()` 已经是 pgvector 余弦相似度检索，可以直接复用。

#### 2.2.2 需要增强的部分

```python
# app/services/search_service.py (增强)

class SearchService:
    async def search(
        self,
        query: str,
        top_k: int = 100,           # 从 5 改为 100（宽松召回）
        kb_id: str = None,
        score_threshold: float = 0.3,  # 从 0.6 改为 0.3（宽松阈值）
        tenant_id: str = None,
        user_id: str = None,
        domain: str = None,
        metadata_filter: Dict[str, str] = None,  # 新增，已实现
    ) -> List[SearchResultItem]:
        """
        核心搜索方法 (v3 增强)

        Args:
            query: 用户查询
            top_k: 返回结果数（默认 100，为 RRF 提供足量候选）
            score_threshold: 余弦相似度阈值（默认 0.3，宽松召回）
            metadata_filter: JSONB 前置过滤条件 {"year": "2023", ...}
        """
        # ... 现有逻辑 ...
```

#### 2.2.3 SQL 模板（含元数据前置过滤）

```sql
SELECT
    c.id,
    c.content,
    c.domain,
    c.node_type,
    c.meta_info,
    c.relationships,
    c.summary,
    (1 - (c.embedding <=> :query_vector::vector)) AS vector_score
FROM document_chunks c
JOIN documents d ON c.document_id = d.id
WHERE
    d.tenant_id = :tenant_id
    AND (1 - (c.embedding <=> :query_vector::vector)) >= :threshold
    -- 领域过滤
    AND (:domain IS NULL OR c.domain = :domain)
    -- 元数据前置过滤 (动态拼接)
    AND (:mf_year IS NULL OR c.meta_info->>'year' = :mf_year)
    AND (:mf_region IS NULL OR c.meta_info->>'region' = :mf_region)
    AND (:mf_tax_type IS NULL OR c.meta_info->>'tax_type' = :mf_tax_type)
    -- 时效过滤 (tax 领域)
    AND (:effective_date IS NULL OR
         c.meta_info->>'effective_date' <= :effective_date)
    AND (:expiry_date IS NULL OR
         c.meta_info->>'expiry_date' >= :expiry_date)
ORDER BY vector_score DESC
LIMIT :limit
```

### 2.3 Sparse 稀疏词汇检索 (BM25)

#### 2.3.1 数据库改造

**新建迁移脚本**：`migrations/add_content_tsvector.py`

```sql
-- Step 1: 新增 tsvector 列（STORED 生成列，自动维护）
ALTER TABLE document_chunks
ADD COLUMN content_tsvector tsvector
GENERATED ALWAYS AS (
    to_tsvector('simple', coalesce(content, ''))
) STORED;

-- Step 2: 建 GIN 索引（CONCURRENTLY 不阻塞读写）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_tsvector
ON document_chunks USING GIN (content_tsvector);

-- Step 3: 验证索引是否已就绪
SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename = 'document_chunks' AND indexname = 'idx_chunks_tsvector';
```

**为什么用 `simple` 配置？**
- `simple` 配置不做英文词干还原，保留中文原字
- 中文不依赖词干，依赖精确字面匹配
- 对于"违约金 5%"、"沪税发〔2023〕11号"这类查询，词干还原反而有害

#### 2.3.2 BM25 检索方法

```python
# app/services/search_service.py (新增)

class SearchService:
    async def bm25_search(
        self,
        query: str,
        top_k: int = 100,
        tenant_id: str = None,
        domain: str = None,
        metadata_filter: Dict[str, str] = None,
    ) -> List[Dict]:
        """
        BM25 稀疏检索 (tsvector + ts_rank)

        Args:
            query: 用户查询原文
            top_k: 返回结果数
            metadata_filter: 前置过滤条件（同 Dense 检索）
        """
        if not query or not query.strip():
            return []

        async with AsyncSessionLocal() as db:
            # 构建基础查询
            select_clause = [
                "c.id", "c.content", "c.domain", "c.node_type",
                "c.meta_info", "c.relationships", "c.summary",
                "ts_rank(c.content_tsvector, plainto_tsquery('simple', :query)) AS bm25_score"
            ]
            where_clauses = [
                "c.content_tsvector @@ plainto_tsquery('simple', :query)",
                "d.tenant_id = :tenant_id",
            ]
            params = {
                "query": query,
                "tenant_id": str(tenant_id),
                "limit": int(top_k),
            }

            # 领域过滤
            if domain:
                where_clauses.append("c.domain = :domain")
                params["domain"] = domain

            # 元数据前置过滤
            if metadata_filter:
                for fkey, fval in metadata_filter.items():
                    pkey = f"mf_{fkey}"
                    where_clauses.append(f"c.meta_info->>'{fkey}' = :{pkey}")
                    params[pkey] = fval

            # 组合 SQL
            sql = text(f"""
                SELECT {', '.join(select_clause)}
                FROM document_chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE {' AND '.join(where_clauses)}
                ORDER BY bm25_score DESC
                LIMIT :limit
            """)

            result = await db.execute(sql, params)
            rows = result.mappings().all()

            return [
                {
                    "id": str(row["id"]),
                    "content": row["content"],
                    "domain": row["domain"],
                    "meta_info": row["meta_info"],
                    "bm25_score": float(row["bm25_score"]),
                }
                for row in rows
            ]
```

#### 2.3.3 ts_query 的选择

| 函数 | 行为 | 适用场景 |
|------|------|----------|
| `plainto_tsquery` | 自动在词之间加 AND | 普通用户查询（默认） |
| `phraseto_tsquery` | 要求词按顺序相邻出现 | 精确短语匹配 |
| `to_tsquery` | 需要用户输入运算符 | 高级搜索语法 |

**本项目使用 `plainto_tsquery`**：用户查询"高新技术企业所得税优惠"自动转为 `高新 AND 技术 AND 企业 AND 所得税 AND 优惠`，匹配包含上述任意词汇的文档。

### 2.4 RRF 融合引擎

#### 2.4.1 完整实现

```python
# app/services/hybrid_search.py (新增)

import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """
    混合检索引擎：Dense + Sparse + RRF 融合

    职责：
    1. 并行执行 Dense 向量检索和 Sparse BM25 检索
    2. 通过 RRF 算法将两路排名融合为统一得分
    3. 输出 Top-N 候选供 Reranker 精排
    """

    # RRF 平滑常数（LlamaIndex 默认值）
    DEFAULT_K = 60

    # 各域权重 (w_dense, w_sparse)
    DOMAIN_WEIGHTS = {
        "legal": (0.4, 0.6),     # BM25 权重高 — 命中洗稿后的实体名
        "tax": (0.5, 0.5),       # 均衡
        "finance": (0.3, 0.7),   # BM25 权重显著高 — 表头名词精确匹配
        "general": (0.5, 0.5),   # 均衡
        None: (0.5, 0.5),        # 未知域
    }

    def __init__(self, search_service):
        self._search_service = search_service

    async def search(
        self,
        query: str,
        tenant_id: str,
        domain: Optional[str] = None,
        metadata_filter: Optional[Dict[str, str]] = None,
        top_k_dense: int = 100,
        top_k_sparse: int = 100,
        top_k_final: int = 50,
    ) -> List[Dict]:
        """
        混合检索主入口

        Args:
            query: 用户查询
            tenant_id: 租户 ID
            domain: 领域（用于权重调节和过滤）
            metadata_filter: JSONB 前置过滤
            top_k_dense/sparse: 两路各自取 Top-N
            top_k_final: RRF 融合后取 Top-N

        Returns:
            [{"id", "content", "domain", "rrf_score", "dense_rank", "sparse_rank"}, ...]
        """
        # Step 1: 并行执行两路检索
        import asyncio

        dense_task = self._search_service.search(
            query=query,
            top_k=top_k_dense,
            score_threshold=0.3,
            tenant_id=tenant_id,
            domain=domain,
            metadata_filter=metadata_filter,
        )
        sparse_task = self._search_service.bm25_search(
            query=query,
            top_k=top_k_sparse,
            tenant_id=tenant_id,
            domain=domain,
            metadata_filter=metadata_filter,
        )

        dense_results, sparse_results = await asyncio.gather(
            dense_task, sparse_task, return_exceptions=True
        )

        # 处理任一检索失败的情况（降级）
        if isinstance(dense_results, Exception):
            logger.warning(f"[HybridSearch] Dense 检索失败，降级为纯 BM25: {dense_results}")
            dense_results = []
        if isinstance(sparse_results, Exception):
            logger.warning(f"[HybridSearch] BM25 检索失败，降级为纯 Dense: {sparse_results}")
            sparse_results = []

        # 如果两路都失败，返回空
        if not dense_results and not sparse_results:
            logger.error("[HybridSearch] 两路检索均失败")
            return []

        # Step 2: RRF 融合
        w_dense, w_sparse = self.DOMAIN_WEIGHTS.get(domain, (0.5, 0.5))
        fused = self._rrf_fusion(
            dense_results=dense_results,
            sparse_results=sparse_results,
            w_dense=w_dense,
            w_sparse=w_sparse,
            k=self.DEFAULT_K,
            top_k=top_k_final,
        )

        logger.info(
            f"[HybridSearch] Dense={len(dense_results)}, Sparse={len(sparse_results)}, "
            f"Fused={len(fused)}, domain={domain}, "
            f"w_dense={w_dense}, w_sparse={w_sparse}"
        )
        return fused

    def _rrf_fusion(
        self,
        dense_results: List,
        sparse_results: List[Dict],
        w_dense: float = 1.0,
        w_sparse: float = 1.0,
        k: int = 60,
        top_k: int = 50,
    ) -> List[Dict]:
        """
        倒数秩融合 (Reciprocal Rank Fusion)

        算法：
            Score_RRF(d) = w_dense / (k + rank_dense(d))
                         + w_sparse / (k + rank_sparse(d))

        Args:
            dense_results:  Dense 检索结果
            sparse_results: BM25 检索结果
            w_dense, w_sparse: 权重
            k: 平滑常数
            top_k: 最终返回数
        """
        scores: Dict[str, float] = {}
        info: Dict[str, dict] = {}

        # Dense 贡献
        for rank, item in enumerate(dense_results, 1):
            item_id = str(item.chunk_id if hasattr(item, 'chunk_id') else item["id"])
            scores[item_id] = w_dense / (k + rank)
            info.setdefault(item_id, {})["dense_rank"] = rank
            info[item_id]["content"] = item.content
            info[item_id]["domain"] = getattr(item, 'domain', None)

        # Sparse 贡献
        for rank, item in enumerate(sparse_results, 1):
            item_id = item["id"]
            scores[item_id] = scores.get(item_id, 0) + w_sparse / (k + rank)
            info.setdefault(item_id, {})["sparse_rank"] = rank
            if "content" not in info[item_id]:
                info[item_id]["content"] = item["content"]
            if "domain" not in info[item_id]:
                info[item_id]["domain"] = item.get("domain")

        # 按 RRF 得分降序排列
        sorted_ids = sorted(scores, key=scores.get, reverse=True)[:top_k]

        return [
            {
                "id": sid,
                "content": info[sid].get("content", ""),
                "domain": info[sid].get("domain"),
                "rrf_score": round(scores[sid], 6),
                "dense_rank": info[sid].get("dense_rank"),
                "sparse_rank": info[sid].get("sparse_rank"),
            }
            for sid in sorted_ids
        ]


# 全局单例
hybrid_search_engine = HybridSearchEngine(search_service)
```

#### 2.4.2 RRF 常数 K 的调优

| K 值 | 效果 | 适用 |
|------|------|------|
| 60 | LlamaIndex 默认值，平滑稳定 | 默认 |
| 30 | 前排文档权重更高，更激进 | 高精度要求的场景 |
| 100 | 后排文档权重更高，更包容 | 高召回要求的场景 |

**K=60 作为默认值**，未来可通过 `app/core/config.py` 加入配置项。

---

## 3. 精排与断崖截断

### 3.1 Cross-Encoder Reranker

#### 3.1.1 复用现有 RerankService

项目已有 `app/services/rerank_service.py`，封装了 SiliconFlow API 的 `bge-reranker-v2-m3` 模型。需要确认接口签名兼容：

```python
# app/services/rerank_service.py (已有，确认接口)

class RerankService:
    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
        max_chars_per_doc: int = 1000,
    ) -> List[RerankResult]:
        """
        Cross-Encoder 重排

        Args:
            query: 用户查询
            documents: 待重排的文档列表
            top_k: 返回 Top-K（None 则返回全部）
            max_chars_per_doc: 单文档最大字符数

        Returns:
            [RerankResult(index, relevance_score, ...), ...]
            其中 relevance_score 为 sigmoid 归一化到 [0,1] 的得分
        """
        ...
```

#### 3.1.2 集成到混合检索链路

```python
async def hybrid_search_with_rerank(
    query: str,
    tenant_id: str,
    domain: str = None,
    metadata_filter: dict = None,
) -> List[Dict]:
    """
    完整链路：混合检索 → RRF → Reranker → Cliff Prune
    """
    from app.services.hybrid_search import hybrid_search_engine
    from app.services.rerank_service import rerank_service
    from app.services.cliff_pruner import cliff_prune

    # Step 1: RRF 融合获取 Top-50
    candidates = await hybrid_search_engine.search(
        query=query,
        tenant_id=tenant_id,
        domain=domain,
        metadata_filter=metadata_filter,
        top_k_final=50,
    )

    if not candidates:
        return []

    # Step 2: Reranker 重排
    try:
        reranked = await rerank_service.rerank(
            query=query,
            documents=[c["content"] for c in candidates],
            top_k=20,
            max_chars_per_doc=1000,
        )
    except Exception as e:
        logger.warning(f"[Reranker] 重排失败，降级为 RRF 原始排序: {e}")
        # 降级：直接返回 RRF 排序的 Top-20
        return candidates[:20]

    # 将重排得分附着到候选上
    for rr in reranked:
        if rr.index < len(candidates):
            candidates[rr.index]["rerank_score"] = rr.relevance_score

    # Step 3: 断崖截断
    pruned = cliff_prune(
        items=candidates,
        score_key="rerank_score",
        min_results=3,
        max_results=20,
        cliff_threshold=0.15,
    )

    return pruned
```

### 3.2 断崖截断算法

#### 3.2.1 完整实现

```python
# app/services/cliff_pruner.py (新增)

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def cliff_prune(
    items: List[Dict[str, Any]],
    score_key: str = "rerank_score",
    min_results: int = 3,
    max_results: int = 20,
    cliff_threshold: float = 0.15,
) -> List[Dict[str, Any]]:
    """
    断崖截断：检测排序得分中的断层，断层后全部抛弃。

    不做固定 Top-K 截断。bge-reranker-v2-m3 的得分分布随
    领域和查询类型剧烈变化（英文 0.995 vs 中文 0.2093），
    固定阈值不可靠。

    改用动态断崖检测：
      从第 min_results 条开始，检查相邻条目的得分差。
      如果差值 > cliff_threshold，则判定为断崖，
      断崖后的条目全部抛弃。

    Args:
        items: 按得分降序排列的条目列表
        score_key: 得分字段名
        min_results: 最少保留数
        max_results: 最多保留数（Token 预算上限）
        cliff_threshold: 相邻得分差阈值

    Returns:
        截断后的条目列表

    Examples:
        >>> cliff_prune([
        ...     {"rerank_score": 0.92}, {"rerank_score": 0.90},
        ...     {"rerank_score": 0.45}, {"rerank_score": 0.10},
        ... ], min_results=2)
        [{"rerank_score": 0.92}, {"rerank_score": 0.90}]
        # 第2→3条的 Δ=0.45 > 0.15，第3条及以后全部抛弃
    """
    if not items:
        return []

    # 按得分降序排序
    sorted_items = sorted(
        items, key=lambda x: x.get(score_key, 0) or 0, reverse=True
    )

    # 如果总数少于最少保留数，直接返回
    if len(sorted_items) <= min_results:
        return sorted_items[:max_results]

    # 从第 min_results 条开始检测断崖
    for i in range(min_results, len(sorted_items)):
        prev_score = sorted_items[i - 1].get(score_key, 0) or 0
        curr_score = sorted_items[i].get(score_key, 0) or 0
        gap = prev_score - curr_score

        if gap > cliff_threshold:
            logger.debug(
                f"[CliffPruner] 断崖检测: 位置 {i}, "
                f"得分 {prev_score:.4f} → {curr_score:.4f}, "
                f"Δ={gap:.4f} > {cliff_threshold}, 截断于 {i} 条"
            )
            return sorted_items[:i]

    # 没有检测到断崖，返回最多 max_results 条
    return sorted_items[:max_results]
```

#### 3.2.2 边界情况处理

| 场景 | 行为 | 原因 |
|------|------|------|
| 候选数 ≤ min_results | 全部保留 | 信息不足，宁可多给不可少给 |
| 得分全部相等（如全部 0.0） | 保留 min_results 条 | 不触发断崖（Δ=0） |
| 第 2→3 条出现断崖 | 保留前 2 条 | 正常断崖检测 |
| 无断崖但 > max_results | 保留 max_results 条 | Token 预算上限 |
| Reranker 得分异常（None/NaN） | 视为 0 | 不会触发误断崖 |

#### 3.2.3 阈值调优建议

| 环境 | 建议阈值 | 说明 |
|------|----------|------|
| 英文文档为主 | 0.20~0.30 | bge-reranker 英文得分分布离散，断崖明显 |
| 中文文档为主 | **0.10~0.15** | 中文得分压缩，断崖不显著 |
| 混合 | 0.15 | 保守值，优先保障不误杀 |

### 3.5 时序去重：Temporal Deduplication

#### 3.5.1 问题场景

系统里同时存在 2021、2022、2023 年三份同名的财务报表，或三个版本的同一税收政策。用户问：

> "最新的高新企业退税率是多少？"

**QueryAnalyzer 无法提取到年份**（"最新"不是年份格式），三份文档语义高度相似、BM25 关键词完全相同，Hybrid Search + Reranker 会全部召回。大模型无法判断用哪一条。

#### 3.5.2 解决方案：两段式"时序倒排与自动择新"

**第一段：查询感知 — QueryAnalyzer 检测"最新"意图**

在 `QueryAnalyzer.analyze()` 的输出中增加 `wants_latest` 和 `temporal_mode` 字段：

```python
# app/services/query_analyzer.py (增强)

# 最新/现行意图关键词
LATEST_INTENT_KEYWORDS = [
    "最新", "最近", "当前", "现行", "现有", "目前",
    "新版本", "新版", "有效", "现有效",
    "新规", "新政", "新政策",
]

def _detect_latest_intent(self, query: str) -> bool:
    """检测查询中是否包含"最新""现行"等时效优先意图"""
    query_clean = re.sub(r"[的的是了]", "", query)  # 去除语气助词干扰
    for kw in self.LATEST_INTENT_KEYWORDS:
        if kw in query_clean:
            return True
    return False
```

增强后的 `analyze()` 输出：

```python
{
    "domain": "tax",
    "filters": {},
    "has_temporal_constraint": False,       # 没有明确年份
    "wants_latest": True,                   # ← 新增：用户要求"最新的"
    "temporal_mode": "latest",              # ← 新增：latest / specific / none
    "entities": {},
}
```

**第二段：数据择新 — 时序去重器**

在 Cliff Prune 之后、关系展开之前，插入时序去重步骤。核心逻辑：

```
输入: [chunk_A_2021, chunk_A_2022, chunk_A_2023, chunk_B, chunk_C]
  │
  ├── Step 1: 按文档标题/语义相似度分组
  │    (同一份政策的不同年份版本归为一组)
  │    → group_1: [chunk_A_2021, chunk_A_2022, chunk_A_2023]
  │    → group_2: [chunk_B]
  │    → group_3: [chunk_C]
  │
  ├── Step 2: 如果用户意图为 wants_latest 或 temporal_mode='latest'
  │    → 每个组内按 effective_date 或 year 降序排列
  │    → 每组只保留第一条（最新的）
  │    → group_1 → [chunk_A_2023] (丢弃 2021, 2022)
  │
  ├── Step 3: 重组候选列表
  │    → [chunk_A_2023, chunk_B, chunk_C]
  │
  └── 附加日志: 记录了丢弃了哪些版本及其原因
```

#### 3.5.3 完整实现

```python
# app/services/hybrid_search.py (新增方法)

import re
from typing import List, Dict, Optional, Set
from datetime import datetime


class HybridSearchEngine:
    # 用于分组去重的元数据键（按优先级）
    DEDUP_GROUP_KEYS = ["document_id", "heading_path"]

    async def temporal_dedup(
        self,
        chunks: List[Dict],
        query_meta: Dict,
    ) -> List[Dict]:
        """
        时序去重：当用户要求"最新"时，每组同类内容只保留最新版本。

        分组依据：
        1. 优先按 heading_path 分组（同一条款的不同年份版本）
        2. 其次按 content 的前 50 字符的相似度分组（无 heading_path 时）

        组内排序：
        1. effective_date（最精确的时序字段）
        2. year（次精确）
        3. created_at（兜底）
        4. chunk_index（最终兜底）

        Args:
            chunks: 断崖截断后的候选列表（含 meta_info）
            query_meta: QueryAnalyzer 的解析结果

        Returns:
            去重后的候选列表
        """
        # 仅在用户要求"最新"时触发
        temporal_mode = query_meta.get("temporal_mode", "none")
        wants_latest = query_meta.get("wants_latest", False)
        if temporal_mode != "latest" and not wants_latest:
            return chunks

        if not chunks:
            return chunks

        # Step 1: 将候选按内容身份分组
        groups = self._group_by_identity(chunks)

        # Step 2: 每组内按时间降序排列，只保留最新
        deduped = []
        discarded_count = 0
        for group in groups:
            if len(group) == 1:
                deduped.extend(group)
                continue

            # 按时间降序排列
            sorted_group = sorted(
                group,
                key=self._extract_timestamp,
                reverse=True,
            )

            # 保留最新的一条
            deduped.append(sorted_group[0])
            discarded_count += len(sorted_group) - 1

            logger.info(
                f"[TemporalDedup] 组内去重: {len(sorted_group)} 条 → 1 条, "
                f"保留: meta_info={sorted_group[0].get('meta_info', {})}, "
                f"丢弃: 年份/日期较早的 {len(sorted_group) - 1} 条"
            )

        logger.info(
            f"[TemporalDedup] 总量 {len(chunks)} → {len(deduped)}, "
            f"丢弃 {discarded_count} 条旧版本, "
            f"mode={temporal_mode}"
        )
        return deduped

    def _group_by_identity(self, chunks: List[Dict]) -> List[List[Dict]]:
        """
        将候选按内容身份分组。

        分组策略（按优先级）：
        1. 相同的 document_id → 同一文档的不同版本
        2. 相同的 heading_path → 同一章节的不同版本
        3. 前 100 字符相同 → 极可能是同一内容的不同年份版本
        """
        # 策略 1: 按 heading_path 分组
        groups_by_path: Dict[str, List[Dict]] = {}
        ungrouped: List[Dict] = []

        for chunk in chunks:
            meta = chunk.get("meta_info") or {}
            heading_path = meta.get("heading_path") if isinstance(meta, dict) else None
            if heading_path:
                groups_by_path.setdefault(str(heading_path), []).append(chunk)
            else:
                ungrouped.append(chunk)

        groups = list(groups_by_path.values())

        # 策略 2: 对无 heading_path 的，按 content 前缀分组
        if ungrouped:
            prefix_groups: Dict[str, List[Dict]] = {}
            for chunk in ungrouped:
                content = chunk.get("content", "")
                prefix = content[:100]  # 取前 100 字符作为指纹
                prefix_groups.setdefault(prefix, []).append(chunk)
            groups.extend(prefix_groups.values())

        return groups

    def _extract_timestamp(self, chunk: Dict) -> float:
        """
        从 chunk 的 meta_info 中提取时间戳（数值越大表示越新）。

        优先级:
        1. effective_date (如 "2023-12-31") → 转为 Unix 时间戳
        2. year (如 "2023") → 转为当年的年中时间戳
        3. created_at (chunk 自身的创建时间)
        4. chunk_index → 作为最后兜底
        """
        meta = chunk.get("meta_info") or {}
        if not isinstance(meta, dict):
            meta = {}

        # 1. effective_date
        eff_date = meta.get("effective_date")
        if eff_date and isinstance(eff_date, str):
            try:
                return datetime.strptime(eff_date, "%Y-%m-%d").timestamp()
            except (ValueError, TypeError):
                pass

        # 2. year
        year = meta.get("year")
        if year and isinstance(year, str):
            try:
                # 取该年 7 月 1 日作为代表时间戳
                return datetime.strptime(f"{year}-07-01", "%Y-%m-%d").timestamp()
            except (ValueError, TypeError):
                pass

        # 3. created_at（来自 chunk 自身的 created_at 字段）
        created = chunk.get("created_at")
        if created:
            if isinstance(created, (int, float)):
                return float(created)

        # 4. chunk_index 兜底（大的 index 通常对应文档尾部，不代表新版本）
        return float(chunk.get("chunk_index", 0))
```

#### 3.5.4 分组去重效果示例

```
去重前 (8 条):
  [0] "第三条：高新技术企业减按15%"  heading_path="税率优惠"  year=2021
  [1] "第三条：高新技术企业减按15%"  heading_path="税率优惠"  year=2022
  [2] "第三条：高新技术企业减按15%"  heading_path="税率优惠"  year=2023  ← 保留
  [3] "第一条：企业所得税税率为25%"  heading_path="基本税率"  year=2021  ← 丢弃
  [4] "第一条：企业所得税税率为25%"  heading_path="基本税率"  year=2022
  [5] "第一条：企业所得税税率为25%"  heading_path="基本税率"  year=2023  ← 保留
  [6] "增值税普通发票税率表"        (无 heading_path)      (无年份)    ← 保留
  [7] "个人所得税专项附加扣除办法"   heading_path="专项扣除"  year=2022  ← 保留

分组:
  group_1 (heading_path="税率优惠"):       [0], [1], [2]  → 保留 [2] (2023)
  group_2 (heading_path="基本税率"):       [3], [4], [5]  → 保留 [5] (2023)
  group_3 (无 heading_path, 无年份):       [6]             → 保留（单条）
  group_4 (heading_path="专项扣除"):       [7]             → 保留（单条）

去重后 (4 条):
  [2] "第三条：高新技术企业减按15%"  year=2023
  [5] "第一条：企业所得税税率为25%"  year=2023
  [6] "增值税普通发票税率表"
  [7] "个人所得税专项附加扣除办法"
```

#### 3.5.5 集成到检索流水线

```
Step 3: Cross-Encoder Reranker
Step 4: Cliff Pruning
Step 4.5: Temporal Dedup  ← 新增
Step 5: Relationship Expansion
Step 6: Prompt Assembly
```

```python
# app/services/unified_retriever.py (增强后的 retrieve 方法)

async def retrieve(self, query, ...):
    # ... 前置步骤 ...

    # ── Step 4: Reranker + Cliff Prune ──
    pruned = await self._rerank_and_prune(query, candidates)

    # ── Step 4.5: 时序去重 ──
    deduped = await hybrid_search_engine.temporal_dedup(
        chunks=pruned,
        query_meta=query_meta,
    )

    # ── Step 5: 关系展开 ──
    enriched = await self._enrich_results(deduped)

    # ... 后续步骤 ...
```

#### 3.5.6 降级策略

| 场景 | 行为 | 影响 |
|------|------|------|
| chunks 中没有任何时间元数据 | 全部保留，不做去重 | 不会误杀 |
| 分组后每组只有 1 条 | 全部保留 | 不影响 |
| 同一组内多条时间戳完全相同 | 保留第一条（按原始顺序） | 结果稳定 |
| 用户未表达"最新"意图 | 跳过整个 dedup 步骤 | 正常返回 |
| `meta_info` 不是 dict 或缺失 | 跳过该 chunk 的分组/排序 | 个别 chunk 可能未被归类 |**

#### 3.5.7 配置项

```python
# app/core/config.py

TEMPORAL_DEDUP_ENABLED: bool = True                    # 总开关
TEMPORAL_DEDUP_GROUP_PREFIX_LENGTH: int = 100          # 内容前缀分组截断长度

### 4.1 域路由

```python
# app/services/query_analyzer.py (增强)

import re
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """
    查询解析器 (v3 增强)

    职责：
    1. 域路由：判断查询属于哪个领域
    2. 结构化条件提取：从自然语言中提取 year/quarter/region/tax_type
    3. 实体识别：识别公司名、合同名等

    设计：纯正则 + 关键词，零 LLM 依赖，<5ms。
    """

    # 域路由关键词（按优先级排列）
    DOMAIN_KEYWORDS: Dict[str, List[str]] = {
        "legal": [
            "合同", "协议", "违约", "赔偿", "诉讼", "起诉", "仲裁",
            "法务", "条款", "义务", "甲方", "乙方", "丙方",
            "违约金", "解除", "终止", "管辖", "效力",
        ],
        "tax": [
            "税务", "税法", "增值税", "所得税", "发票", "申报",
            "税率", "优惠", "减免", "抵扣", "退税", "纳税",
            "税种", "小规模", "一般纳税人",
        ],
        "finance": [
            "财报", "利润", "营收", "成本", "费用", "资产",
            "负债", "财务", "审计", "报表", "预算", "收入",
            "支出", "资产负债表", "利润表", "现金流量表",
        ],
    }

    # 年份正则
    YEAR_REGEX = re.compile(r"(\d{4})\s*年")

    # 季度匹配
    QUARTER_MAP = {
        "第一季度": "Q1", "第1季度": "Q1", "一季度": "Q1",
        "第二季度": "Q2", "第2季度": "Q2", "二季度": "Q2",
        "第三季度": "Q3", "第3季度": "Q3", "三季度": "Q3",
        "第四季度": "Q4", "第4季度": "Q4", "四季度": "Q4",
        "Q1": "Q1", "Q2": "Q2", "Q3": "Q3", "Q4": "Q4",
    }

    # 税种列表
    TAX_TYPES = [
        "增值税", "企业所得税", "个人所得税", "消费税",
        "关税", "印花税", "房产税", "土地使用税",
        "契税", "城市维护建设税", "车辆购置税",
        "资源税", "土地增值税",
    ]

    # 最新/现行意图关键词（用于 temporal dedup 触发）
    LATEST_INTENT_KEYWORDS = [
        "最新", "最近", "当前", "现行", "现有", "目前",
        "新版本", "新版", "有效", "现有效",
        "新规", "新政", "新政策", "新法",
    ]

    # 地域列表
    REGIONS = [
        "全国", "北京市", "上海市", "广东省", "浙江省", "江苏省",
        "深圳市", "广州市", "天津市", "重庆市", "四川省", "湖北省",
        "湖南省", "福建省", "山东省", "河北省", "河南省",
        "安徽省", "陕西省", "辽宁省",
    ]

    def analyze(self, query: str) -> Dict:
        """
        解析用户查询

        Args:
            query: 用户问题原文

        Returns:
            {
                "domain": "tax" | "legal" | "finance" | None,
                "filters": {"year": "2023", "tax_type": "企业所得税", ...},
                "has_temporal_constraint": bool,
                "wants_latest": bool,                        # ← 新增：用户是否要求"最新的"
                "temporal_mode": "latest" / "specific" / "none",  # ← 新增：时效模式
                "entities": {"甲方": "XX科技有限公司"},
            }
        """
        if not query or not query.strip():
            return {"domain": None, "filters": {}, "has_temporal_constraint": False}

        domain = self._route_domain(query)
        filters = self._extract_filters(query)
        has_time = bool(filters.get("year") or filters.get("quarter"))
        wants_latest = self._detect_latest_intent(query)
        entities = self._extract_entities(query)

        # 确定时效模式
        if has_time:
            temporal_mode = "specific"  # 用户指定了具体的年份/季度
        elif wants_latest:
            temporal_mode = "latest"    # 用户要求"最新的"
        else:
            temporal_mode = "none"      # 无时效约束

        result = {
            "domain": domain,
            "filters": filters,
            "has_temporal_constraint": has_time,
            "wants_latest": wants_latest,
            "temporal_mode": temporal_mode,
            "entities": entities,
        }

        logger.debug(f"[QueryAnalyzer] query='{query[:30]}...' → {result}")
        return result

    def _route_domain(self, query: str) -> Optional[str]:
        """域路由：通过关键词判断查询领域"""
        scores = {"legal": 0, "tax": 0, "finance": 0}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw in query:
                    scores[domain] += 1

        max_score = max(scores.values())
        if max_score == 0:
            return None

        # 取得分最高的域
        max_domain = max(scores, key=scores.get)
        return max_domain

    def _extract_filters(self, query: str) -> Dict[str, str]:
        """提取结构化过滤条件"""
        filters = {}

        # 年份
        year_match = self.YEAR_REGEX.search(query)
        if year_match:
            filters["year"] = year_match.group(1)

        # 季度
        for q_text, q_val in self.QUARTER_MAP.items():
            if q_text in query:
                filters["quarter"] = q_val
                break

        # 税种
        for tax_type in self.TAX_TYPES:
            if tax_type in query:
                filters["tax_type"] = tax_type
                break

        # 地域
        for region in self.REGIONS:
            if region in query:
                filters["region"] = region
                break

        return filters

    def _extract_entities(self, query: str) -> Dict[str, str]:
        """
        提取查询中的已知实体
        现阶段返回空 dict，后续可对接知识图谱实体解析
        """
        return {}

    def _detect_latest_intent(self, query: str) -> bool:
        """
        检测查询中是否包含"最新""现行"等时效优先意图。
        用于触发 Temporal Dedup 步骤。
        """
        # 去除常见的语气助词干扰
        query_clean = re.sub(r"[的的是了]", "", query)
        for kw in self.LATEST_INTENT_KEYWORDS:
            if kw in query_clean:
                return True
        return False


# 全局单例
query_analyzer = QueryAnalyzer()
```

### 4.2 前置过滤条件生成

```python
# app/services/query_analyzer.py (续)

class QueryAnalyzer:
    def build_metadata_filter(
        self, query_meta: Dict
    ) -> Optional[Dict[str, str]]:
        """
        将 QueryAnalyzer 的解析结果转为 search_service 的 metadata_filter 参数

        Args:
            query_meta: analyze() 的返回结果

        Returns:
            {"year": "2023", "tax_type": "企业所得税", ...} 或 None
        """
        filters = query_meta.get("filters", {})
        if not filters:
            return None

        metadata_filter = {}

        # 直接可用的精确过滤
        for key in ["year", "quarter", "tax_type", "region"]:
            if key in filters:
                metadata_filter[key] = filters[key]

        return metadata_filter if metadata_filter else None

    def build_temporal_filter(
        self, query_meta: Dict
    ) -> Optional[Dict[str, str]]:
        """
        构建时效过滤条件（tax 领域专用）

        将用户查询中的 year 转为 effective_date/expiry_date 范围。
        如 year=2023 → effective_date <= '2023-12-31' AND expiry_date >= '2023-01-01'
        """
        year = query_meta.get("filters", {}).get("year")
        if not year:
            return None

        try:
            y = int(year)
            return {
                "effective_date": f"{y}-12-31",
                "expiry_date": f"{y}-01-01",
            }
        except ValueError:
            return None
```

---

## 5. 法务领域 Legal 的召回与展开

### 5.1 完整查询处理链路

```
用户: "如果XX科技有限公司提前终止合同，违约金怎么算？"
  │
  ▼
QueryAnalyzer.analyze()
  ├── domain = "legal"           (关键词: "合同", "终止", "违约金")
  ├── filters = {}               (无法提取年份/地域等结构化条件)
  └── entities = {}              (暂未对接图谱)
  │
  ▼
build_metadata_filter() → None   (无法提取结构化过滤)
  │
  ▼
hybrid_search_engine.search(
    domain="legal",
    metadata_filter=None,         ← 不过滤 meta_info
    w_dense=0.4, w_sparse=0.6,   ← BM25 权重 0.6，精准匹配实体
  )
  │
  ▼
Reranker → Cliff Prune (保留 Top-3~10)
  │
  ▼
Relationship Expansion (legal):
  ├── 每个 LEAF 读 relationships["PARENT"]
  ├── _resolve_parent_summary(chunk_id)
  │   ├── 一级: parent.summary (50字摘要)
  │   └── 二级: parent.content[:300] (Phase 2 未完成时的降级)
  └── 附着 parent_summary 到 chunk
  │
  ▼
Prompt Assembly (legal 模板)
  └── [法务条款 1]
      【章节主旨】: {parent_summary}
      【具体条款】: {leaf_content}
```

### 5.2 PARENT Summary 获取（含降级）

```python
# app/services/unified_retriever.py (已有，确认无误)

MAX_PARENT_CHARS = 300  # Phase 2 未完成时的降级截断长度

async def _resolve_parent_summary(self, chunk_id: str) -> Optional[str]:
    """
    获取 PARENT 摘要（语义锚点）

    优先级：
    1. parent.summary（50 字摘要，Phase 2 异步生成）
    2. parent.content[:MAX_PARENT_CHARS]（降级方案，Phase 2 未完成时）
    3. None（无 PARENT 关系）
    """
    if not chunk_id:
        return None

    try:
        async with AsyncSessionLocal() as db:
            chunk = await db.get(DocumentChunk, chunk_id)
            if not chunk or not chunk.relationships:
                return None

            parent_id = chunk.relationships.get("PARENT")
            if not parent_id:
                return None

            try:
                parent_uuid = uuid.UUID(str(parent_id))
            except (ValueError, AttributeError):
                return None

            parent = await db.get(DocumentChunk, parent_uuid)
            if not parent:
                return None

            # 一级：summary（50 字摘要）
            if parent.summary and len(parent.summary) > 5:
                return parent.summary

            # 二级降级：content 前 300 字符
            return parent.content[:MAX_PARENT_CHARS]

    except Exception as e:
        logger.warning(f"[resolve_parent_summary] 失败: {e}")
        return None
```

### 5.3 Prompt 组装

```
[法务条款 1]
【章节主旨】：规定了单方面提前终止合同的违约责任及赔偿标准    ← 25 tokens
【具体条款】：XX科技有限公司(原称:甲方)如提前终止，需支付总金额 5% 的违约金。

[法务条款 2]
【章节主旨】：明确了合同解除后的保密义务存续期限
【具体条款】：合同解除后三年内，双方仍应履行保密义务。
```

**为何展示 3~5 条**：法务每个 LEAF 约 100~300 token，加 summary 后约 150~350 token/条。5 条总计约 750~1750 token，安全可控。

---

## 6. 税务领域 Tax 的召回与展开

### 6.1 完整查询处理链路

```
用户: "2023年上海的高新企业所得税优惠是什么？"
  │
  ▼
QueryAnalyzer.analyze()
  ├── domain = "tax"              (关键词: "所得税", "优惠")
  ├── filters = {
  │     "year": "2023",           (正则提取)
  │     "region": "上海市",        (关键词匹配)
  │     "tax_type": "企业所得税",  (税种列表匹配)
  │   }
  └── has_temporal_constraint = true
  │
  ▼
build_metadata_filter() → {
    "year": "2023",
    "region": "上海市",
    "tax_type": "企业所得税",
  }
build_temporal_filter() → {
    "effective_date": "2023-12-31",
    "expiry_date": "2023-01-01",
  }
  │
  ▼
Dense SQL 最终形态:
  WHERE c.domain = 'tax'
    AND c.meta_info->>'region' = '上海市'
    AND c.meta_info->>'tax_type' = '企业所得税'
    AND c.meta_info->>'effective_date' <= '2023-12-31'
    AND c.meta_info->>'expiry_date' >= '2023-01-01'
  ORDER BY (1 - (c.embedding <=> :vec)) DESC
  LIMIT 100

BM25 SQL 最终形态:
  WHERE c.content_tsvector @@ plainto_tsquery('simple', '高新企业所得税优惠')
    AND c.domain = 'tax'
    AND c.meta_info->>'region' = '上海市'
    AND c.meta_info->>'tax_type' = '企业所得税'
  ORDER BY ts_rank DESC
  LIMIT 100
  │
  ▼
RRF → Reranker → Cliff Prune
  │
  ▼
Relationship Expansion (tax):
  ├── relationships["PREVIOUS"] → 前一条法条 content[:200]
  ├── relationships["NEXT"]     → 后一条法条 content[:200]
  └── 附着到 chunk
  │
  ▼
Prompt Assembly (tax 模板)
  └── [税法规定 1]
      【前一条款】: ...企业所得税税率为25%...
      【核心命中】: 第三条：高新技术企业减按15%的税率征收企业所得税。
      【后一条款】: ...本优惠不包含已被列入异常名录的企业...
```

### 6.2 PREVIOUS/NEXT 展开

```python
# app/services/unified_retriever.py (已有，确认无误)

MAX_PREV_NEXT_CHARS = 200  # 相邻条款截断长度

async def _resolve_prev_next(self, chunk_id: str) -> Dict[str, Optional[str]]:
    """
    获取 PREVIOUS/NEXT 相邻条款

    各截断 200 字符，防止相邻条款过长击穿 token 预算。
    """
    if not chunk_id:
        return {"previous": None, "next": None}

    try:
        async with AsyncSessionLocal() as db:
            chunk = await db.get(DocumentChunk, chunk_id)
            if not chunk or not chunk.relationships:
                return {"previous": None, "next": None}

            prev_content = None
            next_content = None

            prev_id = chunk.relationships.get("PREVIOUS")
            if prev_id:
                try:
                    prev_uuid = uuid.UUID(str(prev_id))
                    prev = await db.get(DocumentChunk, prev_uuid)
                    if prev:
                        prev_content = prev.content[:MAX_PREV_NEXT_CHARS]
                except (ValueError, AttributeError):
                    pass

            next_id = chunk.relationships.get("NEXT")
            if next_id:
                try:
                    next_uuid = uuid.UUID(str(next_id))
                    nxt = await db.get(DocumentChunk, next_uuid)
                    if nxt:
                        next_content = nxt.content[:MAX_PREV_NEXT_CHARS]
                except (ValueError, AttributeError):
                    pass

            return {"previous": prev_content, "next": next_content}

    except Exception as e:
        logger.warning(f"[resolve_prev_next] 失败: {e}")
        return {"previous": None, "next": None}
```

### 6.3 时效过滤的关键意义

**不做过期过滤时的 SQL**：

```sql
WHERE c.domain = 'tax'
  AND c.meta_info->>'tax_type' = '企业所得税'
```

候选集包含**2018年的旧政策**和**2024年的新政策**，向量检索可能因为语义相似而把旧政策排在前面。

**做过期过滤后的 SQL**：

```sql
WHERE c.domain = 'tax'
  AND c.meta_info->>'tax_type' = '企业所得税'
  AND c.meta_info->>'effective_date' <= '2023-12-31'
  AND c.meta_info->>'expiry_date' >= '2023-01-01'
```

2018年的政策如果 `expiry_date` 早于 2023-01-01，已被物理隔离。余弦相似度只在**当前有效的政策**中计算。

**如果用户没提年份怎么办？**

```python
# 用户: "高新技术企业所得税优惠是什么？" (没有年份)
# QueryAnalyzer 无法提取 year
# → 不做时效过滤，全量检索
# → Reranker 根据语义相关性排序
# → 这样的结果可能包含已废止条款
# → 在 Prompt 中标注 [已废止] 给 LLM 自行判断

if not query_meta.get("has_temporal_constraint"):
    # 不做时效过滤
    temporal_filter = None
    # 但增加一个日志标记，让 LLM 感知
    note_expired = True
```

---

## 7. 财务领域 Finance 的召回与展开

### 7.1 完整查询处理链路

```
用户: "字节跳动 2023 年 Q4 的研发费用是多少？"
  │
  ▼
QueryAnalyzer.analyze()
  ├── domain = "finance"
  ├── filters = {"year": "2023", "quarter": "Q4"}
  └── entities = {"company": "字节跳动"}  ← 未来可通过图谱解析
  │
  ▼
前置过滤: {domain: "finance", metadata: {year: "2023"}}
  │
  ▼
Hybrid Search (w_dense=0.3, w_sparse=0.7)
  │
  ▼
Reranker → Cliff Prune
  │
  ▼
Relationship Expansion (finance):
  ├── 检查命中 chunk 的 block_type 是否为 "table"
  ├── 如果是 table:
  │   ├── relationships["PARENT"] → 取 PARENT 正文 content[:300]
  │   └── 附着 parent_context 到 chunk
  └── 如果不是 table:
      └── 不做展开
  │
  ▼
Prompt Assembly (finance 模板)
  └── [财务报表 1]
      【表头语境】：2023年Q4主要财务指标说明，以下数据单位均为万元人民币。
      【核心表格】：
      | 研发费用 | 12,000 | 15,000 (+25%) |
```

### 7.2 表格上下文展开

```python
async def _resolve_finance_context(self, chunk_id: str) -> Optional[str]:
    """
    财务表格上下文展开

    如果命中块是表格，取 PARENT 的 content 前 300 字符，
    通常包含"单位：万元人民币"等关键信息。

    如果不是表格，不展开（普通文本块不需要额外语境）。
    """
    if not chunk_id:
        return None

    try:
        async with AsyncSessionLocal() as db:
            chunk = await db.get(DocumentChunk, chunk_id)
            if not chunk:
                return None

            # 仅当命中块是表格时才做展开
            is_table = False
            if chunk.meta_info:
                # 检查 meta_info 中的 block_type
                if isinstance(chunk.meta_info, dict):
                    block_types = chunk.meta_info.get("block_types", [])
                    is_table = "table" in block_types

            # 也可以通过 chunk 的 domain 和 content 特征判断
            # 更可靠的方式：在入库时将 block_type 写入 meta_info
            if not is_table:
                return None

            parent_id = chunk.relationships.get("PARENT")
            if not parent_id:
                return None

            try:
                parent_uuid = uuid.UUID(str(parent_id))
            except (ValueError, AttributeError):
                return None

            parent = await db.get(DocumentChunk, parent_uuid)
            if not parent:
                return None

            return parent.content[:300]

    except Exception as e:
        logger.warning(f"[resolve_finance_context] 失败: {e}")
        return None
```

### 7.3 BM25 权重 0.7 的数学依据

| 查询 | Dense 向量检索 | BM25 关键词检索 |
|------|---------------|-----------------|
| "研发费用 2023" | 可能匹配到"管理费用"（语义相近） | **精确命中 "研发费用"** |
| "营收增长率" | 可能匹配到"收入增长率"（语义相近） | **精确命中 "营收"** |
| "净利润 1.2亿" | 数字的向量定位差 | 数字不参与 tsquery（默认忽略），但"净利润"精确命中 |

BM25 0.7 权重的效果：如果 BM25 排第 1，Dense 排第 20：

```
BM25 贡献: 0.7 / (60 + 1) = 0.01148
Dense 贡献: 0.3 / (60 + 20) = 0.00375
RRF 总分: 0.01523
```

即使 Dense 排名靠后（第 20），BM25 的高权重仍能确保该条目进入 Top-50 候选。

---

## 8. 通用领域 General 的召回与展开

### 8.1 完整查询处理链路

```
用户: "员工产假的薪资政策是什么？"
  │
  ▼
QueryAnalyzer.analyze()
  ├── domain = None    (未命中任何域关键词)
  └── filters = {}     (无法提取结构化条件)
  │
  ▼
→ domain = "general"   (默认回退)
  │
  ▼
Hybrid Search (w_dense=0.5, w_sparse=0.5, 不过滤)
  │
  ▼
Reranker → Cliff Prune
  │
  ▼
Auto-Merging (向上坍缩):
  ├── 遍历 Top-K 被截断候选
  ├── 统计 relationships["PARENT"] 命中
  ├── 如果 ≥2 个碎片指向同一个 PARENT
  │   ├── 剔除碎片
  │   └── 从 DB 取 PARENT 全文替换
  └── 否则保留原碎片
  │
  ▼
Prompt Assembly (general 模板)
  └── [参考内容 1]
      【综合段落】：(一段连贯的完整上下文)
      [参考内容 2]
      【具体说明】：(独立碎片)
```

### 8.2 Auto-Merging 完整实现

```python
# app/services/hybrid_search.py (新增方法)

class HybridSearchEngine:
    async def auto_merge(
        self,
        chunks: List[Dict],
        min_hits_per_parent: int = 2,
    ) -> List[Dict]:
        """
        Auto-Merging 向上坍缩

        如果 ≥min_hits_per_parent 个碎片指向同一个 PARENT，
        则将这些碎片替换为 PARENT 的完整内容。

        参考 LlamaIndex 的 AutoMergingRetriever 机制。
        但更轻量：不需要 HierarchicalNodeParser，直接利用
        入库时建立的 relationships["PARENT"]。

        Args:
            chunks: 断崖截断后的候选列表
            min_hits_per_parent: 触发坍缩的最小命中数

        Returns:
            坍缩后的候选列表
        """
        if not chunks:
            return []

        # Step 1: 统计每个 PARENT 的被命中次数
        parent_hits: Dict[str, List[int]] = {}
        for idx, chunk in enumerate(chunks):
            parent_id = chunk.get("relationships", {}).get("PARENT")
            if parent_id:
                parent_hits.setdefault(str(parent_id), []).append(idx)

        # Step 2: 筛选出需要坍缩的 PARENT
        parents_to_merge = {
            pid: indices
            for pid, indices in parent_hits.items()
            if len(indices) >= min_hits_per_parent
        }

        if not parents_to_merge:
            return chunks  # 无需坍缩

        # Step 3: 从 DB 取出 PARENT 的完整内容
        from app.models.chunk import DocumentChunk
        from app.db import AsyncSessionLocal
        from sqlalchemy import select

        merged_parents: Dict[str, Dict] = {}
        async with AsyncSessionLocal() as db:
            for pid in parents_to_merge:
                try:
                    parent_uuid = uuid.UUID(pid)
                    result = await db.execute(
                        select(DocumentChunk).where(DocumentChunk.id == parent_uuid)
                    )
                    parent = result.scalar_one_or_none()
                    if parent:
                        merged_parents[pid] = {
                            "id": str(parent.id),
                            "content": parent.content,
                            "domain": parent.domain or "general",
                            "node_type": "parent",
                            "is_merged": True,
                        }
                except (ValueError, AttributeError):
                    continue

        # Step 4: 重组候选列表
        final_chunks = []
        replaced_indices: set = set()

        for pid, indices in parents_to_merge.items():
            replaced_indices.update(indices)
            if pid in merged_parents:
                final_chunks.append(merged_parents[pid])

        # 加入未被替换的碎片
        for idx, chunk in enumerate(chunks):
            if idx not in replaced_indices:
                final_chunks.append(chunk)

        logger.info(
            f"[AutoMerge] {len(chunks)} → {len(final_chunks)} "
            f"(坍缩了 {len(parents_to_merge)} 个 PARENT, "
            f"替换了 {len(replaced_indices)} 个碎片)"
        )
        return final_chunks
```

### 8.3 坍缩效果示例

```
坍缩前 (5 个 256-token 碎片):
  leaf_001: "员工产假期间，基本工资照发"          → PARENT: parent_产假
  leaf_002: "绩效工资按50%发放"                   → PARENT: parent_产假
  leaf_003: "年假需工作满一年"                    → PARENT: parent_年假
  leaf_004: "产假最长不超过128天"                 → PARENT: parent_产假
  leaf_005: "婚假为3个工作日"                     → PARENT: parent_婚假

统计 PARENT 命中:
  parent_产假: 3 次 (leaf_001, leaf_002, leaf_004)  ← ≥2，触发坍缩
  parent_年假: 1 次                                 ← <2，不触发
  parent_婚假: 1 次                                 ← <2，不触发

坍缩后 (3 条):
  parent_产假: "假期薪资...员工产假期间..." (1024 token 完整段落)  ← 替换了 3 个碎片
  leaf_003:   "年假需工作满一年"                                ← 保留
  leaf_005:   "婚假为3个工作日"                                 ← 保留

Token 统计:
  坍缩前: 5 × 256 = 1280 tokens
  坍缩后: 1024 + 256 + 256 = 1536 tokens
  增加 256 tokens，但获取了完整的上下文连贯性
```

---

## 9. 多态 Prompt 组装总控

### 9.1 组装控制器

```python
# app/services/context_assembler.py (新增)

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ContextAssembler:
    """
    多态 Prompt 组装器

    按 domain 分发到不同的组装策略：
    - legal:    PARENT summary + LEAF content
    - tax:      PREVIOUS content + LEAF content + NEXT content
    - finance:  PARENT context + TABLE content
    - general:  Auto-Merged 完整段落
    """

    async def assemble(
        self,
        chunks: List[Dict],
        domain: Optional[str],
        query: str,
    ) -> str:
        """
        组装 LLM 上下文

        Args:
            chunks: 已展开的候选（含 parent_summary, prev_content 等附加信息）
            domain: 查询领域
            query:  用户原始查询

        Returns:
            格式化的上下文字符串
        """
        if not chunks:
            return ""

        if domain == "legal":
            return self._assemble_legal(chunks)
        elif domain == "tax":
            return self._assemble_tax(chunks)
        elif domain == "finance":
            return self._assemble_finance(chunks)
        else:
            return self._assemble_general(chunks)

    def _assemble_legal(self, chunks: List[Dict]) -> str:
        parts = ["<KnowledgeBase type='legal'>"]
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"[法务条款 {i}]")
            parent_summary = chunk.get("parent_summary")
            if parent_summary:
                parts.append(f"【章节主旨】: {parent_summary}")
            parts.append(f"【具体条款】: {chunk.get('content', '')[:500]}")
            parts.append("")
        parts.append("</KnowledgeBase>")
        return "\n".join(parts)

    def _assemble_tax(self, chunks: List[Dict]) -> str:
        parts = ["<KnowledgeBase type='tax'>"]
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"[税法规定 {i}]")
            prev = chunk.get("prev_content")
            if prev:
                parts.append(f"【前一条款】: {prev}")
            parts.append(f"【核心命中】: {chunk.get('content', '')[:500]}")
            nxt = chunk.get("next_content")
            if nxt:
                parts.append(f"【后一条款】: {nxt}")
            parts.append("")
        parts.append("</KnowledgeBase>")
        return "\n".join(parts)

    def _assemble_finance(self, chunks: List[Dict]) -> str:
        parts = ["<KnowledgeBase type='finance'>"]
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"[财务报表 {i}]")
            parent_ctx = chunk.get("parent_context")
            if parent_ctx:
                parts.append(f"【表头语境】: {parent_ctx}")
            content = chunk.get("content", "")[:500]
            # 如果是表格，保留原始 markdown 格式
            if chunk.get("block_type") == "table":
                parts.append(f"【核心表格】:\n{content}")
            else:
                parts.append(f"【数据摘要】: {content}")
            parts.append("")
        parts.append("</KnowledgeBase>")
        return "\n".join(parts)

    def _assemble_general(self, chunks: List[Dict]) -> str:
        parts = ["<KnowledgeBase type='general'>"]
        for i, chunk in enumerate(chunks, 1):
            tag = "综合段落" if chunk.get("is_merged") else "具体说明"
            parts.append(f"[参考内容 {i}]")
            parts.append(f"【{tag}】: {chunk.get('content', '')[:800]}")
            parts.append("")
        parts.append("</KnowledgeBase>")
        return "\n".join(parts)


# 全局单例
context_assembler = ContextAssembler()
```

### 9.2 上下文长度控制

```python
# 各域单条最大 Token 预算（中文字符 ≈ 1 token）
DOMAIN_MAX_CHARS = {
    "legal": 600,     # summary(50) + leaf(500) + overhead
    "tax": 1000,      # prev(200) + leaf(500) + next(200) + overhead
    "finance": 900,   # parent(300) + table(500) + overhead
    "general": 1000,  # parent(800) + overhead
}
```

### 9.3 与现有 `_combine_context` 的兼容

```python
# app/services/unified_retriever.py (增强)

async def retrieve(self, query, ...):
    # ... 现有检索逻辑 ...

    # 新增：域感知上下文组装
    if query_meta.get("domain") and query_meta["domain"] != "general":
        enhanced_chunks = await self._apply_relationship_expansion(
            pruned_chunks, domain=query_meta["domain"]
        )
        combined_context = await context_assembler.assemble(
            chunks=enhanced_chunks,
            domain=query_meta["domain"],
            query=query,
        )
    else:
        # general 域走原有逻辑（或同样走新组装）
        combined_context = context_assembler.assemble(
            chunks=pruned_chunks, domain="general", query=query
        )
```

---

## 10. 与现有系统的集成方案

### 10.1 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/services/hybrid_search.py` | **新增** | HybridSearchEngine：Dense + Sparse + RRF |
| `app/services/cliff_pruner.py` | **新增** | cliff_prune()：断崖截断 |
| `app/services/context_assembler.py` | **新增** | ContextAssembler：四域 Prompt 组装 |
| `app/services/query_analyzer.py` | **增强** | QueryAnalyzer：域路由 + 结构化条件提取 |
| `app/services/search_service.py` | **增强** | 新增 bm25_search() 方法 |
| `app/services/rerank_service.py` | **已有** | 复用，确认接口兼容 |
| `app/services/unified_retriever.py` | **增强** | 集成新链路 |
| `app/models/chunk.py` | **增强** | 新增 content_tsvector 列 |
| `migrations/add_content_tsvector.py` | **新增** | 数据库迁移脚本 |

### 10.2 集成后的 UnifiedRetriever 调用链路

```python
# app/services/unified_retriever.py (增强后的 retrieve 方法)

async def retrieve(self, query, kb_id, session_id, user_id,
                   top_k=5, enable_routing=True, enable_graph=True,
                   tenant_id=None):
    # ── Step 1: 查询解析 ──
    query_meta = query_analyzer.analyze(query)

    # ── Step 2: 智能路由 ──
    route_mode = await smart_router.route(query) if enable_routing else HYBRID
    if route_mode == GREETING:
        return greeting_response(query)

    # ── Step 3: 混合检索 ──
    metadata_filter = query_analyzer.build_metadata_filter(query_meta)
    temporal_filter = query_analyzer.build_temporal_filter(query_meta)
    if temporal_filter:
        metadata_filter = {**(metadata_filter or {}), **temporal_filter}

    candidates = await hybrid_search_engine.search(
        query=query,
        tenant_id=tenant_id,
        domain=query_meta.get("domain"),
        metadata_filter=metadata_filter,
    )

    # ── Step 4: Reranker + Cliff Prune ──
    pruned = await self._rerank_and_prune(query, candidates)

    # ── Step 4.5: 时序去重 (仅在用户要求"最新"时触发) ──
    deduped = await hybrid_search_engine.temporal_dedup(
        chunks=pruned,
        query_meta=query_meta,
    )

    # ── Step 5: 关系展开 ──
    enriched = await self._enrich_results(deduped)

    # ── Step 6: Auto-Merging (仅 general) ──
    if query_meta.get("domain") in (None, "general"):
        enriched = await hybrid_search_engine.auto_merge(enriched)

    # ── Step 7: Prompt 组装 ──

    # ── Step 7: Prompt 组装 ──
    combined_context = await context_assembler.assemble(
        chunks=enriched,
        domain=query_meta.get("domain"),
        query=query,
    )

    return {
        "mode": route_mode.value,
        "rag_results": enriched,
        "combined_context": combined_context,
        "query": query,
        # ... 其他字段同现有逻辑 ...
    }
```

### 10.3 降级矩阵

| 步骤 | 降级触发条件 | 降级行为 | 日志级别 |
|------|-------------|----------|----------|
| QueryAnalyzer | 异常抛出 | domain=None, filters={} | WARNING |
| Dense 检索 | 异常/超时 | 跳过 Dense，纯 BM25 | WARNING |
| BM25 检索 | tsvector 索引缺失/异常 | 跳过 BM25，纯 Dense | WARNING |
| **两路都失败** | 全部异常 | 返回空结果 | **ERROR** |
| RRF 融合 | 只有一路有结果 | 只用那一路（无需融合） | INFO |
| Reranker | API 超时/异常 | 使用 RRF 排序的 Top-20 | WARNING |
| Cliff Pruner | 异常抛出 | 固定 Top-10 截断 | WARNING |
| Relationship Expansion | DB 查询失败 | 跳过展开，保留原始 chunk | WARNING |
| Auto-Merging | 异常抛出 | 跳过坍缩 | WARNING |
| Prompt Assembly | 异常抛出 | 纯文本拼接 | WARNING |

---

## 11. 配置管理中心

所有可调参数集中管理，避免散落在代码中：

```python
# app/core/config.py (新增配置项)

class Settings(BaseSettings):
    # ── Hybrid Search ──
    HYBRID_SEARCH_TOP_K_DENSE: int = 100
    HYBRID_SEARCH_TOP_K_SPARSE: int = 100
    HYBRID_SEARCH_TOP_K_FINAL: int = 50
    HYBRID_SEARCH_RRF_K: int = 60
    HYBRID_SEARCH_DENSE_THRESHOLD: float = 0.3

    # ── Reranker ──
    RERANKER_TOP_K: int = 20
    RERANKER_MAX_CHARS: int = 1000

    # ── Cliff Prune ──
    CLIFF_PRUNE_MIN_RESULTS: int = 3
    CLIFF_PRUNE_MAX_RESULTS: int = 20
    CLIFF_PRUNE_THRESHOLD: float = 0.15

    # ── Relationship Expansion ──
    PARENT_SUMMARY_MAX_CHARS: int = 300
    PREV_NEXT_MAX_CHARS: int = 200
    FINANCE_PARENT_MAX_CHARS: int = 300

    # ── Temporal Dedup ──
    TEMPORAL_DEDUP_ENABLED: bool = True
    TEMPORAL_DEDUP_GROUP_PREFIX_LENGTH: int = 100

    # ── Auto-Merging ──
    AUTO_MERGE_MIN_HITS: int = 2

    # ── Prompt Assembly ──
    LEGAL_MAX_CHARS_PER_ITEM: int = 600
    TAX_MAX_CHARS_PER_ITEM: int = 1000
    FINANCE_MAX_CHARS_PER_ITEM: int = 900
    GENERAL_MAX_CHARS_PER_ITEM: int = 1000
```

---

## 12. 监控与可观测性

### 12.1 关键指标

```python
# 每次检索需要记录以下指标

retrieval_metrics = {
    "query": str,                    # 用户查询（前 50 字符）
    "domain": str,                   # 检测到的领域
    "dense_count": int,              # Dense 检索命中数
    "sparse_count": int,             # BM25 检索命中数
    "fused_count": int,              # RRF 融合后候选数
    "rerank_count": int,             # Reranker 后候选数
    "pruned_count": int,             # 断崖截断后候选数
    "final_count": int,              # 展开后最终进入 Prompt 数
    "total_latency_ms": float,       # 总耗时
    "dense_latency_ms": float,       # Dense 检索耗时
    "sparse_latency_ms": float,      # BM25 检索耗时
    "rerank_latency_ms": float,      # Reranker 耗时
    "deduped_count": int,            # 时序去重丢弃的旧版本数
    "dedup_mode": str,               # 时序去重模式 (latest/specific/none)
    "merged": bool,                  # 是否触发了 Auto-Merging
    "degraded": str,                 # 降级路径（如果有）
}
```

### 12.2 预警阈值

| 指标 | 警告阈值 | 严重阈值 |
|------|----------|----------|
| Dense 检索失败率 | > 1% | > 5% |
| BM25 检索失败率 | > 1% | > 5% |
| Reranker 超时率 | > 5% | > 15% |
| 总延迟 P99 | > 2s | > 5s |
| 降级路径触发率 | > 10% | > 30% |
| 断崖截断后保留 0 条 | 单次 | 连续 5 次 |

### 12.3 可观测性集成

```python
# 在每次检索完成后写入结构化日志
logger.info(
    "[RetrievalTrace] query=%s domain=%s dense=%d sparse=%d "
    "fused=%d rerank=%d pruned=%d deduped=%d final=%d "
    "latency=%.0fms dedup_mode=%s degraded=%s",
    query[:30], domain,
    dense_count, sparse_count,
    fused_count, rerank_count, pruned_count, deduped_count, final_count,
    total_latency, dedup_mode or "none", degraded or "none",
)
```

---

## 13. 测试验证策略

### 13.1 黄金测试集

使用 `rag_backend/tests/evaluators/golden_dataset/queries.json`（已完成 Phase 0），但需要补充检索专用的评估字段：

```json
[
  {
    "id": "RET-TAX-001",
    "domain": "tax",
    "question": "高新技术企业所得税税率是多少？",
    "expected_chunks": ["tax_clause_102"],
    "lifeycle_test": {
      "query_year": "2023",
      "must_exclude_expired": true
    },
    "metrics": ["recall@1", "recall@3", "mrr"]
  },
  {
    "id": "RET-LEG-001",
    "domain": "legal",
    "question": "甲方提前终止合同违约金怎么算？",
    "expected_chunks": ["legal_clause_551"],
    "entity_test": {
      "must_contain_entity": "XX科技有限公司"
    },
    "metrics": ["recall@1", "entity_presence"]
  }
]
```

### 13.2 A/B 测试对比

| 配置 | 说明 | 测试集 Recall@5 |
|------|------|-----------------|
| Baseline (纯 Dense) | 当前生产配置 | 待测量 |
| Hybrid (Dense+BM25+RRF) | 本文方案 | 待测量 |
| Hybrid + Reranker | 本文方案 | 待测量 |
| Hybrid + Reranker + Cliff | 本文方案 | 待测量 |

每个配置在 Golden Dataset 上跑一遍，输出对比报告。

### 13.3 参数敏感度测试

| 参数 | 测试范围 | 推荐值 |
|------|----------|--------|
| RRF K | 30, 60, 100 | 60 |
| w_dense / w_sparse (legal) | (0.3,0.7), (0.4,0.6), (0.5,0.5) | (0.4, 0.6) |
| w_dense / w_sparse (finance) | (0.2,0.8), (0.3,0.7), (0.4,0.6) | (0.3, 0.7) |
| Cliff threshold | 0.10, 0.15, 0.20, 0.25 | 0.15 |
| Dense threshold | 0.2, 0.3, 0.4 | 0.3 |
| BM25 top_k | 50, 100, 200 | 100 |
| Auto-Merge min_hits | 2, 3 | 2 |
