"""
数据库迁移脚本：添加日志系统

添加系统日志表和用户操作日志表，以及用户表的管理员字段
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)).replace('migrations', ''))

from sqlalchemy import text
from app.db.session import AsyncSessionLocal


async def upgrade():
    """升级数据库：添加日志系统相关表"""
    
    async with AsyncSessionLocal() as session:
        # 1. 添加用户表的管理员字段（如果不存在）
        try:
            await session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
            """))
            print("✅ 用户表添加管理员字段成功")
        except Exception as e:
            print(f"⚠️ 用户表管理员字段可能已存在: {e}")
        
        # 2. 创建系统日志表
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                
                -- 日志基本信息
                level VARCHAR(20) NOT NULL,
                category VARCHAR(50) NOT NULL,
                action VARCHAR(100) NOT NULL,
                message TEXT NOT NULL,
                
                -- 关联信息
                user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                session_id VARCHAR(100),
                request_id VARCHAR(100),
                
                -- 详细信息
                module VARCHAR(100),
                function VARCHAR(100),
                line_number INTEGER,
                
                -- 请求相关
                ip_address VARCHAR(45),
                user_agent TEXT,
                endpoint VARCHAR(200),
                method VARCHAR(10),
                status_code INTEGER,
                
                -- 性能指标
                execution_time INTEGER,
                memory_usage INTEGER,
                
                -- 扩展数据
                extra_data JSONB,
                
                -- 错误信息
                error_type VARCHAR(100),
                error_message TEXT,
                stack_trace TEXT,
                
                -- 标记字段
                is_sensitive BOOLEAN DEFAULT FALSE,
                is_archived BOOLEAN DEFAULT FALSE
            );
        """))
        
        # 3. 创建用户操作日志表
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS user_action_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                
                -- 用户信息
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                user_email VARCHAR(255),
                
                -- 操作信息
                action_type VARCHAR(50) NOT NULL,
                action_name VARCHAR(100) NOT NULL,
                description TEXT,
                
                -- 资源信息
                resource_type VARCHAR(50),
                resource_id VARCHAR(100),
                resource_name VARCHAR(200),
                
                -- 操作结果
                success BOOLEAN NOT NULL DEFAULT TRUE,
                result_message TEXT,
                
                -- 请求信息
                ip_address VARCHAR(45),
                user_agent TEXT,
                session_id VARCHAR(100),
                
                -- 扩展信息
                before_data JSONB,
                after_data JSONB,
                extra_info JSONB
            );
        """))
        
        # 4. 创建索引以提高查询性能
        indexes = [
            # 系统日志索引
            "CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level);",
            "CREATE INDEX IF NOT EXISTS idx_system_logs_category ON system_logs(category);",
            "CREATE INDEX IF NOT EXISTS idx_system_logs_action ON system_logs(action);",
            "CREATE INDEX IF NOT EXISTS idx_system_logs_user_id ON system_logs(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_system_logs_session_id ON system_logs(session_id);",
            "CREATE INDEX IF NOT EXISTS idx_system_logs_request_id ON system_logs(request_id);",
            "CREATE INDEX IF NOT EXISTS idx_system_logs_ip_address ON system_logs(ip_address);",
            "CREATE INDEX IF NOT EXISTS idx_system_logs_user_time ON system_logs(user_id, created_at);",
            "CREATE INDEX IF NOT EXISTS idx_system_logs_category_level ON system_logs(category, level);",
            "CREATE INDEX IF NOT EXISTS idx_system_logs_session_time ON system_logs(session_id, created_at);",
            "CREATE INDEX IF NOT EXISTS idx_system_logs_action_time ON system_logs(action, created_at);",
            
            # 用户操作日志索引
            "CREATE INDEX IF NOT EXISTS idx_user_action_logs_created_at ON user_action_logs(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_user_action_logs_user_id ON user_action_logs(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_user_action_logs_action_type ON user_action_logs(action_type);",
            "CREATE INDEX IF NOT EXISTS idx_user_action_logs_user_time ON user_action_logs(user_id, created_at);",
            "CREATE INDEX IF NOT EXISTS idx_user_action_logs_type_time ON user_action_logs(action_type, created_at);",
            "CREATE INDEX IF NOT EXISTS idx_user_action_logs_resource ON user_action_logs(resource_type, resource_id);",
        ]
        
        for index_sql in indexes:
            try:
                await session.execute(text(index_sql))
            except Exception as e:
                print(f"⚠️ 索引可能已存在: {e}")
        
        # 5. 提交事务
        await session.commit()
        print("✅ 日志系统数据库迁移完成")


async def downgrade():
    """降级数据库：删除日志系统相关表"""
    
    async with AsyncSessionLocal() as session:
        # 删除表（注意顺序，先删除有外键依赖的表）
        await session.execute(text("DROP TABLE IF EXISTS user_action_logs CASCADE;"))
        await session.execute(text("DROP TABLE IF EXISTS system_logs CASCADE;"))
        
        # 删除用户表的管理员字段
        await session.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS is_admin;"))
        
        await session.commit()
        print("✅ 日志系统数据库回滚完成")


if __name__ == "__main__":
    import asyncio
    
    async def main():
        print("🚀 开始执行日志系统数据库迁移...")
        await upgrade()
        print("🎉 迁移完成！")
    
    asyncio.run(main())