"""
LangSmith 集成测试脚本

验证 LangSmith 追踪功能是否正常工作
"""

import os
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入 LangSmith 配置
from app.langsmith_integration import setup_langsmith_config, get_langsmith_config, get_tracer


def print_section(title):
    """打印分节标题"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


async def test_langsmith_connection():
    """测试 LangSmith 连接"""
    print_section("1. LangSmith 连接测试")
    
    # 配置
    setup_langsmith_config()
    
    # 获取配置
    config = get_langsmith_config()
    
    print(f"✅ LangSmith 配置信息:")
    print(f"   启用追踪: {config['enabled']}")
    print(f"   追踪状态: {config['tracing']}")
    print(f"   项目名称: {config['project']}")
    print(f"   API 端点: {config['endpoint']}")
    
    if config['api_key']:
        # 只显示前4位和后4位
        key_display = config['api_key'][:8] + "..." + config['api_key'][-4:]
        print(f"   API Key: {key_display}")
    else:
        print(f"   API Key: 未设置")
    
    return config['enabled']


async def test_langsmith_tracer():
    """测试 LangSmith 追踪器"""
    print_section("2. LangSmith 追踪器测试")
    
    tracer = get_tracer()
    
    print(f"✅ 获取追踪器:")
    print(f"   追踪器对象: {tracer}")
    print(f"   LangSmith 客户端: {tracer.client}")
    print(f"   项目名称: {tracer.project_name}")
    
    if not tracer.client:
        print(f"\n⚠️ LangSmith 客户端未初始化")
        print(f"   可能原因:")
        print(f"   1. LANGSMITH_API_KEY 未设置")
        print(f"   2. LANGSMITH_TRACING != 'true'")
        print(f"   3. langsmith 包未安装")
        return False
    
    return True


async def test_trace_llm_call(tracer):
    """测试 LLM 调用追踪"""
    print_section("3. LLM 调用追踪测试")
    
    if not tracer.client:
        print(f"⚠️ 跳过 LLM 追踪测试（客户端未初始化）")
        return
    
    try:
        print(f"📝 测试追踪 LLM 调用...")
        
        tracer.trace_llm_call(
            model_name="MiniMax-Text-01",
            prompt="分析公司的财务状况，包括收入、支出和利润。",
            response="根据财务数据分析，公司2023年总收入为1000万元，支出为600万元，净利润为400万元。",
            token_usage={
                "prompt": 156,
                "completion": 89,
                "total": 245
            },
            metadata={
                "temperature": 0.7,
                "max_tokens": 2000,
                "session_id": "test_session_001"
            }
        )
        
        print(f"✅ LLM 调用追踪成功!")
        print(f"   模型: MiniMax-Text-01")
        print(f"   Token 使用: 156 + 89 = 245")
        
    except Exception as e:
        print(f"❌ LLM 追踪失败: {e}")


async def test_trace_tool_call(tracer):
    """测试工具调用追踪"""
    print_section("4. 工具调用追踪测试")
    
    if not tracer.client:
        print(f"⚠️ 跳过工具追踪测试（客户端未初始化）")
        return
    
    try:
        print(f"📝 测试追踪工具调用...")
        
        # 测试成功调用
        tracer.trace_tool_call(
            tool_name="search_knowledge_base",
            arguments={
                "query": "税务法规",
                "top_k": 5,
                "collection": "tax_laws"
            },
            result={
                "documents": [
                    {"title": "企业所得税法", "content": "..."},
                    {"title": "增值税暂行条例", "content": "..."}
                ],
                "count": 2
            }
        )
        
        print(f"✅ 工具调用追踪成功!")
        print(f"   工具: search_knowledge_base")
        
        # 测试错误调用
        tracer.trace_tool_call(
            tool_name="calculate_tax",
            arguments={"income": 1000000, "tax_rate": 0.25},
            result=None,
            error="参数错误: tax_rate 必须在 0-1 之间"
        )
        
        print(f"✅ 工具错误追踪成功!")
        
    except Exception as e:
        print(f"❌ 工具追踪失败: {e}")


async def test_minimax_adapter():
    """测试 MiniMax 适配器集成"""
    print_section("5. MiniMax 适配器集成测试")
    
    try:
        from app.agent_framework.llm.minimax_adapter import MiniMaxAdapter
        
        # 检查 API Key
        api_key = os.getenv("MINIMAX_API_KEY")
        if not api_key:
            print(f"⚠️ 跳过 MiniMax 适配器测试（MINIMAX_API_KEY 未设置）")
            return
        
        print(f"📝 创建 MiniMax 适配器...")
        
        adapter = MiniMaxAdapter(
            api_key=api_key,
            model_name="MiniMax-Text-01",
            group_id=os.getenv("MINIMAX_GROUP_ID", "")
        )
        
        print(f"✅ MiniMax 适配器创建成功")
        print(f"   模型: {adapter.model_name}")
        print(f"   基础 URL: {adapter.base_url}")
        
        # 测试简单的 LLM 调用
        print(f"\n📝 测试 LLM 调用（带追踪）...")
        
        response = await adapter.generate(
            prompt="你好，请简单介绍一下你自己。",
            temperature=0.7,
            max_tokens=100
        )
        
        print(f"✅ LLM 调用成功!")
        print(f"   模型: {response.model}")
        print(f"   Token: {response.prompt_tokens} + {response.completion_tokens} = {response.total_tokens}")
        print(f"   响应长度: {len(response.content)} 字符")
        print(f"\n   响应内容:")
        print(f"   {response.content[:200]}...")
        
        # 关闭适配器
        await adapter.close()
        
    except Exception as e:
        print(f"❌ MiniMax 适配器测试失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("  LangSmith 集成测试")
    print("=" * 60)
    
    # 1. 测试连接
    enabled = await test_langsmith_connection()
    
    # 2. 测试追踪器
    tracer_ready = await test_langsmith_tracer()
    
    # 3. 获取追踪器
    tracer = get_tracer()
    
    # 4. 测试 LLM 调用追踪
    await test_trace_llm_call(tracer)
    
    # 5. 测试工具调用追踪
    await test_trace_tool_call(tracer)
    
    # 6. 测试 MiniMax 适配器集成
    await test_minimax_adapter()
    
    # 总结
    print_section("测试总结")
    
    print(f"✅ LangSmith 集成状态:")
    print(f"   追踪启用: {enabled}")
    print(f"   追踪器就绪: {tracer_ready}")
    
    if enabled and tracer_ready:
        print(f"\n🎉 LangSmith 集成成功!")
        print(f"\n请访问 https://smith.langchain.com 查看追踪结果")
        print(f"项目名称: {tracer.project_name}")
    else:
        print(f"\n⚠️ LangSmith 集成未完全就绪")
        print(f"\n请检查:")
        print(f"1. .env 文件中是否配置了 LANGSMITH_* 环境变量")
        print(f"2. LANGSMITH_TRACING 是否设置为 'true'")
        print(f"3. LANGSMITH_API_KEY 是否正确")
        print(f"4. 是否已安装 langsmith: pip install langsmith")


if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())
