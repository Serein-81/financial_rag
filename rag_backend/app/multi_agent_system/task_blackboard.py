"""
任务黑板系统 (Task Blackboard)
基于 Blackboard Pattern 的全局任务上下文管理
支持多智能体异步协作、状态共享、冲突检测
"""

import asyncio
import uuid
import logging
from typing import Dict, List, Any, Optional, Callable, Set, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"          # 待处理
    RUNNING = "running"          # 执行中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 取消
    WAITING_DEPENDENCY = "waiting_dependency"  # 等待依赖


class TaskPriority(int, Enum):
    """任务优先级"""
    CRITICAL = 1   # 最高优先级
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class AgentRole(str, Enum):
    """智能体角色"""
    COORDINATOR = "coordinator"      # 协调者
    SPECIALIST = "specialist"        # 专家
    HELPER = "helper"                # 助手
    SYNTHESIZER = "synthesizer"      # 合成器
    MONITOR = "monitor"              # 监控者


@dataclass
class TaskContext:
    """任务上下文"""
    task_id: str
    task_type: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: str = ""
    assigned_to: Optional[str] = None
    
    # 依赖管理
    dependencies: List[str] = field(default_factory=list)  # 依赖的task_id列表
    dependents: List[str] = field(default_factory=list)   # 依赖该任务的task_id列表
    
    # 结果数据
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = None
    intermediate_results: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    
    # 错误处理
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # 执行信息
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: float = 0.0  # 秒
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "priority": self.priority.value if isinstance(self.priority, TaskPriority) else self.priority,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "assigned_to": self.assigned_to,
            "dependencies": self.dependencies,
            "dependents": self.dependents,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "intermediate_results": self.intermediate_results,
            "metadata": self.metadata,
            "tags": list(self.tags),
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time": self.execution_time
        }


@dataclass
class AgentState:
    """智能体状态"""
    agent_id: str
    agent_name: str
    role: AgentRole
    status: str = "idle"  # idle, busy, waiting, error
    current_task_id: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    expertise: List[str] = field(default_factory=list)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    registered_at: datetime = field(default_factory=datetime.now)
    
    # 性能指标
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_execution_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "role": self.role.value if isinstance(self.role, AgentRole) else self.role,
            "status": self.status,
            "current_task_id": self.current_task_id,
            "capabilities": self.capabilities,
            "expertise": self.expertise,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "avg_execution_time": self.avg_execution_time
        }


@dataclass
class BlackboardEvent:
    """黑板事件"""
    event_id: str
    event_type: str
    source: str  # agent_id or system
    target: Optional[str] = None  # agent_id or None (broadcast)
    task_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "target": self.target,
            "task_id": self.task_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "priority": self.priority
        }


class TaskBlackboard:
    """
    任务黑板系统
    
    核心功能：
    1. 全局任务状态管理
    2. 多智能体状态追踪
    3. 任务依赖管理
    4. 冲突检测
    5. 事件发布订阅
    6. 任务优先级调度
    
    设计模式：
    - Blackboard Pattern: 多个智能体共享黑板读写
    - Observer Pattern: 事件驱动通知
    - Producer-Consumer: 任务生产消费
    
    线程安全：使用 asyncio.Lock 保证并发安全
    """
    
    def __init__(self, session_id: str = "default"):
        """
        初始化任务黑板
        
        Args:
            session_id: 会话ID（用于多会话隔离）
        """
        self.session_id = session_id
        
        # 任务存储
        self._tasks: Dict[str, TaskContext] = {}
        self._tasks_by_type: Dict[str, List[str]] = defaultdict(list)
        self._tasks_by_status: Dict[TaskStatus, List[str]] = defaultdict(list)
        self._tasks_by_priority: Dict[TaskPriority, List[str]] = defaultdict(list)
        
        # 智能体注册
        self._agents: Dict[str, AgentState] = {}
        self._agent_subscriptions: Dict[str, Set[str]] = defaultdict(set)  # agent_id -> event_types
        
        # 共享数据区（知识库）
        self._shared_data: Dict[str, Any] = {}
        
        # 事件系统
        self._event_queue: asyncio.Queue[BlackboardEvent] = asyncio.Queue()
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._event_history: List[BlackboardEvent] = []
        
        # 冲突检测
        self._conflict_log: List[Dict[str, Any]] = []
        
        # 锁
        self._lock = asyncio.Lock()
        
        # 统计
        self._stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "total_events": 0
        }
        
        logger.info(f"🗄️ [TaskBlackboard] 初始化完成，会话ID: {session_id}")
    
    # =========================================================================
    # 任务管理
    # =========================================================================
    
    async def create_task(
        self,
        task_type: str,
        description: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        created_by: str = "system",
        input_data: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[Set[str]] = None
    ) -> TaskContext:
        """
        创建新任务
        
        Args:
            task_type: 任务类型
            description: 任务描述
            priority: 优先级
            created_by: 创建者
            input_data: 输入数据
            dependencies: 依赖的task_id列表
            metadata: 元数据
            tags: 标签
            
        Returns:
            TaskContext: 创建的任务上下文
        """
        async with self._lock:
            task_id = str(uuid.uuid4())
            
            task = TaskContext(
                task_id=task_id,
                task_type=task_type,
                description=description,
                priority=priority,
                created_by=created_by,
                input_data=input_data or {},
                dependencies=dependencies or [],
                metadata=metadata or {},
                tags=tags or set()
            )
            
            self._tasks[task_id] = task
            self._tasks_by_type[task_type].append(task_id)
            self._tasks_by_status[TaskStatus.PENDING].append(task_id)
            self._tasks_by_priority[priority].append(task_id)
            
            self._stats["total_tasks"] += 1
            
            await self._emit_event(
                BlackboardEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="task_created",
                    source=created_by,
                    task_id=task_id,
                    data={"task": task.to_dict()}
                )
            )
            
            logger.info(f"📝 [TaskBlackboard] 创建任务: {task_id} ({task_type}) - {description}")
            
            return task
    
    async def get_task(self, task_id: str) -> Optional[TaskContext]:
        """获取任务上下文"""
        async with self._lock:
            return self._tasks.get(task_id)
    
    async def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        output_data: Optional[Dict[str, Any]] = None,
        intermediate_result: Optional[tuple] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[TaskContext]:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            output_data: 输出数据
            intermediate_result: (key, value) 元组
            error: 错误信息
            metadata: 元数据更新
            
        Returns:
            Optional[TaskContext]: 更新后的任务上下文
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                logger.warning(f"⚠️ [TaskBlackboard] 任务不存在: {task_id}")
                return None
            
            old_status = task.status
            
            if status:
                task.status = status
                self._tasks_by_status[old_status].remove(task_id)
                self._tasks_by_status[status].append(task_id)
                
                if status == TaskStatus.RUNNING and not task.started_at:
                    task.started_at = datetime.now()
                elif status == TaskStatus.COMPLETED:
                    task.completed_at = datetime.now()
                    if task.started_at:
                        task.execution_time = (task.completed_at - task.started_at).total_seconds()
                    self._stats["completed_tasks"] += 1
                elif status == TaskStatus.FAILED:
                    self._stats["failed_tasks"] += 1
            
            if output_data:
                task.output_data = output_data
            
            if intermediate_result:
                key, value = intermediate_result
                task.intermediate_results[key] = value
            
            if error:
                task.error = error
                task.retry_count += 1
            
            if metadata:
                task.metadata.update(metadata)
            
            task.updated_at = datetime.now()
            
            await self._emit_event(
                BlackboardEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="task_updated",
                    source="blackboard",
                    task_id=task_id,
                    data={
                        "old_status": old_status.value if isinstance(old_status, TaskStatus) else old_status,
                        "new_status": task.status.value if isinstance(task.status, TaskStatus) else task.status,
                        "task": task.to_dict()
                    }
                )
            )
            
            if status == TaskStatus.COMPLETED:
                await self._notify_dependents(task_id)
            
            return task
    
    async def assign_task(self, task_id: str, agent_id: str) -> bool:
        """分配任务给智能体"""
        async with self._lock:
            task = self._tasks.get(task_id)
            agent = self._agents.get(agent_id)
            
            if not task or not agent:
                return False
            
            task.assigned_to = agent_id
            agent.current_task_id = task_id
            agent.status = "busy"
            
            await self._emit_event(
                BlackboardEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="task_assigned",
                    source="blackboard",
                    target=agent_id,
                    task_id=task_id,
                    data={"agent_name": agent.agent_name}
                )
            )
            
            return True
    
    async def cancel_task(self, task_id: str, reason: str = "") -> bool:
        """取消任务"""
        task = await self.update_task(task_id, status=TaskStatus.CANCELLED)
        if task:
            await self._emit_event(
                BlackboardEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="task_cancelled",
                    source="blackboard",
                    task_id=task_id,
                    data={"reason": reason}
                )
            )
            return True
        return False
    
    async def get_pending_tasks(
        self,
        task_type: Optional[str] = None,
        agent_capabilities: Optional[List[str]] = None
    ) -> List[TaskContext]:
        """获取待处理任务"""
        async with self._lock:
            pending_ids = self._tasks_by_status.get(TaskStatus.PENDING, [])
            tasks = []
            
            for task_id in pending_ids:
                task = self._tasks.get(task_id)
                if not task:
                    continue
                
                if task_type and task.task_type != task_type:
                    continue
                
                if task.dependencies:
                    deps_completed = all(
                        self._tasks.get(dep_id) and 
                        self._tasks[dep_id].status == TaskStatus.COMPLETED
                        for dep_id in task.dependencies
                    )
                    if not deps_completed:
                        continue
                
                if agent_capabilities:
                    if task.task_type not in agent_capabilities:
                        continue
                
                tasks.append(task)
            
            return sorted(tasks, key=lambda t: t.priority.value)
    
    # =========================================================================
    # 智能体管理
    # =========================================================================
    
    async def register_agent(
        self,
        agent_name: str,
        role: AgentRole,
        capabilities: Optional[List[str]] = None,
        expertise: Optional[List[str]] = None
    ) -> AgentState:
        """
        注册智能体
        
        Args:
            agent_name: 智能体名称
            role: 角色
            capabilities: 能力列表
            expertise: 专业领域列表
            
        Returns:
            AgentState: 智能体状态
        """
        async with self._lock:
            agent_id = str(uuid.uuid4())
            
            agent = AgentState(
                agent_id=agent_id,
                agent_name=agent_name,
                role=role,
                capabilities=capabilities or [],
                expertise=expertise or []
            )
            
            self._agents[agent_id] = agent
            
            await self._emit_event(
                BlackboardEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="agent_registered",
                    source=agent_id,
                    data={"agent": agent.to_dict()}
                )
            )
            
            logger.info(f"🤖 [TaskBlackboard] 注册智能体: {agent_id} ({agent_name}) - {role.value}")
            
            return agent
    
    async def update_agent_status(
        self,
        agent_id: str,
        status: str,
        heartbeat: bool = True
    ) -> Optional[AgentState]:
        """更新智能体状态"""
        async with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return None
            
            agent.status = status
            if heartbeat:
                agent.last_heartbeat = datetime.now()
            
            if status == "idle" and agent.current_task_id:
                agent.current_task_id = None
            
            return agent
    
    async def get_available_agents(
        self,
        role: Optional[AgentRole] = None,
        capability: Optional[str] = None
    ) -> List[AgentState]:
        """获取可用智能体"""
        async with self._lock:
            agents = []
            
            for agent in self._agents.values():
                if agent.status != "idle":
                    continue
                
                if role and agent.role != role:
                    continue
                
                if capability and capability not in agent.capabilities:
                    continue
                
                agents.append(agent)
            
            return agents
    
    # =========================================================================
    # 共享数据管理
    # =========================================================================
    
    async def write_shared_data(self, key: str, value: Any, ttl: int = 0) -> None:
        """
        写入共享数据
        
        Args:
            key: 数据键
            value: 数据值
            ttl: 生存时间（秒），0表示永不过期
        """
        async with self._lock:
            self._shared_data[key] = {
                "value": value,
                "timestamp": datetime.now(),
                "ttl": ttl
            }
            
            await self._emit_event(
                BlackboardEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="shared_data_updated",
                    source="blackboard",
                    data={"key": key}
                )
            )
    
    async def read_shared_data(self, key: str) -> Optional[Any]:
        """读取共享数据"""
        async with self._lock:
            data = self._shared_data.get(key)
            if data:
                return data["value"]
            return None
    
    async def get_all_shared_data(self) -> Dict[str, Any]:
        """获取所有共享数据"""
        async with self._lock:
            return {k: v["value"] for k, v in self._shared_data.items()}
    
    # =========================================================================
    # 事件系统
    # =========================================================================
    
    async def _emit_event(self, event: BlackboardEvent) -> None:
        """发布事件"""
        self._event_history.append(event)
        self._stats["total_events"] += 1
        
        handlers = self._event_handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"❌ [TaskBlackboard] 事件处理异常: {e}")
        
        await self._event_queue.put(event)
    
    async def subscribe(
        self,
        agent_id: str,
        event_types: List[str]
    ) -> None:
        """订阅事件"""
        async with self._lock:
            self._agent_subscriptions[agent_id].update(event_types)
    
    async def unsubscribe(self, agent_id: str, event_types: List[str]) -> None:
        """取消订阅"""
        async with self._lock:
            self._agent_subscriptions[agent_id].difference_update(event_types)
    
    async def get_event_stream(
        self,
        event_types: Optional[List[str]] = None,
        timeout: float = 30.0
    ) -> AsyncGenerator[BlackboardEvent, None]:
        """
        获取事件流
        
        Args:
            event_types: 过滤的事件类型
            timeout: 超时时间
            
        Yields:
            BlackboardEvent: 事件
        """
        while True:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=timeout
                )
                
                if event_types is None or event.event_type in event_types:
                    yield event
                elif event.event_type == "shutdown":
                    break
                    
            except asyncio.TimeoutError:
                break
    
    # =========================================================================
    # 依赖管理
    # =========================================================================
    
    async def add_dependency(
        self,
        task_id: str,
        depends_on: str
    ) -> bool:
        """添加任务依赖"""
        async with self._lock:
            task = self._tasks.get(task_id)
            depends_task = self._tasks.get(depends_on)
            
            if not task or not depends_task:
                return False
            
            if depends_on not in task.dependencies:
                task.dependencies.append(depends_on)
            
            if task_id not in depends_task.dependents:
                depends_task.dependents.append(task_id)
            
            await self.update_task(task_id, status=TaskStatus.WAITING_DEPENDENCY)
            
            return True
    
    async def _notify_dependents(self, completed_task_id: str) -> None:
        """通知依赖该任务的任务"""
        async with self._lock:
            task = self._tasks.get(completed_task_id)
            if not task:
                return
            
            for dependent_id in task.dependents:
                dependent = self._tasks.get(dependent_id)
                if not dependent:
                    continue
                
                all_deps_completed = all(
                    self._tasks.get(dep_id) and 
                    self._tasks[dep_id].status == TaskStatus.COMPLETED
                    for dep_id in dependent.dependencies
                )
                
                if all_deps_completed and dependent.status == TaskStatus.WAITING_DEPENDENCY:
                    await self.update_task(dependent_id, status=TaskStatus.PENDING)
                    
                    await self._emit_event(
                        BlackboardEvent(
                            event_id=str(uuid.uuid4()),
                            event_type="dependency_ready",
                            source="blackboard",
                            task_id=dependent_id,
                            data={"ready_task_id": completed_task_id}
                        )
                    )
    
    # =========================================================================
    # 冲突检测
    # =========================================================================
    
    async def check_conflicts(self, task_id: str) -> List[Dict[str, Any]]:
        """检查任务冲突"""
        conflicts = []
        
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return conflicts
            
            for other_id, other_task in self._tasks.items():
                if other_id == task_id:
                    continue
                
                if other_task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    continue
                
                if self._has_resource_conflict(task, other_task):
                    conflicts.append({
                        "type": "resource_conflict",
                        "task_id": task_id,
                        "conflicting_task_id": other_id,
                        "description": f"任务 {task_id} 与 {other_id} 存在资源冲突"
                    })
                
                if self._has_semantic_conflict(task, other_task):
                    conflicts.append({
                        "type": "semantic_conflict",
                        "task_id": task_id,
                        "conflicting_task_id": other_id,
                        "description": f"任务 {task_id} 与 {other_id} 存在语义冲突"
                    })
            
            if conflicts:
                self._conflict_log.extend(conflicts)
        
        return conflicts
    
    def _has_resource_conflict(self, task1: TaskContext, task2: TaskContext) -> bool:
        """检查资源冲突"""
        resources1 = task1.metadata.get("resources", set())
        resources2 = task2.metadata.get("resources", set())
        return bool(resources1 & resources2)
    
    def _has_semantic_conflict(self, task1: TaskContext, task2: TaskContext) -> bool:
        """检查语义冲突"""
        tags1 = task1.tags
        tags2 = task2.tags
        
        conflicting_tags = {"finance", "tax", "legal"}
        return bool(tags1 & tags2 & conflicting_tags)
    
    # =========================================================================
    # 统计与监控
    # =========================================================================
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        async with self._lock:
            return {
                "session_id": self.session_id,
                "stats": self._stats.copy(),
                "active_agents": sum(1 for a in self._agents.values() if a.status == "idle"),
                "busy_agents": sum(1 for a in self._agents.values() if a.status == "busy"),
                "total_agents": len(self._agents),
                "total_tasks": len(self._tasks),
                "pending_tasks": len(self._tasks_by_status.get(TaskStatus.PENDING, [])),
                "running_tasks": len(self._tasks_by_status.get(TaskStatus.RUNNING, [])),
                "completed_tasks": len(self._tasks_by_status.get(TaskStatus.COMPLETED, [])),
                "failed_tasks": len(self._tasks_by_status.get(TaskStatus.FAILED, [])),
                "conflict_count": len(self._conflict_log),
                "shared_data_keys": len(self._shared_data)
            }
    
    async def get_task_graph(self) -> Dict[str, Any]:
        """获取任务依赖图"""
        async with self._lock:
            nodes = []
            edges = []
            
            for task_id, task in self._tasks.items():
                nodes.append({
                    "id": task_id,
                    "type": task.task_type,
                    "status": task.status.value if isinstance(task.status, TaskStatus) else task.status,
                    "priority": task.priority.value if isinstance(task.priority, TaskPriority) else task.priority,
                    "label": task.description[:50]
                })
                
                for dep_id in task.dependencies:
                    edges.append({
                        "from": dep_id,
                        "to": task_id
                    })
            
            return {"nodes": nodes, "edges": edges}
    
    # =========================================================================
    # 清理与重置
    # =========================================================================
    
    async def clear_session(self) -> None:
        """清理会话数据"""
        async with self._lock:
            self._tasks.clear()
            self._tasks_by_type.clear()
            self._tasks_by_status.clear()
            self._tasks_by_priority.clear()
            self._shared_data.clear()
            self._conflict_log.clear()
            self._event_history.clear()
            
            while not self._event_queue.empty():
                try:
                    self._event_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            
            logger.info(f"🗑️ [TaskBlackboard] 会话数据已清理: {self.session_id}")


class BlackboardContext:
    """
    黑板上下文管理器
    
    提供便捷的上下文访问接口
    """
    
    def __init__(self, blackboard: TaskBlackboard):
        self.blackboard = blackboard
    
    async def __aenter__(self) -> "BlackboardContext":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            logger.error(f"❌ [BlackboardContext] 异常: {exc_val}")
    
    async def create_parallel_tasks(
        self,
        task_specs: List[Dict[str, Any]],
        created_by: str = "system"
    ) -> List[TaskContext]:
        """
        创建并行任务组
        
        Args:
            task_specs: 任务规格列表
            created_by: 创建者
            
        Returns:
            List[TaskContext]: 创建的任务列表
        """
        tasks = []
        for spec in task_specs:
            task = await self.blackboard.create_task(
                task_type=spec.get("task_type", "general"),
                description=spec.get("description", ""),
                priority=TaskPriority(spec.get("priority", TaskPriority.NORMAL.value)),
                created_by=created_by,
                input_data=spec.get("input_data", {}),
                tags=set(spec.get("tags", []))
            )
            tasks.append(task)
        
        return tasks
    
    async def wait_for_completion(
        self,
        task_ids: List[str],
        timeout: float = 120.0,
        poll_interval: float = 1.0
    ) -> Dict[str, TaskContext]:
        """
        等待任务完成
        
        Args:
            task_ids: 任务ID列表
            timeout: 超时时间
            poll_interval: 轮询间隔
            
        Returns:
            Dict[str, TaskContext]: 完成的任务字典
        """
        start_time = asyncio.get_event_loop().time()
        completed = {}
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            for task_id in task_ids:
                if task_id in completed:
                    continue
                
                task = await self.blackboard.get_task(task_id)
                if task and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    completed[task_id] = task
            
            if len(completed) == len(task_ids):
                break
            
            await asyncio.sleep(poll_interval)
        
        return completed
