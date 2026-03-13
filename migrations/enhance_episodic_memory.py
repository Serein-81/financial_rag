"""
增强情景记忆 - 添加向量检索和相关性评分能力

改进内容：
1. 为 ChatMessage 添加 embedding 向量字段
2. 添加 importance 重要性字段
3. 添加 access_count 访问次数字段
4. 添加 last_accessed 最后访问时间字段
5. 创建向量索引以提升检索性能
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db import AsyncSessionLocal


async def add_episodic_memory_enhancements():
    """为情景记忆添加增强功能"""
    
    async with AsyncSessionLocal() as db:
        print("🔧 开始增强情景记忆系统...")
        
        try:
            # 1. 确保 pgvector 扩展已启用
            print("📦 检查 pgvector 扩展...")
            await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            
            # 2. 为 chat_messages 表添加新字段
            print("🆕 添加向量和元数据字段...")
            
            # 添加向量字段（1536维，适配OpenAI/智谱等主流模型）
            await db.execute(text("""
                ALTER TABLE chat_messages 
                ADD COLUMN IF NOT EXISTS embedding vector(1536);
            """))
            
            # 添加重要性字段
            await db.execute(text("""
                ALTER TABLE chat_messages 
                ADD COLUMN IF NOT EXISTS importance FLOAT DEFAULT 0.5;
            """))
            
            # 添加访问统计字段
            await db.execute(text("""
                ALTER TABLE chat_messages 
                ADD COLUMN IF NOT EXISTS access_count INTEGER DEFAULT 0;
            """))
            
            # 添加最后访问时间
            await db.execute(text("""
                ALTER TABLE chat_messages 
                ADD COLUMN IF NOT EXISTS last_accessed TIMESTAMP WITH TIME ZONE DEFAULT NOW();
            """))
            
            # 3. 创建向量索引以提升检索性能
            print("📊 创建向量索引...")
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_embedding 
                ON chat_messages USING ivfflat (embedding vector_cosine_ops) 
                WITH (lists = 100);
            """))
            
            # 4. 创建复合索引以优化常见查询
            print("🔍 创建复合索引...")
            
            # 会话ID + 创建时间索引（用于按时间检索）
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_time 
                ON chat_messages (session_id, created_at);
            """))
            
            # 重要性 + 最后访问时间索引（用于重要性排序）
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_importance_access 
                ON chat_messages (importance DESC, last_accessed DESC);
            """))
            
            # 访问次数索引（用于热度排序）
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_access_count 
                ON chat_messages (access_count DESC);
            """))
            
            # 5. 更新现有记录的默认值
            print("🔄 更新现有记录...")
            await db.execute(text("""
                UPDATE chat_messages 
                SET 
                    importance = 0.5,
                    access_count = 0,
                    last_accessed = created_at
                WHERE importance IS NULL;
            """))
            
            await db.commit()
            print("✅ 情景记忆增强完成！")
            
            # 6. 验证改动
            print("🔍 验证数据库结构...")
            result = await db.execute(text("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'chat_messages' 
                AND column_name IN ('embedding', 'importance', 'access_count', 'last_accessed')
                ORDER BY column_name;
            """))
            
            columns = result.fetchall()
            print("📋 新增字段:")
            for col in columns:
                print(f"   - {col[0]}: {col[1]} (nullable: {col[2]})")
            
            # 检查索引
            result = await db.execute(text("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE tablename = 'chat_messages' 
                AND indexname LIKE 'idx_chat_messages_%'
                ORDER BY indexname;
            """))
            
            indexes = result.fetchall()
            print("📊 创建的索引:")
            for idx in indexes:
                print(f"   - {idx[0]}")
            
        except Exception as e:
            print(f"❌ 迁移失败: {e}")
            await db.rollback()
            raise
        finally:
            await db.close()


async def rollback_episodic_memory_enhancements():
    """回滚情景记忆增强（如果需要）"""
    
    async with AsyncSessionLocal() as db:
        print("🔄 开始回滚情景记忆增强...")
        
        try:
            # 删除索引
            await db.execute(text("DROP INDEX IF EXISTS idx_chat_messages_embedding;"))
            await db.execute(text("DROP INDEX IF EXISTS idx_chat_messages_session_time;"))
            await db.execute(text("DROP INDEX IF EXISTS idx_chat_messages_importance_access;"))
            await db.execute(text("DROP INDEX IF EXISTS idx_chat_messages_access_count;"))
            
            # 删除字段
            await db.execute(text("ALTER TABLE chat_messages DROP COLUMN IF EXISTS embedding;"))
            await db.execute(text("ALTER TABLE chat_messages DROP COLUMN IF EXISTS importance;"))
            await db.execute(text("ALTER TABLE chat_messages DROP COLUMN IF EXISTS access_count;"))
            await db.execute(text("ALTER TABLE chat_messages DROP COLUMN IF EXISTS last_accessed;"))
            
            await db.commit()
            print("✅ 回滚完成！")
            
        except Exception as e:
            print(f"❌ 回滚失败: {e}")
            await db.rollback()
            raise
        finally:
            await db.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        asyncio.run(rollback_episodic_memory_enhancements())
    else:
        asyncio.run(add_episodic_memory_enhancements())