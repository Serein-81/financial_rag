import asyncio
import sys
import os
import importlib

# 将当前目录加入系统路径
sys.path.append(os.getcwd())

from sqlalchemy.ext.asyncio import create_async_engine

# 你的 Docker 数据库地址
DATABASE_URL = "postgresql+asyncpg://postgres:REDACTED_PG_PASSWORD@localhost:5432/rag_db"


async def create_tables():
    print(f"🔌 正在连接数据库...")
    engine = create_async_engine(DATABASE_URL, echo=False)

    try:
        # 1. 先导入 Base
        from app.db.base import Base

        # 2. 核心：精准导入所有模型文件
        print("📂 正在扫描并注册所有模型...")
        model_files = [
            "app.models.user",
            "app.models.knowledge_base",
            "app.models.document",
            "app.models.chunk",
            "app.models.chat",
            "app.models.search_log"
        ]

        for module_name in model_files:
            try:
                importlib.import_module(module_name)
                print(f"   ✅ 已加载模型: {module_name}")
            except Exception as e:
                print(f"   ❌ 加载失败 {module_name}: {e}")

        # 3. 打印检查，看现在 Base 认识多少张表了
        tables = list(Base.metadata.tables.keys())
        print(f"\n📋 准备在 Docker 中创建以下 {len(tables)} 张表:")
        for t in tables:
            print(f"   - {t}")

        # 4. 执行创建
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        print("\n" + "=" * 40)
        print("🎉🎉🎉 全表建库成功！")
        print("请在 Navicat 的 rag_db 下刷新查看！")
        print("=" * 40 + "\n")

    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_tables())