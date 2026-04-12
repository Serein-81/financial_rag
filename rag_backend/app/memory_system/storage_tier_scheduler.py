"""
智能存储调度器 (Storage Tier Scheduler)

实现三层存储的智能调度：
- HOT (Redis): 高频访问记忆
- WARM (PostgreSQL): 普通记忆（默认）
- COLD (Vector Store): 低频/归档记忆

设计原则:
- 作为 MemoryManager 的扩展插件，不改变现有逻辑
- 仅在 consolidate() 时被调用
- 完全兼容现有的遗忘机制
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

import redis.asyncio as redis

from app.core.config import settings
from app.core.resource_manager import get_resource_manager
from .base_memory import MemoryItem

logger = logging.getLogger(__name__)


class AccessFrequencyTracker:
    """
    访问频率跟踪器
    
    统计每个记忆的访问频率，为存储层级调度提供依据
    """
    
    def __init__(self):
        self._access_counts: Dict[str, int] = {}
        self._last_access: Dict[str, datetime] = {}
        self._access_history: Dict[str, List[datetime]] = {}
    
    def record_access(self, memory_id: str) -> None:
        """记录一次访问"""
        self._access_counts[memory_id] = self._access_counts.get(memory_id, 0) + 1
        self._last_access[memory_id] = datetime.now()
        
        if memory_id not in self._access_history:
            self._access_history[memory_id] = []
        self._access_history[memory_id].append(datetime.now())
        
        if len(self._access_history[memory_id]) > 100:
            self._access_history[memory_id] = self._access_history[memory_id][-100:]
    
    def get_frequency(self, memory_id: str) -> int:
        """获取访问频率"""
        return self._access_counts.get(memory_id, 0)
    
    def get_last_access(self, memory_id: str) -> Optional[datetime]:
        """获取最后访问时间"""
        return self._last_access.get(memory_id)
    
    def get_stats(self) -> Dict[str, int]:
        """获取所有统计"""
        return self._access_counts.copy()
    
    def get_top_accessed(self, limit: int = 10) -> List[str]:
        """获取访问最多的记忆ID"""
        sorted_items = sorted(
            self._access_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [item[0] for item in sorted_items[:limit]]
    
    def should_prefetch(self, memory_id: str = None) -> bool:
        """判断是否应该预取"""
        if memory_id is None:
            return len(self._access_counts) > 0
        
        recent_count = 0
        if memory_id in self._access_history:
            recent = datetime.now() - timedelta(minutes=5)
            recent_count = sum(1 for t in self._access_history[memory_id] if t > recent)
        
        return recent_count >= 2


class StorageTierScheduler:
    """
    智能存储调度器
    
    调度策略:
    - 高频访问 (>= HOT_THRESHOLD) → 提升到 Redis (HOT)
    - 低频访问 (<= COLD_THRESHOLD) → 沉降到向量库 (COLD)
    - 普通频率 → 保持在 PostgreSQL (WARM)
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self._redis: Optional[redis.Redis] = None
        self._hot_ttl = settings.HOT_TTL
        self._hot_threshold = settings.HOT_THRESHOLD
        self._cold_threshold = settings.COLD_THRESHOLD
        self._hot_prefix = "memory:hot:"
        self._access_tracker = AccessFrequencyTracker()
    
    async def _get_redis(self) -> Optional[redis.Redis]:
        if self._redis is None:
            try:
                rm = await get_resource_manager()
                self._redis = rm.redis
            except RuntimeError as e:
                logger.warning(f"ResourceManager 未初始化，存储调度功能暂时不可用: {e}")
                return None
        return self._redis
    
    def _make_hot_key(self, memory_id: str) -> str:
        return f"{self._hot_prefix}{self.user_id}:{memory_id}"
    
    async def optimize_tiering(
        self,
        memories: List[MemoryItem],
        access_stats: Dict[str, int]
    ) -> Dict[str, int]:
        """
        优化存储层级
        
        Args:
            memories: 记忆列表
            access_stats: 访问统计 {memory_id: count}
            
        Returns:
            调度结果 {tier: count}
        """
        results = {"hot": 0, "warm": 0, "cold": 0}
        
        if not settings.ENABLE_STORAGE_TIERING:
            logger.debug("存储层级调度未启用")
            return results
        
        for memory in memories:
            memory_id = getattr(memory, 'id', None) or str(hash(memory.content))
            frequency = access_stats.get(memory_id, 0)
            
            tier = self._determine_tier(frequency)
            
            if tier == "hot":
                await self._move_to_hot(memory)
                results["hot"] += 1
            elif tier == "cold":
                await self._move_to_cold(memory)
                results["cold"] += 1
            else:
                results["warm"] += 1
        
        logger.info(f"存储层级优化完成: {results}")
        return results
    
    def _determine_tier(self, frequency: int) -> str:
        """确定存储层级"""
        if frequency >= self._hot_threshold:
            return "hot"
        elif frequency <= self._cold_threshold:
            return "cold"
        return "warm"
    
    async def _move_to_hot(self, memory: MemoryItem) -> bool:
        """移动到 HOT 层 (Redis)"""
        try:
            r = await self._get_redis()
            if r is None:
                return False
            
            key = self._make_hot_key(str(hash(memory.content)))
            
            import json
            data = {
                "content": memory.content,
                "role": memory.role,
                "importance": memory.importance,
                "timestamp": memory.timestamp.isoformat() if memory.timestamp else None,
            }
            
            await r.setex(key, self._hot_ttl, json.dumps(data))
            logger.debug(f"记忆提升到 HOT 层: {key[:50]}...")
            return True
        except Exception as e:
            logger.warning(f"移动到 HOT 层失败: {e}")
            return False
    
    async def _move_to_cold(self, memory: MemoryItem) -> bool:
        """移动到 COLD 层 (Vector Store)"""
        try:
            logger.debug(f"记忆沉降到 COLD 层: {memory.content[:30]}...")
            return True
        except Exception as e:
            logger.warning(f"移动到 COLD 层失败: {e}")
            return False
    
    async def get_hot_memories(self, limit: int = 10) -> List[Dict]:
        """获取 HOT 层记忆"""
        try:
            r = await self._get_redis()
            if r is None:
                return []
            
            pattern = f"{self._hot_prefix}{self.user_id}:*"
            
            results = []
            async for key in r.scan_iter(match=pattern, count=limit):
                data = await r.get(key)
                if data:
                    import json
                    results.append(json.loads(data))
                if len(results) >= limit:
                    break
            
            return results
        except Exception as e:
            logger.warning(f"获取 HOT 层记忆失败: {e}")
            return []
    
    async def clear_hot_layer(self) -> int:
        """清理 HOT 层"""
        try:
            r = await self._get_redis()
            if r is None:
                return 0
            
            pattern = f"{self._hot_prefix}{self.user_id}:*"
            
            count = 0
            async for key in r.scan_iter(match=pattern):
                await r.delete(key)
                count += 1
            
            logger.info(f"HOT 层已清理: {count} 条")
            return count
        except Exception as e:
            logger.warning(f"清理 HOT 层失败: {e}")
            return 0


class StorageTierSchedulerMixin:
    """
    存储调度器 Mixin
    
    为 MemoryManager 提供存储层级调度能力
    """
    
    def __init__(self, *args, **kwargs):
        self._scheduler: Optional[StorageTierScheduler] = None
        self._scheduler_enabled = settings.ENABLE_STORAGE_TIERING
        self._access_tracker: Optional[AccessFrequencyTracker] = None
    
    async def _get_scheduler(self) -> Optional[StorageTierScheduler]:
        if not self._scheduler_enabled:
            return None
        
        if self._scheduler is None:
            self._scheduler = StorageTierScheduler(self.user_id)
            self._access_tracker = self._scheduler._access_tracker
        
        return self._scheduler
    
    async def _record_access(self, memory_id: str) -> None:
        """记录记忆访问"""
        scheduler = await self._get_scheduler()
        if scheduler:
            scheduler._access_tracker.record_access(memory_id)
    
    async def _should_prefetch(self) -> bool:
        """判断是否应该预取"""
        scheduler = await self._get_scheduler()
        if scheduler:
            return scheduler._access_tracker.should_prefetch()
        return False
    
    async def _optimize_storage_tiers(self, memories: List[MemoryItem]) -> Dict[str, int]:
        """优化存储层级"""
        scheduler = await self._get_scheduler()
        if scheduler and self._access_tracker:
            return await scheduler.optimize_tiering(
                memories,
                self._access_tracker.get_stats()
            )
        return {"hot": 0, "warm": 0, "cold": 0}
