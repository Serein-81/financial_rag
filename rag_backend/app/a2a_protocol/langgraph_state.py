"""
A2A LangGraph State Integration

A2A Task 模型与 LangGraph State 的集成
将 A2A 协议作为 LangGraph 的状态载体
"""

import logging
from typing import TypedDict, Optional, Dict, Any, List, Callable, Union, Sequence
from datetime import datetime
from uuid import uuid4
from dataclasses import dataclass, field

from .models import Task, TaskStatus, Message, TextPart

logger = logging.getLogger(__name__)


class A2ATaskState(TypedDict, total=False):
    """
    A2A 任务状态

    LangGraph State 的核心载体，包含：
    1. messages: 对话历史
    2. a2a_task_bus: A2A 任务队列
    """
    messages: List[Dict[str, Any]]
    a2a_task_bus: List["A2ATaskEntry"]
    current_agent: Optional[str]
    agent_results: Dict[str, Any]
    routing_decision: Optional[Dict[str, Any]]


@dataclass
class A2ATaskEntry:
    """
    A2A 任务条目

    存储在 LangGraph State 的 a2a_task_bus 中
    """
    task_id: str
    from_agent: str
    to_agent: str
    status: str
    message: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "status": self.status,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "A2ATaskEntry":
        """从字典创建"""
        return cls(
            task_id=data.get("task_id", str(uuid4())),
            from_agent=data.get("from_agent", ""),
            to_agent=data.get("to_agent", ""),
            status=data.get("status", "pending"),
            message=data.get("message", {}),
            result=data.get("result"),
            error=data.get("error"),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
        )

    @classmethod
    def from_task(cls, task: Task, to_agent: str, from_agent: str = "orchestrator") -> "A2ATaskEntry":
        """从 A2A Task 创建"""
        message_dict = {
            "content": cls._extract_content_from_task(task),
            "parts": [],
            "metadata": task.metadata
        }

        return cls(
            task_id=task.id,
            from_agent=from_agent,
            to_agent=to_agent,
            status=task.status.value,
            message=message_dict,
        )

    @staticmethod
    def _extract_content_from_task(task: Task) -> str:
        """从 Task 提取内容"""
        user_msgs = [m for m in task.messages if m.role == "user"]
        if user_msgs:
            parts_text = []
            for part in user_msgs[0].parts:
                if hasattr(part, 'text'):
                    parts_text.append(part.text)
            return "\n".join(parts_text) if parts_text else ""
        return ""


class A2ATaskBus:
    """
    A2A 任务总线

    管理 LangGraph State 中的 a2a_task_bus
    提供任务的提交、查询、状态更新等操作
    """

    def __init__(self):
        self._tasks: List[A2ATaskEntry] = []
        self._pending: Dict[str, A2ATaskEntry] = {}
        self._completed: Dict[str, A2ATaskEntry] = {}
        logger.info("🚌 A2ATaskBus 初始化")

    def submit_task(
        self,
        to_agent: str,
        message: Union[str, Dict[str, Any]],
        from_agent: str = "orchestrator",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        提交任务到总线

        Args:
            to_agent: 目标 Agent
            message: 任务消息（字符串或字典）
            from_agent: 来源 Agent
            metadata: 附加元数据

        Returns:
            任务 ID
        """
        task_id = str(uuid4())

        if isinstance(message, str):
            message_dict = {
                "content": message,
                "parts": [],
                "metadata": metadata or {}
            }
        else:
            message_dict = message

        entry = A2ATaskEntry(
            task_id=task_id,
            from_agent=from_agent,
            to_agent=to_agent,
            status="pending",
            message=message_dict
        )

        self._tasks.append(entry)
        self._pending[task_id] = entry
        logger.info(f"📬 任务提交: {task_id} -> {to_agent}")

        return task_id

    def get_task(self, task_id: str) -> Optional[A2ATaskEntry]:
        """获取任务"""
        return self._pending.get(task_id) or self._completed.get(task_id)

    def complete_task(self, task_id: str, result: Any) -> bool:
        """
        标记任务完成

        Args:
            task_id: 任务 ID
            result: 执行结果

        Returns:
            是否成功
        """
        entry = self._pending.pop(task_id, None)
        if entry:
            entry.status = "completed"
            entry.result = result
            entry.updated_at = datetime.utcnow().isoformat()
            self._completed[task_id] = entry
            logger.info(f"✅ 任务完成: {task_id}")
            return True
        return False

    def fail_task(self, task_id: str, error: str) -> bool:
        """标记任务失败"""
        entry = self._pending.pop(task_id, None)
        if entry:
            entry.status = "failed"
            entry.error = error
            entry.updated_at = datetime.utcnow().isoformat()
            self._completed[task_id] = entry
            logger.warning(f"❌ 任务失败: {task_id} - {error}")
            return True
        return False

    def get_pending_tasks(self) -> List[A2ATaskEntry]:
        """获取待处理任务"""
        return list(self._pending.values())

    def get_completed_tasks(self) -> List[A2ATaskEntry]:
        """获取已完成任务"""
        return list(self._completed.values())

    def get_tasks_by_agent(self, agent_name: str) -> List[A2ATaskEntry]:
        """获取指定 Agent 的任务"""
        return [t for t in self._tasks if t.to_agent == agent_name]

    def to_state(self) -> List[Dict[str, Any]]:
        """转换为 State 格式"""
        return [entry.to_dict() for entry in self._tasks]

    @classmethod
    def from_state(cls, state: List[Dict[str, Any]]) -> "A2ATaskBus":
        """从 State 创建"""
        bus = cls()
        for entry_dict in state:
            entry = A2ATaskEntry.from_dict(entry_dict)
            bus._tasks.append(entry)
            if entry.status == "completed" or entry.status == "failed":
                bus._completed[entry.task_id] = entry
            else:
                bus._pending[entry.task_id] = entry
        return bus


class FinancialAgentState(TypedDict, total=False):
    """
    金融专家 Agent 状态

    LangGraph State 定义，包含：
    1. 对话消息历史
    2. A2A 任务总线
    3. 当前 Agent 信息
    4. Agent 执行结果
    5. 路由决策
    """
    messages: List[Dict[str, Any]]
    a2a_task_bus: List[Dict[str, Any]]
    current_agent: Optional[str]
    agent_results: Dict[str, Any]
    routing_decision: Optional[Dict[str, Any]]
    context: Dict[str, Any]
    user_query: str
    intent: Optional[Dict[str, Any]]
    available_agents: List[Dict[str, Any]]


def create_initial_state(user_query: str) -> FinancialAgentState:
    """
    创建初始状态

    Args:
        user_query: 用户查询

    Returns:
        初始化的状态字典
    """
    return FinancialAgentState(
        messages=[],
        a2a_task_bus=[],
        current_agent=None,
        agent_results={},
        routing_decision=None,
        context={},
        user_query=user_query,
        intent=None,
        available_agents=[]
    )


def add_message_to_state(
    state: FinancialAgentState,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> FinancialAgentState:
    """
    向状态添加消息

    Args:
        state: 当前状态
        role: 消息角色（user/assistant/system）
        content: 消息内容
        metadata: 附加元数据

    Returns:
        更新后的状态
    """
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": metadata or {}
    }
    state["messages"] = state.get("messages", []) + [message]
    return state


def submit_a2a_task(
    state: FinancialAgentState,
    to_agent: str,
    message: Union[str, Dict[str, Any]],
    from_agent: str = "orchestrator"
) -> FinancialAgentState:
    """
    向状态提交 A2A 任务

    Args:
        state: 当前状态
        to_agent: 目标 Agent
        message: 任务消息
        from_agent: 来源 Agent

    Returns:
        更新后的状态
    """
    bus = A2ATaskBus.from_state(state.get("a2a_task_bus", []))
    task_id = bus.submit_task(to_agent, message, from_agent)
    state["a2a_task_bus"] = bus.to_state()
    return state


def complete_a2a_task(
    state: FinancialAgentState,
    task_id: str,
    result: Any
) -> FinancialAgentState:
    """
    标记 A2A 任务完成

    Args:
        state: 当前状态
        task_id: 任务 ID
        result: 执行结果

    Returns:
        更新后的状态
    """
    bus = A2ATaskBus.from_state(state.get("a2a_task_bus", []))
    bus.complete_task(task_id, result)
    state["a2a_task_bus"] = bus.to_state()

    entry = bus.get_task(task_id)
    if entry:
        state["agent_results"][entry.to_agent] = result

    return state


def get_pending_a2a_tasks(state: FinancialAgentState) -> List[A2ATaskEntry]:
    """获取待处理的 A2A 任务"""
    bus = A2ATaskBus.from_state(state.get("a2a_task_bus", []))
    return bus.get_pending_tasks()


def enrich_state_with_agents(
    state: FinancialAgentState,
    registry: Any,
    include_cards: bool = True
) -> FinancialAgentState:
    """
    使用 AgentRegistry 丰富状态

    Args:
        state: 当前状态
        registry: AgentRegistry 实例
        include_cards: 是否包含完整的 AgentCard

    Returns:
        丰富后的状态
    """
    try:
        all_agents = registry.list_all_agents()

        agent_info = []
        for card in all_agents:
            if include_cards:
                agent_info.append({
                    "name": card.name,
                    "description": card.description,
                    "skills": [{"id": s.id, "name": s.name} for s in card.skills] if card.skills else [],
                    "url": card.url,
                    "card": card.model_dump() if hasattr(card, 'model_dump') else {}
                })
            else:
                agent_info.append({
                    "name": card.name,
                    "description": card.description,
                    "skills": [s.id for s in card.skills] if card.skills else []
                })

        state["available_agents"] = agent_info
        logger.info(f"📋 状态已丰富: {len(agent_info)} 个 Agent")

    except Exception as e:
        logger.error(f"❌ 丰富状态失败: {e}")
        state["available_agents"] = []

    return state