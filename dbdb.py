# init_db.py
import asyncio
from app.db import engine, Base
# 必须导入所有模型，否则 create_all 找不到它们
from app.models.user import User, KnowledgeBase
from app.models.chat import ChatSession, ChatMessage
from app.models import Document, DocumentChunk

async def init_models():
    async with engine.begin() as conn:
        # 小心：这会重建表结构，如果表不存在则创建
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 数据库表结构初始化完成！")

if __name__ == "__main__":
    asyncio.run(init_models())