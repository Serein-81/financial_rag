#!/usr/bin/env python3
"""
语义记忆数据表迁移脚本

创建 semantic_memories 表，用于存储用户的长期知识记忆
"""

import asyncio
import asyncpg
import os
from datetime import datetime

# 数据库配置
DB_CONFIG = {
    "host": os.getenv("POSTGRES_SERVER", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "123456"),
    "database": os.getenv("POSTGRES_DB", "rag_db")
}


async def create_semantic_memory_table():
    """创建语义记忆表"""
    
    # 创建表的SQL
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS semantic_memories (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        
        -- 核心内容
        content TEXT NOT NULL,
        role VARCHAR(20) DEFAULT 'system',
        
        -- 向量嵌入（1536维）
        embedding VECTOR(1536),
        
        -- 记忆属性
        importance FLOAT DEFAULT 0.5 CHECK (importance >= 0.0 AND importance <= 1.0),
        access_count INTEGER DEFAULT 0 CHECK (access_count >= 0),
        decay_factor FLOAT DEFAULT 1.0 CHECK (decay_factor >= 0.0 AND decay_factor <= 1.0),
        
        -- 分类和标签
        memory_type VARCHAR(50) DEFAULT 'knowledge',
        tags JSONB,
        
        -- 元数据
        metadata JSONB,
        source_session_id UUID,
        
        -- 时间戳
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        last_accessed TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """
    
    # 创建索引的SQL
    create_indexes_sql = [
        # 用户隔离索引（最重要）
        "CREATE INDEX IF NOT EXISTS idx_semantic_memories_user_id ON semantic_memories(user_id);",
        
        # 向量检索索引
        "CREATE INDEX IF NOT EXISTS idx_semantic_memories_embedding ON semantic_memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);",
        
        # 重要性和访问频率索引
        "CREATE INDEX IF NOT EXISTS idx_semantic_memories_importance ON semantic_memories(importance DESC);",
        "CREATE INDEX IF NOT EXISTS idx_semantic_memories_access_count ON semantic_memories(access_count DESC);",
        
        # 时间索引
        "CREATE INDEX IF NOT EXISTS idx_semantic_memories_created_at ON semantic_memories(created_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_semantic_memories_last_accessed ON semantic_memories(last_accessed DESC);",
        
        # 复合索引（用户+重要性）
        "CREATE INDEX IF NOT EXISTS idx_semantic_memories_user_importance ON semantic_memories(user_id, importance DESC);",
        
        # 记忆类型索引
        "CREATE INDEX IF NOT EXISTS idx_semantic_memories_type ON semantic_memories(memory_type);",
        
        # 来源会话索引
        "CREATE INDEX IF NOT EXISTS idx_semantic_memories_source_session ON semantic_memories(source_session_id);"
    ]
    
    # 创建更新时间触发器
    create_trigger_sql = """
    CREATE OR REPLACE FUNCTION update_semantic_memory_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    
    DROP TRIGGER IF EXISTS trigger_update_semantic_memory_updated_at ON semantic_memories;
    CREATE TRIGGER trigger_update_semantic_memory_updated_at
        BEFORE UPDATE ON semantic_memories
        FOR EACH ROW
        EXECUTE FUNCTION update_semantic_memory_updated_at();
    """
    
    print("🚀 开始创建语义记忆数据表...")
    
    try:
        # 连接数据库
        conn = await asyncpg.connect(**DB_CONFIG)
        print("✅ 数据库连接成功")
        
        # 确保 vector 扩展已启用
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("✅ pgvector 扩展已启用")
        
        # 创建表
        await conn.execute(create_table_sql)
        print("✅ semantic_memories 表创建成功")
        
        # 创建索引
        for i, index_sql in enumerate(create_indexes_sql, 1):
            await conn.execute(index_sql)
            print(f"✅ 索引 {i}/{len(create_indexes_sql)} 创建成功")
        
        # 创建触发器
        await conn.execute(create_trigger_sql)
        print("✅ 更新时间触发器创建成功")
        
        # 验证表结构
        result = await conn.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'semantic_memories'
            ORDER BY ordinal_position;
        """)
        
        print("\n📋 表结构验证:")
        for row in result:
            nullable = "NULL" if row['is_nullable'] == 'YES' else "NOT NULL"
            default = f" DEFAULT {row['column_default']}" if row['column_default'] else ""
            print(f"  - {row['column_name']}: {row['data_type']} {nullable}{default}")
        
        # 验证索引
        indexes = await conn.fetch("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'semantic_memories'
            ORDER BY indexname;
        """)
        
        print(f"\n🔍 索引验证 ({len(indexes)} 个):")
        for idx in indexes:
            print(f"  - {idx['indexname']}")
        
        await conn.close()
        print(f"\n🎉 语义记忆表创建完成！时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"❌ 创建失败: {e}")
        raise


async def rollback_semantic_memory_table():
    """回滚语义记忆表（删除表和相关对象）"""
    
    rollback_sql = [
        "DROP TRIGGER IF EXISTS trigger_update_semantic_memory_updated_at ON semantic_memories;",
        "DROP FUNCTION IF EXISTS update_semantic_memory_updated_at();",
        "DROP TABLE IF EXISTS semantic_memories CASCADE;"
    ]
    
    print("🔄 开始回滚语义记忆数据表...")
    
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        
        for sql in rollback_sql:
            await conn.execute(sql)
        
        await conn.close()
        print("✅ 语义记忆表回滚完成")
        
    except Exception as e:
        print(f"❌ 回滚失败: {e}")
        raise


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        asyncio.run(rollback_semantic_memory_table())
    else:
        asyncio.run(create_semantic_memory_table())