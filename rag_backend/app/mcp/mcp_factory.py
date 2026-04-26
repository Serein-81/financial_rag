"""
MCP 客户端工厂 - 支持本地/云端/STDIO 三种模式

使用方法：
1. 在 .env 中设置 MCP_MODE=local/cloud/stdio
2. 本地模式：需要本地启动 MCP HTTP 服务器
3. 云端模式：连接远程 MCP HTTP 服务器
4. STDIO 模式：启动本地 MCP STDIO 服务器，通过子进程通信

环境变量配置：
- MCP_MODE: 运行模式 (local/cloud/stdio)
- MCP_LOCAL_URL: 本地 HTTP MCP 服务器地址
- MCP_SERVER_URL: 云端 MCP 服务器地址
- MCP_API_KEY: API 密钥
"""

import os
import httpx
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MCPMode(Enum):
    """MCP 运行模式"""
    LOCAL = "local"
    CLOUD = "cloud"
    STDIO = "stdio"
    AUTO = "auto"


@dataclass
class MCPToolResult:
    """MCP 工具调用结果"""
    success: bool
    data: Any
    error: Optional[str] = None


class BaseMCPClient:
    """MCP 客户端基类"""

    async def connect(self) -> None:
        raise NotImplementedError

    async def disconnect(self) -> None:
        raise NotImplementedError

    async def call_tool(self, tool_name: str, **kwargs) -> MCPToolResult:
        raise NotImplementedError

    async def list_tools(self) -> List[Dict[str, Any]]:
        raise NotImplementedError


class LocalMCPClient(BaseMCPClient):
    """本地 MCP HTTP 客户端"""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            logger.info("本地 MCP 客户端已连接")
            return

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/health")
                if response.status_code == 200:
                    self._connected = True
                    logger.info(f"✅ 本地 MCP HTTP 服务器连接成功: {self.base_url}")
                else:
                    raise ConnectionError(f"健康检查失败: {response.status_code}")
        except (ValueError, KeyError) as e:
            logger.warning(f"⚠️ 本地 MCP HTTP 服务器未运行(数据错误): {e}")
            raise ConnectionError(f"无法连接到本地 MCP 服务器: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"⚠️ 本地 MCP HTTP 服务器未运行(IO错误): {e}")
            raise ConnectionError(f"无法连接到本地 MCP 服务器: {e}")
        except Exception as e:
            logger.warning(f"⚠️ 本地 MCP HTTP 服务器未运行: {e}")
            raise ConnectionError(f"无法连接到本地 MCP 服务器: {e}")

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("本地 MCP HTTP 客户端已断开")

    async def call_tool(self, tool_name: str, **kwargs) -> MCPToolResult:
        if not self._connected:
            await self.connect()

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.base_url}/mcp/call",
                    headers=self._headers,
                    json={"tool_name": tool_name, "arguments": kwargs}
                )
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    return MCPToolResult(success=False, data=None, error=result["error"])

                return MCPToolResult(success=True, data=result.get("result", result))
        except httpx.TimeoutException:
            return MCPToolResult(success=False, data=None, error=f"工具调用超时: {tool_name}")
        except (ValueError, KeyError) as e:
            return MCPToolResult(success=False, data=None, error=f"本地工具调用数据错误: {e}")
        except (OSError, IOError) as e:
            return MCPToolResult(success=False, data=None, error=f"本地工具调用IO错误: {e}")
        except Exception as e:
            return MCPToolResult(success=False, data=None, error=str(e))

    async def list_tools(self) -> List[Dict[str, Any]]:
        if not self._connected:
            await self.connect()

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.base_url}/tools", headers=self._headers)
            response.raise_for_status()
            data = response.json()
            return data.get("tools", [])


class CloudMCPClient(BaseMCPClient):
    """云端 MCP HTTP 客户端"""

    def __init__(self, server_url: str, api_key: str, timeout: int = 120):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self._connected = False
        self._tools: List[Dict[str, Any]] = []

    async def connect(self) -> None:
        if self._connected:
            logger.info("云端 MCP 客户端已连接")
            return

        logger.info(f"🔌 连接云端 MCP 服务器: {self.server_url}")

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.server_url}/health")
                response.raise_for_status()
        except (ValueError, KeyError) as e:
            raise ConnectionError(f"无法连接到云端 MCP 服务器(数据错误): {e}")
        except (OSError, IOError) as e:
            raise ConnectionError(f"无法连接到云端 MCP 服务器(IO错误): {e}")
        except Exception as e:
            raise ConnectionError(f"无法连接到云端 MCP 服务器: {e}")

        await self._load_tools()
        self._connected = True
        logger.info(f"✅ 云端 MCP 服务器连接成功，共 {len(self._tools)} 个工具")

    async def _load_tools(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.server_url}/tools",
                    headers=self._headers
                )
                response.raise_for_status()
                data = response.json()
                self._tools = data.get("tools", [])
        except (ValueError, KeyError) as e:
            logger.error(f"获取工具列表数据失败: {e}")
            self._tools = []
        except (OSError, IOError) as e:
            logger.error(f"获取工具列表IO失败: {e}")
            self._tools = []
        except Exception as e:
            logger.error(f"获取工具列表失败: {e}")
            self._tools = []

    async def disconnect(self) -> None:
        self._connected = False
        self._tools = []
        logger.info("云端 MCP 客户端已断开")

    async def call_tool(self, tool_name: str, **kwargs) -> MCPToolResult:
        if not self._connected:
            await self.connect()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.server_url}/mcp/call",
                    headers=self._headers,
                    json={"tool_name": tool_name, "arguments": kwargs}
                )
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    return MCPToolResult(success=False, data=None, error=result["error"])

                return MCPToolResult(success=True, data=result.get("result", result))
        except httpx.TimeoutException:
            return MCPToolResult(success=False, data=None, error=f"工具调用超时: {tool_name}")
        except (ValueError, KeyError) as e:
            return MCPToolResult(success=False, data=None, error=f"云端工具调用数据错误: {e}")
        except (OSError, IOError) as e:
            return MCPToolResult(success=False, data=None, error=f"云端工具调用IO错误: {e}")
        except Exception as e:
            return MCPToolResult(success=False, data=None, error=str(e))

    async def list_tools(self) -> List[Dict[str, Any]]:
        if not self._connected:
            await self.connect()
        return self._tools


class LocalMCPStdioClient(BaseMCPClient):
    """本地 MCP STDIO 客户端 - 通过子进程与 STDIO 服务器通信"""

    def __init__(
        self,
        server_command: str = None,
        working_directory: str = None
    ):
        from app.mcp.stdio_client import LocalMCPClient as StdioClient
        self._stdio_client = StdioClient(
            server_command=server_command,
            working_directory=working_directory
        )
        self._connected = False
        self._tools: List[Dict[str, Any]] = []

    async def connect(self) -> None:
        if self._connected:
            logger.info("本地 MCP STDIO 客户端已连接")
            return

        try:
            await self._stdio_client.connect()
            self._connected = True
            
            stdio_tools = self._stdio_client.list_tools()
            self._tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "source": "local_stdio"
                }
                for t in stdio_tools
            ]
            
            logger.info(f"✅ 本地 MCP STDIO 服务器连接成功，共 {len(self._tools)} 个工具")
        except Exception as e:
            logger.error(f"连接本地 MCP STDIO 服务器失败: {e}", exc_info=True)
            raise ConnectionError(f"无法连接到本地 MCP STDIO 服务器: {e}")

    async def disconnect(self) -> None:
        if self._connected:
            await self._stdio_client.disconnect()
            self._connected = False
            self._tools = []
            logger.info("本地 MCP STDIO 客户端已断开")

    async def call_tool(self, tool_name: str, **kwargs) -> MCPToolResult:
        if not self._connected:
            await self.connect()

        try:
            result = await self._stdio_client.call_tool(tool_name, **kwargs)
            return MCPToolResult(success=True, data=result, error=None)
        except Exception as e:
            logger.error(f"STDIO 工具调用失败: {tool_name} - {e}", exc_info=True)
            return MCPToolResult(success=False, data=None, error=str(e))

    async def list_tools(self) -> List[Dict[str, Any]]:
        if not self._connected:
            await self.connect()
        return self._tools


class HybridMCPClient(BaseMCPClient):
    """混合 MCP 客户端 - 同时管理本地 STDIO 和云端连接，优先使用本地 STDIO"""
    
    def __init__(self, stdio_command: str = None, working_directory: str = None,
                 cloud_url: str = "http://127.0.0.1:8080", cloud_key: str = "", timeout: int = 120):
        self.stdio_client = LocalMCPStdioClient(
            server_command=stdio_command,
            working_directory=working_directory
        )
        self.cloud_client = CloudMCPClient(
            server_url=cloud_url,
            api_key=cloud_key,
            timeout=timeout
        )
        self._stdio_connected = False
        self._cloud_connected = False
    
    async def connect(self) -> None:
        """连接两个服务器，优先本地 STDIO"""
        logger.info("🔄 混合模式：尝试连接本地 STDIO 和云端 MCP 服务器")
        
        self._stdio_connected = False
        self._cloud_connected = False
        
        try:
            await self.stdio_client.connect()
            self._stdio_connected = True
            logger.info("✅ 混合模式：本地 STDIO MCP 连接成功")
        except Exception as e:
            logger.warning(f"⚠️ 混合模式：本地 STDIO MCP 连接失败: {e}")
        
        try:
            await self.cloud_client.connect()
            self._cloud_connected = True
            logger.info("✅ 混合模式：云端 MCP 连接成功")
        except Exception as e:
            logger.warning(f"⚠️ 混合模式：云端 MCP 连接失败: {e}")
        
        if not self._stdio_connected and not self._cloud_connected:
            raise ConnectionError("无法连接到任何 MCP 服务器（本地和云端都失败）")
        
        logger.info(f"📊 混合模式连接状态：本地 STDIO={self._stdio_connected}, 云端={self._cloud_connected}")
    
    async def disconnect(self) -> None:
        """断开两个连接"""
        if self._stdio_connected:
            await self.stdio_client.disconnect()
            self._stdio_connected = False
        if self._cloud_connected:
            await self.cloud_client.disconnect()
            self._cloud_connected = False
        logger.info("混合模式：已断开所有连接")
    
    async def call_tool(self, tool_name: str, **kwargs) -> MCPToolResult:
        """调用工具：优先本地 STDIO，失败则使用云端"""
        if self._stdio_connected:
            try:
                result = await self.stdio_client.call_tool(tool_name, **kwargs)
                if result.success:
                    return result
                logger.warning(f"⚠️ 本地 STDIO 工具 {tool_name} 调用失败，尝试云端: {result.error}")
            except Exception as e:
                logger.warning(f"⚠️ 本地 STDIO 工具 {tool_name} 调用异常: {e}")
        
        if self._cloud_connected:
            logger.info(f"🔄 使用云端调用工具: {tool_name}")
            return await self.cloud_client.call_tool(tool_name, **kwargs)
        
        return MCPToolResult(
            success=False, 
            data=None, 
            error="无可用的 MCP 服务器（本地和云端都不可用）"
        )
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有工具：合并本地 STDIO 和云端的工具列表"""
        all_tools = []
        
        if self._stdio_connected:
            try:
                local_tools = await self.stdio_client.list_tools()
                for tool in local_tools:
                    tool["source"] = "local_stdio"
                    all_tools.append(tool)
                logger.info(f"📋 本地 STDIO 工具: {len(local_tools)} 个")
            except Exception as e:
                logger.warning(f"⚠️ 获取本地 STDIO 工具列表失败: {e}")
        
        if self._cloud_connected:
            try:
                cloud_tools = await self.cloud_client.list_tools()
                for tool in cloud_tools:
                    tool["source"] = "cloud"
                    all_tools.append(tool)
                logger.info(f"📋 云端工具: {len(cloud_tools)} 个")
            except Exception as e:
                logger.warning(f"⚠️ 获取云端工具列表失败: {e}")
        
        logger.info(f"📊 混合模式总计: {len(all_tools)} 个工具")
        return all_tools


class MCPClientFactory:
    """MCP 客户端工厂 - 根据配置自动选择模式"""

    _instance: Optional["MCPClientFactory"] = None
    _client: Optional[BaseMCPClient] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_mode(cls) -> MCPMode:
        """获取当前模式"""
        mode_str = os.getenv("MCP_MODE", "stdio").lower()
        try:
            return MCPMode(mode_str)
        except ValueError:
            logger.warning(f"无效的 MCP_MODE: {mode_str}，使用默认值 stdio")
            return MCPMode.STDIO

    @classmethod
    def is_local(cls) -> bool:
        """是否本地 HTTP 模式"""
        return cls.get_mode() == MCPMode.LOCAL

    @classmethod
    def is_cloud(cls) -> bool:
        """是否云端 HTTP 模式"""
        return cls.get_mode() == MCPMode.CLOUD

    @classmethod
    def is_stdio(cls) -> bool:
        """是否本地 STDIO 模式"""
        return cls.get_mode() == MCPMode.STDIO
    
    @classmethod
    def is_auto(cls) -> bool:
        """是否自动模式"""
        return cls.get_mode() == MCPMode.AUTO

    async def get_client(self) -> BaseMCPClient:
        """获取 MCP 客户端实例"""
        if self._client is not None:
            return self._client

        mode = self.get_mode()
        logger.info(f"📦 初始化 MCP 客户端，模式: {mode.value}")

        if mode == MCPMode.STDIO:
            stdio_command = os.getenv("MCP_STDIO_COMMAND", "python -m app.mcp.stdio_server")
            working_dir = os.getenv("MCP_WORKING_DIR", os.getcwd())
            self._client = LocalMCPStdioClient(
                server_command=stdio_command,
                working_directory=working_dir
            )
            logger.info(f"   STDIO 模式: {stdio_command}")
        elif mode == MCPMode.AUTO:
            stdio_command = os.getenv("MCP_STDIO_COMMAND", "python -m app.mcp.stdio_server")
            working_dir = os.getenv("MCP_WORKING_DIR", os.getcwd())
            cloud_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8080")
            cloud_key = os.getenv("MCP_API_KEY", "")
            timeout = int(os.getenv("MCP_TIMEOUT", "120"))
            self._client = HybridMCPClient(
                stdio_command=stdio_command,
                working_directory=working_dir,
                cloud_url=cloud_url,
                cloud_key=cloud_key,
                timeout=timeout
            )
            logger.info(f"   自动模式: 本地 STDIO + 云端 HTTP")
        elif mode == MCPMode.LOCAL:
            local_url = os.getenv("MCP_LOCAL_URL", "http://127.0.0.1:8001")
            local_key = os.getenv("MCP_LOCAL_API_KEY", "")
            self._client = LocalMCPClient(base_url=local_url, api_key=local_key)
            logger.info(f"   本地 HTTP 模式: {local_url}")
        else:
            cloud_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8080")
            cloud_key = os.getenv("MCP_API_KEY", "")
            timeout = int(os.getenv("MCP_TIMEOUT", "120"))
            self._client = CloudMCPClient(server_url=cloud_url, api_key=cloud_key, timeout=timeout)
            logger.info(f"   云端 HTTP 模式: {cloud_url}")

        return self._client

    async def connect(self) -> None:
        """连接到 MCP 服务器"""
        client = await self.get_client()
        await client.connect()

    async def disconnect(self) -> None:
        """断开连接"""
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def call_tool(self, tool_name: str, **kwargs) -> MCPToolResult:
        """调用 MCP 工具"""
        client = await self.get_client()
        return await client.call_tool(tool_name, **kwargs)

    async def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有工具"""
        client = await self.get_client()
        return await client.list_tools()

    def print_mode_info(self) -> None:
        """打印当前模式信息"""
        mode = self.get_mode()
        logger.info("🔧 MCP 配置信息:")
        logger.info(f"   模式: {mode.value.upper()}")
        if mode == MCPMode.STDIO:
            logger.info(f"   STDIO 命令: {os.getenv('MCP_STDIO_COMMAND', 'python -m app.mcp.stdio_server')}")
        elif mode == MCPMode.AUTO:
            logger.info(f"   STDIO 命令: {os.getenv('MCP_STDIO_COMMAND', 'python -m app.mcp.stdio_server')}")
            logger.info(f"   云端地址: {os.getenv('MCP_SERVER_URL', 'http://127.0.0.1:8080')}")
        elif mode == MCPMode.LOCAL:
            logger.info(f"   本地地址: {os.getenv('MCP_LOCAL_URL', 'http://127.0.0.1:8001')}")
        else:
            logger.info(f"   云端地址: {os.getenv('MCP_SERVER_URL', 'http://127.0.0.1:8080')}")


mcp_factory = MCPClientFactory()
