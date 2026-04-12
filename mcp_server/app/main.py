"""
MCP 服务器主入口

提供 FastMCP 服务端和 FastAPI SSE 端点
云端服务，监听 8080 端口
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.auth.api_key import verify_api_key
from app.tools.base import registry
from app.tools.tax_tools import register_tax_tools
from app.tools.legal_tools import register_legal_tools
from app.tools.financial_tools import register_financial_tools
from app.tools.enterprise_tools import register_enterprise_tools

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 MCP 服务器启动中...")
    logger.info(f"📡 服务地址: {settings.host}:{settings.port}")

    register_tax_tools()
    logger.info("✅ 税务工具注册完成")

    register_legal_tools()
    logger.info("✅ 法律工具注册完成")

    register_financial_tools()
    logger.info("✅ 财务工具注册完成")

    register_enterprise_tools()
    logger.info("✅ 企业工具注册完成")

    tools_count = len(registry.list_tools())
    logger.info(f"🎉 已注册 {tools_count} 个工具")
    logger.info(f"📋 工具列表: {[t['name'] for t in registry.list_tools()]}")

    yield

    logger.info("👋 MCP 服务器关闭")


app = FastAPI(
    title="MCP Server",
    description="财务税务远程工具服务 - 提供税务计算、法律匹配、财务分析、企业信息查询等工具",
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
    tools_count = len(registry.list_tools())
    return {
        "status": "healthy",
        "version": "1.0.0",
        "tools_count": tools_count,
        "api_keys_configured": settings.api_keys_count
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
        logger.warning(f"❌ 工具不存在: {tool_name}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"工具 '{tool_name}' 不存在"
        )

    logger.info(f"📤 执行工具: {tool_name}")
    logger.debug(f"📥 参数: {arguments}")

    try:
        result = await tool.run(**arguments)

        if not result.get("success", True):
            logger.warning(f"⚠️ 工具执行返回错误: {tool_name} - {result.get('error', '未知错误')}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=result
            )

        logger.info(f"✅ 工具执行成功: {tool_name}")
        return result

    except Exception as e:
        logger.error(f"❌ 工具执行异常: {tool_name} - {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": str(e),
                "message": f"工具执行失败: {str(e)}"
            }
        )


@app.get("/sse")
async def sse_endpoint(authorized: bool = Depends(verify_api_key)):
    """
    SSE 端点 - 建立 SSE 长连接

    用于 MCP 客户端通过 SSE 接收工具列表和通知
    """
    async def event_generator():
        logger.info("📡 SSE 客户端连接")

        tools_count = len(registry.list_tools())

        yield {
            "event": "connected",
            "data": f'{{"status": "connected", "tools_count": {tools_count}}}'
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
                "data": f'{{"timestamp": "{asyncio.get_event_loop().time()}"}}'
            }

    return EventSourceResponse(event_generator())


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

    logger.info(f"📤 MCP 调用: {tool_name}")
    logger.debug(f"📥 参数: {arguments}")

    tool = registry.get(tool_name)
    if not tool:
        logger.warning(f"❌ MCP 工具不存在: {tool_name}")
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32602,
                "message": f"工具 '{tool_name}' 不存在"
            },
            "id": None
        }

    try:
        result = await tool.run(**arguments)

        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": tool_name
        }

    except Exception as e:
        logger.error(f"❌ MCP 调用异常: {tool_name} - {str(e)}", exc_info=True)
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": f"工具执行失败: {str(e)}"
            },
            "id": tool_name
        }


def create_mcp_server():
    """创建 MCP 服务器实例（供独立运行时使用）"""
    return app


if __name__ == "__main__":
    import uvicorn

    logger.info(f"🚀 启动 MCP 服务器，监听端口: {settings.port}")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
