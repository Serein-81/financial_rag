"""
数据库迁移脚本：完善用户注册功能

添加手机号、昵称、企业信息等字段
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)).replace('migrations', ''))

from sqlalchemy import text
from app.db.session import AsyncSessionLocal


async def upgrade():
    """升级数据库：添加用户注册相关字段"""
    
    async with AsyncSessionLocal() as session:
        print("🚀 开始更新用户表结构...")
        
        # 1. 添加手机号字段（必填，唯一）
        try:
            await session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
            """))
            print("✅ 添加手机号字段")
        except Exception as e:
            print(f"⚠️ 手机号字段可能已存在: {e}")
        
        # 2. 添加昵称字段
        try:
            await session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS nickname VARCHAR(50);
            """))
            print("✅ 添加昵称字段")
        except Exception as e:
            print(f"⚠️ 昵称字段可能已存在: {e}")
        
        # 3. 添加个人简介字段
        try:
            await session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS bio TEXT;
            """))
            print("✅ 添加个人简介字段")
        except Exception as e:
            print(f"⚠️ 个人简介字段可能已存在: {e}")
        
        # 4. 添加企业名称字段
        try:
            await session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS company_name VARCHAR(200);
            """))
            print("✅ 添加企业名称字段")
        except Exception as e:
            print(f"⚠️ 企业名称字段可能已存在: {e}")
        
        # 5. 添加职位字段
        try:
            await session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS company_position VARCHAR(100);
            """))
            print("✅ 添加职位字段")
        except Exception as e:
            print(f"⚠️ 职位字段可能已存在: {e}")
        
        # 6. 添加手机号验证状态字段
        try:
            await session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS is_phone_verified BOOLEAN DEFAULT FALSE;
            """))
            print("✅ 添加手机号验证状态字段")
        except Exception as e:
            print(f"⚠️ 手机号验证状态字段可能已存在: {e}")
        
        # 7. 添加更新时间字段
        try:
            await session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
            """))
            print("✅ 添加更新时间字段")
        except Exception as e:
            print(f"⚠️ 更新时间字段可能已存在: {e}")
        
        # 8. 修改字段长度限制
        try:
            await session.execute(text("""
                ALTER TABLE users 
                ALTER COLUMN email TYPE VARCHAR(255);
            """))
            await session.execute(text("""
                ALTER TABLE users 
                ALTER COLUMN full_name TYPE VARCHAR(100);
            """))
            print("✅ 更新字段长度限制")
        except Exception as e:
            print(f"⚠️ 字段长度可能已更新: {e}")
        
        # 9. 创建手机号唯一索引
        try:
            await session.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone) 
                WHERE phone IS NOT NULL;
            """))
            print("✅ 创建手机号唯一索引")
        except Exception as e:
            print(f"⚠️ 手机号索引可能已存在: {e}")
        
        # 10. 创建昵称索引
        try:
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_users_nickname ON users(nickname);
            """))
            print("✅ 创建昵称索引")
        except Exception as e:
            print(f"⚠️ 昵称索引可能已存在: {e}")
        
        # 11. 为现有用户设置默认手机号（如果需要）
        try:
            await session.execute(text("""
                UPDATE users 
                SET phone = CONCAT('000', LPAD(CAST(EXTRACT(EPOCH FROM created_at)::BIGINT % 100000000 AS TEXT), 8, '0'))
                WHERE phone IS NULL;
            """))
            print("✅ 为现有用户设置默认手机号")
        except Exception as e:
            print(f"⚠️ 设置默认手机号失败: {e}")
        
        # 12. 设置手机号为非空约束（在设置默认值后）
        try:
            await session.execute(text("""
                ALTER TABLE users 
                ALTER COLUMN phone SET NOT NULL;
            """))
            print("✅ 设置手机号为必填字段")
        except Exception as e:
            print(f"⚠️ 手机号约束可能已存在: {e}")
        
        # 提交事务
        await session.commit()
        print("✅ 用户表结构更新完成")


async def downgrade():
    """降级数据库：删除新增字段"""
    
    async with AsyncSessionLocal() as session:
        # 删除新增字段
        await session.execute(text("""
            ALTER TABLE users 
            DROP COLUMN IF EXISTS phone,
            DROP COLUMN IF EXISTS nickname,
            DROP COLUMN IF EXISTS bio,
            DROP COLUMN IF EXISTS company_name,
            DROP COLUMN IF EXISTS company_position,
            DROP COLUMN IF EXISTS is_phone_verified,
            DROP COLUMN IF EXISTS updated_at;
        """))
        
        await session.commit()
        print("✅ 用户表结构回滚完成")


if __name__ == "__main__":
    import asyncio
    
    async def main():
        print("🚀 开始执行用户注册功能数据库迁移...")
        await upgrade()
        print("🎉 迁移完成！")
    
    asyncio.run(main())