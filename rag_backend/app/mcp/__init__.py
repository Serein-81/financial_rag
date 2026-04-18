"""
MCP 模块 - 远程工具服务客户端

支持本地/云端模式切换：
- 本地模式：直接调用本地 MCP 服务器
- 云端模式：调用远程云端 MCP 服务器

使用方法：
1. 在 .env 中设置 MCP_MODE=local 或 MCP_MODE=cloud
2. 使用 mcp_factory 统一调用
"""

from app.mcp.client_manager import (
    MCPClientManager,
    MCPToolInfo,
    MCPError,
    MCPTimeoutError,
    MCPConnectionError,
)

from app.mcp.mcp_factory import (
    MCPClientFactory,
    MCPMode,
    MCPToolResult,
    BaseMCPClient,
    LocalMCPClient,
    CloudMCPClient,
    HybridMCPClient,
    mcp_factory,
)

__all__ = [
    # 客户端管理器
    "MCPClientManager",
    "MCPToolInfo",
    "MCPError",
    "MCPTimeoutError",
    "MCPConnectionError",
    # 工厂类
    "MCPClientFactory",
    "MCPMode",
    "MCPToolResult",
    "BaseMCPClient",
    "LocalMCPClient",
    "CloudMCPClient",
    "HybridMCPClient",
    "mcp_factory",
]
