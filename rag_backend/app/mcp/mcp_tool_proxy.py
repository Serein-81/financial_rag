"""
MCP 工具代理

将 MCP 远程工具包装成本地 LangChain 工具
让 Agent 可以通过统一的接口调用本地工具和 MCP 工具
"""

import os
import logging
from typing import Any, Dict, Optional
from langchain_core.tools import tool

from app.agent_framework.tools.tool_router import get_mcp_tools, TOOL_ROUTING_CONFIG

logger = logging.getLogger(__name__)


class MCPToolProxy:
    """
    MCP 工具代理
    
    负责连接 MCP 服务器并提供工具调用接口
    """
    
    _instance: Optional["MCPToolProxy"] = None
    _client_manager = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_client(self):
        """获取 MCP 客户端"""
        if self._client_manager is None:
            from app.mcp.client_manager import MCPClientManager, MCP_SERVER_URL, MCP_API_KEY, MCP_TIMEOUT
            
            if not MCP_SERVER_URL:
                logger.warning("MCP_SERVER_URL 未配置，MCP 工具将不可用")
                return None
            
            self._client_manager = MCPClientManager(
                server_url=MCP_SERVER_URL,
                api_key=MCP_API_KEY,
                timeout=MCP_TIMEOUT
            )
            try:
                await self._client_manager.connect()
                logger.info(f"✅ MCP 工具代理已连接到 {MCP_SERVER_URL}")
            except Exception as e:
                logger.error(f"❌ MCP 连接失败: {e}")
                self._client_manager = None
                return None
        
        return self._client_manager
    
    async def call_tool(self, tool_name: str, **kwargs) -> str:
        """
        调用 MCP 工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            工具执行结果
        """
        client = await self.get_client()
        if client is None:
            return f"错误: MCP 服务不可用，请检查 MCP_SERVER_URL 配置"
        
        try:
            result = await client.call_tool(tool_name, **kwargs)
            return result
        except Exception as e:
            logger.error(f"MCP 工具调用失败: {tool_name} - {e}")
            return f"错误: 调用 {tool_name} 失败 - {str(e)}"
    
    async def close(self):
        """关闭 MCP 连接"""
        if self._client_manager:
            await self._client_manager.disconnect()
            self._client_manager = None


_mcp_proxy: Optional[MCPToolProxy] = None


async def get_mcp_proxy() -> MCPToolProxy:
    """获取 MCP 代理单例"""
    global _mcp_proxy
    if _mcp_proxy is None:
        _mcp_proxy = MCPToolProxy()
    return _mcp_proxy


def create_mcp_tool_wrapper(tool_name: str, tool_config: Dict) -> Any:
    """
    为 MCP 工具创建 LangChain @tool 装饰器包装器
    
    Args:
        tool_name: 工具名称
        tool_config: 工具配置
        
    Returns:
        LangChain 工具函数
    """
    description = tool_config.get("description", "")
    input_params = tool_config.get("input_params", [])
    
    param_str = ", ".join([f"{p}: str" for p in input_params]) if input_params else ""
    
    async def mcp_tool_func(**kwargs) -> str:
        """MCP 工具包装函数"""
        proxy = await get_mcp_proxy()
        result = await proxy.call_tool(tool_name, **kwargs)
        return result
    
    mcp_tool_func.__name__ = tool_name
    mcp_tool_func.__doc__ = description
    
    return tool(description=description)(mcp_tool_func)


async def get_all_mcp_tools_as_langchain_tools() -> list:
    """
    获取所有 MCP 工具作为 LangChain 工具列表
    
    Returns:
        LangChain 工具列表
    """
    mcp_tools = get_mcp_tools()
    langchain_tools = []
    
    for tool_name in mcp_tools:
        config = TOOL_ROUTING_CONFIG.get(tool_name)
        if config:
            try:
                lc_tool = create_mcp_tool_wrapper(tool_name, config)
                langchain_tools.append(lc_tool)
                logger.info(f"✅ 注册 MCP 工具: {tool_name}")
            except Exception as e:
                logger.error(f"❌ 注册 MCP 工具失败: {tool_name} - {e}")
    
    return langchain_tools


def get_mcp_tools_info() -> list:
    """
    获取 MCP 工具信息列表（用于 System Prompt）
    
    Returns:
        工具信息列表
    """
    tools_info = []
    for tool_name in get_mcp_tools():
        config = TOOL_ROUTING_CONFIG.get(tool_name)
        if config:
            tools_info.append({
                "name": tool_name,
                "description": config.get("description", ""),
                "category": "mcp",
                "input_params": config.get("input_params", []),
                "example": config.get("example", ""),
            })
    return tools_info
