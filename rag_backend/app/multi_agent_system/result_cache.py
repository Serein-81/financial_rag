"""
结果缓存系统 (Result Cache)
语义相似度缓存，支持过期时间和LRU淘汰策略
"""

import asyncio
import hashlib
import time
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict
import logging
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """
    缓存条目
    
    代表缓存中的一个条目
    """
    cache_key: str
    query: str
    query_embedding: Optional[List[float]] = None
    result: Any = None
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    ttl_seconds: int = 3600
    hit_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl_seconds
    
    def touch(self):
        """更新访问时间"""
        self.last_accessed = datetime.now()
        self.access_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "cache_key": self.cache_key,
            "query": self.query,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "ttl_seconds": self.ttl_seconds,
            "hit_count": self.hit_count,
            "is_expired": self.is_expired()
        }


@dataclass
class CacheConfig:
    """缓存配置"""
    max_size: int = 1000                   # 最大缓存条目数
    default_ttl: int = 3600                # 默认过期时间（秒）
    similarity_threshold: float = 0.85     # 语义相似度阈值
    enable_semantic: bool = True          # 是否启用语义缓存
    cleanup_interval: int = 300            # 清理间隔（秒）
    embedding_model: Optional[str] = None  # 嵌入模型名称


class ResultCache:
    """
    结果缓存
    
    支持精确匹配和语义相似度匹配的结果缓存
    
    使用示例：
        cache = ResultCache(config=CacheConfig(max_size=1000))
        
        # 存储结果
        await cache.set("query_key", "原始查询", result)
        
        # 获取结果（精确匹配）
        result = await cache.get("query_key")
        
        # 获取结果（语义相似度）
        result = await cache.get_similar("类似的查询", embedding)
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self._exact_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._semantic_cache: Dict[str, CacheEntry] = {}
        self._key_hash_map: Dict[str, str] = {}  # hash -> key
        
        self._total_hits = 0
        self._total_misses = 0
        self._total_sets = 0
        self._total_evictions = 0
        
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()
        
        logger.info(f"💾 [缓存] 初始化完成: max_size={self.config.max_size}, "
                   f"ttl={self.config.default_ttl}s, "
                   f"semantic={self.config.enable_semantic}")
    
    def _generate_key(self, query: str) -> str:
        """生成缓存键"""
        normalized = query.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]
    
    def _calculate_similarity(
        self,
        emb1: List[float],
        emb2: List[float]
    ) -> float:
        """计算余弦相似度"""
        if not emb1 or not emb2:
            return 0.0
        
        vec1 = np.array(emb1)
        vec2 = np.array(emb2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    async def set(
        self,
        query: str,
        result: Any,
        ttl: Optional[int] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        存储结果到缓存
        
        Args:
            query: 查询文本
            result: 查询结果
            ttl: 过期时间（秒）
            embedding: 查询的嵌入向量
            metadata: 额外元数据
            
        Returns:
            缓存键
        """
        async with self._lock:
            cache_key = self._generate_key(query)
            ttl = ttl or self.config.default_ttl
            
            entry = CacheEntry(
                cache_key=cache_key,
                query=query,
                query_embedding=embedding,
                result=result,
                ttl_seconds=ttl,
                metadata=metadata or {}
            )
            
            # 更新精确缓存
            if cache_key in self._exact_cache:
                self._exact_cache.move_to_end(cache_key)
            
            self._exact_cache[cache_key] = entry
            self._key_hash_map[cache_key] = cache_key
            
            # 更新语义缓存
            if embedding and self.config.enable_semantic:
                self._semantic_cache[cache_key] = entry
            
            # LRU淘汰
            await self._evict_if_needed()
            
            self._total_sets += 1
            logger.debug(f"💾 [缓存] 存储: {cache_key[:8]}...")
            
            return cache_key
    
    async def get(self, query: str) -> Optional[Any]:
        """
        获取缓存结果（精确匹配）
        
        Args:
            query: 查询文本
            
        Returns:
            缓存结果，不存在则返回 None
        """
        async with self._lock:
            cache_key = self._generate_key(query)
            
            if cache_key not in self._exact_cache:
                self._total_misses += 1
                logger.debug(f"❌ [缓存] 未命中: {cache_key[:8]}...")
                return None
            
            entry = self._exact_cache[cache_key]
            
            if entry.is_expired():
                await self._remove_entry(cache_key)
                self._total_misses += 1
                logger.debug(f"⏰ [缓存] 已过期: {cache_key[:8]}...")
                return None
            
            entry.touch()
            self._exact_cache.move_to_end(cache_key)
            
            self._total_hits += 1
            entry.hit_count += 1
            logger.debug(f"✅ [缓存] 命中: {cache_key[:8]}... (第{entry.hit_count}次)")
            
            return entry.result
    
    async def get_similar(
        self,
        query: str,
        embedding: List[float],
        threshold: Optional[float] = None
    ) -> Optional[Tuple[Any, float]]:
        """
        获取语义相似的缓存结果
        
        Args:
            query: 查询文本
            embedding: 查询的嵌入向量
            threshold: 相似度阈值
            
        Returns:
            (结果, 相似度) 元组，不存在则返回 None
        """
        if not self.config.enable_semantic:
            return None
        
        threshold = threshold or self.config.similarity_threshold
        
        async with self._lock:
            best_match: Optional[CacheEntry] = None
            best_similarity = 0.0
            
            for cache_key, entry in self._semantic_cache.items():
                if entry.is_expired():
                    await self._remove_entry(cache_key)
                    continue
                
                if entry.query_embedding:
                    similarity = self._calculate_similarity(
                        embedding,
                        entry.query_embedding
                    )
                    
                    if similarity >= threshold and similarity > best_similarity:
                        best_similarity = similarity
                        best_match = entry
            
            if best_match:
                best_match.touch()
                self._total_hits += 1
                best_match.hit_count += 1
                logger.info(f"🎯 [缓存] 语义命中: {best_match.cache_key[:8]}..., "
                          f"相似度={best_similarity:.3f}")
                return (best_match.result, best_similarity)
            
            self._total_misses += 1
            logger.debug(f"❌ [缓存] 语义未命中")
            return None
    
    async def _remove_entry(self, cache_key: str):
        """移除缓存条目"""
        if cache_key in self._exact_cache:
            del self._exact_cache[cache_key]
        
        if cache_key in self._semantic_cache:
            del self._semantic_cache[cache_key]
        
        if cache_key in self._key_hash_map:
            del self._key_hash_map[cache_key]
    
    async def _evict_if_needed(self):
        """LRU淘汰"""
        while len(self._exact_cache) > self.config.max_size:
            oldest_key = next(iter(self._exact_cache))
            await self._remove_entry(oldest_key)
            self._total_evictions += 1
            logger.debug(f"🗑️ [缓存] LRU淘汰: {oldest_key[:8]}...")
    
    async def invalidate(self, query: str) -> bool:
        """
        使缓存失效
        
        Args:
            query: 查询文本
            
        Returns:
            是否成功使失效
        """
        async with self._lock:
            cache_key = self._generate_key(query)
            
            if cache_key in self._exact_cache:
                await self._remove_entry(cache_key)
                logger.info(f"🔄 [缓存] 失效: {cache_key[:8]}...")
                return True
            
            return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """
        使匹配模式的缓存失效
        
        Args:
            pattern: 查询模式（简单包含匹配）
            
        Returns:
            失效的条目数量
        """
        async with self._lock:
            count = 0
            keys_to_remove = []
            
            for cache_key, entry in self._exact_cache.items():
                if pattern.lower() in entry.query.lower():
                    keys_to_remove.append(cache_key)
            
            for key in keys_to_remove:
                await self._remove_entry(key)
                count += 1
            
            if count > 0:
                logger.info(f"🔄 [缓存] 模式失效 [{pattern}]: {count} 条")
            
            return count
    
    async def clear(self):
        """清空所有缓存"""
        async with self._lock:
            count = len(self._exact_cache)
            
            self._exact_cache.clear()
            self._semantic_cache.clear()
            self._key_hash_map.clear()
            
            logger.info(f"🗑️ [缓存] 清空: {count} 条")
    
    async def start_cleanup_task(self):
        """启动清理任务"""
        if self._cleanup_task is None:
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info(f"🧹 [缓存] 清理任务已启动")
    
    async def stop_cleanup_task(self):
        """停止清理任务"""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info(f"🛑 [缓存] 清理任务已停止")
    
    async def _cleanup_loop(self):
        """清理过期条目"""
        while self._running:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ [缓存] 清理异常: {e}")
    
    async def _cleanup_expired(self):
        """清理过期条目"""
        async with self._lock:
            keys_to_remove = [
                cache_key for cache_key, entry in self._exact_cache.items()
                if entry.is_expired()
            ]
            
            for key in keys_to_remove:
                await self._remove_entry(key)
            
            if keys_to_remove:
                logger.info(f"🗑️ [缓存] 清理过期: {len(keys_to_remove)} 条")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_requests = self._total_hits + self._total_misses
        hit_rate = self._total_hits / max(total_requests, 1)
        
        all_entries = list(self._exact_cache.values())
        
        top_hit_entries = sorted(
            all_entries,
            key=lambda x: x.hit_count,
            reverse=True
        )[:5]
        
        return {
            "total_entries": len(all_entries),
            "semantic_entries": len(self._semantic_cache),
            "total_hits": self._total_hits,
            "total_misses": self._total_misses,
            "hit_rate": hit_rate,
            "total_sets": self._total_sets,
            "total_evictions": self._total_evictions,
            "config": {
                "max_size": self.config.max_size,
                "default_ttl": self.config.default_ttl,
                "similarity_threshold": self.config.similarity_threshold,
                "enable_semantic": self.config.enable_semantic
            },
            "top_entries": [
                {
                    "cache_key": e.cache_key[:8],
                    "query": e.query[:50],
                    "hit_count": e.hit_count,
                    "access_count": e.access_count
                }
                for e in top_hit_entries
            ]
        }
    
    async def warmup(
        self,
        entries: List[Tuple[str, Any, Optional[List[float]]]]
    ):
        """
        预热缓存
        
        Args:
            entries: [(query, result, embedding), ...]
        """
        async with self._lock:
            for query, result, embedding in entries:
                cache_key = await self.set(query, result, embedding=embedding)
                logger.debug(f"🔥 [缓存] 预热: {cache_key[:8]}...")
            
            logger.info(f"🔥 [缓存] 预热完成: {len(entries)} 条")


class SemanticIndex:
    """
    语义索引
    
    用于加速语义相似度搜索
    """
    
    def __init__(self):
        self._vectors: Dict[str, np.ndarray] = {}
        self._keys: List[str] = []
        self._matrix: Optional[np.ndarray] = None
        self._dirty = True
        self._lock = asyncio.Lock()
    
    async def add(self, key: str, embedding: List[float]):
        """添加向量"""
        async with self._lock:
            self._vectors[key] = np.array(embedding)
            self._keys.append(key)
            self._dirty = True
    
    async def remove(self, key: str):
        """移除向量"""
        async with self._lock:
            if key in self._vectors:
                del self._vectors[key]
                if key in self._keys:
                    self._keys.remove(key)
                self._dirty = True
    
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        搜索最相似的向量
        
        Args:
            query_embedding: 查询向量
            top_k: 返回前k个结果
            
        Returns:
            [(key, similarity), ...]
        """
        async with self._lock:
            if not self._vectors:
                return []
            
            if self._dirty:
                await self._rebuild_matrix()
            
            query_vec = np.array(query_embedding).reshape(1, -1)
            similarities = np.dot(self._matrix, query_vec.T).flatten()
            
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            return [
                (self._keys[i], float(similarities[i]))
                for i in top_indices
                if similarities[i] > 0
            ]
    
    async def _rebuild_matrix(self):
        """重建矩阵"""
        if not self._vectors:
            self._matrix = np.array([])
            self._dirty = False
            return
        
        self._keys = list(self._vectors.keys())
        self._matrix = np.vstack([self._vectors[k] for k in self._keys])
        self._dirty = False


# 全局缓存实例
_cache: Optional[ResultCache] = None


def get_cache() -> ResultCache:
    """获取全局缓存实例"""
    global _cache
    if _cache is None:
        _cache = ResultCache()
    return _cache
