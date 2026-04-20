"""
状态管理器

提供状态的生命周期管理和持久化功能

主要功能：
1. 状态的创建、读取、更新、删除（CRUD）
2. 状态历史记录
3. 状态快照管理
4. 状态缓存
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
from contextlib import asynccontextmanager

from app.state.unified_state import UnifiedState
from app.state.state_factory import StateFactory
from app.state.state_validator import StateValidator, ValidationError

logger = logging.getLogger(__name__)


@dataclass
class StateHistoryEntry:
    """
    状态历史条目
    
    记录状态的变化历史
    """
    timestamp: datetime
    phase: str
    iteration: int
    action: str
    state_snapshot: Dict[str, Any]
    user: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class StateCache:
    """
    状态缓存
    
    提供内存缓存功能，减少数据库访问
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        初始化缓存
        
        Args:
            max_size: 最大缓存条目数
            ttl_seconds: 缓存过期时间（秒）
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存的状态
        
        Args:
            request_id: 请求 ID
        
        Returns:
            缓存的状态，如果不存在或已过期则返回 None
        """
        async with self._lock:
            if request_id not in self._cache:
                return None
            
            # 检查是否过期
            timestamp = self._timestamps.get(request_id)
            if timestamp:
                if datetime.now() - timestamp > timedelta(seconds=self.ttl_seconds):
                    # 已过期，删除
                    del self._cache[request_id]
                    del self._timestamps[request_id]
                    return None
            
            return self._cache.get(request_id)
    
    async def set(self, request_id: str, state: Dict[str, Any]):
        """
        设置缓存的状态
        
        Args:
            request_id: 请求 ID
            state: 状态字典
        """
        async with self._lock:
            # 如果缓存已满，删除最老的条目
            if len(self._cache) >= self.max_size:
                oldest_key = min(
                    self._timestamps.keys(),
                    key=lambda k: self._timestamps[k]
                )
                del self._cache[oldest_key]
                del self._timestamps[oldest_key]
            
            self._cache[request_id] = state
            self._timestamps[request_id] = datetime.now()
    
    async def delete(self, request_id: str):
        """
        删除缓存条目
        
        Args:
            request_id: 请求 ID
        """
        async with self._lock:
            if request_id in self._cache:
                del self._cache[request_id]
            if request_id in self._timestamps:
                del self._timestamps[request_id]
    
    async def clear(self):
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()


class StateManager:
    """
    状态管理器
    
    提供状态的生命周期管理，包括：
    1. 状态 CRUD 操作
    2. 状态历史记录
    3. 状态验证
    4. 状态缓存
    
    使用示例：
    ```python
    manager = StateManager()
    
    # 创建状态
    state = await manager.create_state(
        session_id="sess-001",
        tenant_id="tenant-001",
        user_id="user-001",
        user_query="分析税务问题"
    )
    
    # 更新状态
    state["current_phase"] = "processing"
    await manager.update_state(state)
    
    # 获取状态
    current_state = await manager.get_state(state["request_id"])
    
    # 删除状态
    await manager.delete_state(state["request_id"])
    ```
    """
    
    def __init__(
        self,
        enable_cache: bool = True,
        cache_max_size: int = 1000,
        cache_ttl_seconds: int = 3600,
        enable_history: bool = True,
        max_history_size: int = 10000
    ):
        """
        初始化状态管理器
        
        Args:
            enable_cache: 是否启用缓存
            cache_max_size: 缓存最大大小
            cache_ttl_seconds: 缓存过期时间
            enable_history: 是否启用历史记录
            max_history_size: 历史记录最大条数
        """
        self.validator = StateValidator()
        self.factory = StateFactory()
        
        # 缓存
        self.enable_cache = enable_cache
        if enable_cache:
            self.cache = StateCache(
                max_size=cache_max_size,
                ttl_seconds=cache_ttl_seconds
            )
        
        # 历史记录
        self.enable_history = enable_history
        self.max_history_size = max_history_size
        self._history: Dict[str, List[StateHistoryEntry]] = {}
        self._history_lock = asyncio.Lock()
    
    async def create_state(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
        user_query: str,
        **kwargs
    ) -> UnifiedState:
        """
        创建新状态
        
        Args:
            session_id: 会话 ID
            tenant_id: 租户 ID
            user_id: 用户 ID
            user_query: 用户查询
            **kwargs: 其他参数
        
        Returns:
            UnifiedState: 创建的状态
        
        Raises:
            ValidationError: 如果状态验证失败
        """
        # 使用工厂创建状态
        state = self.factory.create_initial_state(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            user_query=user_query,
            **kwargs
        )
        
        # 验证状态
        result = self.validator.validate(state)
        if not result:
            raise ValidationError(result.errors)
        
        # 保存到缓存
        if self.enable_cache:
            await self.cache.set(state["request_id"], state)
        
        # 记录历史
        if self.enable_history:
            await self._add_history(
                request_id=state["request_id"],
                phase=state["current_phase"],
                iteration=state["iteration"],
                action="create",
                state_snapshot=state
            )
        
        logger.info(
            f"[StateManager] 创建状态: request_id={state['request_id']}, "
            f"session_id={session_id}"
        )
        
        return state
    
    async def get_state(self, request_id: str) -> Optional[UnifiedState]:
        """
        获取状态
        
        Args:
            request_id: 请求 ID
        
        Returns:
            UnifiedState: 状态，如果不存在则返回 None
        """
        # 先从缓存获取
        if self.enable_cache:
            cached = await self.cache.get(request_id)
            if cached:
                logger.debug(f"[StateManager] 从缓存获取状态: {request_id}")
                return cached
        
        # TODO: 从数据库获取
        # 这里应该实现从持久化存储获取的逻辑
        
        return None
    
    async def update_state(
        self,
        state: UnifiedState,
        action: str = "update",
        user: Optional[str] = None
    ) -> UnifiedState:
        """
        更新状态
        
        Args:
            state: 状态字典
            action: 操作类型（用于历史记录）
            user: 操作人
        
        Returns:
            UnifiedState: 更新后的状态
        
        Raises:
            ValidationError: 如果状态验证失败
        """
        # 更新时间戳
        state["updated_at"] = datetime.now()
        
        # 验证状态
        result = self.validator.validate(state)
        if not result:
            logger.warning(
                f"[StateManager] 状态验证失败: request_id={state['request_id']}, "
                f"errors={result.errors}"
            )
            # 严格模式下抛出异常
            raise ValidationError(result.errors)
        
        # 保存到缓存
        if self.enable_cache:
            await self.cache.set(state["request_id"], state)
        
        # 记录历史
        if self.enable_history:
            await self._add_history(
                request_id=state["request_id"],
                phase=state["current_phase"],
                iteration=state["iteration"],
                action=action,
                state_snapshot=state,
                user=user
            )
        
        logger.debug(
            f"[StateManager] 更新状态: request_id={state['request_id']}, "
            f"phase={state['current_phase']}"
        )
        
        return state
    
    async def delete_state(self, request_id: str) -> bool:
        """
        删除状态
        
        Args:
            request_id: 请求 ID
        
        Returns:
            bool: 是否删除成功
        """
        # 从缓存删除
        if self.enable_cache:
            await self.cache.delete(request_id)
        
        # 从历史记录删除
        if self.enable_history:
            async with self._history_lock:
                if request_id in self._history:
                    del self._history[request_id]
        
        logger.info(f"[StateManager] 删除状态: request_id={request_id}")
        
        return True
    
    async def get_state_history(
        self,
        request_id: str,
        limit: Optional[int] = None
    ) -> List[StateHistoryEntry]:
        """
        获取状态历史
        
        Args:
            request_id: 请求 ID
            limit: 返回条数限制
        
        Returns:
            List[StateHistoryEntry]: 状态历史列表
        """
        async with self._history_lock:
            history = self._history.get(request_id, [])
            
            if limit:
                return history[-limit:]
            
            return history
    
    async def _add_history(
        self,
        request_id: str,
        phase: str,
        iteration: int,
        action: str,
        state_snapshot: Dict[str, Any],
        user: Optional[str] = None
    ):
        """
        添加历史记录
        
        Args:
            request_id: 请求 ID
            phase: 当前阶段
            iteration: 当前迭代
            action: 操作类型
            state_snapshot: 状态快照
            user: 操作人
        """
        async with self._history_lock:
            if request_id not in self._history:
                self._history[request_id] = []
            
            entry = StateHistoryEntry(
                timestamp=datetime.now(),
                phase=phase,
                iteration=iteration,
                action=action,
                state_snapshot=state_snapshot,
                user=user
            )
            
            self._history[request_id].append(entry)
            
            # 如果历史记录超过限制，删除最老的
            if len(self._history[request_id]) > self.max_history_size:
                self._history[request_id] = self._history[request_id][-self.max_history_size:]
    
    @asynccontextmanager
    async def transaction(self, request_id: str):
        """
        状态事务上下文管理器
        
        在事务中执行多个状态更新，确保原子性。
        如果发生异常，所有更新都会被回滚。
        
        Args:
            request_id: 请求 ID
        
        Usage:
            ```python
            async with manager.transaction(request_id) as state:
                state["phase"] = "processing"
                state["iteration"] += 1
                # 如果这里发生异常，所有更改都会被回滚
            ```
        """
        original_state = await self.get_state(request_id)
        if not original_state:
            raise ValueError(f"状态不存在: {request_id}")
        
        # 复制原始状态用于回滚
        backup = original_state.copy()
        
        try:
            yield original_state
            # 提交更改
            await self.update_state(original_state)
        except Exception as e:
            # 回滚到原始状态
            await self.update_state(backup)
            logger.error(
                f"[StateManager] 事务回滚: request_id={request_id}, error={e}"
            )
            raise
    
    async def cleanup_expired_states(self, max_age_seconds: int = 86400):
        """
        清理过期状态
        
        Args:
            max_age_seconds: 最大保留时间（秒），默认 24 小时
        """
        threshold = datetime.now() - timedelta(seconds=max_age_seconds)
        
        if self.enable_cache:
            # 清理缓存
            async with self.cache._lock:
                expired_keys = [
                    request_id
                    for request_id, timestamp in self.cache._timestamps.items()
                    if timestamp < threshold
                ]
                
                for key in expired_keys:
                    await self.cache.delete(key)
        
        if self.enable_history:
            # 清理历史记录
            async with self._history_lock:
                for request_id in list(self._history.keys()):
                    history = self._history[request_id]
                    if history and history[0].timestamp < threshold:
                        del self._history[request_id]
        
        logger.info(
            f"[StateManager] 清理过期状态: "
            f"max_age={max_age_seconds}秒"
        )
