import asyncio
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    url = "http://8.148.226.49:5000/sse"
    logger.info("🔄 正在连接阿里云 MCP 节点...")
    logger.info(f"📍 目标地址: {url}")

    try:
        from mcp.client.session import ClientSession
        from mcp.client.sse import sse_client

        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.info("✅ 连接成功！获取云端工具列表...")

                tools = await session.list_tools()
                logger.info(f"\n📋 发现 {len(tools.tools)} 个工具:")
                for tool in tools.tools:
                    logger.info(f"   - {tool.name}: {tool.description}")

                logger.info("\n🧮 正在调用云端 add 工具计算 99 + 1...")
                result = await session.call_tool("add", arguments={"a": 99, "b": 1})

                logger.info(f"🎉 云端返回结果: {result.content[0].text}")
                return True

    except ImportError as e:
        logger.error(f"❌ mcp库未安装: {e}")
        logger.info("请确保已在Docker容器中安装: pip install mcp>=1.0.0")
        return False
    except Exception as e:
        logger.error(f"❌ 连接失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
