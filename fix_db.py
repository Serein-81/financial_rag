# fix_db.py
import asyncio
from sqlalchemy import text
from app.db import engine

async def fix_schema():
    print("🔧 正在尝试修复数据库表结构...")
    async with engine.begin() as conn:
        try:
            # 执行原生 SQL 给 chat_messages 表添加 sources 列
            # JSON 类型对应 SQLAlchemy 的 JSON
            await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN sources JSON;"))
            print("✅ 成功！已添加 'sources' 字段。")
        except Exception as e:
            # 如果报错，可能是列已经存在，或者表不存在
            if "already exists" in str(e):
                print("⚠️  'sources' 字段已经存在，无需修复。")
            else:
                print(f"❌ 修复失败: {e}")

if __name__ == "__main__":
    asyncio.run(fix_schema())