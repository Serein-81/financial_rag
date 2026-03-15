import asyncio
import asyncpg

# 👇 这里已经改成了你刚才设置的密码和库名
DB_CONFIG = {
    "user": "postgres",
    "password": "REDACTED_PG_PASSWORD",  # 你的自定义密码
    "database": "rag_db",  # 你的自定义库名
    "host": "localhost",
    "port": "5432",
}


async def init_vector_extension():
    print("🔌 正在连接数据库...")
    try:
        # 连接数据库
        conn = await asyncpg.connect(**DB_CONFIG)
        print("✅ 连接成功！正在开启 vector 插件...")

        # 核心指令：开启向量扩展
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        print("🎉 成功！数据库现在支持向量存储了！")
        await conn.close()
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        print("提示：请检查 docker 容器是否正在运行，或者密码是否写错了。")


if __name__ == "__main__":
    asyncio.run(init_vector_extension())