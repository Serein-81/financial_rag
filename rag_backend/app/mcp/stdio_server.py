"""
MCP STDIO 服务器

通过标准输入/输出进行 JSON-RPC 通信的 MCP 服务器
所有日志输出到 stderr，不影响 stdout 的 JSON-RPC 通信

启动方式:
    python -m app.mcp.stdio_server
"""

import asyncio
import sys
import json
import logging
from typing import Any, Dict

from app.mcp import get_unified_tools
from app.mcp.decorators import get_registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


class LocalMCPServer:
    """本地 MCP STDIO 服务器"""
    
    def __init__(self):
        self.tools: Dict[str, callable] = {}
        self._initialized = False
    
    def register_tools(self):
        """注册所有 MCP 工具"""
        logger.info("正在注册 MCP 工具...")
        
        registry = get_registry()
        
        for tool_name, metadata in registry.items():
            logger.info(f"已注册工具: {tool_name} ({metadata.source.value}) - {metadata.description[:50]}...")
        
        try:
            unified = get_unified_tools()
            all_tools = unified["all"]
            
            for tool_func in all_tools:
                self.tools[tool_func.name] = tool_func
            
            logger.info(f"✅ 工具注册完成，共 {len(self.tools)} 个")
            logger.info(f"   - 本地工具: {len(unified['local'])} 个")
            logger.info(f"   - 云端工具: {len(unified['cloud'])} 个")
        except Exception as e:
            logger.error(f"注册工具失败: {e}", exc_info=True)
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理 JSON-RPC 请求"""
        method = request.get("method")
        request_id = request.get("id")
        
        if method == "initialize":
            return self._handle_initialize(request)
        elif method == "tools/list":
            return self._handle_list_tools(request_id)
        elif method == "tools/call":
            return await self._handle_call_tool(request)
        else:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": request_id
            }
    
    def _handle_initialize(self, request: Dict) -> Dict[str, Any]:
        """处理初始化请求"""
        logger.info("收到初始化请求")
        self._initialized = True
        return {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "local-mcp-server", "version": "1.0.0"}
            },
            "id": request.get("id")
        }
    
    def _handle_list_tools(self, request_id: Any) -> Dict[str, Any]:
        """处理工具列表请求"""
        from app.mcp.decorators import get_registry
        
        registry = get_registry()
        tools = []
        
        for tool_name, metadata in registry.items():
            tools.append({
                "name": metadata.name,
                "description": metadata.description,
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            })
        
        logger.info(f"返回 {len(tools)} 个工具列表")
        return {"jsonrpc": "2.0", "result": {"tools": tools}, "id": request_id}
    
    async def _handle_call_tool(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理工具调用请求"""
        params = request.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        request_id = request.get("id")
        
        if not tool_name:
            return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Missing tool name"}, "id": request_id}
        
        if tool_name not in self.tools:
            return {"jsonrpc": "2.0", "error": {"code": -32602, "message": f"Tool not found: {tool_name}"}, "id": request_id}
        
        try:
            logger.info(f"调用工具: {tool_name}")
            tool_func = self.tools[tool_name]
            result = await tool_func(**arguments)
            
            if isinstance(result, dict):
                content = json.dumps(result, ensure_ascii=False)
            else:
                content = str(result)
            
            return {
                "jsonrpc": "2.0",
                "result": {"content": [{"type": "text", "text": content}]},
                "id": request_id
            }
        except Exception as e:
            logger.error(f"工具执行失败: {tool_name} - {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": f"Tool execution failed: {str(e)}"},
                "id": request_id
            }
    
    async def run(self):
        """运行 STDIO 服务器主循环"""
        logger.info("MCP STDIO 服务器启动")
        
        self.register_tools()
        
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            try:
                request = json.loads(line)
                response = await self.handle_request(request)
                
                response_line = json.dumps(response, ensure_ascii=False)
                print(response_line, flush=True)
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败: {e}")
                error_response = {"jsonrpc": "2.0", "error": {"code": -32700, "message": f"Parse error: {str(e)}"}, "id": None}
                print(json.dumps(error_response), flush=True)
            except Exception as e:
                logger.error(f"处理请求失败: {e}", exc_info=True)
                error_response = {"jsonrpc": "2.0", "error": {"code": -32603, "message": f"Internal error: {str(e)}"}, "id": None}
                print(json.dumps(error_response), flush=True)


async def main():
    """主入口"""
    server = LocalMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
