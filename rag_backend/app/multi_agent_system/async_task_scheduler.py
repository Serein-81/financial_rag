"""
异步任务调度器 (Async Task Scheduler)
基于 asyncio.gather 的并行任务调度系统
支持任务分组、超时控制、熔断器模式、优先级调度
"""

import asyncio
import uuid
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from functools import wraps

logger = logging.getLogger(__name__)


class TaskGroup(str, Enum):
    """任务分组"""
    CRITICAL = "critical"          # 关键任务（同步等待结果）
    NORMAL = "normal"              # 普通任务（可并行）
    BACKGROUND = "background"      # 后台任务（不阻塞主流程）
    BATCH = "batch"                # 批处理任务


class TaskState(str, Enum):
    """任务执行状态"""
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class CircuitState(str, Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态


@dataclass
class TaskResult:
    """任务执行结果"""
    task_id: str
    state: TaskState
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_success(self) -> bool:
        """是否成功"""
        return self.state == TaskState.COMPLETED
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "state": self.state.value if isinstance(self.state, TaskState) else self.state,
            "result": self.result,
            "error": self.error,
            "execution_time": self.execution_time,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata
        }


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5       # 失败次数阈值
    success_threshold: int = 2        # 恢复需要的成功次数
    timeout: float = 60.0             # 熔断持续时间（秒）
    half_open_max_calls: int = 3      # 半开状态最大并发调用数


class CircuitBreaker:
    """
    熔断器
    
    防止故障级联传播，保护系统稳定性
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> TaskResult:
        """
        通过熔断器执行函数
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            TaskResult: 执行结果
        """
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    logger.info(f"🔄 [CircuitBreaker:{self.name}] 切换到半开状态")
                else:
                    return TaskResult(
                        task_id=str(uuid.uuid4()),
                        state=TaskState.FAILED,
                        error=f"Circuit breaker OPEN for {self.name}"
                    )
            
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.config.half_open_max_calls:
                    return TaskResult(
                        task_id=str(uuid.uuid4()),
                        state=TaskState.FAILED,
                        error=f"Circuit breaker HALF_OPEN max calls reached for {self.name}"
                    )
                self.half_open_calls += 1
        
        task_id = str(uuid.uuid4())
        started_at = datetime.now()
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await self._on_success()
            
            return TaskResult(
                task_id=task_id,
                state=TaskState.COMPLETED,
                result=result,
                started_at=started_at,
                completed_at=datetime.now(),
                execution_time=(datetime.now() - started_at).total_seconds()
            )
            
        except Exception as e:
            await self._on_failure()
            
            return TaskResult(
                task_id=task_id,
                state=TaskState.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.now(),
                execution_time=(datetime.now() - started_at).total_seconds()
            )
    
    def _should_attempt_reset(self) -> bool:
        """是否应该尝试恢复"""
        if not self.last_failure_time:
            return True
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.config.timeout
    
    async def _on_success(self) -> None:
        """记录成功"""
        async with self._lock:
            self.failure_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.success_count = 0
                    logger.info(f"✅ [CircuitBreaker:{self.name}] 恢复为关闭状态")
    
    async def _on_failure(self) -> None:
        """记录失败"""
        async with self._lock:
            self.failure_count += 1
            self.success_count = 0
            self.last_failure_time = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(f"⚠️ [CircuitBreaker:{self.name}] 切换到开启状态")
            elif self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(f"⚠️ [CircuitBreaker:{self.name}] 触发熔断，失败次数: {self.failure_count}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取熔断器状态"""
        return {
            "name": self.name,
            "state": self.state.value if isinstance(self.state, CircuitState) else self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


@dataclass
class TaskSpec:
    """任务规格"""
    task_id: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    group: TaskGroup = TaskGroup.NORMAL
    priority: int = 0  # 数字越小优先级越高
    timeout: float = 60.0
    retry_count: int = 0
    max_retries: int = 3
    use_circuit_breaker: bool = False
    circuit_breaker_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "group": self.group.value if isinstance(self.group, TaskGroup) else self.group,
            "priority": self.priority,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "use_circuit_breaker": self.use_circuit_breaker,
            "circuit_breaker_name": self.circuit_breaker_name,
            "metadata": self.metadata
        }


class AsyncTaskScheduler:
    """
    异步任务调度器
    
    核心功能：
    1. 基于 asyncio.gather 的并行任务执行
    2. 任务分组和优先级调度
    3. 超时控制和取消机制
    4. 熔断器模式保护
    5. 任务重试策略
    6. 执行进度追踪
    
    使用示例：
    ```python
    scheduler = AsyncTaskScheduler()
    
    # 并行执行多个任务
    results = await scheduler.execute_parallel([
        TaskSpec(task_id="1", func=agent1.run, kwargs={"query": "..."}),
        TaskSpec(task_id="2", func=agent2.run, kwargs={"query": "..."}),
        TaskSpec(task_id="3", func=agent3.run, kwargs={"query": "..."}),
    ])
    ```
    """
    
    def __init__(self, max_concurrent: int = 10):
        """
        初始化调度器
        
        Args:
            max_concurrent: 最大并发任务数
        """
        self.max_concurrent = max_concurrent
        self._tasks: Dict[str, asyncio.Task] = {}
        self._task_specs: Dict[str, TaskSpec] = {}
        self._results: Dict[str, TaskResult] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._cancel_events: Dict[str, asyncio.Event] = {}
        self._progress_callbacks: List[Callable] = []
        self._lock = asyncio.Lock()
        
        logger.info(f"⚡ [AsyncTaskScheduler] 初始化完成，最大并发: {max_concurrent}")
    
    def register_circuit_breaker(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        注册熔断器
        
        Args:
            name: 熔断器名称
            config: 熔断器配置
            
        Returns:
            CircuitBreaker: 熔断器实例
        """
        breaker = CircuitBreaker(name, config)
        self._circuit_breakers[name] = breaker
        logger.info(f"🔧 [AsyncTaskScheduler] 注册熔断器: {name}")
        return breaker
    
    def on_progress(self, callback: Callable) -> None:
        """注册进度回调"""
        self._progress_callbacks.append(callback)
    
    async def _execute_single_task(
        self,
        spec: TaskSpec,
        progress_callback: Optional[Callable] = None
    ) -> TaskResult:
        """
        执行单个任务
        
        Args:
            spec: 任务规格
            progress_callback: 进度回调
            
        Returns:
            TaskResult: 任务结果
        """
        task_id = spec.task_id
        started_at = datetime.now()
        
        await self._emit_progress(task_id, TaskState.RUNNING)
        
        async def run_with_semaphore():
            async with self._semaphore:
                if asyncio.iscoroutinefunction(spec.func):
                    return await asyncio.wait_for(
                        spec.func(*spec.args, **spec.kwargs),
                        timeout=spec.timeout
                    )
                else:
                    return spec.func(*spec.args, **spec.kwargs)
        
        try:
            if spec.use_circuit_breaker and spec.circuit_breaker_name:
                breaker = self._circuit_breakers.get(spec.circuit_breaker_name)
                if breaker:
                    result = await breaker.call(run_with_semaphore)
                else:
                    result = await run_with_semaphore()
            else:
                result = await run_with_semaphore()
            
            completed_at = datetime.now()
            task_result = TaskResult(
                task_id=task_id,
                state=TaskState.COMPLETED,
                result=result,
                started_at=started_at,
                completed_at=completed_at,
                execution_time=(completed_at - started_at).total_seconds(),
                metadata=spec.metadata
            )
            
            await self._emit_progress(task_id, TaskState.COMPLETED, task_result)
            
            return task_result
            
        except asyncio.TimeoutError:
            completed_at = datetime.now()
            task_result = TaskResult(
                task_id=task_id,
                state=TaskState.TIMEOUT,
                error=f"Task timeout after {spec.timeout}s",
                started_at=started_at,
                completed_at=completed_at,
                execution_time=(completed_at - started_at).total_seconds(),
                metadata=spec.metadata
            )
            
            await self._emit_progress(task_id, TaskState.TIMEOUT, task_result)
            
            if spec.retry_count < spec.max_retries:
                spec.retry_count += 1
                logger.warning(f"🔄 [AsyncTaskScheduler] 任务 {task_id} 超时，执行第 {spec.retry_count} 次重试")
                return await self._execute_single_task(spec, progress_callback)
            
            return task_result
            
        except asyncio.CancelledError:
            completed_at = datetime.now()
            task_result = TaskResult(
                task_id=task_id,
                state=TaskState.CANCELLED,
                error="Task cancelled",
                started_at=started_at,
                completed_at=completed_at,
                execution_time=(completed_at - started_at).total_seconds(),
                metadata=spec.metadata
            )
            
            await self._emit_progress(task_id, TaskState.CANCELLED, task_result)
            return task_result
            
        except Exception as e:
            completed_at = datetime.now()
            task_result = TaskResult(
                task_id=task_id,
                state=TaskState.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=completed_at,
                execution_time=(completed_at - started_at).total_seconds(),
                metadata=spec.metadata
            )
            
            await self._emit_progress(task_id, TaskState.FAILED, task_result)
            
            if spec.retry_count < spec.max_retries:
                spec.retry_count += 1
                logger.warning(f"🔄 [AsyncTaskScheduler] 任务 {task_id} 失败，执行第 {spec.retry_count} 次重试")
                return await self._execute_single_task(spec, progress_callback)
            
            return task_result
    
    async def _emit_progress(
        self,
        task_id: str,
        state: TaskState,
        result: Optional[TaskResult] = None
    ) -> None:
        """发送进度更新"""
        for callback in self._progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task_id, state, result)
                else:
                    callback(task_id, state, result)
            except Exception as e:
                logger.error(f"❌ [AsyncTaskScheduler] 进度回调异常: {e}")
    
    async def execute_parallel(
        self,
        specs: List[TaskSpec],
        return_exceptions: bool = False,
        timeout: Optional[float] = None
    ) -> Dict[str, TaskResult]:
        """
        并行执行多个任务
        
        使用 asyncio.gather 实现真正的并行执行
        
        Args:
            specs: 任务规格列表
            return_exceptions: 是否在结果中返回异常
            timeout: 全局超时时间
            
        Returns:
            Dict[str, TaskResult]: task_id -> TaskResult
        """
        if not specs:
            return {}
        
        sorted_specs = sorted(specs, key=lambda s: (s.group.value, s.priority))
        
        async with self._lock:
            self._task_specs.update({spec.task_id: spec for spec in specs})
        
        logger.info(f"🚀 [AsyncTaskScheduler] 开始并行执行 {len(specs)} 个任务")
        
        try:
            if timeout:
                results = await asyncio.wait_for(
                    asyncio.gather(
                        *[self._execute_single_task(spec) for spec in sorted_specs],
                        return_exceptions=return_exceptions
                    ),
                    timeout=timeout
                )
            else:
                results = await asyncio.gather(
                    *[self._execute_single_task(spec) for spec in sorted_specs],
                    return_exceptions=return_exceptions
                )
            
            result_map = {}
            for i, spec in enumerate(sorted_specs):
                result = results[i]
                
                if isinstance(result, Exception) and not return_exceptions:
                    result = TaskResult(
                        task_id=spec.task_id,
                        state=TaskState.FAILED,
                        error=str(result)
                    )
                
                if isinstance(result, TaskResult):
                    self._results[spec.task_id] = result
                    result_map[spec.task_id] = result
            
            success_count = sum(1 for r in result_map.values() if r.is_success())
            logger.info(f"✅ [AsyncTaskScheduler] 并行任务完成: {success_count}/{len(specs)} 成功")
            
            return result_map
            
        except asyncio.TimeoutError:
            logger.error(f"⏰ [AsyncTaskScheduler] 全局超时: {timeout}s")
            await self.cancel_all()
            
            return self._results.copy()
    
    async def execute_group(
        self,
        specs: List[TaskSpec],
        group: TaskGroup,
        timeout: Optional[float] = None
    ) -> Dict[str, TaskResult]:
        """
        执行指定分组的任务
        
        Args:
            specs: 任务规格列表
            group: 任务分组
            timeout: 超时时间
            
        Returns:
            Dict[str, TaskResult]: task_id -> TaskResult
        """
        group_specs = [s for s in specs if s.group == group]
        return await self.execute_parallel(group_specs, timeout=timeout)
    
    async def execute_critical_first(
        self,
        specs: List[TaskSpec],
        timeout: Optional[float] = None
    ) -> Dict[str, TaskResult]:
        """
        关键任务优先执行
        
        CRITICAL 组任务先执行，其他组任务并行执行
        
        Args:
            specs: 任务规格列表
            timeout: 全局超时时间
            
        Returns:
            Dict[str, TaskResult]: task_id -> TaskResult
        """
        critical_specs = [s for s in specs if s.group == TaskGroup.CRITICAL]
        other_specs = [s for s in specs if s.group != TaskGroup.CRITICAL]
        
        results = {}
        
        if critical_specs:
            critical_results = await self.execute_parallel(critical_specs, timeout=timeout)
            results.update(critical_results)
        
        if other_specs:
            other_results = await self.execute_parallel(other_specs, timeout=timeout)
            results.update(other_results)
        
        return results
    
    async def execute_with_dependencies(
        self,
        specs: List[TaskSpec],
        dependency_graph: Dict[str, List[str]],
        timeout: Optional[float] = None
    ) -> Dict[str, TaskResult]:
        """
        按依赖关系执行任务
        
        Args:
            specs: 任务规格列表
            dependency_graph: 依赖图 {task_id: [depends_on_ids]}
            timeout: 全局超时时间
            
        Returns:
            Dict[str, TaskResult]: task_id -> TaskResult
        """
        spec_map = {spec.task_id: spec for spec in specs}
        results = {}
        completed = set()
        pending = set(spec_map.keys())
        
        while pending:
            ready_tasks = [
                task_id for task_id in pending
                if all(dep in completed for dep in dependency_graph.get(task_id, []))
            ]
            
            if not ready_tasks:
                remaining = [spec_map[tid] for tid in pending]
                remaining_results = await self.execute_parallel(remaining, timeout=timeout)
                results.update(remaining_results)
                break
            
            ready_specs = [spec_map[tid] for tid in ready_tasks]
            batch_results = await self.execute_parallel(ready_specs, timeout=timeout)
            
            for task_id, result in batch_results.items():
                results[task_id] = result
                completed.add(task_id)
                pending.discard(task_id)
                
                if not result.is_success():
                    for dependent_id in pending:
                        if task_id in dependency_graph.get(dependent_id, []):
                            logger.warning(f"⚠️ [AsyncTaskScheduler] 任务 {task_id} 失败，依赖它的 {dependent_id} 可能受影响")
        
        return results
    
    async def submit_task(
        self,
        spec: TaskSpec
    ) -> asyncio.Task:
        """
        提交单个任务（不等待结果）
        
        Args:
            spec: 任务规格
            
        Returns:
            asyncio.Task: asyncio 任务对象
        """
        async with self._lock:
            self._task_specs[spec.task_id] = spec
            self._cancel_events[spec.task_id] = asyncio.Event()
        
        task = asyncio.create_task(self._execute_single_task(spec))
        self._tasks[spec.task_id] = task
        
        logger.debug(f"📤 [AsyncTaskScheduler] 提交任务: {spec.task_id}")
        
        return task
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消指定任务"""
        async with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.cancel()
                
                if task_id in self._cancel_events:
                    self._cancel_events[task_id].set()
                
                logger.info(f"🛑 [AsyncTaskScheduler] 取消任务: {task_id}")
                return True
            
            return False
    
    async def cancel_all(self) -> None:
        """取消所有任务"""
        async with self._lock:
            for task_id, task in self._tasks.items():
                task.cancel()
                
                if task_id in self._cancel_events:
                    self._cancel_events[task_id].set()
            
            logger.info("🛑 [AsyncTaskScheduler] 取消所有任务")
    
    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """获取任务结果"""
        async with self._lock:
            return self._results.get(task_id)
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取调度器统计信息"""
        async with self._lock:
            total_tasks = len(self._task_specs)
            completed_tasks = sum(1 for r in self._results.values() if r.state == TaskState.COMPLETED)
            failed_tasks = sum(1 for r in self._results.values() if r.state == TaskState.FAILED)
            running_tasks = sum(1 for t in self._tasks.values() if not t.done())
            
            total_execution_time = sum(r.execution_time for r in self._results.values())
            avg_execution_time = total_execution_time / len(self._results) if self._results else 0
            
            return {
                "max_concurrent": self.max_concurrent,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "running_tasks": running_tasks,
                "pending_tasks": total_tasks - len(self._results) - running_tasks,
                "avg_execution_time": round(avg_execution_time, 3),
                "circuit_breakers": {
                    name: breaker.get_stats()
                    for name, breaker in self._circuit_breakers.items()
                }
            }
    
    async def wait_all(
        self,
        timeout: Optional[float] = None
    ) -> Dict[str, TaskResult]:
        """
        等待所有任务完成
        
        Args:
            timeout: 超时时间
            
        Returns:
            Dict[str, TaskResult]: task_id -> TaskResult
        """
        if not self._tasks:
            return {}
        
        try:
            if timeout:
                await asyncio.wait(self._tasks.values(), timeout=timeout)
            else:
                await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        except Exception as e:
            logger.error(f"❌ [AsyncTaskScheduler] 等待任务异常: {e}")
        
        return self._results.copy()


class RetryPolicy:
    """
    重试策略
    
    支持指数退避、抖动等策略
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """
        获取重试延迟
        
        Args:
            attempt: 当前重试次数
            
        Returns:
            float: 延迟时间（秒）
        """
        delay = min(self.base_delay * (self.exponential_base ** attempt), self.max_delay)
        
        if self.jitter:
            import random
            delay *= (0.5 + random.random())
        
        return delay
    
    async def execute(
        self,
        func: Callable,
        *args,
        on_retry: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        带重试执行函数
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            on_retry: 重试回调
            **kwargs: 关键字参数
            
        Returns:
            函数执行结果
            
        Raises:
            最后一次执行的异常
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = self.get_delay(attempt)
                    logger.warning(f"🔄 [RetryPolicy] 第 {attempt + 1} 次重试，延迟 {delay:.2f}s: {e}")
                    
                    if on_retry:
                        on_retry(attempt, e, delay)
                    
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ [RetryPolicy] 超过最大重试次数 {self.max_retries}")
        
        raise last_exception


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    exponential_base: float = 2.0,
    jitter: bool = True
):
    """
    重试装饰器
    
    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟
        exponential_base: 指数基数
        jitter: 是否添加抖动
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            policy = RetryPolicy(
                max_retries=max_retries,
                base_delay=base_delay,
                exponential_base=exponential_base,
                jitter=jitter
            )
            return await policy.execute(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        import time
                        import random
                        delay = min(base_delay * (exponential_base ** attempt), 60)
                        if jitter:
                            delay *= (0.5 + random.random())
                        time.sleep(delay)
            
            raise last_exception
        
        if asyncio.iscoroutinefunction(func):
            return wrapper
        return sync_wrapper
    
    return decorator


def with_circuit_breaker(breaker_name: str, config: Optional[CircuitBreakerConfig] = None):
    """
    熔断器装饰器
    
    Args:
        breaker_name: 熔断器名称
        config: 熔断器配置
    """
    def decorator(func: Callable) -> Callable:
        breaker = CircuitBreaker(breaker_name, config)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        
        return wrapper
    
    return decorator
