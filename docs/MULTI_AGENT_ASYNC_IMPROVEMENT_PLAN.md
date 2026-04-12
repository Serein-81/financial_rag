# 多智能体系统异步并行架构改善方案

## 一、问题背景与目标

### 1.1 当前系统痛点

| 痛点 | 现状 | 影响 |
|------|------|------|
| **串行为主** | 多专家协作主要是顺序执行 | 响应延迟高，用户体验差 |
| **缺乏并行** | 没有异步并行触发机制 | 资源利用率低，处理效率差 |
| **群聊场景** | 没有静默监控和关键词拦截 | 无法支持企业群聊智能助手场景 |
| **结果整合** | 多结果合并较简单 | 输出质量不稳定，缺乏深度整合 |

### 1.2 改善目标

```
目标: 构建新一代异步并行多智能体协作平台

核心能力:
├── 🚀 异步广播模式: 并行触发多个 Agent
├── 📋 状态黑板: 全局任务上下文管理
├── 🔔 群聊智能: 关键词激活 + 静默监控
└── 🎯 自然整合: LLM 驱动的结果合成
```

---

## 二、核心组件设计

### 2.1 TaskBlackboard - 状态黑板系统

#### 2.1.1 设计理念

```
传统方式 vs 黑板模式:

传统方式:
Agent A ──→ Agent B ──→ Agent C ──→ 最终结果
   │          │           │
   └──────────┴───────────┴──→ 耦合严重，难以扩展

黑板模式:
┌─────────────────────────────────────────┐
│              TaskBlackboard             │
│  ┌─────────────────────────────────────┐ │
│  │  Global Context (全局上下文)        │ │
│  │  - session_id                       │ │
│  │  - user_id                          │ │
│  │  - original_query                   │ │
│  │  - intent_analysis                  │ │
│  └─────────────────────────────────────┘ │
│  ┌─────────────────────────────────────┐ │
│  │  SubTask Registry (子任务注册)      │ │
│  │  - task_id_1: {status, result}      │ │
│  │  - task_id_2: {status, result}      │ │
│  │  - task_id_3: {status, result}      │ │
│  └─────────────────────────────────────┘ │
│  ┌─────────────────────────────────────┐ │
│  │  Knowledge Cache (知识缓存)          │ │
│  │  - retrieved_docs                   │ │
│  │  - intermediate_findings            │ │
│  └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
     ↑          ↑          ↑
  Agent A   Agent B   Agent C (并行读取/写入)
```

#### 2.1.2 数据模型

```python
# app/multi_agent_system/blackboard/models.py

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"           # 等待中
    RUNNING = "running"            # 执行中
    COMPLETED = "completed"        # 已完成
    FAILED = "failed"              # 失败
    CANCELLED = "cancelled"        # 已取消
    TIMEOUT = "timeout"            # 超时


class TaskPriority(str, Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class SubTask(BaseModel):
    """子任务模型"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_type: str = Field(description="Agent 类型: finance/tax/legal/helper")
    task_type: str = Field(description="任务类型: analyze/calculate/check/search")
    description: str = Field(description="任务描述")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="输入数据")
    output_data: Optional[Dict[str, Any]] = Field(default=None, description="输出数据")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)
    dependencies: List[str] = Field(default_factory=list, description="依赖的子任务ID")
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = Field(default=0, description="重试次数")
    max_retries: int = Field(default=3, description="最大重试次数")
    timeout_seconds: float = Field(default=60.0)


class BlackboardContext(BaseModel):
    """黑板全局上下文"""
    session_id: str = Field(description="会话ID")
    user_id: str = Field(description="用户ID")
    tenant_id: str = Field(default="default", description="租户ID")
    original_query: str = Field(description="原始用户查询")
    language: str = Field(default="zh-CN", description="语言")
    
    # 意图分析结果
    intent_result: Optional[Dict[str, Any]] = None
    
    # 任务注册表
    subtasks: Dict[str, SubTask] = Field(default_factory=dict)
    
    # 知识缓存
    retrieved_documents: List[Dict[str, Any]] = Field(default_factory=list)
    intermediate_findings: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 执行控制
    parallel_enabled: bool = Field(default=True, description="是否启用并行")
    timeout_total: float = Field(default=120.0, description="总超时时间")
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BlackboardEvent(str, Enum):
    """黑板事件类型"""
    TASK_REGISTERED = "task_registered"       # 任务注册
    TASK_STARTED = "task_started"             # 任务开始
    TASK_COMPLETED = "task_completed"         # 任务完成
    TASK_FAILED = "task_failed"               # 任务失败
    CONTEXT_UPDATED = "context_updated"       # 上下文更新
    ALL_TASKS_COMPLETED = "all_tasks_completed" # 所有任务完成
    TIMEOUT_TRIGGERED = "timeout_triggered"   # 超时触发
```

#### 2.1.3 核心实现

```python
# app/multi_agent_system/blackboard/manager.py

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any, Set
from datetime import datetime
from collections import defaultdict

from .models import (
    BlackboardContext, 
    SubTask, 
    TaskStatus, 
    TaskPriority,
    BlackboardEvent
)

logger = logging.getLogger(__name__)


class TaskBlackboard:
    """
    任务黑板管理器
    
    职责:
    1. 管理全局上下文
    2. 注册和跟踪子任务
    3. 提供任务依赖管理
    4. 发布黑板事件
    5. 超时控制
    """
    
    def __init__(self, context: BlackboardContext):
        """
        初始化黑板
        
        Args:
            context: 初始上下文
        """
        self.context = context
        self._lock = asyncio.Lock()
        self._subscribers: Dict[BlackboardEvent, List[Callable]] = defaultdict(list)
        self._task_completion_futures: Dict[str, asyncio.Future] = {}
        
        logger.info(f"📋 [Blackboard] 初始化完成, session_id={context.session_id}")
    
    # ==================== 任务管理 ====================
    
    async def register_task(self, task: SubTask) -> str:
        """
        注册子任务
        
        Args:
            task: 子任务对象
            
        Returns:
            task_id: 任务ID
        """
        async with self._lock:
            self.context.subtasks[task.task_id] = task
            self.context.updated_at = datetime.now()
            
            # 创建完成 Future
            self._task_completion_futures[task.task_id] = asyncio.get_event_loop().create_future()
            
            await self._publish_event(BlackboardEvent.TASK_REGISTERED, {
                "task_id": task.task_id,
                "agent_type": task.agent_type,
                "dependencies": task.dependencies
            })
            
            logger.info(f"📋 [Blackboard] 注册任务: {task.task_id} -> {task.agent_type}")
            
            return task.task_id
    
    async def register_tasks(self, tasks: List[SubTask]) -> List[str]:
        """
        批量注册任务
        
        Args:
            tasks: 任务列表
            
        Returns:
            task_ids: 任务ID列表
        """
        task_ids = []
        for task in tasks:
            task_id = await self.register_task(task)
            task_ids.append(task_id)
        
        logger.info(f"📋 [Blackboard] 批量注册 {len(tasks)} 个任务")
        
        return task_ids
    
    async def update_task_status(
        self, 
        task_id: str, 
        status: TaskStatus,
        output_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            output_data: 输出数据
            error_message: 错误信息
        """
        async with self._lock:
            if task_id not in self.context.subtasks:
                raise ValueError(f"任务不存在: {task_id}")
            
            task = self.context.subtasks[task_id]
            old_status = task.status
            task.status = status
            
            if status == TaskStatus.RUNNING and task.started_at is None:
                task.started_at = datetime.now()
                await self._publish_event(BlackboardEvent.TASK_STARTED, {
                    "task_id": task_id
                })
            
            if status == TaskStatus.COMPLETED:
                task.completed_at = datetime.now()
                task.output_data = output_data
                self.context.intermediate_findings.append({
                    "task_id": task_id,
                    "agent_type": task.agent_type,
                    "output": output_data,
                    "timestamp": datetime.now().isoformat()
                })
                
                # 触发 Future
                if task_id in self._task_completion_futures:
                    self._task_completion_futures[task_id].set_result(output_data)
                
                await self._publish_event(BlackboardEvent.TASK_COMPLETED, {
                    "task_id": task_id,
                    "agent_type": task.agent_type
                })
                
                # 检查是否所有任务都完成
                await self._check_all_tasks_completed()
            
            elif status == TaskStatus.FAILED:
                task.completed_at = datetime.now()
                task.error_message = error_message
                
                # 触发 Future 异常
                if task_id in self._task_completion_futures:
                    self._task_completion_futures[task_id].set_exception(
                        Exception(error_message or "Task failed")
                    )
                
                await self._publish_event(BlackboardEvent.TASK_FAILED, {
                    "task_id": task_id,
                    "error": error_message
                })
            
            self.context.updated_at = datetime.now()
            
            logger.info(f"📋 [Blackboard] 任务状态更新: {task_id} {old_status} -> {status}")
    
    async def get_ready_tasks(self) -> List[SubTask]:
        """
        获取就绪的任务（依赖已全部完成）
        
        Returns:
            就绪任务列表
        """
        async with self._lock:
            ready_tasks = []
            
            for task_id, task in self.context.subtasks.items():
                if task.status != TaskStatus.PENDING:
                    continue
                
                # 检查依赖是否都已完成
                dependencies_met = all(
                    self.context.subtasks.get(dep_id, SubTask(task_id="")).status == TaskStatus.COMPLETED
                    for dep_id in task.dependencies
                )
                
                if dependencies_met:
                    ready_tasks.append(task)
            
            # 按优先级排序
            ready_tasks.sort(key=lambda t: t.priority.value, reverse=True)
            
            return ready_tasks
    
    async def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务输出数据
        """
        task = self.context.subtasks.get(task_id)
        if task:
            return task.output_data
        return None
    
    # ==================== 事件机制 ====================
    
    async def subscribe(self, event: BlackboardEvent, callback: Callable) -> None:
        """
        订阅黑板事件
        
        Args:
            event: 事件类型
            callback: 回调函数
        """
        self._subscribers[event].append(callback)
    
    async def _publish_event(self, event: BlackboardEvent, data: Dict[str, Any]) -> None:
        """
        发布事件
        
        Args:
            event: 事件类型
            data: 事件数据
        """
        for callback in self._subscribers.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event, data)
                else:
                    callback(event, data)
            except Exception as e:
                logger.error(f"❌ [Blackboard] 事件回调异常: {e}")
    
    # ==================== 超时控制 ====================
    
    async def _check_all_tasks_completed(self) -> None:
        """检查是否所有任务都完成"""
        all_completed = all(
            task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
            for task in self.context.subtasks.values()
        )
        
        if all_completed and self.context.subtasks:
            await self._publish_event(BlackboardEvent.ALL_TASKS_COMPLETED, {
                "completed_count": sum(
                    1 for t in self.context.subtasks.values() 
                    if t.status == TaskStatus.COMPLETED
                ),
                "failed_count": sum(
                    1 for t in self.context.subtasks.values() 
                    if t.status == TaskStatus.FAILED
                )
            })
    
    # ==================== 上下文查询 ====================
    
    def get_all_results(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有任务结果
        
        Returns:
            {task_id: output_data} 字典
        """
        return {
            task_id: task.output_data
            for task_id, task in self.context.subtasks.items()
            if task.status == TaskStatus.COMPLETED and task.output_data
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取执行摘要
        
        Returns:
            摘要信息
        """
        tasks = list(self.context.subtasks.values())
        
        return {
            "total_tasks": len(tasks),
            "pending": sum(1 for t in tasks if t.status == TaskStatus.PENDING),
            "running": sum(1 for t in tasks if t.status == TaskStatus.RUNNING),
            "completed": sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
            "duration_seconds": (
                max(t.completed_at for t in tasks if t.completed_at) - 
                min(t.created_at for t in tasks)
            ).total_seconds() if tasks else 0
        }
```

---

### 2.2 AsyncTaskScheduler - 异步任务调度器

#### 2.2.1 设计理念

```
AsyncTaskScheduler 核心逻辑:

┌─────────────────────────────────────────────────────────┐
│                    Task Queue (任务队列)                 │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Task A (priority=3) ───┐                             │ │
│  │ Task B (priority=2) ───┼──→ Ready Queue              │ │
│  │ Task C (priority=1) ───┘                             │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│              Dependency Graph (依赖图)                   │
│                                                         │
│    Task A ──────┬──────→ Task D                         │
│                 │                                       │
│    Task B ──────┼──────→ Task E                         │
│                 │                                       │
│    Task C ─────┴──────→ Task F                         │
│                                                         │
└─────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│           Async Execution Engine (异步执行引擎)          │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ Worker 1 │  │ Worker 2 │  │ Worker 3 │  ...          │
│  │ Agent A  │  │ Agent B  │  │ Agent C  │               │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘               │
│       │             │             │                     │
│       ▼             ▼             ▼                     │
│  ┌─────────────────────────────────────┐               │
│  │  asyncio.gather() - 并行等待所有完成  │               │
│  └─────────────────────────────────────┘               │
│                    │                                     │
│                    ▼                                     │
│  ┌─────────────────────────────────────┐               │
│  │  Result Aggregation (结果聚合)      │               │
│  └─────────────────────────────────────┘               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### 2.2.2 核心实现

```python
# app/multi_agent_system/scheduler/async_task_scheduler.py

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable, Set, Type
from datetime import datetime
from enum import Enum

from ..blackboard.models import SubTask, TaskStatus, TaskPriority, BlackboardContext
from ..blackboard.manager import TaskBlackboard

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """执行模式"""
    SEQUENTIAL = "sequential"     # 顺序执行
    PARALLEL = "parallel"         # 完全并行
    DAG = "dag"                   # 有向无环图 (支持依赖)
    PARALLEL_WITH_DEPENDENCIES = "parallel_with_dependencies"  # 带依赖的并行


class AgentExecutor:
    """Agent 执行器接口"""
    
    async def execute(self, task: SubTask, blackboard: TaskBlackboard) -> Dict[str, Any]:
        """
        执行任务
        
        Args:
            task: 任务对象
            blackboard: 黑板管理器
            
        Returns:
            执行结果
        """
        raise NotImplementedError


class AsyncTaskScheduler:
    """
    异步任务调度器
    
    核心功能:
    1. 支持多种执行模式 (串行/并行/DAG)
    2. 任务依赖管理
    3. 并发控制
    4. 超时管理
    5. 重试机制
    6. 结果聚合
    """
    
    def __init__(
        self,
        max_concurrency: int = 5,
        default_timeout: float = 60.0,
        enable_retry: bool = True,
        max_retries: int = 3
    ):
        """
        初始化调度器
        
        Args:
            max_concurrency: 最大并发数
            default_timeout: 默认超时时间
            enable_retry: 是否启用重试
            max_retries: 最大重试次数
        """
        self.max_concurrency = max_concurrency
        self.default_timeout = default_timeout
        self.enable_retry = enable_retry
        self.max_retries = max_retries
        
        self._executors: Dict[str, AgentExecutor] = {}
        self._semaphore = asyncio.Semaphore(max_concurrency)
        
        logger.info(f"🚀 [Scheduler] 初始化完成, max_concurrency={max_concurrency}")
    
    def register_executor(self, agent_type: str, executor: AgentExecutor) -> None:
        """
        注册 Agent 执行器
        
        Args:
            agent_type: Agent 类型标识
            executor: 执行器实例
        """
        self._executors[agent_type] = executor
        logger.info(f"🚀 [Scheduler] 注册执行器: {agent_type}")
    
    async def execute_parallel(
        self,
        blackboard: TaskBlackboard,
        task_ids: Optional[List[str]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        并行执行任务
        
        Args:
            blackboard: 黑板管理器
            task_ids: 指定任务ID列表, None 表示执行所有就绪任务
            timeout: 超时时间
            
        Returns:
            执行结果字典
        """
        timeout = timeout or self.default_timeout
        
        # 获取要执行的任务
        if task_ids:
            tasks_to_run = [
                blackboard.context.subtasks[tid]
                for tid in task_ids
                if tid in blackboard.context.subtasks
            ]
        else:
            tasks_to_run = await blackboard.get_ready_tasks()
        
        if not tasks_to_run:
            logger.warning("⚠️ [Scheduler] 没有可执行的任务")
            return {"status": "no_tasks", "results": {}}
        
        logger.info(f"🚀 [Scheduler] 准备并行执行 {len(tasks_to_run)} 个任务")
        
        # 创建执行任务
        execution_tasks = [
            self._execute_single_task(task, blackboard)
            for task in tasks_to_run
        ]
        
        try:
            # 使用 asyncio.gather 并行执行，带超时控制
            results = await asyncio.wait_for(
                asyncio.gather(*execution_tasks, return_exceptions=True),
                timeout=timeout
            )
            
            # 整理结果
            result_dict = {}
            for i, task in enumerate(tasks_to_run):
                result = results[i]
                if isinstance(result, Exception):
                    logger.error(f"❌ [Scheduler] 任务 {task.task_id} 执行异常: {result}")
                    result_dict[task.task_id] = {"error": str(result)}
                else:
                    result_dict[task.task_id] = result
            
            return {
                "status": "completed",
                "results": result_dict,
                "executed_count": len(tasks_to_run)
            }
            
        except asyncio.TimeoutError:
            logger.error(f"⏰ [Scheduler] 执行超时, timeout={timeout}s")
            return {
                "status": "timeout",
                "results": {},
                "executed_count": 0
            }
    
    async def execute_dag(
        self,
        blackboard: TaskBlackboard,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        DAG 模式执行（支持任务依赖）
        
        Args:
            blackboard: 黑板管理器
            timeout: 总超时时间
            
        Returns:
            执行结果字典
        """
        timeout = timeout or self.default_timeout * 3
        start_time = datetime.now()
        
        logger.info(f"🚀 [Scheduler] 启动 DAG 执行模式")
        
        all_results = {}
        completed_task_ids: Set[str] = set()
        
        while True:
            # 检查是否超时
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                logger.error(f"⏰ [Scheduler] DAG 执行超时")
                break
            
            # 获取就绪任务
            ready_tasks = await blackboard.get_ready_tasks()
            ready_tasks = [t for t in ready_tasks if t.task_id not in completed_task_ids]
            
            if not ready_tasks:
                # 检查是否所有任务都完成
                remaining = [
                    t for t in blackboard.context.subtasks.values()
                    if t.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
                    and t.task_id not in completed_task_ids
                ]
                
                if not remaining:
                    logger.info("✅ [Scheduler] DAG 执行完成")
                    break
                
                # 有任务但没有就绪的，可能死锁
                logger.warning(f"⚠️ [Scheduler] 可能有依赖死锁, remaining={len(remaining)}")
                break
            
            # 按层级分组（同一层可以并行）
            level_tasks = self._group_by_level(ready_tasks)
            
            for level, tasks in level_tasks.items():
                logger.info(f"🚀 [Scheduler] 执行层级 {level}, 任务数={len(tasks)}")
                
                # 并行执行同层任务
                execution_tasks = [
                    self._execute_single_task(task, blackboard)
                    for task in tasks
                ]
                
                try:
                    results = await asyncio.wait_for(
                        asyncio.gather(*execution_tasks, return_exceptions=True),
                        timeout=self.default_timeout
                    )
                    
                    for i, task in enumerate(tasks):
                        completed_task_ids.add(task.task_id)
                        result = results[i]
                        if isinstance(result, Exception):
                            logger.error(f"❌ [Scheduler] 任务 {task.task_id} 失败: {result}")
                            all_results[task.task_id] = {"error": str(result)}
                        else:
                            all_results[task.task_id] = result
                            
                except asyncio.TimeoutError:
                    logger.error(f"⏰ [Scheduler] 层级 {level} 执行超时")
                    for task in tasks:
                        await blackboard.update_task_status(
                            task.task_id, 
                            TaskStatus.TIMEOUT,
                            error_message="Level execution timeout"
                        )
        
        return {
            "status": "completed",
            "results": all_results,
            "total_duration": (datetime.now() - start_time).total_seconds()
        }
    
    async def _execute_single_task(
        self,
        task: SubTask,
        blackboard: TaskBlackboard
    ) -> Dict[str, Any]:
        """
        执行单个任务（带信号量和重试）
        
        Args:
            task: 任务对象
            blackboard: 黑板管理器
            
        Returns:
            执行结果
        """
        # 获取执行器
        executor = self._executors.get(task.agent_type)
        if not executor:
            raise ValueError(f"未找到执行器: {task.agent_type}")
        
        # 更新状态为运行中
        await blackboard.update_task_status(task.task_id, TaskStatus.RUNNING)
        
        # 使用信号量控制并发
        async with self._semaphore:
            attempt = 0
            last_error = None
            
            while attempt <= self.max_retries if self.enable_retry else True:
                try:
                    logger.info(f"🚀 [Scheduler] 执行任务: {task.task_id} (attempt={attempt})")
                    
                    # 执行任务
                    result = await asyncio.wait_for(
                        executor.execute(task, blackboard),
                        timeout=task.timeout_seconds
                    )
                    
                    # 成功，更新状态
                    await blackboard.update_task_status(
                        task.task_id, 
                        TaskStatus.COMPLETED,
                        output_data=result
                    )
                    
                    return result
                    
                except asyncio.TimeoutError:
                    last_error = f"Task timeout after {task.timeout_seconds}s"
                    logger.warning(f"⏰ [Scheduler] 任务 {task.task_id} 超时")
                    
                except Exception as e:
                    last_error = str(e)
                    logger.error(f"❌ [Scheduler] 任务 {task.task_id} 异常: {e}")
                
                attempt += 1
                
                if attempt <= self.max_retries:
                    # 重试前等待
                    await asyncio.sleep(min(2 ** attempt, 10))
        
        # 最终失败
        await blackboard.update_task_status(
            task.task_id,
            TaskStatus.FAILED,
            error_message=last_error
        )
        
        raise Exception(last_error)
    
    def _group_by_level(self, tasks: List[SubTask]) -> Dict[int, List[SubTask]]:
        """
        按依赖层级分组
        
        Args:
            tasks: 任务列表
            
        Returns:
            {level: [tasks]} 字典
        """
        levels: Dict[int, List[SubTask]] = defaultdict(list)
        task_levels: Dict[str, int] = {}
        
        def get_level(task: SubTask) -> int:
            if task.task_id in task_levels:
                return task_levels[task.task_id]
            
            if not task.dependencies:
                level = 0
            else:
                level = max(
                    get_level(blackboard.context.subtasks[dep_id])
                    for dep_id in task.dependencies
                    if dep_id in blackboard.context.subtasks
                ) + 1
            
            task_levels[task.task_id] = level
            return level
        
        for task in tasks:
            level = get_level(task)
            levels[level].append(task)
        
        return dict(sorted(levels.items()))
```

---

### 2.3 KeywordActivator - 关键词激活系统

#### 2.3.1 设计理念

```
群聊关键词监控架构:

┌─────────────────────────────────────────────────────────┐
│                 GroupChat Stream (群聊消息流)            │
│                                                         │
│  消息1: "张三: 帮我查一下这个月的报销"  ←── 触发关键词: "报销" │
│  消息2: "李四: 好的，我来处理"         ←── 普通消息       │
│  消息3: "王五: @AI 帮我看看合同有没有风险" ←── 触发关键词: "合同" │
│  消息4: "赵六: 今天天气真好啊"         ←── 普通消息       │
│                                                         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│            KeywordActivator (关键词激活器)               │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Keyword Rules (关键词规则)                           ││
│  │                                                     ││
│  │ 规则1: ["报销", "报销申请"] → FinanceSpecialist       ││
│  │ 规则2: ["合同", "协议"] → LegalSpecialist            ││
│  │ 规则3: ["税务", "纳税"] → TaxSpecialist              ││
│  │ 规则4: ["天气", "明天"] → HelperAgent                ││
│  │                                                     ││
│  │ 阈值: trigger_threshold=2                            ││
│  │      (同一个关键词出现N次才触发)                     ││
│  └─────────────────────────────────────────────────────┘│
│                          │                              │
│                          ▼                              │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Match Engine (匹配引擎)                              ││
│  │                                                     ││
│  │ - 正则表达式匹配                                     ││
│  │ - 模糊匹配 (编辑距离)                                ││
│  │ - 同义词扩展                                         ││
│  │ - 上下文感知                                         ││
│  └─────────────────────────────────────────────────────┘│
│                          │                              │
│                          ▼                              │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Activation Manager (激活管理器)                      ││
│  │                                                     ││
│  │ - 激活计数器                                         ││
│  │ - 冷却时间控制 (cooldown=300s)                       ││
│  │ - 优先级排序                                         ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Response Action (响应动作)                  │
│                                                         │
│  1. 静默监听模式 (silent=True)                           │
│     - 不回复消息                                         │
│     - 记录到黑板                                         │
│                                                         │
│  2. 主动提示模式 (silent=False)                          │
│     - @用户 提醒已记录任务                                │
│     - 询问是否需要帮助                                    │
│                                                         │
│  3. 立即执行模式 (auto_execute=True)                     │
│     - 直接触发对应 Agent                                 │
│     - 返回执行结果                                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### 2.3.2 核心实现

```python
# app/multi_agent_system/keyword/keyword_activator.py

import asyncio
import re
import logging
from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from difflib import SequenceMatcher

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class ActivationMode(str):
    """激活模式"""
    SILENT = "silent"             # 静默监听
    NOTIFY = "notify"             # 主动提示
    AUTO_EXECUTE = "auto_execute" # 立即执行


class KeywordRule(BaseModel):
    """关键词规则"""
    rule_id: str
    keywords: List[str] = Field(description="触发关键词列表")
    agent_type: str = Field(description="关联的 Agent 类型")
    priority: int = Field(default=1, description="优先级 (1-5)")
    mode: ActivationMode = Field(default=ActivationMode.SILENT)
    cooldown_seconds: float = Field(default=300.0, description="冷却时间")
    fuzzy_match: bool = Field(default=True, description="是否模糊匹配")
    fuzzy_threshold: float = Field(default=0.8, description="模糊匹配阈值")
    response_template: Optional[str] = Field(
        default=None, 
        description="响应模板"
    )
    enabled: bool = Field(default=True)


class KeywordMatch(BaseModel):
    """关键词匹配结果"""
    rule_id: str
    matched_keyword: str
    agent_type: str
    confidence: float = Field(description="匹配置信度 0-1")
    message_context: str = Field(description="匹配的上下文")
    match_type: str = Field(description="exact/fuzzy/regex")


@dataclass
class ActivationRecord:
    """激活记录"""
    rule_id: str
    agent_type: str
    triggered_at: datetime
    message_count: int = 1
    last_message: str = ""
    
    def is_in_cooldown(self, current_time: datetime, cooldown: float) -> bool:
        """检查是否在冷却期"""
        elapsed = (current_time - self.triggered_at).total_seconds()
        return elapsed < cooldown


class KeywordActivator:
    """
    关键词激活器
    
    核心功能:
    1. 关键词规则管理
    2. 消息内容匹配 (精确/模糊/正则)
    3. 激活计数器与阈值控制
    4. 冷却时间管理
    5. 多种激活模式
    """
    
    def __init__(
        self,
        trigger_threshold: int = 2,
        default_cooldown: float = 300.0,
        default_mode: ActivationMode = ActivationMode.SILENT,
        enable_fuzzy_match: bool = True,
        fuzzy_threshold: float = 0.8
    ):
        """
        初始化激活器
        
        Args:
            trigger_threshold: 触发阈值 (关键词出现次数)
            default_cooldown: 默认冷却时间 (秒)
            default_mode: 默认激活模式
            enable_fuzzy_match: 是否启用模糊匹配
            fuzzy_threshold: 模糊匹配阈值
        """
        self.trigger_threshold = trigger_threshold
        self.default_cooldown = default_cooldown
        self.default_mode = default_mode
        self.enable_fuzzy_match = enable_fuzzy_match
        self.fuzzy_threshold = fuzzy_threshold
        
        self._rules: Dict[str, KeywordRule] = {}
        self._keyword_to_rules: Dict[str, Set[str]] = defaultdict(set)
        self._activation_records: Dict[str, ActivationRecord] = {}
        self._activation_counter: Dict[str, int] = defaultdict(int)
        self._pending_activations: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        
        # 默认规则
        self._load_default_rules()
        
        logger.info(f"🔔 [KeywordActivator] 初始化完成")
        logger.info(f"   - 触发阈值: {trigger_threshold}")
        logger.info(f"   - 模糊匹配: {enable_fuzzy_match}")
        logger.info(f"   - 规则数量: {len(self._rules)}")
    
    def _load_default_rules(self) -> None:
        """加载默认关键词规则"""
        default_rules = [
            KeywordRule(
                rule_id="finance_reimburse",
                keywords=["报销", "报销申请", "差旅费", "交通费", "招待费"],
                agent_type="finance_specialist",
                priority=3,
                mode=ActivationMode.SILENT,
                response_template="已记录您的报销相关问题，稍后为您处理。"
            ),
            KeywordRule(
                rule_id="finance_analysis",
                keywords=["财务分析", "资产负债", "利润表", "现金流"],
                agent_type="finance_specialist",
                priority=4,
                mode=ActivationMode.AUTO_EXECUTE
            ),
            KeywordRule(
                rule_id="tax_query",
                keywords=["税务", "纳税", "增值税", "企业所得税", "个税"],
                agent_type="tax_specialist",
                priority=3,
                mode=ActivationMode.SILENT
            ),
            KeywordRule(
                rule_id="legal_contract",
                keywords=["合同", "协议", "条款", "违约", "签署"],
                agent_type="legal_specialist",
                priority=4,
                mode=ActivationMode.AUTO_EXECUTE,
                response_template="检测到合同相关讨论，已为您准备合同审查服务。"
            ),
            KeywordRule(
                rule_id="legal_compliance",
                keywords=["合规", "合规检查", "风险", "违规", "审查"],
                agent_type="legal_specialist",
                priority=2,
                mode=ActivationMode.NOTIFY
            ),
            KeywordRule(
                rule_id="helper_weather",
                keywords=["天气", "明天", "温度", "下雨", "晴天"],
                agent_type="helper_agent",
                priority=1,
                mode=ActivationMode.AUTO_EXECUTE
            ),
            KeywordRule(
                rule_id="helper_search",
                keywords=["搜索", "查找", "查询", "在哪里", "怎么走"],
                agent_type="helper_agent",
                priority=2,
                mode=ActivationMode.NOTIFY
            ),
        ]
        
        for rule in default_rules:
            self.add_rule(rule)
    
    # ==================== 规则管理 ====================
    
    def add_rule(self, rule: KeywordRule) -> None:
        """
        添加关键词规则
        
        Args:
            rule: 关键词规则
        """
        self._rules[rule.rule_id] = rule
        
        # 建立关键词到规则的映射
        for keyword in rule.keywords:
            self._keyword_to_rules[keyword.lower()].add(rule.rule_id)
        
        logger.info(f"🔔 [KeywordActivator] 添加规则: {rule.rule_id} -> {rule.agent_type}")
    
    def remove_rule(self, rule_id: str) -> bool:
        """
        移除规则
        
        Args:
            rule_id: 规则ID
            
        Returns:
            是否成功移除
        """
        if rule_id not in self._rules:
            return False
        
        rule = self._rules[rule_id]
        
        # 清理映射
        for keyword in rule.keywords:
            self._keyword_to_rules[keyword.lower()].discard(rule_id)
        
        del self._rules[rule_id]
        
        logger.info(f"🔔 [KeywordActivator] 移除规则: {rule_id}")
        
        return True
    
    def update_rule(self, rule_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新规则
        
        Args:
            rule_id: 规则ID
            updates: 更新字段
            
        Returns:
            是否成功更新
        """
        if rule_id not in self._rules:
            return False
        
        # 移除旧映射
        old_rule = self._rules[rule_id]
        for keyword in old_rule.keywords:
            self._keyword_to_rules[keyword.lower()].discard(rule_id)
        
        # 更新规则
        updated_rule = old_rule.copy(update=updates)
        
        # 重建映射
        for keyword in updated_rule.keywords:
            self._keyword_to_rules[keyword.lower()].add(rule_id)
        
        self._rules[rule_id] = updated_rule
        
        return True
    
    # ==================== 消息处理 ====================
    
    async def process_message(
        self,
        message: str,
        sender_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[KeywordMatch]:
        """
        处理群聊消息
        
        Args:
            message: 消息内容
            sender_id: 发送者ID
            context: 额外上下文
            
        Returns:
            匹配结果列表
        """
        context = context or {}
        matches = []
        current_time = datetime.now()
        
        async with self._lock:
            # 1. 精确关键词匹配
            exact_matches = await self._match_exact_keywords(message)
            matches.extend(exact_matches)
            
            # 2. 模糊匹配
            if self.enable_fuzzy_match:
                fuzzy_matches = await self._match_fuzzy_keywords(message)
                matches.extend(fuzzy_matches)
            
            # 3. 更新激活计数器
            for match in matches:
                await self._update_activation_counter(match, current_time)
            
            # 4. 检查是否触发激活
            triggered_agents = await self._check_activation_threshold(
                [m.agent_type for m in matches],
                current_time
            )
            
            if triggered_agents:
                logger.info(f"🔔 [KeywordActivator] 触发激活: {triggered_agents}")
                
                # 加入待处理队列
                for agent_type in triggered_agents:
                    await self._pending_activations.put({
                        "agent_type": agent_type,
                        "message": message,
                        "sender_id": sender_id,
                        "context": context,
                        "matches": [m for m in matches if m.agent_type == agent_type]
                    })
        
        return matches
    
    async def _match_exact_keywords(self, message: str) -> List[KeywordMatch]:
        """精确关键词匹配"""
        matches = []
        message_lower = message.lower()
        
        for keyword, rule_ids in self._keyword_to_rules.items():
            if keyword in message_lower:
                for rule_id in rule_ids:
                    rule = self._rules[rule_id]
                    if rule.enabled:
                        matches.append(KeywordMatch(
                            rule_id=rule_id,
                            matched_keyword=keyword,
                            agent_type=rule.agent_type,
                            confidence=1.0,
                            message_context=message,
                            match_type="exact"
                        ))
        
        return matches
    
    async def _match_fuzzy_keywords(self, message: str) -> List[KeywordMatch]:
        """模糊关键词匹配"""
        matches = []
        message_lower = message.lower()
        words = re.findall(r'\w+', message_lower)
        
        for rule_id, rule in self._rules.items():
            if not rule.enabled or not rule.fuzzy_match:
                continue
            
            for keyword in rule.keywords:
                keyword_lower = keyword.lower()
                
                # 检查是否已精确匹配
                if keyword_lower in message_lower:
                    continue
                
                # 检查编辑距离
                for word in words:
                    ratio = SequenceMatcher(None, keyword_lower, word).ratio()
                    
                    if ratio >= rule.fuzzy_threshold:
                        matches.append(KeywordMatch(
                            rule_id=rule_id,
                            matched_keyword=keyword,
                            agent_type=rule.agent_type,
                            confidence=ratio,
                            message_context=message,
                            match_type="fuzzy"
                        ))
        
        return matches
    
    async def _update_activation_counter(
        self, 
        match: KeywordMatch,
        current_time: datetime
    ) -> None:
        """更新激活计数器"""
        agent_type = match.agent_type
        
        # 检查是否在冷却期
        record = self._activation_records.get(agent_type)
        if record and record.is_in_cooldown(current_time, self.default_cooldown):
            # 在冷却期，增加计数但不重置
            record.message_count += 1
            record.last_message = match.message_context
        else:
            # 不在冷却期，重置计数
            self._activation_counter[agent_type] = 1
            self._activation_records[agent_type] = ActivationRecord(
                rule_id=match.rule_id,
                agent_type=agent_type,
                triggered_at=current_time,
                message_count=1,
                last_message=match.message_context
            )
    
    async def _check_activation_threshold(
        self,
        agent_types: List[str],
        current_time: datetime
    ) -> List[str]:
        """检查是否达到激活阈值"""
        triggered = []
        
        for agent_type in set(agent_types):
            counter = self._activation_counter[agent_type]
            
            if counter >= self.trigger_threshold:
                # 检查是否在冷却期
                record = self._activation_records.get(agent_type)
                
                if not record or not record.is_in_cooldown(current_time, self.default_cooldown):
                    triggered.append(agent_type)
                    # 重置计数器
                    self._activation_counter[agent_type] = 0
        
        return triggered
    
    # ==================== 激活结果处理 ====================
    
    async def get_pending_activations(self) -> List[Dict[str, Any]]:
        """
        获取待处理的激活队列
        
        Returns:
            待处理激活列表
        """
        activations = []
        
        while not self._pending_activations.empty():
            try:
                activation = self._pending_activations.get_nowait()
                activations.append(activation)
            except asyncio.QueueEmpty:
                break
        
        return activations
    
    # ==================== 状态查询 ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
            "activation_records": {
                agent_type: {
                    "message_count": record.message_count,
                    "last_triggered": record.triggered_at.isoformat()
                }
                for agent_type, record in self._activation_records.items()
            },
            "pending_activations": self._pending_activations.qsize()
        }
```

---

### 2.4 ResultSynthesizer - 智能结果合成器

#### 2.4.1 设计理念

```
结果合成流程:

┌─────────────────────────────────────────────────────────┐
│              Multi-Agent Results (多Agent结果)           │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  Finance    │  │    Tax      │  │   Legal     │     │
│  │  Specialist │  │  Specialist  │  │  Specialist │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │             │
│         ▼                ▼                ▼             │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Result Aggregation (结果聚合)                        ││
│  │                                                     ││
│  │ {                                                    ││
│  │   "finance": { "revenue": 100, "cost": 80 },       ││
│  │   "tax": { "vat": 13, "income_tax": 5 },           ││
│  │   "legal": { "risk_level": "medium" }              ││
│  │ }                                                    ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│           ResultSynthesizer (结果合成器)                 │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │  Stage 1: Conflict Detection (冲突检测)              ││
│  │                                                     ││
│  │  - 数据一致性检查                                    ││
│  │  - 结论冲突检测                                      ││
│  │  - 优先级排序                                        ││
│  └─────────────────────────────────────────────────────┘│
│                          │                              │
│                          ▼                              │
│  ┌─────────────────────────────────────────────────────┐│
│  │  Stage 2: Information Fusion (信息融合)              ││
│  │                                                     ││
│  │  - 补充缺失信息                                       ││
│  │  - 关联分析                                          ││
│  │  - 交叉验证                                          ││
│  └─────────────────────────────────────────────────────┘│
│                          │                              │
│                          ▼                              │
│  ┌─────────────────────────────────────────────────────┐│
│  │  Stage 3: Insight Generation (洞察生成)              ││
│  │                                                     ││
│  │  - 趋势分析                                          ││
│  │  - 风险识别                                          ││
│  │  - 机会发现                                          ││
│  │  - 建议提炼                                          ││
│  └─────────────────────────────────────────────────────┘│
│                          │                              │
│                          ▼                              │
│  ┌─────────────────────────────────────────────────────┐│
│  │  Stage 4: Natural Language Generation (自然语言生成)││
│  │                                                     ││
│  │  - 结构化输出                                       ││
│  │  - 可读性优化                                        ││
│  │  - 上下文适配                                        ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Final Synthesized Output                   │
│                                                         │
│  综合分析报告:                                          │
│                                                         │
│  📊 财务概况:                                           │
│     - 收入: 100万元 (同比增长 20%)                     │
│     - 成本: 80万元 (需关注)                             │
│     - 利润率: 20% (行业平均水平)                        │
│                                                         │
│  📋 税务风险:                                           │
│     - 增值税: 已合规                                    │
│     - 风险点: 部分发票可能不合规                         │
│                                                         │
│  ⚖️ 法律合规:                                          │
│     - 合同审查: 通过                                    │
│     - 建议: 完善合同条款                                 │
│                                                         │
│  💡 综合建议:                                           │
│     - 短期: 优化成本结构                                 │
│     - 中期: 关注税务合规                                 │
│     - 长期: 建立全面风险管理体系                         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### 2.4.2 核心实现

```python
# app/multi_agent_system/synthesizer/result_synthesizer.py

import asyncio
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field

from app.agent_framework.llm.base_adapter import BaseLLMAdapter

logger = logging.getLogger(__name__)


class ConflictType(str, Enum):
    """冲突类型"""
    DATA_INCONSISTENCY = "data_inconsistency"   # 数据不一致
    CONCLUSION_CONFLICT = "conclusion_conflict" # 结论冲突
    PRIORITY_CONFLICT = "priority_conflict"     # 优先级冲突


@dataclass
class Conflict:
    """冲突描述"""
    conflict_type: ConflictType
    source_agents: List[str]
    description: str
    resolution: Optional[str] = None


@dataclass
class Insight:
    """洞察描述"""
    category: str  # trend/risk/opportunity/recommendation
    title: str
    description: str
    confidence: float
    evidence: List[str] = field(default_factory=list)
    priority: int = 1  # 1-5, 5最高


class SynthesisConfig(BaseModel):
    """合成配置"""
    enable_conflict_resolution: bool = True
    enable_insight_generation: bool = True
    max_insights: int = 10
    confidence_threshold: float = 0.6
    language: str = "zh-CN"
    output_format: str = "natural"  # natural/structured/markdown
    include_raw_data: bool = False
    include_reasoning: bool = True


class SynthesisResult(BaseModel):
    """合成结果"""
    summary: str = Field(description="综合摘要")
    sections: Dict[str, Any] = Field(
        default_factory=dict, 
        description="分节详细内容"
    )
    conflicts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="检测到的冲突"
    )
    insights: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="生成的洞察"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="整体置信度"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="元数据"
    )


class ResultSynthesizer:
    """
    结果合成器
    
    核心功能:
    1. 多源结果聚合
    2. 冲突检测与解决
    3. 信息智能融合
    4. 洞察生成
    5. 自然语言输出
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        config: Optional[SynthesisConfig] = None
    ):
        """
        初始化合成器
        
        Args:
            llm_adapter: LLM 适配器
            config: 合成配置
        """
        self.llm_adapter = llm_adapter
        self.config = config or SynthesisConfig()
        
        logger.info(f"🎯 [Synthesizer] 初始化完成")
    
    async def synthesize(
        self,
        results: Dict[str, Dict[str, Any]],
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SynthesisResult:
        """
        合成多Agent结果
        
        Args:
            results: {agent_type: result_data} 字典
            query: 原始查询
            context: 额外上下文
            
        Returns:
            合成结果
        """
        context = context or {}
        
        logger.info(f"🎯 [Synthesizer] 开始合成 {len(results)} 个Agent结果")
        
        # Stage 1: 冲突检测
        conflicts = []
        if self.config.enable_conflict_resolution:
            conflicts = await self._detect_conflicts(results)
            logger.info(f"🎯 [Synthesizer] 检测到 {len(conflicts)} 个冲突")
        
        # Stage 2: 信息融合
        fused_data = await self._fuse_information(results, conflicts)
        
        # Stage 3: 洞察生成
        insights = []
        if self.config.enable_insight_generation:
            insights = await self._generate_insights(fused_data, query)
            logger.info(f"🎯 [Synthesizer] 生成 {len(insights)} 个洞察")
        
        # Stage 4: 自然语言生成
        summary, sections = await self._generate_natural_language(
            fused_data, 
            insights, 
            conflicts,
            query,
            context
        )
        
        # 计算整体置信度
        confidence = self._calculate_confidence(results, insights, conflicts)
        
        return SynthesisResult(
            summary=summary,
            sections=sections,
            conflicts=[self._conflict_to_dict(c) for c in conflicts],
            insights=[self._insight_to_dict(i) for i in insights],
            confidence=confidence,
            metadata={
                "agent_count": len(results),
                "agent_types": list(results.keys()),
                "synthesized_at": datetime.now().isoformat(),
                "language": self.config.language
            }
        )
    
    # ==================== Stage 1: 冲突检测 ====================
    
    async def _detect_conflicts(
        self, 
        results: Dict[str, Dict[str, Any]]
    ) -> List[Conflict]:
        """检测多源结果冲突"""
        conflicts = []
        
        # 检查数值不一致
        numeric_keys = self._find_common_numeric_keys(results)
        for key in numeric_keys:
            values = [
                (agent, r.get(key))
                for agent, r in results.items()
                if key in r and isinstance(r[key], (int, float))
            ]
            
            if len(values) >= 2:
                # 计算差异
                nums = [v[1] for v in values]
                avg = sum(nums) / len(nums)
                max_diff = max(abs(n - avg) for n in nums)
                
                # 如果差异超过平均值 10%，认为有冲突
                if avg != 0 and max_diff / abs(avg) > 0.1:
                    conflicts.append(Conflict(
                        conflict_type=ConflictType.DATA_INCONSISTENCY,
                        source_agents=[v[0] for v in values],
                        description=f"指标 '{key}' 的值不一致: {[v[1] for v in values]}",
                        resolution=f"采用平均值: {avg:.2