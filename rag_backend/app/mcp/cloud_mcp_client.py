"""
云端 MCP HTTP 客户端

连接云端 MCP 服务器
云端连接失败时返回错误，由 MCP 路由器决定是否回退到本地
"""

import logging
import os
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class CloudMCPClient:
    """
    云端 MCP HTTP 客户端
    
    连接到云端 MCP 服务器（如 mcp_server 文件夹部署的云端服务）
    """
    
    def __init__(
        self,
        server_url: str = None,
        api_key: str = None,
        timeout: int = 120
    ):
        self.server_url = (server_url or os.getenv("MCP_SERVER_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("MCP_API_KEY", "")
        self.timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        } if self.api_key else {}
        self._connected = False
        self._tools: List[Dict[str, Any]] = []
    
    @property
    def is_configured(self) -> bool:
        """检查是否配置了云端服务器"""
        return bool(self.server_url)
    
    async def connect(self) -> bool:
        """连接到云端 MCP 服务器"""
        if not self.is_configured:
            logger.warning("⚠️ 云端 MCP 服务器未配置")
            return False
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.server_url}/health")
                if response.status_code == 200:
                    self._connected = True
                    logger.info(f"✅ 云端 MCP 连接成功: {self.server_url}")
                    return True
                else:
                    logger.warning(f"⚠️ 云端 MCP 健康检查失败: {response.status_code}")
                    return False
        except Exception as e:
            logger.warning(f"⚠️ 无法连接到云端 MCP: {e}")
            self._connected = False
            return False
    
    async def disconnect(self):
        """断开连接"""
        self._connected = False
        logger.info("云端 MCP 客户端已断开")
    
    async def call_tool(self, tool_name: str, **kwargs) -> 'MCPToolResult':
        """调用云端 MCP 工具"""
        from app.mcp.mcp_factory import MCPToolResult
        
        if not self._connected:
            connected = await self.connect()
            if not connected:
                return MCPToolResult(
                    success=False,
                    data=None,
                    error=f"无法连接到云端 MCP 服务器: {self.server_url}"
                )
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.server_url}/mcp/call",
                    headers=self._headers,
                    json={"tool_name": tool_name, "arguments": kwargs}
                )
                
                if response.status_code != 200:
                    return MCPToolResult(
                        success=False,
                        data=None,
                        error=f"HTTP错误: {response.status_code}"
                    )
                
                result = response.json()
                
                if "error" in result:
                    return MCPToolResult(
                        success=False,
                        data=None,
                        error=result["error"]
                    )
                
                return MCPToolResult(
                    success=True,
                    data=result.get("result", result)
                )
                
        except httpx.TimeoutException:
            return MCPToolResult(
                success=False,
                data=None,
                error=f"工具调用超时: {tool_name}"
            )
        except Exception as e:
            logger.error(f"云端 MCP 调用失败: {e}", exc_info=True)
            return MCPToolResult(
                success=False,
                data=None,
                error=str(e)
            )
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """列出云端可用工具"""
        if not self._connected:
            await self.connect()
        
        if not self._tools:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        f"{self.server_url}/tools",
                        headers=self._headers
                    )
                    if response.status_code == 200:
                        data = response.json()
                        self._tools = data.get("tools", [])
            except Exception as e:
                logger.warning(f"获取云端工具列表失败: {e}")
        
        return self._tools


cloud_mcp_client = CloudMCPClient()
