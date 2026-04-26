"""
A2A Transport Layer

A2A 协议传输层实现
支持本地传输（复用 message_bus）和 HTTP 传输（跨服务通信）
支持策略模式切换（GRAPH_STATE/HTTP/LOCAL）
"""

from .base import (
    TransportConfig,
    TransportType,
    AgentTransport,
    TransportError
)
from .strategy import (
    TransportMode,
    TransportStrategy,
    TransportEnvelope
)
from .langgraph_transport import (
    LangGraphTransport,
    StateBlackboard
)
from .http_transport import HttpAgentTransport
from .local_transport import LocalAgentTransport
from .manager import TransportManager, get_transport_manager, shutdown_transport_manager
from .factory import (
    TransportStrategyFactory,
    get_transport_factory,
    create_default_strategy,
    build_prompt_with_agent_cards,
    A2ATaskBusContext
)

__all__ = [
    "TransportConfig",
    "TransportType",
    "AgentTransport",
    "TransportError",
    "TransportMode",
    "TransportStrategy",
    "TransportEnvelope",
    "LangGraphTransport",
    "StateBlackboard",
    "LocalAgentTransport",
    "HttpAgentTransport",
    "TransportManager",
    "get_transport_manager",
    "shutdown_transport_manager",
    "TransportStrategyFactory",
    "get_transport_factory",
    "create_default_strategy",
    "build_prompt_with_agent_cards",
    "A2ATaskBusContext",
]
