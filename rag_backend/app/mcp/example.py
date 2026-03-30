import asyncio
import logging
from app.mcp.client_manager import MCPClientManager, MCPToolInfo, MCP_SERVER_URL, MCP_API_KEY, MCP_TIMEOUT
from app.mcp.langchain_adapter import MCPToolAdapter, LangGraphMCPIntegration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_basic_usage():
    """基础使用示例: 直接调用 MCP 工具"""
    logger.info("=" * 60)
    logger.info("示例 1: 基础使用 - 直接调用 MCP 工具")
    logger.info("=" * 60)

    async with MCPClientManager(
        server_url=MCP_SERVER_URL,
        api_key=MCP_API_KEY,
        timeout=MCP_TIMEOUT
    ) as mcp_client:

        logger.info(f"已连接，已加载 {len(mcp_client.tools)} 个工具")
        for tool in mcp_client.tools:
            logger.info(f"  - {tool.name}: {tool.description[:50]}...")

        if mcp_client.tools:
            first_tool = mcp_client.tools[0]
            logger.info(f"\n调用工具: {first_tool.name}")

            sample_args = _generate_sample_args(first_tool)
            result = await mcp_client.call_tool(first_tool.name, sample_args)
            logger.info(f"结果: {result[:200]}...")


async def example_langgraph_integration():
    """LangGraph 集成示例"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 2: LangGraph 集成")
    logger.info("=" * 60)

    async with MCPClientManager(
        server_url=MCP_SERVER_URL,
        api_key=MCP_API_KEY,
        timeout=MCP_TIMEOUT
    ) as mcp_client:

        integration = LangGraphMCPIntegration(mcp_client)
        tools = await integration.get_tools_for_agent()

        logger.info(f"已转换为 {len(tools)} 个 LangChain @tool:")
        for langchain_tool in tools:
            logger.info(f"  - {langchain_tool.name}")
            logger.info(f"    描述: {langchain_tool.description[:50]}...")

            if hasattr(langchain_tool, "args_schema") and langchain_tool.args_schema:
                schema = langchain_tool.args_schema
                if hasattr(schema, "model_fields"):
                    logger.info(f"    参数: {list(schema.model_fields.keys())}")


async def example_connection_resilience():
    """连接弹性示例: 模拟断线重连"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 3: 连接弹性 - 自动重连")
    logger.info("=" * 60)

    client = MCPClientManager(
        server_url=MCP_SERVER_URL,
        api_key=MCP_API_KEY,
        timeout=MCP_TIMEOUT,
        dynamic_timeout=True
    )

    try:
        await client.connect()
        logger.info("✅ 连接成功")

        if client.tools:
            tool = client.tools[0]
            sample_args = _generate_sample_args(tool)

            logger.info(f"调用工具: {tool.name}")
            result = await client.call_tool(
                tool.name,
                sample_args,
                auto_reconnect=True,
                max_retries=3
            )
            logger.info(f"✅ 成功: {result[:100]}...")

    except Exception as e:
        logger.error(f"❌ 失败: {e}")
    finally:
        await client.disconnect()
        logger.info("🔌 已断开连接")


def _generate_sample_args(tool_info: MCPToolInfo) -> dict:
    """根据 schema 生成示例参数"""
    properties = tool_info.input_schema.get("properties", {})
    required = tool_info.input_schema.get("required", [])
    args = {}

    for param_name, param_schema in properties.items():
        param_type = param_schema.get("type", "string")

        if param_type == "string":
            args[param_name] = f"sample_{param_name}"
        elif param_type == "number":
            args[param_name] = 123.45
        elif param_type == "integer":
            args[param_name] = 100
        elif param_type == "boolean":
            args[param_name] = True
        elif param_type == "array":
            args[param_name] = ["item1", "item2"]
        elif param_type == "object":
            args[param_name] = {"key": "value"}

    return args


async def main():
    """运行所有示例"""
    logger.info("\n🚀 MCP 客户端使用示例")
    logger.info("注意: 需要云端 MCP 服务器运行在 http://8.148.226.49:8080/sse")
    logger.info("-" * 60)

    try:
        await example_basic_usage()
    except Exception as e:
        logger.error(f"示例1失败: {e}")

    try:
        await example_langgraph_integration()
    except Exception as e:
        logger.error(f"示例2失败: {e}")

    try:
        await example_connection_resilience()
    except Exception as e:
        logger.error(f"示例3失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
