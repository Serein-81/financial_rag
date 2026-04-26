"""
本地 MCP STDIO 客户端

通过子进程调用本地 MCP STDIO 服务器
所有日志输出到 stderr，不影响 stdout 的 JSON-RPC 通信
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MCPToolInfo:
    """MCP 工具信息"""
    
    def __init__(self, name: str, description: str = "", input_schema: Dict = None):
        self.name = name
        self.description = description
        self.input_schema = input_schema or {}
    
    def __repr__(self):
        return f"MCPToolInfo(name={self.name}, description={self.description[:50]}...)"


class LocalMCPClient:
    """
    本地 MCP STDIO 客户端
    
    通过子进程与本地 MCP STDIO 服务器通信
    """
    
    def __init__(
        self,
        server_command: str = None,
        working_directory: str = None
    ):
        self.server_command = server_command or "python -m app.mcp.stdio_server"
        self.working_directory = working_directory or os.getcwd()
        self._process: Optional[asyncio.subprocess.Process] = None
        self._connected = False
        self._tools: List[MCPToolInfo] = []
        self._request_id = 0
        self._response_futures: Dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> None:
        """连接到本地 MCP STDIO 服务器"""
        if self._connected:
            logger.info("本地 MCP 客户端已连接")
            return
        
        try:
            logger.info(f"启动本地 MCP STDIO 服务器: {self.server_command}")
            
            self._process = await asyncio.create_subprocess_shell(
                self.server_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_directory,
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )
            
            # 启动读取响应任务
            self._reader_task = asyncio.create_task(self._read_responses())
            
            # 等待服务器启动
            await asyncio.sleep(0.5)
            
            init_request = {
                "jsonrpc": "2.0",
                "id": self._get_next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {
                        "name": "local-mcp-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            response = await self._send_request(init_request)
            
            if "error" in response:
                raise Exception(f"初始化失败: {response['error']}")
            
            self._connected = True
            logger.info("本地 MCP STDIO 服务器已连接")
            
            await self._refresh_tools()
            
        except Exception as e:
            logger.error(f"连接本地 MCP 服务器失败: {e}", exc_info=True)
            self._connected = False
            if self._reader_task:
                self._reader_task.cancel()
                self._reader_task = None
            if self._process:
                self._process.terminate()
                self._process = None
            raise
    
    async def _refresh_tools(self) -> None:
        """刷新工具列表"""
        try:
            request = {
                "jsonrpc": "2.0",
                "id": self._get_next_id(),
                "method": "tools/list",
                "params": {}
            }
            
            response = await self._send_request(request)
            
            if "error" not in response and "result" in response:
                tools_data = response["result"].get("tools", [])
                self._tools = [
                    MCPToolInfo(
                        name=t["name"],
                        description=t.get("description", ""),
                        input_schema=t.get("inputSchema", {})
                    )
                    for t in tools_data
                ]
                logger.info(f"已加载 {len(self._tools)} 个工具")
        except Exception as e:
            logger.warning(f"刷新工具列表失败: {e}")
    
    def _get_next_id(self) -> int:
        """获取下一个请求 ID"""
        self._request_id += 1
        return self._request_id
    
    async def _send_request(self, request: Dict) -> Dict:
        """发送请求并等待响应"""
        if not self._process:
            raise Exception("未连接到 MCP 服务器")
        
        request_id = request["id"]
        future = asyncio.get_event_loop().create_future()
        self._response_futures[request_id] = future
        
        request_str = json.dumps(request, ensure_ascii=False)
        self._process.stdin.write((request_str + "\n").encode("utf-8"))
        await self._process.stdin.drain()
        
        try:
            response = await asyncio.wait_for(future, timeout=120)
            return response
        except asyncio.TimeoutError:
            self._response_futures.pop(request_id, None)
            raise Exception(f"请求超时: {request.get('method')}")
    
    async def _read_responses(self) -> None:
        """读取服务器响应"""
        if not self._process or not self._process.stdout:
            return
        
        try:
            while self._process and self._process.returncode is None:
                line = await self._process.stdout.readline()
                if not line:
                    break
                
                try:
                    response = json.loads(line.decode("utf-8"))
                    request_id = response.get("id")
                    
                    if request_id in self._response_futures:
                        future = self._response_futures.pop(request_id)
                        if not future.done():
                            future.set_result(response)
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"响应 JSON 解析失败: {e}")
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"读取响应失败: {e}", exc_info=True)
    
    async def call_tool(self, tool_name: str, **kwargs) -> str:
        """
        调用 MCP 工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            工具执行结果（字符串形式）
        """
        if not self._connected:
            await self.connect()
        
        try:
            request = {
                "jsonrpc": "2.0",
                "id": self._get_next_id(),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": kwargs
                }
            }
            
            response = await self._send_request(request)
            
            if "error" in response:
                error_msg = response["error"].get("message", "Unknown error")
                logger.error(f"工具调用失败: {tool_name} - {error_msg}")
                return f"错误: {error_msg}"
            
            result = response.get("result", {})
            content = result.get("content", [])
            
            if content and len(content) > 0:
                return content[0].get("text", "")
            else:
                return "工具执行成功，但无返回内容"
                
        except Exception as e:
            logger.error(f"调用工具失败: {tool_name} - {e}", exc_info=True)
            return f"错误: 调用 {tool_name} 失败 - {str(e)}"
    
    def list_tools(self) -> List[MCPToolInfo]:
        """列出所有可用工具"""
        return self._tools
    
    async def disconnect(self) -> None:
        """断开连接"""
        self._connected = False
        
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        
        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
            except Exception as e:
                logger.warning(f"关闭进程失败: {e}")
            finally:
                self._process = None
        
        self._tools = []
        self._response_futures.clear()
        logger.info("本地 MCP 客户端已断开")
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
