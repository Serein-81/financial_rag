#!/usr/bin/env python3
"""
添加搜索优化索引

为关键词搜索和全文搜索创建数据库索引，提升搜索性能
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.session import AsyncSessionLocal


async def create_search_indexes():
    """创建搜索优化索引"""
    
    print("🔧 开始创建搜索优化索引...")
    
    async with AsyncSessionLocal() as db:
        try:
            # 1. 为 document_chunks 内容创建全文搜索索引
            print("📝 创建全文搜索索引...")
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chunks_content_fts 
                ON document_chunks 
                USING gin(to_tsvector('english', content))
            """))
            
            # 2. 为 document_chunks 内容创建三元组索引（支持 LIKE 查询）
            print("🔤 创建三元组索引...")
            await db.execute(text("""
                CREATE EXTENSION IF NOT EXISTS pg_trgm
            """))
            
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chunks_content_trigram 
                ON document_chunks 
                USING gin(content gin_trgm_ops)
            """))
            
            # 3. 为 documents 表创建复合索引
            print("📚 创建文档复合索引...")
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_documents_kb_created 
                ON documents(kb_id, created_at DESC)
            """))
            
            # 4. 为 document_chunks 创建复合索引
            print("📄 创建文档块复合索引...")
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chunks_doc_index 
                ON document_chunks(document_id, chunk_index)
            """))
            
            # 5. 为 chat_messages 创建全文搜索索引（记忆搜索）
            print("💬 创建聊天消息全文搜索索引...")
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_content_fts 
                ON chat_messages 
                USING gin(to_tsvector('english', content))
            """))
            
            # 6. 为 chat_messages 创建会话时间索引
            print("⏰ 创建聊天消息会话时间索引...")
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_time 
                ON chat_messages(session_id, created_at DESC)
            """))
            
            # 7. 为 semantic_memories 创建用户内容索引
            print("🧠 创建语义记忆索引...")
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_semantic_memories_user_content 
                ON semantic_memories 
                USING gin(to_tsvector('english', content))
            """))
            
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_semantic_memories_user_importance 
                ON semantic_memories(user_id, importance DESC, last_accessed DESC)
            """))
            
            # 提交所有更改
            await db.commit()
            
            print("✅ 所有搜索索引创建完成！")
            
        except Exception as e:
            print(f"❌ 创建索引失败: {e}")
            await db.rollback()
            raise


async def check_indexes():
    """检查索引是否存在"""
    
    print("🔍 检查现有索引...")
    
    async with AsyncSessionLocal() as db:
        # 查询所有相关索引
        result = await db.execute(text("""
            SELECT 
                schemaname,
                tablename,
                indexname,
                indexdef
            FROM pg_indexes 
            WHERE tablename IN ('document_chunks', 'documents', 'chat_messages', 'semantic_memories')
            AND indexname LIKE 'idx_%'
            ORDER BY tablename, indexname
        """))
        
        indexes = result.fetchall()
        
        if indexes:
            print(f"📊 找到 {len(indexes)} 个相关索引:")
            for idx in indexes:
                print(f"  📋 {idx.tablename}.{idx.indexname}")
        else:
            print("⚠️ 未找到相关索引")


async def analyze_tables():
    """分析表统计信息，优化查询计划"""
    
    print("📈 分析表统计信息...")
    
    tables = ['document_chunks', 'documents', 'chat_messages', 'semantic_memories']
    
    async with AsyncSessionLocal() as db:
        for table in tables:
            try:
                await db.execute(text(f"ANALYZE {table}"))
                print(f"  ✅ 分析完成: {table}")
            except Exception as e:
                print(f"  ⚠️ 分析失败 {table}: {e}")
        
        await db.commit()


async def main():
    """主函数"""
    
    print("🚀 搜索索引优化脚本")
    print("=" * 50)
    
    try:
        # 1. 检查现有索引
        await check_indexes()
        print()
        
        # 2. 创建新索引
        await create_search_indexes()
        print()
        
        # 3. 分析表统计信息
        await analyze_tables()
        print()
        
        # 4. 再次检查索引
        print("🔍 验证索引创建结果:")
        await check_indexes()
        
        print("=" * 50)
        print("🎉 搜索索引优化完成！")
        print()
        print("📋 性能提升预期:")
        print("  • 关键词搜索: 10-100倍提升")
        print("  • 全文搜索: 5-50倍提升")
        print("  • 记忆搜索: 5-20倍提升")
        print("  • 文档级搜索: 3-10倍提升")
        
    except Exception as e:
        print(f"❌ 脚本执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())