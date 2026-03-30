"""
MCP 服务器主入口

提供 FastMCP 服务端和 FastAPI SSE 端点
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.auth.api_key import verify_api_key
from app.tools.base import registry
from app.tools.tax_tools import register_tax_tools, tax_tools
from app.tools.legal_tools import register_legal_tools, legal_tools
from app.tools.financial_tools import register_financial_tools, financial_tools
from app.tools.enterprise_tools import register_enterprise_tools, enterprise_tools

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 MCP 服务器启动中...")
    register_tax_tools()
    register_legal_tools()
    register_financial_tools()
    register_enterprise_tools()
    logger.info(f"✅ 已注册 {len(registry.list_tools())} 个工具")
    yield
    logger.info("👋 MCP 服务器关闭")


app = FastAPI(
    title="MCP Server",
    description="财务税务远程工具服务 - 提供税务计算、法律匹配、财务分析等工具",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "tools_count": len(registry.list_tools())
    }


@app.get("/tools")
async def list_tools(authorized: bool = Depends(verify_api_key)):
    """列出所有可用工具"""
    tools = registry.list_tools()
    return {
        "total": len(tools),
        "tools": tools
    }


@app.get("/tools/stats")
async def get_tools_stats(authorized: bool = Depends(verify_api_key)):
    """获取工具统计信息"""
    return registry.get_stats()


@app.post("/tools/{tool_name}/execute")
async def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    authorized: bool = Depends(verify_api_key)
):
    """
    执行指定工具

    Args:
        tool_name: 工具名称
        arguments: 工具参数

    Returns:
        工具执行结果
    """
    tool = registry.get(tool_name)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"工具 '{tool_name}' 不存在"
        )

    logger.info(f"📤 执行工具: {tool_name}, 参数: {arguments}")
    result = await tool.run(**arguments)

    if not result.get("success", True):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=result
        )

    return result


@app.get("/sse")
async def sse_endpoint(authorized: bool = Depends(verify_api_key)):
    """
    SSE 端点 - 建立 SSE 长连接

    用于 MCP 客户端通过 SSE 接收工具列表和通知
    """
    async def event_generator():
        logger.info("📡 SSE 客户端连接")

        yield {
            "event": "connected",
            "data": '{"status": "connected", "tools_count": ' + str(len(registry.list_tools())) + '}'
        }

        tools_info = {
            "type": "tools_list",
            "tools": registry.list_tools()
        }
        yield {
            "event": "tools_list",
            "data": str(tools_info)
        }

        while True:
            await asyncio.sleep(60)
            yield {
                "event": "heartbeat",
                "data": '{"timestamp": "' + asyncio.get_event_loop().time().__str__() + '"}'
            }

    return EventSourceResponse(event_generator())


from pydantic import BaseModel


class MCPCallRequest(BaseModel):
    """MCP 调用请求"""
    tool_name: str
    arguments: Dict[str, Any] = {}


@app.post("/mcp/call")
async def mcp_call(
    request: MCPCallRequest,
    authorized: bool = Depends(verify_api_key)
):
    """
    MCP JSON-RPC 调用端点

    符合 MCP 协议规范的调用接口
    """
    tool_name = request.tool_name
    arguments = request.arguments
    tool = registry.get(tool_name)
    if not tool:
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32602,
                "message": f"工具 '{tool_name}' 不存在"
            },
            "id": None
        }

    result = await tool.run(**arguments)

    return {
        "jsonrpc": "2.0",
        "result": result,
        "id": tool_name
    }


def create_mcp_server():
    """创建 MCP 服务器实例（供独立运行时使用）"""
    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )
