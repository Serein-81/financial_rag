"""
MCP 客户端工厂 - 支持本地/云端切换

使用方法：
1. 在 .env 中设置 MCP_MODE=local 或 MCP_MODE=cloud
2. 本地模式：需要本地启动 MCP 服务器 (python -m uvicorn ...)
3. 云端模式：连接远程 MCP 服务器
"""

import os
import httpx
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MCPMode(Enum):
    """MCP 运行模式"""
    LOCAL = "local"
    CLOUD = "cloud"


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
    """本地 MCP 客户端 - 直接调用本地工具"""

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
                    logger.info(f"✅ 本地 MCP 服务器连接成功: {self.base_url}")
                else:
                    raise ConnectionError(f"健康检查失败: {response.status_code}")
        except (ValueError, KeyError) as e:
            logger.warning(f"⚠️ 本地 MCP 服务器未运行(数据错误): {e}")
            raise ConnectionError(f"无法连接到本地 MCP 服务器: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"⚠️ 本地 MCP 服务器未运行(IO错误): {e}")
            raise ConnectionError(f"无法连接到本地 MCP 服务器: {e}")
        except Exception as e:
            logger.warning(f"⚠️ 本地 MCP 服务器未运行: {e}")
            raise ConnectionError(f"无法连接到本地 MCP 服务器: {e}")

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("本地 MCP 客户端已断开")

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
    """云端 MCP 客户端 - 调用远程 HTTP API"""

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
        mode_str = os.getenv("MCP_MODE", "local").lower()
        try:
            return MCPMode(mode_str)
        except ValueError:
            logger.warning(f"无效的 MCP_MODE: {mode_str}，使用默认值 local")
            return MCPMode.LOCAL

    @classmethod
    def is_local(cls) -> bool:
        """是否本地模式"""
        return cls.get_mode() == MCPMode.LOCAL

    @classmethod
    def is_cloud(cls) -> bool:
        """是否云端模式"""
        return cls.get_mode() == MCPMode.CLOUD

    async def get_client(self) -> BaseMCPClient:
        """获取 MCP 客户端实例"""
        if self._client is not None:
            return self._client

        mode = self.get_mode()
        logger.info(f"📦 初始化 MCP 客户端，模式: {mode.value}")

        if mode == MCPMode.LOCAL:
            local_url = os.getenv("MCP_LOCAL_URL", "http://127.0.0.1:8001")
            local_key = os.getenv("MCP_LOCAL_API_KEY", "")
            self._client = LocalMCPClient(base_url=local_url, api_key=local_key)
            logger.info(f"   本地模式: {local_url}")
        else:
            cloud_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8080")
            cloud_key = os.getenv("MCP_API_KEY", "")
            timeout = int(os.getenv("MCP_TIMEOUT", "120"))
            self._client = CloudMCPClient(server_url=cloud_url, api_key=cloud_key, timeout=timeout)
            logger.info(f"   云端模式: {cloud_url}")

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
        print(f"\n🔧 MCP 配置信息:")
        print(f"   模式: {mode.value.upper()}")
        if mode == MCPMode.LOCAL:
            print(f"   本地地址: {os.getenv('MCP_LOCAL_URL', 'http://127.0.0.1:8001')}")
        else:
            print(f"   云端地址: {os.getenv('MCP_SERVER_URL', 'http://127.0.0.1:8080')}")


mcp_factory = MCPClientFactory()
