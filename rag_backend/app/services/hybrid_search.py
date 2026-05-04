"""
混合检索引擎 (Hybrid Search Engine)

Dense (pgvector HNSW) + Sparse (tsvector BM25) + RRF 融合。
支持时序去重 (Temporal Dedup) 和 Auto-Merging 向上坍缩。
"""

import uuid
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """
    混合检索引擎：Dense + Sparse + RRF 融合 + 时序去重 + Auto-Merging
    """

    DEFAULT_K = 60

    DOMAIN_WEIGHTS = {
        "legal": (0.4, 0.6),
        "tax": (0.5, 0.5),
        "finance": (0.3, 0.7),
        "general": (0.5, 0.5),
        None: (0.5, 0.5),
    }

    def __init__(self, search_service):
        self._search_service = search_service

    async def search(
        self,
        query: str,
        tenant_id: str,
        domain: Optional[str] = None,
        metadata_filter: Optional[Dict[str, str]] = None,
        jsonb_array_filter: Optional[Dict[str, str]] = None,
        top_k_dense: int = 100,
        top_k_sparse: int = 100,
        top_k_final: int = 50,
    ) -> List[Dict]:
        """Dense + Sparse 并行检索 + RRF 融合"""
        import asyncio

        dense_task = self._search_service.search(
            query=query, top_k=top_k_dense, score_threshold=0.3,
            tenant_id=tenant_id, domain=domain, metadata_filter=metadata_filter,
            jsonb_array_filter=jsonb_array_filter,
        )
        sparse_task = self._search_service.bm25_search(
            query=query, top_k=top_k_sparse,
            tenant_id=tenant_id, domain=domain, metadata_filter=metadata_filter,
            jsonb_array_filter=jsonb_array_filter,
        )

        dense_results, sparse_results = await asyncio.gather(
            dense_task, sparse_task, return_exceptions=True
        )

        if isinstance(dense_results, Exception):
            logger.warning(f"[HybridSearch] Dense 检索失败，降级为纯 BM25: {dense_results}")
            dense_results = []
        if isinstance(sparse_results, Exception):
            logger.warning(f"[HybridSearch] BM25 检索失败，降级为纯 Dense: {sparse_results}")
            sparse_results = []

        if not dense_results and not sparse_results:
            logger.error("[HybridSearch] 两路检索均失败")
            return []

        w_dense, w_sparse = self.DOMAIN_WEIGHTS.get(domain, (0.5, 0.5))
        fused = self._rrf_fusion(
            dense_results=dense_results, sparse_results=sparse_results,
            w_dense=w_dense, w_sparse=w_sparse,
            k=self.DEFAULT_K, top_k=top_k_final,
        )

        logger.info(
            f"[HybridSearch] Dense={len(dense_results)}, Sparse={len(sparse_results)}, "
            f"Fused={len(fused)}, domain={domain}, w_dense={w_dense}, w_sparse={w_sparse}"
        )
        return fused

    def _rrf_fusion(
        self, dense_results: List, sparse_results: List[Dict],
        w_dense: float = 1.0, w_sparse: float = 1.0,
        k: int = 60, top_k: int = 50,
    ) -> List[Dict]:
        """Reciprocal Rank Fusion"""
        scores: Dict[str, float] = {}
        info: Dict[str, dict] = {}

        for rank, item in enumerate(dense_results, 1):
            item_id = str(item.chunk_id if hasattr(item, 'chunk_id') else item["id"])
            scores[item_id] = w_dense / (k + rank)
            info.setdefault(item_id, {})["dense_rank"] = rank
            info[item_id]["content"] = item.content
            info[item_id]["domain"] = getattr(item, 'domain', None)
            info[item_id]["meta_info"] = getattr(item, 'meta_info', getattr(item, 'metadata', {}))

        for rank, item in enumerate(sparse_results, 1):
            item_id = item["id"]
            scores[item_id] = scores.get(item_id, 0) + w_sparse / (k + rank)
            info.setdefault(item_id, {})["sparse_rank"] = rank
            if "content" not in info[item_id]:
                info[item_id]["content"] = item["content"]
            if "domain" not in info[item_id]:
                info[item_id]["domain"] = item.get("domain")
            if "meta_info" not in info[item_id]:
                info[item_id]["meta_info"] = item.get("meta_info", {})

        sorted_ids = sorted(scores, key=scores.get, reverse=True)[:top_k]
        return [
            {
                "id": sid,
                "content": info[sid].get("content", ""),
                "domain": info[sid].get("domain"),
                "meta_info": info[sid].get("meta_info", {}),
                "rrf_score": round(scores[sid], 6),
                "dense_rank": info[sid].get("dense_rank"),
                "sparse_rank": info[sid].get("sparse_rank"),
            }
            for sid in sorted_ids
        ]

    # ============================================================
    # 时序去重 (Temporal Dedup)
    # ============================================================

    async def temporal_dedup(
        self, chunks: List[Dict], query_meta: Dict,
    ) -> List[Dict]:
        """
        时序去重：当用户要求"最新"时，每组同类内容只保留最新版本。
        """
        temporal_mode = query_meta.get("temporal_mode", "none")
        wants_latest = query_meta.get("wants_latest", False)
        if temporal_mode != "latest" and not wants_latest:
            return chunks
        if not chunks:
            return chunks

        groups = self._group_by_identity(chunks)
        deduped = []
        discarded_count = 0

        for group in groups:
            if len(group) == 1:
                deduped.extend(group)
                continue
            sorted_group = sorted(group, key=self._extract_timestamp, reverse=True)
            deduped.append(sorted_group[0])
            discarded_count += len(sorted_group) - 1
            logger.info(
                f"[TemporalDedup] 组内去重: {len(sorted_group)} -> 1, "
                f"保留年: {sorted_group[0].get('meta_info', {}).get('year', 'unknown')}"
            )

        logger.info(
            f"[TemporalDedup] 总量 {len(chunks)} -> {len(deduped)}, 丢弃 {discarded_count}"
        )
        return deduped

    def _group_by_identity(self, chunks: List[Dict]) -> List[List[Dict]]:
        """按 heading_path 或 content 前缀分组"""
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
        if ungrouped:
            prefix_groups: Dict[str, List[Dict]] = {}
            for chunk in ungrouped:
                prefix = chunk.get("content", "")[:100]
                prefix_groups.setdefault(prefix, []).append(chunk)
            groups.extend(prefix_groups.values())

        return groups

    def _extract_timestamp(self, chunk: Dict) -> float:
        """从 meta_info 中提取时间戳（越大越新）"""
        meta = chunk.get("meta_info") or {}
        if not isinstance(meta, dict):
            meta = {}

        eff_date = meta.get("effective_date")
        if eff_date and isinstance(eff_date, str):
            try:
                return datetime.strptime(eff_date, "%Y-%m-%d").timestamp()
            except (ValueError, TypeError):
                pass

        year = meta.get("year")
        if year and isinstance(year, str):
            try:
                return datetime.strptime(f"{year}-07-01", "%Y-%m-%d").timestamp()
            except (ValueError, TypeError):
                pass

        return 0.0

    # ============================================================
    # Auto-Merging 向上坍缩
    # ============================================================

    async def auto_merge(
        self, chunks: List[Dict], min_hits_per_parent: int = 2,
    ) -> List[Dict]:
        """
        Auto-Merging 向上坍缩。

        如果 >= min_hits_per_parent 个碎片指向同一个 PARENT，
        则将这些碎片替换为 PARENT 的完整内容。
        """
        if not chunks:
            return []

        parent_hits: Dict[str, List[int]] = {}
        for idx, chunk in enumerate(chunks):
            meta = chunk.get("meta_info") or {}
            relationships = meta.get("relationships") if isinstance(meta, dict) else {}
            if not isinstance(relationships, dict):
                relationships = {}
            parent_id = relationships.get("PARENT")
            if parent_id:
                parent_hits.setdefault(str(parent_id), []).append(idx)

        parents_to_merge = {
            pid: indices for pid, indices in parent_hits.items()
            if len(indices) >= min_hits_per_parent
        }

        if not parents_to_merge:
            return chunks

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

        final_chunks = []
        replaced_indices: set = set()
        for pid, indices in parents_to_merge.items():
            replaced_indices.update(indices)
            if pid in merged_parents:
                final_chunks.append(merged_parents[pid])

        for idx, chunk in enumerate(chunks):
            if idx not in replaced_indices:
                final_chunks.append(chunk)

        logger.info(
            f"[AutoMerge] {len(chunks)} -> {len(final_chunks)} "
            f"(坍缩 {len(parents_to_merge)} PARENT)"
        )
        return final_chunks


from app.services.search_service import search_service
hybrid_search_engine = HybridSearchEngine(search_service)
