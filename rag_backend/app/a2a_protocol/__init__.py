"""
A2A Protocol Implementation

Google Agent2Agent Protocol 实现
用于多智能体系统的标准化通信
"""

from .agent_card import AgentCard, AgentSkill, AgentCapabilities, AgentCardBuilder
from .registry import AgentRegistry, AgentType, agent_registry
from .server import A2AServer
from .client import A2AClient
from .wrapper import AgentWrapper, AgentWrapperConfig
from .dispatcher import HybridDispatcher, DispatchStrategy, DispatchResult, MultiAgentResult
from .models import (
    Task,
    TaskStatus,
    Message,
    MessagePart,
    TextPart,
    DataPart,
    TaskSubmitParams,
    TaskGetParams,
    TaskSendSubscribeParams,
    TaskStatusUpdateEvent
)
from .transports import (
    TransportConfig,
    TransportType,
    AgentTransport,
    TransportError,
    LocalAgentTransport,
    HttpAgentTransport,
    TransportManager,
    get_transport_manager,
    TransportMode,
    TransportStrategy,
    TransportEnvelope,
    LangGraphTransport,
    StateBlackboard,
    TransportStrategyFactory,
    get_transport_factory,
    create_default_strategy,
    build_prompt_with_agent_cards,
    A2ATaskBusContext
)
from .langgraph_state import (
    A2ATaskState,
    A2ATaskEntry,
    A2ATaskBus,
    FinancialAgentState,
    create_initial_state,
    add_message_to_state,
    submit_a2a_task,
    complete_a2a_task,
    get_pending_a2a_tasks,
    enrich_state_with_agents
)
from .orchestrator_node import (
    OrchestratorDecision,
    orchestrator_node,
    multi_agent_orchestrator_node,
    create_orchestrator_with_llm
)

__all__ = [
    "AgentCard",
    "AgentSkill",
    "AgentCapabilities",
    "AgentCardBuilder",
    "AgentRegistry",
    "AgentType",
    "A2AServer",
    "A2AClient",
    "AgentWrapper",
    "AgentWrapperConfig",
    "HybridDispatcher",
    "DispatchStrategy",
    "DispatchResult",
    "MultiAgentResult",
    "Task",
    "TaskStatus",
    "Message",
    "MessagePart",
    "TextPart",
    "DataPart",
    "TaskSubmitParams",
    "TaskGetParams",
    "TaskSendSubscribeParams",
    "TaskStatusUpdateEvent",
    "TransportConfig",
    "TransportType",
    "AgentTransport",
    "TransportError",
    "LocalAgentTransport",
    "HttpAgentTransport",
    "TransportManager",
    "get_transport_manager",
    "agent_registry",
    "TransportMode",
    "TransportStrategy",
    "TransportEnvelope",
    "LangGraphTransport",
    "StateBlackboard",
    "TransportStrategyFactory",
    "get_transport_factory",
    "create_default_strategy",
    "build_prompt_with_agent_cards",
    "A2ATaskBusContext",
    "A2ATaskState",
    "A2ATaskEntry",
    "A2ATaskBus",
    "FinancialAgentState",
    "create_initial_state",
    "add_message_to_state",
    "submit_a2a_task",
    "complete_a2a_task",
    "get_pending_a2a_tasks",
    "enrich_state_with_agents",
    "OrchestratorDecision",
    "orchestrator_node",
    "multi_agent_orchestrator_node",
    "create_orchestrator_with_llm",
]
