# migrations/create_advanced_features_simple.py

"""
简化版高级特性数据库迁移脚本
不依赖 .env 文件，直接使用硬编码连接
"""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


# 数据库连接配置（硬编码，避免 .env 编码问题）
DATABASE_URL = "postgresql+asyncpg://postgres:REDACTED_PG_PASSWORD@localhost:5432/rag_db"


async def create_tables():
    """创建所有高级特性的表"""
    
    print("🔄 开始创建高级特性数据库表...")
    
    engine = create_async_engine(DATABASE_URL)
    
    try:
        async with engine.begin() as conn:
            # ==========================================
            # 1. Agent 决策可视化表
            # ==========================================
            print("\n📊 创建 Agent 追踪表...")
            
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS agent_traces (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id UUID,
                    message_id UUID,
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
            
            print("✅ Agent 追踪表创建成功")
            
            # ==========================================
            # 2. 工具调用链追踪表
            # ==========================================
            print("\n🔧 创建工具调用追踪表...")
            
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tool_call_traces (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    trace_id UUID REFERENCES agent_traces(id) ON DELETE CASCADE,
                    parent_call_id UUID REFERENCES tool_call_traces(id) ON DELETE CASCADE,
                    tool_name VARCHAR NOT NULL,
                    tool_type VARCHAR DEFAULT 'function',
                    input_params JSONB,
                    output_result TEXT,
                    start_time FLOAT NOT NULL,
                    end_time FLOAT,
                    duration FLOAT,
                    status VARCHAR DEFAULT 'running',
                    error_message TEXT,
                    metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            print("✅ 工具调用追踪表创建成功")
            
            # ==========================================
            # 3. 自动 Prompt 优化表
            # ==========================================
            print("\n🤖 创建 Prompt 优化表...")
            
            # Prompt 模板表
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS prompt_templates (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR UNIQUE NOT NULL,
                    version VARCHAR NOT NULL,
                    template_text TEXT NOT NULL,
                    agent_type VARCHAR NOT NULL,
                    use_case VARCHAR DEFAULT 'general',
                    is_active BOOLEAN DEFAULT TRUE,
                    is_baseline BOOLEAN DEFAULT FALSE,
                    variables JSONB,
                    description TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE
                );
            """))
            
            # Prompt 执行记录表
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS prompt_executions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    template_id UUID REFERENCES prompt_templates(id) ON DELETE CASCADE,
                    trace_id UUID REFERENCES agent_traces(id) ON DELETE CASCADE,
                    user_query TEXT NOT NULL,
                    final_answer TEXT,
                    execution_time FLOAT,
                    iterations_count INTEGER,
                    tool_calls_count INTEGER,
                    success BOOLEAN NOT NULL,
                    user_feedback INTEGER,
                    auto_score FLOAT,
                    error_type VARCHAR,
                    error_message TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # A/B 测试表
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS prompt_ab_tests (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    test_name VARCHAR UNIQUE NOT NULL,
                    description TEXT,
                    template_a_id UUID REFERENCES prompt_templates(id),
                    template_b_id UUID REFERENCES prompt_templates(id),
                    traffic_split FLOAT DEFAULT 0.5,
                    status VARCHAR DEFAULT 'running',
                    start_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    end_date TIMESTAMP WITH TIME ZONE,
                    total_executions INTEGER DEFAULT 0,
                    winner_template_id UUID,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE
                );
            """))
            
            print("✅ Prompt 优化表创建成功")
            
            # ==========================================
            # 4. 创建索引
            # ==========================================
            print("\n📑 创建索引...")
            
            # Agent 追踪索引
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_agent_traces_session_id ON agent_traces(session_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_agent_traces_created_at ON agent_traces(created_at DESC);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_agent_steps_trace_id ON agent_steps(trace_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_agent_steps_step_number ON agent_steps(trace_id, step_number);"))
            
            # 工具调用索引
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tool_calls_trace_id ON tool_call_traces(trace_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tool_calls_tool_name ON tool_call_traces(tool_name);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tool_calls_created_at ON tool_call_traces(created_at DESC);"))
            
            # Prompt 优化索引
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prompt_executions_template_id ON prompt_executions(template_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prompt_executions_created_at ON prompt_executions(created_at DESC);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prompt_ab_tests_status ON prompt_ab_tests(status);"))
            
            print("✅ 索引创建成功")
        
        print("\n🎉 所有高级特性数据库表创建完成！")
        print("\n📊 已创建的表：")
        print("   1. agent_traces - Agent 追踪记录")
        print("   2. agent_steps - Agent 执行步骤")
        print("   3. tool_call_traces - 工具调用追踪")
        print("   4. prompt_templates - Prompt 模板")
        print("   5. prompt_executions - Prompt 执行记录")
        print("   6. prompt_ab_tests - A/B 测试")
        
        return True
        
    except Exception as e:
        print(f"❌ 创建表失败: {e}")
        return False
        
    finally:
        await engine.dispose()


async def main():
    """主函数"""
    success = await create_tables()
    
    if success:
        print("\n✅ 数据库迁移成功完成！")
        print("\n🚀 下一步：")
        print("   1. 启动应用: python -m uvicorn app.main:app --reload")
        print("   2. 访问文档: http://localhost:8000/docs")
        print("   3. 运行测试: python test_all_advanced_features.py")
    else:
        print("\n❌ 数据库迁移失败！")
        print("请检查数据库连接和权限设置")


if __name__ == "__main__":
    asyncio.run(main())