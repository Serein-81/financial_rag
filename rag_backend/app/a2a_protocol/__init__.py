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
    get_transport_manager
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
]
