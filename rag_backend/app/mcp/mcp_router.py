"""
MCP 路由器

根据工具类型自动路由到对应的 MCP 服务器
自动使用装饰器元数据获取工具信息
"""

import logging
import os
from typing import Dict, Any, Optional

from app.mcp.decorators import (
    ToolSource,
    get_tool_metadata,
    get_tool_source,
    get_registry,
)

logger = logging.getLogger(__name__)


class MCPRouter:
    """
    MCP 路由器
    
    功能：
    1. 自动使用 @local_tool/@cloud_tool 装饰器元数据
    2. 根据工具类型自动路由到本地/云端
    3. 云端失败自动回退到本地实现
    """
    
    def __init__(self):
        self._initialized = False
    
    def _ensure_initialized(self):
        """确保初始化"""
        if not self._initialized:
            self._refresh_routing()
            self._initialized = True
    
    def _refresh_routing(self):
        """刷新路由配置"""
        registry = get_registry()
        logger.info(f"🔄 MCP 路由器刷新配置，共 {len(registry)} 个工具")
    
    def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """获取工具信息（描述、参数等）"""
        self._ensure_initialized()
        
        registry = get_registry()
        if tool_name in registry:
            meta = registry[tool_name]
            return {
                "name": meta.name,
                "description": meta.description,
                "source": meta.source.value,
                "tags": meta.tags,
                "timeout": meta.timeout
            }
        
        return {"name": tool_name, "description": "", "source": "unknown"}
    
    def get_all_tools_info(self) -> Dict[str, Any]:
        """获取所有工具信息"""
        self._ensure_initialized()
        
        registry = get_registry()
        
        local_tools = []
        cloud_tools = []
        
        for name, meta in registry.items():
            tool_info = {
                "name": meta.name,
                "description": meta.description,
                "tags": meta.tags
            }
            if meta.source == ToolSource.LOCAL:
                local_tools.append(tool_info)
            else:
                cloud_tools.append(tool_info)
        
        return {
            "local_tools": local_tools,
            "cloud_tools": cloud_tools,
            "total_count": len(registry)
        }
    
    async def call_tool(self, tool_name: str, **kwargs) -> Any:
        """统一工具调用接口
        
        自动路由：
        1. 根据装饰器元数据判断工具类型
        2. @local_tool → 本地 STDIO
        3. @cloud_tool → 云端 HTTP，失败回退本地
        """
        self._ensure_initialized()
        
        registry = get_registry()
        if tool_name not in registry:
            return {
                "status": "error",
                "error": f"工具不存在: {tool_name}",
                "available_tools": list(registry.keys())
            }
        
        meta = registry[tool_name]
        
        try:
            if meta.source == ToolSource.LOCAL:
                return await self._call_local(tool_name, **kwargs)
            else:
                return await self._call_with_fallback(tool_name, **kwargs)
        except Exception as e:
            logger.error(f"工具 {tool_name} 调用失败: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "tool": tool_name,
                "source": meta.source.value
            }
    
    async def _call_local(self, tool_name: str, **kwargs) -> Any:
        """调用本地工具"""
        try:
            from app.mcp import get_all_local_tools
            
            local_tools = get_all_local_tools()
            
            for tool_func in local_tools:
                if tool_func.name == tool_name:
                    result = await tool_func(**kwargs)
                    return result
            
            return {
                "status": "error",
                "error": f"本地工具未找到: {tool_name}"
            }
        except Exception as e:
            logger.error(f"本地工具调用失败: {tool_name} - {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "source": "local"
            }
    
    async def _call_with_fallback(self, tool_name: str, **kwargs) -> Any:
        """云端调用，失败回退本地"""
        try:
            result = await self._call_cloud(tool_name, **kwargs)
            if result.get("status") == "success":
                return result
        except Exception as e:
            logger.warning(f"云端调用失败，尝试本地: {e}")
        
        logger.info(f"回退到本地实现: {tool_name}")
        return await self._call_local(tool_name, **kwargs)
    
    async def _call_cloud(self, tool_name: str, **kwargs) -> Any:
        """调用云端 MCP"""
        try:
            from app.mcp.cloud_mcp_client import cloud_mcp_client
            
            if not cloud_mcp_client.is_configured:
                raise Exception("云端 MCP 未配置")
            
            result = await cloud_mcp_client.call_tool(tool_name, **kwargs)
            
            if result.success:
                return result.data
            else:
                raise Exception(result.error)
        except Exception as e:
            logger.warning(f"云端 MCP 调用失败: {e}")
            raise


mcp_router = MCPRouter()
