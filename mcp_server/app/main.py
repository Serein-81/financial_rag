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

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    if settings.log_level in ["INFO", "DEBUG"]:
        logger.info("MCP Server starting...")

    try:
        register_tax_tools()
        if settings.log_level == "DEBUG":
            logger.info("Tax tools registered")
    except Exception as e:
        logger.error(f"Tax tools registration failed: {e}")

    try:
        register_legal_tools()
        if settings.log_level == "DEBUG":
            logger.info("Legal tools registered")
    except Exception as e:
        logger.error(f"Legal tools registration failed: {e}")

    try:
        register_financial_tools()
        if settings.log_level == "DEBUG":
            logger.info("Financial tools registered")
    except Exception as e:
        logger.error(f"Financial tools registration failed: {e}")

    # 企业工具需要访问本地API，暂时跳过
    # 如果需要启用，取消下面注释
    # try:
    #     from app.tools.enterprise_tools import register_enterprise_tools
    #     register_enterprise_tools()
    #     if settings.log_level == "DEBUG":
    #         logger.info("Enterprise tools registered")
    # except Exception as e:
    #     logger.error(f"Enterprise tools registration failed: {e}")

    tools_count = len(registry.list_tools())
    if settings.log_level in ["INFO", "DEBUG"]:
        logger.info(f"Total tools registered: {tools_count}")

    yield

    if settings.log_level in ["INFO", "DEBUG"]:
        logger.info("MCP Server shutting down")


app = FastAPI(
    title="MCP Server",
    description="Financial & Tax Remote Tools Service",
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
    """Health check endpoint"""
    tools_count = len(registry.list_tools())
    return {
        "status": "healthy",
        "version": "1.0.0",
        "tools_count": tools_count
    }


@app.get("/tools")
async def list_tools(authorized: bool = Depends(verify_api_key)):
    """List all available tools"""
    tools = registry.list_tools()
    return {"total": len(tools), "tools": tools}


@app.get("/tools/stats")
async def get_tools_stats(authorized: bool = Depends(verify_api_key)):
    """Get tools statistics"""
    return registry.get_stats()


class MCPCallRequest(BaseModel):
    """MCP call request"""
    tool_name: str
    arguments: Dict[str, Any] = {}


@app.post("/mcp/call")
async def mcp_call(
    request: MCPCallRequest,
    authorized: bool = Depends(verify_api_key)
):
    """MCP JSON-RPC call endpoint"""
    tool_name = request.tool_name
    arguments = request.arguments

    tool = registry.get(tool_name)
    if not tool:
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32602,
                "message": f"Tool '{tool_name}' not found"
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
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": f"Tool execution failed: {str(e)}"
            },
            "id": tool_name
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
