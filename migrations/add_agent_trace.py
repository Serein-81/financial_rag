# migrations/add_agent_trace.py

"""
添加 Agent 追踪相关表

创建 agent_traces 和 agent_steps 表用于记录 Agent 的执行过程
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.session import engine


async def upgrade():
    """创建 Agent 追踪相关表"""
    
    print("🔄 开始创建 Agent 追踪表...")
    
    async with engine.begin() as conn:
        # 创建 agent_traces 表
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS agent_traces (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
                message_id UUID REFERENCES chat_messages(id) ON DELETE CASCADE,
                agent_type VARCHAR NOT NULL,
                user_query TEXT NOT NULL,
                final_answer TEXT,
                total_iterations INTEGER DEFAULT 0,
                total_time FLOAT DEFAULT 0.0,
                tool_calls_count INTEGER DEFAULT 0,
                status VARCHAR DEFAULT 'running',
                error_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP WITH TIME ZONE
            );
        """))
        
        print("✅ agent_traces 表创建成功")
        
        # 创建 agent_steps 表
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS agent_steps (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                trace_id UUID NOT NULL REFERENCES agent_traces(id) ON DELETE CASCADE,
                step_number INTEGER NOT NULL,
                step_type VARCHAR NOT NULL,
                content TEXT NOT NULL,
                tool_name VARCHAR,
                tool_input JSONB,
                tool_output TEXT,
                tool_duration FLOAT,
                confidence FLOAT,
                metadata JSONB,
                timestamp FLOAT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        print("✅ agent_steps 表创建成功")
        
        # 创建索引
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_agent_traces_session_id 
            ON agent_traces(session_id);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_agent_traces_created_at 
            ON agent_traces(created_at DESC);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_agent_steps_trace_id 
            ON agent_steps(trace_id);
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_agent_steps_step_number 
            ON agent_steps(trace_id, step_number);
        """))
        
        print("✅ 索引创建成功")
    
    print("🎉 Agent 追踪表创建完成！")


async def downgrade():
    """删除 Agent 追踪相关表"""
    
    print("🔄 开始删除 Agent 追踪表...")
    
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS agent_steps CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS agent_traces CASCADE;"))
    
    print("✅ Agent 追踪表删除完成")


async def main():
    """主函数"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        await downgrade()
    else:
        await upgrade()
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
