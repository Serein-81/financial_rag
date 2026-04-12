"""
A2A Transport Layer

A2A 协议传输层实现
支持本地传输（复用 message_bus）和 HTTP 传输（跨服务通信）
"""

from .base import (
    TransportConfig,
    TransportType,
    AgentTransport,
    TransportError
)
from .local_transport import LocalAgentTransport
from .http_transport import HttpAgentTransport
from .manager import TransportManager, get_transport_manager, shutdown_transport_manager

__all__ = [
    "TransportConfig",
    "TransportType", 
    "AgentTransport",
    "TransportError",
    "LocalAgentTransport",
    "HttpAgentTransport",
    "TransportManager",
    "get_transport_manager",
    "shutdown_transport_manager",
]
