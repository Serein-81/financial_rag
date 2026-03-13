# migrations/docker_migration.py

"""
Docker 环境专用的数据库迁移脚本
用于在容器启动时自动创建高级特性表
"""

import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# 从环境变量读取数据库配置
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "REDACTED_PG_PASSWORD")
POSTGRES_SERVER = os.getenv("POSTGRES_SERVER", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "rag_db")

DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"


async def wait_for_db():
    """等待数据库服务启动"""
    print("🔄 等待数据库服务启动...")
    
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            engine = create_async_engine(DATABASE_URL)
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            print("✅ 数据库连接成功")
            return True
        except Exception as e:
            retry_count += 1
            print(f"⏳ 数据库连接失败 ({retry_count}/{max_retries}): {e}")
            await asyncio.sleep(2)
    
    print("❌ 数据库连接超时")
    return False


async def create_advanced_features_tables():
    """创建高级特性数据库表"""
    
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


async def insert_sample_data():
    """插入示例数据"""
    print("\n🌱 插入示例数据...")
    
    engine = create_async_engine(DATABASE_URL)
    
    try:
        async with engine.begin() as conn:
            # 插入示例 Prompt 模板
            await conn.execute(text("""
                INSERT INTO prompt_templates (name, version, template_text, agent_type, description, is_baseline)
                VALUES 
                    ('react_agent_basic', '1.0', '你是一个智能助手，请按照以下步骤思考：\n1. 分析问题\n2. 选择工具\n3. 执行行动\n4. 观察结果\n5. 给出答案', 'react', 'ReAct Agent 基础版本', true),
                    ('react_agent_enhanced', '2.0', '你是一个高效的智能助手。请遵循 ReAct 框架：\n\nThought: 分析当前情况和需要采取的行动\nAction: 选择并执行最合适的工具\nObservation: 仔细观察工具执行结果\n\n重复上述过程直到能够给出完整答案。', 'react', 'ReAct Agent 增强版本', false)
                ON CONFLICT (name) DO NOTHING;
            """))
            
            print("✅ 示例数据插入成功")
            
    except Exception as e:
        print(f"⚠️ 插入示例数据失败: {e}")
        
    finally:
        await engine.dispose()


async def main():
    """主函数"""
    print("🐳 Docker 环境数据库迁移开始...")
    
    # 1. 等待数据库启动
    if not await wait_for_db():
        print("❌ 数据库连接失败，退出迁移")
        sys.exit(1)
    
    # 2. 创建高级特性表
    if not await create_advanced_features_tables():
        print("❌ 表创建失败，退出迁移")
        sys.exit(1)
    
    # 3. 插入示例数据
    await insert_sample_data()
    
    print("\n✅ Docker 环境数据库迁移完成！")
    print("\n🚀 高级特性已就绪：")
    print("   🎯 Agent 决策可视化")
    print("   🔧 工具调用链追踪")
    print("   🤖 自动 Prompt 优化")
    
    print("\n📖 API 文档地址: http://localhost:8000/docs")
    print("🔍 查看新增的 API 标签:")
    print("   - Agent Trace")
    print("   - Tool Trace")
    print("   - Prompt Optimization")


if __name__ == "__main__":
    asyncio.run(main())