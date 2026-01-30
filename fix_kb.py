# fix_kb.py
import asyncio
from sqlalchemy import text
from app.db import engine


async def fix_kb_schema():
    print("🔧 正在尝试修复 knowledge_bases 表结构...")
    async with engine.begin() as conn:
        try:
            # 1. 暴力添加 user_id 列
            await conn.execute(text("ALTER TABLE knowledge_bases ADD COLUMN user_id UUID;"))
            print("✅ 成功！已添加 'user_id' 字段。")

            # 2. 尝试添加外键约束 (让它关联到 users 表)
            # 这一步可能会失败(如果里面已经有脏数据)，但非必须，主要是为了数据完整性
            try:
                await conn.execute(text(
                    "ALTER TABLE knowledge_bases ADD CONSTRAINT fk_kb_user FOREIGN KEY (user_id) REFERENCES users(id);"))
                print("✅ 成功！已添加外键约束。")
            except Exception as e:
                print(f"⚠️ 外键约束添加跳过 (可能是数据不兼容): {e}")

        except Exception as e:
            if "already exists" in str(e):
                print("⚠️ 'user_id' 字段可能已经存在。")
            else:
                print(f"❌ 修复失败: {e}")


if __name__ == "__main__":
    asyncio.run(fix_kb_schema())