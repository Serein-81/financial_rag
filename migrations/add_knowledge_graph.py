"""
添加知识图谱表

创建实体表和关系表
"""

import asyncio
from sqlalchemy import text
from app.db import AsyncSessionLocal


async def create_kg_tables():
    """创建知识图谱表"""
    async with AsyncSessionLocal() as db:
        # 创建实体表
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS kg_entities (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                type VARCHAR(50) NOT NULL,
                properties JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # 创建关系表
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS kg_relations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                subject_id UUID REFERENCES kg_entities(id) ON DELETE CASCADE,
                predicate VARCHAR(100) NOT NULL,
                object_id UUID REFERENCES kg_entities(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # 创建索引
        await db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_kg_entities_name 
            ON kg_entities(name)
        """))
        
        await db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_kg_relations_subject 
            ON kg_relations(subject_id)
        """))
        
        await db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_kg_relations_object 
            ON kg_relations(object_id)
        """))
        
        await db.commit()
        print("✅ 知识图谱表创建成功")


if __name__ == "__main__":
    asyncio.run(create_kg_tables())
