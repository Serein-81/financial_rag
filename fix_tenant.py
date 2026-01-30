import asyncio
import sys
import os

# 1. 强行把当前目录加入 Python 搜索路径，解决找不到 app 模块的问题
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sqlalchemy import text

# 2. 尝试多种方式获取数据库连接
try:
    from app.db.base import AsyncSessionLocal

    print("✅ 成功从 app.db.base 导入")
except ImportError:
    try:
        from app.db import AsyncSessionLocal

        print("✅ 成功从 app.db 导入")
    except ImportError as e:
        print(f"❌ 导入失败，请检查目录结构。错误: {e}")
        sys.exit(1)


async def relax_tenant_constraint():
    print("🔧 正在修复数据库限制 (Tenant ID)...")

    # 3. 获取数据库引擎
    engine = None
    if hasattr(AsyncSessionLocal, 'kw'):
        engine = AsyncSessionLocal.kw['bind']
    elif hasattr(AsyncSessionLocal, 'class_'):
        engine = AsyncSessionLocal.class_.kw['bind']

    if not engine:
        print("❌ 无法获取引擎对象")
        return

    async with engine.begin() as conn:
        try:
            # 4. 执行 SQL：允许 tenant_id 为空
            print("正在修改 knowledge_bases 表结构...")
            await conn.execute(text("ALTER TABLE knowledge_bases ALTER COLUMN tenant_id DROP NOT NULL;"))
            print("✅ 成功！knowledge_bases 表的 tenant_id 已改为可空。")

            # 顺便尝试修复 documents 表（如果有的话）
            try:
                await conn.execute(text("ALTER TABLE documents ALTER COLUMN tenant_id DROP NOT NULL;"))
                print("✅ 成功！documents 表的 tenant_id 已改为可空。")
            except Exception:
                pass  # documents 表可能没有这个字段，忽略

        except Exception as e:
            print(f"⚠️ 执行过程中遇到问题 (可能已经修复过): {e}")


if __name__ == "__main__":
    # Windows 下 asyncio 的兼容性设置
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(relax_tenant_constraint())