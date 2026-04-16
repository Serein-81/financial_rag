"""
任务调度器

提供任务调度和管理功能

功能：
1. 任务优先级调度
2. 任务状态跟踪
3. 任务依赖管理
4. 任务超时管理
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import heapq

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class TaskConfig:
    """任务配置"""
    priority: int = 5  # 优先级（1-10，1最高）
    timeout: float = 30.0  # 超时时间（秒）
    max_retries: int = 3  # 最大重试次数
    retry_delay: float = 1.0  # 重试延迟（秒）
    dependencies: List[str] = field(default_factory=list)  # 依赖的任务 ID


@dataclass
class TaskMetadata:
    """任务元数据"""
    task_id: str
    task_type: str
    request_id: str
    tenant_id: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    config: TaskConfig = field(default_factory=TaskConfig)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    attempts: int = 0
    priority: int = 5
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "config": {
                "priority": self.config.priority,
                "timeout": self.config.timeout,
                "max_retries": self.config.max_retries,
                "retry_delay": self.config.retry_delay,
                "dependencies": self.config.dependencies
            },
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "result": self.result,
            "error": self.error,
            "attempts": self.attempts,
            "priority": self.priority
        }


class Task:
    """任务对象"""
    
    def __init__(
        self,
        task_id: str,
        task_type: str,
        coro_func: Callable,
        request_id: str,
        tenant_id: str,
        user_id: str,
        config: Optional[TaskConfig] = None,
        args: tuple = (),
        kwargs: dict = None
    ):
        """
        初始化任务
        
        Args:
            task_id: 任务 ID
            task_type: 任务类型
            coro_func: 协程函数
            request_id: 请求 ID
            tenant_id: 租户 ID
            user_id: 用户 ID
            config: 任务配置
            args: 位置参数
            kwargs: 关键字参数
        """
        self.task_id = task_id
        self.task_type = task_type
        self.coro_func = coro_func
        self.request_id = request_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.config = config or TaskConfig()
        self.args = args
        self.kwargs = kwargs or {}
        
        self.metadata = TaskMetadata(
            task_id=task_id,
            task_type=task_type,
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            config=self.config,
            priority=self.config.priority
        )
        
        # 优先级队列中用于比较的元素
        self._heap_element: tuple = ()
    
    def __lt__(self, other: "Task") -> bool:
        """优先级比较（数字越小优先级越高）"""
        return self.config.priority < other.config.priority
    
    def __repr__(self) -> str:
        return f"Task(id={self.task_id}, type={self.task_type}, priority={self.config.priority})"


class TaskScheduler:
    """
    任务调度器
    
    提供基于优先级的任务调度和管理
    
    功能：
    1. 优先级队列调度
    2. 任务状态跟踪
    3. 依赖管理
    4. 超时管理
    5. 任务取消
    
    使用示例：
    ```python
    scheduler = TaskScheduler(max_workers=10)
    
    # 添加任务
    task_id = await scheduler.add_task(
        task_type="retrieval",
        coro_func=retrieval_task,
        request_id="req-001",
        tenant_id="tenant-001",
        user_id="user-001"
    )
    
    # 获取任务状态
    status = scheduler.get_task_status(task_id)
    
    # 取消任务
    await scheduler.cancel_task(task_id)
    
    # 获取统计
    stats = scheduler.get_stats()
    ```
    """
    
    def __init__(
        self,
        max_workers: int = 10,
        default_timeout: float = 30.0,
        enable_metrics: bool = True
    ):
        """
        初始化调度器
        
        Args:
            max_workers: 最大并发工作数
            default_timeout: 默认超时时间
            enable_metrics: 是否启用指标收集
        """
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self.enable_metrics = enable_metrics
        
        # 任务存储
        self._tasks: Dict[str, Task] = {}
        self._task_queue: List[Task] = []
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._completed_tasks: Dict[str, TaskMetadata] = {}
        
        # 依赖图
        self._dependencies: Dict[str, List[str]] = defaultdict(list)
        self._dependents: Dict[str, List[str]] = defaultdict(list)
        
        # 锁
        self._lock = asyncio.Lock()
        
        # 信号量（控制并发）
        self._semaphore = asyncio.Semaphore(max_workers)
        
        # 运行标志
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        
        # 指标
        self._metrics = {
            "total_tasks_added": 0,
            "total_tasks_completed": 0,
            "total_tasks_failed": 0,
            "total_tasks_cancelled": 0,
            "total_tasks_timeout": 0,
            "peak_concurrent_tasks": 0,
            "current_concurrent_tasks": 0
        }
        
        logger.info(
            f"[TaskScheduler] 初始化: max_workers={max_workers}, "
            f"default_timeout={default_timeout}s"
        )
    
    async def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("[TaskScheduler] 调度器已在运行")
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("[TaskScheduler] 调度器已启动")
    
    async def stop(self):
        """停止调度器"""
        if not self._running:
            logger.warning("[TaskScheduler] 调度器未运行")
            return
        
        self._running = False
        
        # 取消调度任务
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        # 取消所有运行中的任务
        for task in self._running_tasks.values():
            task.cancel()
        
        if self._running_tasks:
            await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)
        
        logger.info("[TaskScheduler] 调度器已停止")
    
    async def add_task(
        self,
        task_type: str,
        coro_func: Callable,
        request_id: str,
        tenant_id: str,
        user_id: str,
        config: Optional[TaskConfig] = None,
        args: tuple = (),
        kwargs: dict = None,
        dependencies: Optional[List[str]] = None
    ) -> str:
        """
        添加任务
        
        Args:
            task_type: 任务类型
            coro_func: 协程函数
            request_id: 请求 ID
            tenant_id: 租户 ID
            user_id: 用户 ID
            config: 任务配置
            args: 位置参数
            kwargs: 关键字参数
            dependencies: 依赖的任务 ID
            
        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())
        
        config = config or TaskConfig()
        if config.timeout <= 0:
            config.timeout = self.default_timeout
        
        task = Task(
            task_id=task_id,
            task_type=task_type,
            coro_func=coro_func,
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            config=config,
            args=args,
            kwargs=kwargs
        )
        
        async with self._lock:
            self._tasks[task_id] = task
            self._completed_tasks[task_id] = task.metadata
            
            # 添加到优先级队列
            heapq.heappush(self._task_queue, task)
            
            # 记录依赖
            if dependencies:
                for dep_id in dependencies:
                    self._dependencies[task_id].append(dep_id)
                    self._dependents[dep_id].append(task_id)
            
            self._metrics["total_tasks_added"] += 1
        
        logger.info(
            f"[TaskScheduler] 添加任务: task_id={task_id}, "
            f"type={task_type}, priority={config.priority}"
        )
        
        return task_id
    
    async def _scheduler_loop(self):
        """调度循环"""
        logger.info("[TaskScheduler] 调度循环开始")
        
        while self._running:
            try:
                # 等待队列中有任务
                if not self._task_queue:
                    await asyncio.sleep(0.1)
                    continue
                
                async with self._lock:
                    # 检查是否有可运行的任务
                    available_tasks = []
                    
                    while self._task_queue:
                        task = heapq.heappop(self._task_queue)
                        
                        # 检查依赖是否满足
                        if self._check_dependencies(task):
                            available_tasks.append(task)
                        else:
                            # 依赖未满足，放回队列
                            heapq.heappush(self._task_queue, task)
                            break
                    
                    # 启动可用任务
                    for task in available_tasks:
                        await self._start_task(task)
                
                await asyncio.sleep(0.01)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TaskScheduler] 调度循环异常: {e}")
                await asyncio.sleep(1)
        
        logger.info("[TaskScheduler] 调度循环结束")
    
    def _check_dependencies(self, task: Task) -> bool:
        """
        检查任务依赖是否满足
        
        Args:
            task: 任务对象
            
        Returns:
            是否满足
        """
        for dep_id in self._dependencies[task.task_id]:
            dep_meta = self._completed_tasks.get(dep_id)
            if not dep_meta:
                return False
            if dep_meta.status != TaskStatus.COMPLETED:
                return False
        
        return True
    
    async def _start_task(self, task: Task):
        """
        启动任务
        
        Args:
            task: 任务对象
        """
        # 获取信号量
        await self._semaphore.acquire()
        
        task.metadata.status = TaskStatus.RUNNING
        task.metadata.started_at = datetime.now()
        task.metadata.attempts += 1
        
        # 创建异步任务
        asyncio_task = asyncio.create_task(
            self._run_task(task)
        )
        
        self._running_tasks[task.task_id] = asyncio_task
        
        # 更新并发计数
        self._metrics["current_concurrent_tasks"] = len(self._running_tasks)
        self._metrics["peak_concurrent_tasks"] = max(
            self._metrics["peak_concurrent_tasks"],
            len(self._running_tasks)
        )
        
        logger.info(
            f"[TaskScheduler] 启动任务: task_id={task.task_id}, "
            f"attempt={task.metadata.attempts}"
        )
    
    async def _run_task(self, task: Task):
        """
        运行任务
        
        Args:
            task: 任务对象
        """
        try:
            # 带超时执行
            result = await asyncio.wait_for(
                task.coro_func(*task.args, **task.kwargs),
                timeout=task.config.timeout
            )
            
            # 任务成功
            task.metadata.status = TaskStatus.COMPLETED
            task.metadata.completed_at = datetime.now()
            task.metadata.result = result
            
            self._metrics["total_tasks_completed"] += 1
            
            logger.info(
                f"[TaskScheduler] 任务完成: task_id={task.task_id}, "
                f"duration={(task.metadata.completed_at - task.metadata.started_at).total_seconds():.2f}s"
            )
            
        except asyncio.TimeoutError:
            # 超时
            task.metadata.status = TaskStatus.TIMEOUT
            task.metadata.completed_at = datetime.now()
            task.metadata.error = f"任务执行超过 {task.config.timeout} 秒"
            
            self._metrics["total_tasks_timeout"] += 1
            
            logger.warning(
                f"[TaskScheduler] 任务超时: task_id={task.task_id}, "
                f"timeout={task.config.timeout}s"
            )
            
            # 检查是否需要重试
            await self._handle_task_failure(task)
            
        except asyncio.CancelledError:
            # 被取消
            task.metadata.status = TaskStatus.CANCELLED
            task.metadata.completed_at = datetime.now()
            
            self._metrics["total_tasks_cancelled"] += 1
            
            logger.info(f"[TaskScheduler] 任务取消: task_id={task.task_id}")
            
        except Exception as e:
            # 其他错误
            task.metadata.error = str(e)
            
            logger.error(
                f"[TaskScheduler] 任务失败: task_id={task.task_id}, "
                f"error={e}"
            )
            
            await self._handle_task_failure(task)
            
        finally:
            # 释放信号量
            self._semaphore.release()
            
            # 从运行中移除
            if task.task_id in self._running_tasks:
                del self._running_tasks[task.task_id]
            
            self._metrics["current_concurrent_tasks"] = len(self._running_tasks)
    
    async def _handle_task_failure(self, task: Task):
        """
        处理任务失败
        
        Args:
            task: 任务对象
        """
        if task.metadata.attempts < task.config.max_retries:
            # 还有重试机会
            task.metadata.status = TaskStatus.PENDING
            
            # 延迟后重试
            await asyncio.sleep(task.config.retry_delay)
            
            # 重新加入队列
            heapq.heappush(self._task_queue, task)
            
            logger.info(
                f"[TaskScheduler] 任务重试: task_id={task.task_id}, "
                f"attempt={task.metadata.attempts + 1}/{task.config.max_retries}"
            )
        else:
            # 重试次数用尽
            task.metadata.status = TaskStatus.FAILED
            task.metadata.completed_at = datetime.now()
            
            self._metrics["total_tasks_failed"] += 1
            
            logger.error(
                f"[TaskScheduler] 任务重试失败: task_id={task.task_id}, "
                f"attempts={task.metadata.attempts}"
            )
    
    def get_task_status(self, task_id: str) -> Optional[TaskMetadata]:
        """
        获取任务状态
        
        Args:
            task_id: 任务 ID
            
        Returns:
            任务元数据
        """
        return self._completed_tasks.get(task_id)
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            是否成功取消
        """
        async with self._lock:
            # 检查是否在队列中
            for i, task in enumerate(self._task_queue):
                if task.task_id == task_id:
                    self._task_queue.pop(i)
                    heapq.heapify(self._task_queue)
                    
                    task.metadata.status = TaskStatus.CANCELLED
                    task.metadata.completed_at = datetime.now()
                    
                    self._metrics["total_tasks_cancelled"] += 1
                    
                    logger.info(f"[TaskScheduler] 取消队列中任务: task_id={task_id}")
                    return True
            
            # 检查是否在运行中
            if task_id in self._running_tasks:
                self._running_tasks[task_id].cancel()
                logger.info(f"[TaskScheduler] 取消运行中任务: task_id={task_id}")
                return True
            
            return False
    
    def get_pending_count(self) -> int:
        """获取待处理任务数"""
        return len(self._task_queue)
    
    def get_running_count(self) -> int:
        """获取运行中任务数"""
        return len(self._running_tasks)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计字典
        """
        return {
            "scheduler": {
                "max_workers": self.max_workers,
                "default_timeout": self.default_timeout,
                "running": self._running
            },
            "tasks": {
                "pending": self.get_pending_count(),
                "running": self.get_running_count(),
                "total": len(self._tasks),
                "completed": self._metrics["total_tasks_completed"],
                "failed": self._metrics["total_tasks_failed"],
                "cancelled": self._metrics["total_tasks_cancelled"],
                "timeout": self._metrics["total_tasks_timeout"]
            },
            "concurrency": {
                "current": self._metrics["current_concurrent_tasks"],
                "peak": self._metrics["peak_concurrent_tasks"]
            },
            "metrics": self._metrics.copy()
        }
