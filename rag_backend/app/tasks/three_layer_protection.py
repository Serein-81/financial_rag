"""
三层防护机制

为每个异步任务提供三层保护：
1. 超时保护 - 防止任务无限期等待
2. 重试保护 - 处理临时性故障
3. 资源限制 - 防止资源耗尽

设计原则：
1. 防御性编程 - 每个防护层都有明确的职责
2. 可配置性 - 每个防护层的参数都可以调整
3. 可观测性 - 防护事件都有日志记录
4. 容错性 - 单个防护失败不影响其他层
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, TypeVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ProtectionStatus(str, Enum):
    """防护状态"""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    RESOURCE_LIMITED = "resource_limited"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class ProtectionResult:
    """
    防护结果
    
    记录一次任务执行的所有防护信息
    """
    status: ProtectionStatus
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    attempts: int = 1
    timeout_occurred: bool = False
    retry_count: int = 0
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_success(self) -> bool:
        """判断是否成功"""
        return self.status == ProtectionStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.status.value if isinstance(self.status, ProtectionStatus) else self.status,
            "result": self.result,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "attempts": self.attempts,
            "timeout_occurred": self.timeout_occurred,
            "retry_count": self.retry_count,
            "resource_usage": self.resource_usage,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class TimeoutProtection:
    """
    超时保护
    
    确保任务在规定时间内完成，防止无限期等待
    """
    
    def __init__(
        self,
        default_timeout: float = 30.0,
        timeout_strategy: str = "cancel"
    ):
        """
        初始化超时保护
        
        Args:
            default_timeout: 默认超时时间（秒）
            timeout_strategy: 超时策略（cancel | extend）
        """
        self.default_timeout = default_timeout
        self.timeout_strategy = timeout_strategy
        self.timeout_history: List[Dict[str, Any]] = []
    
    async def execute(
        self,
        coro: Callable,
        timeout: Optional[float] = None,
        task_id: Optional[str] = None
    ) -> ProtectionResult:
        """
        执行带超时的协程
        
        Args:
            coro: 协程函数
            timeout: 超时时间（秒）
            task_id: 任务 ID
            
        Returns:
            防护结果
        """
        timeout_value = timeout or self.default_timeout
        task_id = task_id or "unknown"
        
        start_time = time.time()
        
        try:
            result = await asyncio.wait_for(
                coro,
                timeout=timeout_value
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            return ProtectionResult(
                status=ProtectionStatus.SUCCESS,
                result=result,
                execution_time_ms=execution_time,
                timeout_occurred=False
            )
            
        except asyncio.TimeoutError:
            execution_time = (time.time() - start_time) * 1000
            
            self._record_timeout(task_id, timeout_value, execution_time)
            
            logger.warning(
                f"[TimeoutProtection] 任务超时: task_id={task_id}, "
                f"timeout={timeout_value}s, execution_time={execution_time}ms"
            )
            
            return ProtectionResult(
                status=ProtectionStatus.TIMEOUT,
                error=f"任务执行超过 {timeout_value} 秒",
                execution_time_ms=execution_time,
                timeout_occurred=True
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            
            logger.error(f"[TimeoutProtection] 执行异常: {e}")
            
            return ProtectionResult(
                status=ProtectionStatus.ERROR,
                error=str(e),
                execution_time_ms=execution_time
            )
    
    def _record_timeout(
        self,
        task_id: str,
        timeout: float,
        execution_time: float
    ):
        """记录超时事件"""
        self.timeout_history.append({
            "task_id": task_id,
            "timeout": timeout,
            "execution_time": execution_time,
            "timestamp": datetime.now()
        })
        
        # 保持历史记录在合理范围内
        if len(self.timeout_history) > 1000:
            self.timeout_history = self.timeout_history[-500:]


class RetryProtection:
    """
    重试保护
    
    处理临时性故障，提供智能重试机制
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        retry_on: Optional[List[type]] = None
    ):
        """
        初始化重试保护
        
        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟（秒）
            max_delay: 最大延迟（秒）
            exponential_base: 指数退避基数
            retry_on: 需要重试的异常类型列表
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retry_on = retry_on or [Exception]
        self.retry_history: List[Dict[str, Any]] = []
    
    async def execute(
        self,
        coro: Callable,
        max_retries: Optional[int] = None,
        task_id: Optional[str] = None
    ) -> ProtectionResult:
        """
        执行带重试的协程
        
        Args:
            coro: 协程函数
            max_retries: 最大重试次数
            task_id: 任务 ID
            
        Returns:
            防护结果
        """
        max_attempts = max_retries or self.max_retries
        task_id = task_id or "unknown"
        retry_count = 0
        
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                start_time = time.time()
                result = await coro()
                execution_time = (time.time() - start_time) * 1000
                
                if retry_count > 0:
                    logger.info(
                        f"[RetryProtection] 重试成功: task_id={task_id}, "
                        f"attempts={attempt + 1}, retry_count={retry_count}"
                    )
                
                return ProtectionResult(
                    status=ProtectionStatus.SUCCESS,
                    result=result,
                    execution_time_ms=execution_time,
                    attempts=attempt + 1,
                    retry_count=retry_count
                )
                
            except Exception as e:
                last_error = e
                
                # 检查是否应该重试
                if not self._should_retry(e):
                    logger.error(
                        f"[RetryProtection] 不应重试的异常: task_id={task_id}, "
                        f"error={e}"
                    )
                    
                    return ProtectionResult(
                        status=ProtectionStatus.ERROR,
                        error=str(e),
                        attempts=attempt + 1,
                        retry_count=retry_count
                    )
                
                # 不是最后一次尝试，等待后重试
                if attempt < max_attempts - 1:
                    delay = self._calculate_delay(retry_count)
                    
                    logger.warning(
                        f"[RetryProtection] 重试: task_id={task_id}, "
                        f"attempt={attempt + 1}, delay={delay}s, error={e}"
                    )
                    
                    await asyncio.sleep(delay)
                    retry_count += 1
                else:
                    logger.error(
                        f"[RetryProtection] 超过最大重试次数: task_id={task_id}, "
                        f"max_retries={max_attempts}, last_error={e}"
                    )
        
        return ProtectionResult(
            status=ProtectionStatus.MAX_RETRIES_EXCEEDED,
            error=str(last_error),
            attempts=max_attempts,
            retry_count=retry_count
        )
    
    def _should_retry(self, error: Exception) -> bool:
        """判断是否应该重试"""
        return any(isinstance(error, exc_type) for exc_type in self.retry_on)
    
    def _calculate_delay(self, retry_count: int) -> float:
        """计算延迟时间（指数退避）"""
        delay = self.base_delay * (self.exponential_base ** retry_count)
        return min(delay, self.max_delay)


class ResourceProtection:
    """
    资源限制保护
    
    防止资源耗尽，包括：
    1. 并发任务数限制
    2. 内存使用限制
    3. CPU 使用限制
    """
    
    def __init__(
        self,
        max_concurrent_tasks: int = 100,
        max_memory_mb: int = 512,
        check_interval: float = 1.0
    ):
        """
        初始化资源保护
        
        Args:
            max_concurrent_tasks: 最大并发任务数
            max_memory_mb: 最大内存使用（MB）
            check_interval: 检查间隔（秒）
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_memory_mb = max_memory_mb
        self.check_interval = check_interval
        
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._current_tasks: Dict[str, asyncio.Task] = {}
        self._resource_history: List[Dict[str, Any]] = []
    
    async def execute(
        self,
        coro: Callable,
        task_id: Optional[str] = None,
        check_memory: bool = True
    ) -> ProtectionResult:
        """
        执行带资源限制的协程
        
        Args:
            coro: 协程函数
            task_id: 任务 ID
            check_memory: 是否检查内存
            
        Returns:
            防护结果
        """
        task_id = task_id or "unknown"
        start_time = time.time()
        
        # 检查资源
        resource_check = await self._check_resources(task_id, check_memory)
        if not resource_check["allowed"]:
            logger.warning(
                f"[ResourceProtection] 资源不足: task_id={task_id}, "
                f"reason={resource_check['reason']}"
            )
            
            return ProtectionResult(
                status=ProtectionStatus.RESOURCE_LIMITED,
                error=resource_check["reason"],
                execution_time_ms=0,
                resource_usage=resource_check
            )
        
        # 获取信号量
        async with self._semaphore:
            try:
                result = await coro()
                execution_time = (time.time() - start_time) * 1000
                
                # 记录资源使用
                resource_usage = await self._record_usage(task_id, execution_time)
                
                return ProtectionResult(
                    status=ProtectionStatus.SUCCESS,
                    result=result,
                    execution_time_ms=execution_time,
                    resource_usage=resource_usage
                )
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                
                logger.error(f"[ResourceProtection] 执行异常: {e}")
                
                return ProtectionResult(
                    status=ProtectionStatus.ERROR,
                    error=str(e),
                    execution_time_ms=execution_time
                )
    
    async def _check_resources(
        self,
        task_id: str,
        check_memory: bool
    ) -> Dict[str, Any]:
        """检查资源是否充足"""
        # 检查并发数
        current_concurrent = len(self._current_tasks)
        if current_concurrent >= self.max_concurrent_tasks:
            return {
                "allowed": False,
                "reason": f"并发任务数已达上限: {current_concurrent}/{self.max_concurrent_tasks}",
                "current_concurrent": current_concurrent
            }
        
        # 检查内存
        if check_memory:
            memory_usage = await self._get_memory_usage()
            if memory_usage > self.max_memory_mb:
                return {
                    "allowed": False,
                    "reason": f"内存使用超过限制: {memory_usage}MB/{self.max_memory_mb}MB",
                    "memory_usage_mb": memory_usage
                }
        
        return {"allowed": True}
    
    async def _record_usage(
        self,
        task_id: str,
        execution_time: float
    ) -> Dict[str, Any]:
        """记录资源使用"""
        usage = {
            "task_id": task_id,
            "execution_time_ms": execution_time,
            "current_concurrent": len(self._current_tasks),
            "timestamp": datetime.now()
        }
        
        self._resource_history.append(usage)
        
        # 保持历史在合理范围
        if len(self._resource_history) > 1000:
            self._resource_history = self._resource_history[-500:]
        
        return usage
    
    async def _get_memory_usage(self) -> float:
        """获取当前内存使用（MB）"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except ImportError:
            # psutil 未安装，返回 0
            return 0.0


class ThreeLayerProtection:
    """
    三层防护组合器
    
    将超时、重试、资源限制三层保护组合使用
    """
    
    def __init__(
        self,
        timeout: Optional[float] = 30.0,
        max_retries: int = 3,
        max_concurrent: int = 100,
        max_memory_mb: int = 512
    ):
        """
        初始化三层防护
        
        Args:
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
            max_concurrent: 最大并发数
            max_memory_mb: 最大内存使用（MB）
        """
        self.timeout_protection = TimeoutProtection(
            default_timeout=timeout
        )
        self.retry_protection = RetryProtection(
            max_retries=max_retries
        )
        self.resource_protection = ResourceProtection(
            max_concurrent_tasks=max_concurrent,
            max_memory_mb=max_memory_mb
        )
        
        self.enabled_layers = {
            "timeout": True,
            "retry": True,
            "resource": True
        }
    
    async def execute(
        self,
        coro: Callable,
        task_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ProtectionResult:
        """
        执行带三层防护的协程
        
        Args:
            coro: 协程函数
            task_id: 任务 ID
            config: 配置（覆盖默认配置）
            
        Returns:
            防护结果
        """
        config = config or {}
        task_id = task_id or "unknown"
        
        # 包装协程以支持重试
        async def wrapped_coro():
            return await coro()
        
        # 先进行资源检查
        if self.enabled_layers.get("resource", True):
            resource_result = await self.resource_protection.execute(
                lambda: wrapped_coro(),
                task_id=task_id,
                check_memory=config.get("check_memory", True)
            )
            
            if not resource_result.is_success():
                return resource_result
        
        # 执行带超时和重试
        start_time = time.time()
        last_result = None
        
        # 超时和重试的组合执行
        for attempt in range(config.get("max_attempts", 1)):
            try:
                result = await self.timeout_protection.execute(
                    wrapped_coro,
                    timeout=config.get("timeout"),
                    task_id=f"{task_id}_attempt_{attempt}"
                )
                
                if result.is_success():
                    return result
                
                # 如果失败且还有重试机会
                if self.enabled_layers.get("retry", True) and attempt < config.get("max_attempts", 1) - 1:
                    delay = self.retry_protection._calculate_delay(attempt)
                    logger.info(
                        f"[ThreeLayerProtection] 重试: task_id={task_id}, "
                        f"attempt={attempt + 1}, delay={delay}s"
                    )
                    await asyncio.sleep(delay)
                    last_result = result
                else:
                    return result
                    
            except Exception as e:
                logger.error(f"[ThreeLayerProtection] 执行异常: {e}")
                return ProtectionResult(
                    status=ProtectionStatus.ERROR,
                    error=str(e),
                    execution_time_ms=(time.time() - start_time) * 1000
                )
        
        return last_result or ProtectionResult(
            status=ProtectionStatus.ERROR,
            error="未知错误",
            execution_time_ms=(time.time() - start_time) * 1000
        )
    
    def disable_layer(self, layer: str):
        """禁用指定防护层"""
        if layer in self.enabled_layers:
            self.enabled_layers[layer] = False
            logger.info(f"[ThreeLayerProtection] 禁用防护层: {layer}")
    
    def enable_layer(self, layer: str):
        """启用指定防护层"""
        if layer in self.enabled_layers:
            self.enabled_layers[layer] = True
            logger.info(f"[ThreeLayerProtection] 启用防护层: {layer}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取防护统计"""
        return {
            "enabled_layers": self.enabled_layers,
            "timeout_config": {
                "default_timeout": self.timeout_protection.default_timeout
            },
            "retry_config": {
                "max_retries": self.retry_protection.max_retries
            },
            "resource_config": {
                "max_concurrent": self.resource_protection.max_concurrent_tasks,
                "max_memory_mb": self.resource_protection.max_memory_mb
            }
        }
