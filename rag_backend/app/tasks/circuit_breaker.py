"""
熔断器实现

防止级联故障的熔断器模式实现

功能：
1. 熔断状态管理（关闭、打开、半开）
2. 故障计数和阈值
3. 自动恢复
4. 事件回调
"""

import asyncio
import logging
import time
from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitBreakerState(str, Enum):
    """熔断器状态"""
    CLOSED = "closed"  # 关闭（正常工作）
    OPEN = "open"  # 打开（快速失败）
    HALF_OPEN = "half_open"  # 半开（测试恢复）


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5  # 失败阈值
    success_threshold: int = 2  # 恢复成功阈值
    timeout: float = 60.0  # 超时时间（秒）
    half_open_max_calls: int = 3  # 半开状态最大调用数


@dataclass
class CircuitBreakerStats:
    """熔断器统计"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_state_change: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "state_changes": self.state_changes,
            "last_state_change": self.last_state_change.isoformat() if self.last_state_change else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes
        }


class CircuitBreaker:
    """
    熔断器
    
    实现熔断器模式，防止级联故障
    
    状态转换：
    - CLOSED -> OPEN: 失败次数超过阈值
    - OPEN -> HALF_OPEN: 超时时间到达
    - HALF_OPEN -> CLOSED: 连续成功次数超过阈值
    - HALF_OPEN -> OPEN: 任何失败
    
    使用示例：
    ```python
    cb = CircuitBreaker(failure_threshold=5)
    
    @cb
    async def risky_operation():
        # 可能失败的操作
        pass
    
    result = await cb.execute(risky_operation)
    ```
    """
    
    def __init__(
        self,
        name: str = "default",
        config: Optional[CircuitBreakerConfig] = None,
        on_state_change: Optional[Callable] = None,
        on_rejected: Optional[Callable] = None
    ):
        """
        初始化熔断器
        
        Args:
            name: 熔断器名称
            config: 配置
            on_state_change: 状态变化回调
            on_rejected: 调用被拒绝回调
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.on_state_change = on_state_change
        self.on_rejected = on_rejected
        
        self._state = CircuitBreakerState.CLOSED
        self._stats = CircuitBreakerStats()
        self._last_state_change_time = time.time()
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
        
        logger.info(f"[CircuitBreaker] 初始化: name={name}, config={self.config}")
    
    @property
    def state(self) -> CircuitBreakerState:
        """获取当前状态"""
        return self._state
    
    @property
    def stats(self) -> CircuitBreakerStats:
        """获取统计信息"""
        return self._stats
    
    def _should_allow_request(self) -> bool:
        """
        判断是否允许请求
        
        Returns:
            是否允许
        """
        if self._state == CircuitBreakerState.CLOSED:
            return True
        
        if self._state == CircuitBreakerState.OPEN:
            # 检查是否超时
            elapsed = time.time() - self._last_state_change_time
            if elapsed >= self.config.timeout:
                return True
            return False
        
        if self._state == CircuitBreakerState.HALF_OPEN:
            # 半开状态，限制调用数
            return self._half_open_calls < self.config.half_open_max_calls
        
        return False
    
    async def _transition_to(self, new_state: CircuitBreakerState):
        """
        状态转换
        
        Args:
            new_state: 新状态
        """
        if self._state == new_state:
            return
        
        old_state = self._state
        self._state = new_state
        self._last_state_change_time = time.time()
        self._stats.last_state_change = datetime.now()
        self._stats.state_changes += 1
        
        if new_state == CircuitBreakerState.HALF_OPEN:
            self._half_open_calls = 0
        
        logger.info(
            f"[CircuitBreaker] 状态变化: name={self.name}, "
            f"{old_state.value} -> {new_state.value}"
        )
        
        if self.on_state_change:
            try:
                await self.on_state_change(old_state, new_state)
            except Exception:
                logger.error("[CircuitBreaker] 状态变化回调异常")
    
    async def _record_success(self):
        """记录成功"""
        self._stats.successful_calls += 1
        self._stats.consecutive_successes += 1
        self._stats.consecutive_failures = 0
        
        # 半开状态下连续成功
        if self._state == CircuitBreakerState.HALF_OPEN:
            if self._stats.consecutive_successes >= self.config.success_threshold:
                await self._transition_to(CircuitBreakerState.CLOSED)
                self._stats.consecutive_successes = 0
    
    async def _record_failure(self):
        """记录失败"""
        self._stats.failed_calls += 1
        self._stats.consecutive_failures += 1
        self._stats.consecutive_successes = 0
        self._stats.last_failure = datetime.now()
        
        # 关闭状态下连续失败
        if self._state == CircuitBreakerState.CLOSED:
            if self._stats.consecutive_failures >= self.config.failure_threshold:
                await self._transition_to(CircuitBreakerState.OPEN)
        
        # 半开状态下任何失败
        elif self._state == CircuitBreakerState.HALF_OPEN:
            await self._transition_to(CircuitBreakerState.OPEN)
    
    async def execute(
        self,
        coro_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        执行带熔断保护的函数
        
        Args:
            coro_func: 协程函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            函数执行结果
            
        Raises:
            CircuitBreakerOpenError: 熔断器打开时
        """
        async with self._lock:
            self._stats.total_calls += 1
            
            if not self._should_allow_request():
                self._stats.rejected_calls += 1
                
                if self.on_rejected:
                    try:
                        await self.on_rejected(self._state)
                    except Exception:
                        logger.error("[CircuitBreaker] 拒绝回调异常")
                
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is {self._state.value}"
                )
            
            # 半开状态计数
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._half_open_calls += 1
        
        try:
            result = await coro_func(*args, **kwargs)
            await self._record_success()
            return result
            
        except Exception:
            await self._record_failure()
            raise
    
    def __call__(self, coro_func: Callable) -> Callable:
        """
        装饰器形式使用
        
        Args:
            coro_func: 协程函数
            
        Returns:
            装饰后的函数
        """
        @wraps(coro_func)
        async def wrapper(*args, **kwargs):
            return await self.execute(coro_func, *args, **kwargs)
        
        return wrapper
    
    async def reset(self):
        """重置熔断器"""
        async with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._stats = CircuitBreakerStats()
            self._half_open_calls = 0
            self._last_state_change_time = time.time()
            
            logger.info(f"[CircuitBreaker] 重置: name={self.name}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取熔断器状态
        
        Returns:
            状态信息
        """
        return {
            "name": self.name,
            "state": self._state.value,
            "stats": self._stats.to_dict(),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
                "half_open_max_calls": self.config.half_open_max_calls
            }
        }


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""
    pass


class CircuitBreakerRegistry:
    """
    熔断器注册表
    
    管理多个熔断器实例
    """
    
    def __init__(self):
        """初始化注册表"""
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        获取或创建熔断器
        
        Args:
            name: 熔断器名称
            config: 配置
            
        Returns:
            熔断器实例
        """
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name=name,
                    config=config
                )
            
            return self._breakers[name]
    
    async def get(self, name: str) -> Optional[CircuitBreaker]:
        """
        获取熔断器
        
        Args:
            name: 熔断器名称
            
        Returns:
            熔断器实例，不存在则返回 None
        """
        return self._breakers.get(name)
    
    async def get_all_status(self) -> List[Dict[str, Any]]:
        """
        获取所有熔断器状态
        
        Returns:
            状态列表
        """
        return [
            breaker.get_status()
            for breaker in self._breakers.values()
        ]
    
    async def reset_all(self):
        """重置所有熔断器"""
        for breaker in self._breakers.values():
            await breaker.reset()


# 全局注册表
_global_registry = CircuitBreakerRegistry()


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """获取全局熔断器注册表"""
    return _global_registry
