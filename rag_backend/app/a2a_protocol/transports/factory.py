"""
Transport Strategy Factory

传输策略工厂类
根据配置创建对应的传输策略实例
支持运行时切换传输模式
"""

import logging
from typing import Optional, Dict, Any, List
from functools import lru_cache

from .strategy import TransportStrategy, TransportMode, TransportEnvelope
from .langgraph_transport import LangGraphTransport, StateBlackboard
from .http_transport import HttpAgentTransport
from .local_transport import LocalAgentTransport
from .base import TransportConfig, TransportType
from ..registry import AgentRegistry
from app.core.config import settings

logger = logging.getLogger(__name__)


class TransportStrategyFactory:
    """
    传输策略工厂

    功能：
    1. 根据配置创建对应模式的传输策略
    2. 维护传输策略实例（单例）
    3. 支持运行时切换模式

    使用方式：
        factory = TransportStrategyFactory()
        strategy = factory.create_strategy()
        result = await strategy.send_message(...)
    """

    _instance: Optional["TransportStrategyFactory"] = None

    @classmethod
    def get_instance(cls) -> "TransportStrategyFactory":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = TransportStrategyFactory()
        return cls._instance

    def __init__(self):
        self._current_strategy: Optional[TransportStrategy] = None
        self._strategy_cache: Dict[str, TransportStrategy] = {}
        self._registry = AgentRegistry.get_instance()
        self._blackboard: Optional[StateBlackboard] = None
        logger.info("🏭 TransportStrategyFactory 初始化")

    @property
    def current_mode(self) -> TransportMode:
        """获取当前传输模式"""
        return self._current_strategy.mode if self._current_strategy else TransportMode.GRAPH_STATE

    @property
    def current_strategy(self) -> Optional[TransportStrategy]:
        """获取当前传输策略实例"""
        return self._current_strategy

    def create_strategy(
        self,
        mode: Optional[str] = None,
        use_cache: bool = True
    ) -> TransportStrategy:
        """
        创建传输策略实例

        Args:
            mode: 传输模式（从环境变量读取或显式指定）
            use_cache: 是否使用缓存实例

        Returns:
            对应模式的传输策略实例
        """
        target_mode = self._resolve_mode(mode)

        if use_cache and target_mode.value in self._strategy_cache:
            logger.info(f"📦 使用缓存的策略: {target_mode.value}")
            return self._strategy_cache[target_mode.value]

        strategy = self._create_strategy_instance(target_mode)
        self._strategy_cache[target_mode.value] = strategy

        if self._current_strategy is None:
            self._current_strategy = strategy

        return strategy

    def _resolve_mode(self, mode: Optional[str] = None) -> TransportMode:
        """解析传输模式"""
        if mode:
            try:
                return TransportMode(mode.lower())
            except ValueError:
                logger.warning(f"⚠️ 无效的传输模式: {mode}，使用配置值")
                mode = None

        config_mode = getattr(settings, "A2A_TRANSPORT_MODE", "graph_state")
        try:
            return TransportMode(config_mode.lower())
        except ValueError:
            logger.warning(f"⚠️ 配置无效的传输模式: {config_mode}，默认使用 graph_state")
            return TransportMode.GRAPH_STATE

    def _create_strategy_instance(self, mode: TransportMode) -> TransportStrategy:
        """根据模式创建策略实例"""
        logger.info(f"🔧 创建传输策略实例: {mode.value}")

        if mode == TransportMode.GRAPH_STATE:
            if self._blackboard is None:
                self._blackboard = StateBlackboard()
            strategy = LangGraphTransport(state_blackboard=self._blackboard)
            self._register_default_agents(strategy)
            return strategy

        elif mode == TransportMode.HTTP:
            config = TransportConfig(
                transport_type=TransportType.HTTP,
                url=getattr(settings, "A2A_HTTP_BASE_URL", "http://localhost:8000"),
                timeout=getattr(settings, "A2A_HTTP_TIMEOUT", 30.0),
                retry_times=getattr(settings, "A2A_HTTP_RETRY_TIMES", 3)
            )
            return HttpAgentTransport(config)

        elif mode == TransportMode.LOCAL:
            config = TransportConfig(transport_type=TransportType.LOCAL)
            return LocalAgentTransport(config)

        raise ValueError(f"不支持的传输模式: {mode}")

    def _register_default_agents(self, strategy: LangGraphTransport) -> None:
        """注册默认 Agent 处理函数到状态黑板"""
        try:
            agents = self._registry.list_all_agents()
            for card in agents:
                logger.info(f"✅ 注册 Agent 到状态黑板: {card.name}")
        except Exception as e:
            logger.warning(f"⚠️ 注册默认 Agent 失败: {e}")

    def switch_mode(self, new_mode: str) -> TransportStrategy:
        """
        切换传输模式

        Args:
            new_mode: 新的传输模式

        Returns:
            新的传输策略实例
        """
        logger.info(f"🔄 切换传输模式: {self.current_mode.value} -> {new_mode}")
        self._current_strategy = self.create_strategy(mode=new_mode)
        return self._current_strategy

    def get_blackboard(self) -> Optional[StateBlackboard]:
        """获取状态黑板实例"""
        return self._blackboard

    def reset(self) -> None:
        """重置工厂状态"""
        self._current_strategy = None
        self._strategy_cache.clear()
        self._blackboard = None
        logger.info("🔄 TransportStrategyFactory 已重置")


def get_transport_factory() -> TransportStrategyFactory:
    """获取传输策略工厂实例"""
    return TransportStrategyFactory.get_instance()


def create_default_strategy() -> TransportStrategy:
    """创建默认传输策略（使用配置的模式）"""
    factory = get_transport_factory()
    return factory.create_strategy()


def build_prompt_with_agent_cards(cards: List[Any]) -> str:
    """
    使用 AgentCard 构建动态提示

    用于 Orchestrator 节点中动态生成 LLM Prompt

    Args:
        cards: AgentCard 列表

    Returns:
        格式化的提示字符串
    """
    if not cards:
        return "当前无可用专家Agent。"

    header = "当前可用的专家智能体：\n\n"
    agent_lines = []

    for i, card in enumerate(cards, 1):
        skills = ", ".join([s.name for s in card.skills]) if card.skills else "通用能力"
        line = f"{i}. **{card.name}**：{card.description}\n   技能：{skills}"
        agent_lines.append(line)

    footer = "\n请根据用户问题，选择最合适的专家智能体处理。"

    return header + "\n".join(agent_lines) + footer


class A2ATaskBusContext:
    """
    A2A 任务总线上下文

    用于 LangGraph State 中管理 A2A 任务队列
    提供任务提交、查询、结果回写等操作
    """

    def __init__(self, strategy: TransportStrategy):
        self._strategy = strategy
        self._pending_tasks: Dict[str, Any] = {}

    async def submit_task(
        self,
        to_agent: str,
        message: Dict[str, Any],
        tenant_id: Optional[str] = None
    ) -> str:
        """
        提交任务到总线

        Args:
            to_agent: 目标 Agent
            message: 任务消息
            tenant_id: 租户 ID

        Returns:
            任务 ID
        """
        result = await self._strategy.send_message(
            to_agent=to_agent,
            message=message,
            tenant_id=tenant_id
        )
        task_id = result.get("task_id")
        if task_id:
            self._pending_tasks[task_id] = {
                "to_agent": to_agent,
                "status": "queued"
            }
        return task_id

    def get_pending_tasks(self) -> Dict[str, Any]:
        """获取待处理任务"""
        return self._pending_tasks.copy()

    def mark_completed(self, task_id: str, result: Any) -> None:
        """标记任务完成"""
        if task_id in self._pending_tasks:
            self._pending_tasks[task_id]["status"] = "completed"
            self._pending_tasks[task_id]["result"] = result

    def mark_failed(self, task_id: str, error: str) -> None:
        """标记任务失败"""
        if task_id in self._pending_tasks:
            self._pending_tasks[task_id]["status"] = "failed"
            self._pending_tasks[task_id]["error"] = error