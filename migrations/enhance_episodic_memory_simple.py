"""
增强情景记忆 - 简化版迁移脚本

直接连接数据库，不依赖应用配置
"""

import asyncio
import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


async def run_migration():
    """运行数据库迁移"""
    
    # 获取数据库连接参数
    print("请输入数据库连接信息:")
    host = input("主机 (默认: localhost): ").strip() or "localhost"
    port = input("端口 (默认: 5432): ").strip() or "5432"
    user = input("用户名 (默认: postgres): ").strip() or "postgres"
    password = input("密码: ").strip()
    database = input("数据库名 (默认: rag_db): ").strip() or "rag_db"
    
    if not password:
        print("❌ 密码不能为空")
        return
    
    DATABASE_URL = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    
    print("🔧 开始增强情景记忆系统...")
    print(f"📡 连接数据库: postgresql+asyncpg://{user}:***@{host}:{port}/{database}")
    
    try:
        # 创建数据库引擎
        engine = create_async_engine(DATABASE_URL, echo=False)
        
        # 创建会话
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as session:
            # 1. 确保 pgvector 扩展已启用
            print("📦 检查 pgvector 扩展...")
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            
            # 2. 为 chat_messages 表添加新字段
            print("🆕 添加向量和元数据字段...")
            
            # 添加向量字段（1536维，适配OpenAI/智谱等主流模型）
            try:
                await session.execute(text("""
                    ALTER TABLE chat_messages 
                    ADD COLUMN IF NOT EXISTS embedding vector(1536);
                """))
                print("   ✅ 添加 embedding 字段")
            except Exception as e:
                print(f"   ⚠️ embedding 字段可能已存在: {e}")
            
            # 添加重要性字段
            try:
                await session.execute(text("""
                    ALTER TABLE chat_messages 
                    ADD COLUMN IF NOT EXISTS importance FLOAT DEFAULT 0.5;
                """))
                print("   ✅ 添加 importance 字段")
            except Exception as e:
                print(f"   ⚠️ importance 字段可能已存在: {e}")
            
            # 添加访问统计字段
            try:
                await session.execute(text("""
                    ALTER TABLE chat_messages 
                    ADD COLUMN IF NOT EXISTS access_count INTEGER DEFAULT 0;
                """))
                print("   ✅ 添加 access_count 字段")
            except Exception as e:
                print(f"   ⚠️ access_count 字段可能已存在: {e}")
            
            # 添加最后访问时间
            try:
                await session.execute(text("""
                    ALTER TABLE chat_messages 
                    ADD COLUMN IF NOT EXISTS last_accessed TIMESTAMP WITH TIME ZONE DEFAULT NOW();
                """))
                print("   ✅ 添加 last_accessed 字段")
            except Exception as e:
                print(f"   ⚠️ last_accessed 字段可能已存在: {e}")
            
            # 3. 创建向量索引以提升检索性能
            print("📊 创建向量索引...")
            try:
                await session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_embedding 
                    ON chat_messages USING ivfflat (embedding vector_cosine_ops) 
                    WITH (lists = 100);
                """))
                print("   ✅ 创建向量索引")
            except Exception as e:
                print(f"   ⚠️ 向量索引创建失败: {e}")
            
            # 4. 创建复合索引以优化常见查询
            print("🔍 创建复合索引...")
            
            # 会话ID + 创建时间索引（用于按时间检索）
            try:
                await session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_session_time 
                    ON chat_messages (session_id, created_at);
                """))
                print("   ✅ 创建会话时间索引")
            except Exception as e:
                print(f"   ⚠️ 会话时间索引可能已存在: {e}")
            
            # 重要性 + 最后访问时间索引（用于重要性排序）
            try:
                await session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_importance_access 
                    ON chat_messages (importance DESC, last_accessed DESC);
                """))
                print("   ✅ 创建重要性访问索引")
            except Exception as e:
                print(f"   ⚠️ 重要性访问索引可能已存在: {e}")
            
            # 访问次数索引（用于热度排序）
            try:
                await session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_access_count 
                    ON chat_messages (access_count DESC);
                """))
                print("   ✅ 创建访问次数索引")
            except Exception as e:
                print(f"   ⚠️ 访问次数索引可能已存在: {e}")
            
            # 5. 更新现有记录的默认值
            print("🔄 更新现有记录...")
            result = await session.execute(text("""
                UPDATE chat_messages 
                SET 
                    importance = 0.5,
                    access_count = 0,
                    last_accessed = created_at
                WHERE importance IS NULL;
            """))
            print(f"   ✅ 更新了 {result.rowcount} 条记录")
            
            await session.commit()
            print("✅ 情景记忆增强完成！")
            
            # 6. 验证改动
            print("🔍 验证数据库结构...")
            result = await session.execute(text("""
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
            result = await session.execute(text("""
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
        
        await engine.dispose()
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        print("💡 请检查:")
        print("   1. 数据库是否运行")
        print("   2. 连接参数是否正确")
        print("   3. 是否安装了 pgvector 扩展")
        raise


if __name__ == "__main__":
    print("🚀 开始情景记忆增强迁移")
    print("=" * 60)
    
    asyncio.run(run_migration())