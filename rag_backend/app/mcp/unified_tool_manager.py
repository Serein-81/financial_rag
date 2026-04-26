"""
MCP 统一工具管理器

统一管理所有 MCP 工具：
1. 本地 STDIO MCP（访问本地数据库）
2. 云端 MCP HTTP（访问外部 API）

云端 MCP 连接失败时，自动回退到本地 MCP Server
"""

import logging
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class UnifiedToolManager:
    """
    MCP 统一工具管理器
    
    特性：
    1. 自动识别工具类型（本地/云端）
    2. 云端连接失败自动回退到本地 MCP Server
    3. 统一的工具调用接口
    4. 支持 LangChain @tool 装饰器
    """
    
    def __init__(self):
        self._local_tools: Dict[str, callable] = {}
        self._cloud_tools: Dict[str, callable] = {}
        self._initialized = False
    
    def register_local_tool(self, name: str, func: callable):
        """注册本地 STDIO MCP 工具"""
        self._local_tools[name] = func
        logger.debug(f"注册本地工具: {name}")
    
    def register_cloud_tool(self, name: str, func: callable):
        """注册云端 MCP HTTP 工具"""
        self._cloud_tools[name] = func
        logger.debug(f"注册云端工具: {name}")
    
    def get_tool(self, name: str) -> Optional[callable]:
        """获取工具函数（优先本地）"""
        if name in self._local_tools:
            return self._local_tools[name]
        if name in self._cloud_tools:
            return self._cloud_tools[name]
        return None
    
    def list_tools(self) -> Dict[str, List[str]]:
        """列出所有工具"""
        return {
            "local": list(self._local_tools.keys()),
            "cloud": list(self._cloud_tools.keys()),
            "all": list(self._local_tools.keys()) + list(self._cloud_tools.keys())
        }
    
    async def call_tool(self, name: str, **kwargs) -> Any:
        """统一工具调用接口
        
        优先调用本地工具，云端连接失败时尝试本地 MCP Server
        """
        tool = self.get_tool(name)
        if not tool:
            return {
                "status": "error",
                "error": f"工具不存在: {name}",
                "available_tools": self.list_tools()["all"]
            }
        
        try:
            result = await tool(**kwargs)
            return result
        except Exception as e:
            logger.error(f"工具 {name} 执行失败: {e}", exc_info=True)
            
            if name in self._cloud_tools:
                logger.warning(f"云端工具 {name} 失败，尝试本地 MCP Server...")
                return await self._fallback_to_local_mcp(name, **kwargs)
            
            return {
                "status": "error",
                "error": f"工具执行失败: {str(e)}",
                "tool": name
            }
    
    async def _fallback_to_local_mcp(self, tool_name: str, **kwargs) -> Any:
        """回退到本地 MCP Server"""
        try:
            from app.mcp.mcp_factory import mcp_factory
            
            logger.info(f"使用本地 MCP Server 调用工具: {tool_name}")
            result = await mcp_factory.call_tool(tool_name, **kwargs)
            
            if result.success:
                return result.data
            else:
                return {
                    "status": "error",
                    "error": f"本地 MCP Server 调用失败: {result.error}",
                    "fallback": "local_mcp"
                }
        except Exception as e:
            logger.error(f"本地 MCP Server 回退失败: {e}", exc_info=True)
            return {
                "status": "error",
                "error": f"工具执行失败，云端和本地 MCP 都不可用: {str(e)}",
                "fallback_attempted": True
            }


unified_tool_manager = UnifiedToolManager()


def register_all_unified_tools():
    """注册所有统一工具"""
    logger.info("🔧 初始化统一 MCP 工具管理器...")
    
    register_local_mcp_tools()
    register_cloud_mcp_tools()
    
    tool_lists = unified_tool_manager.list_tools()
    logger.info(f"✅ 工具注册完成：本地 {len(tool_lists['local'])} 个，云端 {len(tool_lists['cloud'])} 个")
    
    return unified_tool_manager


def register_local_mcp_tools():
    """注册本地 STDIO MCP 工具
    
    本地工具：访问本地数据库的工具
    """
    from app.mcp import get_all_mcp_tools
    
    try:
        local_tools = get_all_mcp_tools()
        for tool_func in local_tools:
            unified_tool_manager.register_local_tool(tool_func.name, tool_func)
            logger.debug(f"✅ 注册本地 STDIO MCP 工具: {tool_func.name}")
    except Exception as e:
        logger.error(f"注册本地 MCP 工具失败: {e}", exc_info=True)


def register_cloud_mcp_tools():
    """注册云端 MCP HTTP 工具
    
    云端工具：访问外部 API 的工具
    """
    pass


def get_unified_tool_manager() -> UnifiedToolManager:
    """获取统一工具管理器单例"""
    if not unified_tool_manager._initialized:
        register_all_unified_tools()
        unified_tool_manager._initialized = True
    return unified_tool_manager
