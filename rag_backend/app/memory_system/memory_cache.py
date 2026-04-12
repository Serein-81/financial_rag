"""
记忆缓存层 (Memory Cache)

为 MemoryManager 提供 Redis 缓存能力，作为旁路缓存模式
设计原则:
- 不改变 MemoryManager 的写入路径
- 仅在读取时增加缓存层
- 缓存失效由 MemoryManager 显式触发

防御机制:
1. 缓存穿透：使用空值缓存（NULL Cache）防止穿透攻击
2. 缓存击穿：使用互斥锁防止并发击穿
3. 缓存雪崩：使用随机 TTL 偏移量防止集中失效
"""

import json
import logging
import random
import asyncio
from typing import List, Optional, Any, Dict

import redis.asyncio as redis

from app.core.config import settings
from app.core.resource_manager import get_resource_manager
from .base_memory import MemoryItem

logger = logging.getLogger(__name__)

NULL_CACHE_MARKER = "__NULL__"  # 空值缓存标记
NULL_CACHE_TTL = 60  # 空值缓存过期时间（秒）


class MemoryCache:
    """
    MemoryManager 的 Redis 缓存层
    
    采用旁路缓存模式（Cache-Aside Pattern）:
    1. 读取时: 先查缓存，未命中则查数据库，回填缓存
    2. 写入时: MemoryManager 直接写数据库，显式失效缓存
    
    防御机制:
    1. 缓存穿透：使用空值缓存（NULL Cache）防止穿透攻击
    2. 缓存击穿：使用互斥锁防止并发击穿
    3. 缓存雪崩：使用随机 TTL 偏移量防止集中失效
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._redis = redis_client
        self._ttl = settings.MEMORY_CACHE_TTL
        self._prefix = settings.MEMORY_CACHE_PREFIX
        self._lock = asyncio.Lock()  # 缓存击穿防御：互斥锁
        self._cache_locks: Dict[str, asyncio.Lock] = {}  # per-key locks for finer granularity
    
    def _get_randomized_ttl(self) -> int:
        """
        获取随机化的 TTL（缓存雪崩防御）
        
        在基础 TTL 上添加随机偏移量，避免大量缓存同时过期
        随机范围为基础 TTL 的 ±10%
        """
        base_ttl = self._ttl
        # 添加基础 TTL 的 ±10% 随机偏移量
        jitter = int(base_ttl * 0.1)
        randomized_ttl = base_ttl + random.randint(-jitter, jitter)
        # 确保 TTL 至少为原值的 50%
        return max(int(base_ttl * 0.5), randomized_ttl)
    
    def _get_key_lock(self, session_id: str, memory_type: str) -> asyncio.Lock:
        """
        获取特定 key 的锁（缓存击穿防御）
        
        使用细粒度锁，只锁定特定的 session_id + memory_type 组合
        """
        key = f"{session_id}:{memory_type}"
        if key not in self._cache_locks:
            self._cache_locks[key] = asyncio.Lock()
        return self._cache_locks[key]
    
    async def _get_redis(self) -> Optional[redis.Redis]:
        if self._redis is None:
            try:
                rm = await get_resource_manager()
                self._redis = rm.redis
            except RuntimeError as e:
                logger.warning(f"ResourceManager 未初始化，缓存功能暂时不可用: {e}")
                return None
        return self._redis
    
    def _make_key(self, session_id: str, memory_type: str = "all") -> str:
        return f"{self._prefix}{session_id}:{memory_type}"
    
    async def get_memories(self, session_id: str, memory_type: str = "all") -> Optional[List[Dict]]:
        """
        从缓存获取记忆
        
        Args:
            session_id: 会话ID
            memory_type: 记忆类型 (working/episodic/semantic/all)
            
        Returns:
            缓存的记忆列表，未命中返回 None
            注意：返回空列表表示缓存中存在空值（防御缓存穿透）
            返回 None 表示缓存未命中，需要查询数据库
        """
        try:
            r = await self._get_redis()
            if r is None:
                return None
            
            key = self._make_key(session_id, memory_type)
            cached = await r.get(key)
            
            if cached:
                # 缓存命中
                if cached == NULL_CACHE_MARKER:
                    # 缓存穿透防御：检测到空值缓存，直接返回空列表
                    logger.debug(f"缓存命中(空值): {key}")
                    return []  # 返回空列表而非 None，表示缓存中有空值
                
                logger.debug(f"缓存命中: {key}")
                return json.loads(cached)
            
            # 缓存未命中
            logger.debug(f"缓存未命中: {key}")
            return None  # 返回 None 表示需要查询数据库
        except Exception as e:
            logger.warning(f"读取缓存失败: {e}")
            return None
    
    async def set_memories(
        self, 
        session_id: str, 
        memories: List[Any],
        memory_type: str = "all"
    ) -> bool:
        """
        将记忆写入缓存
        
        Args:
            session_id: 会话ID
            memories: 记忆项列表
            memory_type: 记忆类型
            
        Returns:
            是否成功
        """
        try:
            r = await self._get_redis()
            if r is None:
                return False
            
            key = self._make_key(session_id, memory_type)
            
            # 缓存穿透防御：如果记忆为空，写入空值缓存标记
            if not memories:
                # 使用较短的 TTL（60秒）作为空值缓存
                await r.setex(key, NULL_CACHE_TTL, NULL_CACHE_MARKER)
                logger.debug(f"缓存写入(空值): {key} (TTL={NULL_CACHE_TTL}s)")
            else:
                # 缓存雪崩防御：使用随机化 TTL
                randomized_ttl = self._get_randomized_ttl()
                serialized = json.dumps(memories, default=self._serialize_memory_item)
                await r.setex(key, randomized_ttl, serialized)
                logger.debug(f"缓存写入: {key} (TTL={randomized_ttl}s)")
            
            return True
        except Exception as e:
            logger.warning(f"写入缓存失败: {e}")
            return False
    
    async def set_null_cache(self, session_id: str, memory_type: str = "all") -> bool:
        """
        设置空值缓存（缓存穿透防御）
        
        当查询数据库返回空结果时，调用此方法缓存空值标记
        防止同一请求反复穿透到数据库
        
        Args:
            session_id: 会话ID
            memory_type: 记忆类型
            
        Returns:
            是否成功
        """
        try:
            r = await self._get_redis()
            if r is None:
                return False
            
            key = self._make_key(session_id, memory_type)
            # 使用较短的 TTL（60秒）作为空值缓存
            await r.setex(key, NULL_CACHE_TTL, NULL_CACHE_MARKER)
            logger.debug(f"空值缓存写入: {key} (TTL={NULL_CACHE_TTL}s)")
            return True
        except Exception as e:
            logger.warning(f"写入空值缓存失败: {e}")
            return False
    
    async def invalidate(self, session_id: str, memory_type: str = "all") -> bool:
        """
        使缓存失效（写入时调用）
        
        Args:
            session_id: 会话ID
            memory_type: 记忆类型，None 表示全部
            
        Returns:
            是否成功
        """
        try:
            r = await self._get_redis()
            if r is None:
                return False
            
            if memory_type == "all":
                pattern = f"{self._prefix}{session_id}:*"
                keys = []
                async for key in r.scan_iter(match=pattern):
                    keys.append(key)
                if keys:
                    await r.delete(*keys)
                    logger.debug(f"缓存失效(批量): {len(keys)} keys")
            else:
                key = self._make_key(session_id, memory_type)
                await r.delete(key)
                logger.debug(f"缓存失效: {key}")
            
            return True
        except Exception as e:
            logger.warning(f"缓存失效失败: {e}")
            return False
    
    async def get_cached_count(self, session_id: str) -> Dict[str, bool]:
        """
        获取各类型记忆的缓存状态
        
        Returns:
            {memory_type: is_cached}
        """
        result = {}
        memory_types = ["working", "episodic", "semantic", "all"]
        
        try:
            r = await self._get_redis()
            if r is None:
                return {mt: False for mt in memory_types}
            
            for mt in memory_types:
                key = self._make_key(session_id, mt)
                result[mt] = await r.exists(key) > 0
        except Exception as e:
            logger.warning(f"检查缓存状态失败: {e}")
            result = {mt: False for mt in memory_types}
        
        return result
    
    def _serialize_memory_item(self, obj: Any) -> Any:
        """序列化 MemoryItem"""
        if isinstance(obj, MemoryItem):
            return {
                "content": obj.content,
                "role": obj.role,
                "importance": obj.importance,
                "timestamp": obj.timestamp.isoformat() if hasattr(obj, 'timestamp') and obj.timestamp else None,
                "metadata": obj.metadata,
                "embedding": obj.embedding.tolist() if hasattr(obj, 'embedding') and obj.embedding is not None else None,
            }
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)


class CachedMemoryManagerMixin:
    """
    缓存增强 Mixin
    
    为 MemoryManager 提供缓存能力
    使用方式: class CachedMemoryManager(CachedMemoryManagerMixin, MemoryManager)
    """
    
    def __init__(self, *args, **kwargs):
        self._cache: Optional[MemoryCache] = None
        self._cache_enabled = settings.ENABLE_MEMORY_CACHE
    
    async def _get_cache(self) -> Optional[MemoryCache]:
        if not self._cache_enabled:
            return None
        
        if self._cache is None:
            self._cache = MemoryCache()
        
        return self._cache
    
    async def _invalidate_cache(self, memory_type: str = "all") -> None:
        """写入后调用，失效相关缓存"""
        cache = await self._get_cache()
        if cache:
            await cache.invalidate(self.session_id, memory_type)
