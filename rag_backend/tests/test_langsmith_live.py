"""
LangSmith 实时追踪测试
运行一次真实的 LLM 调用来验证追踪功能
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 验证 LangSmith 配置
print("=" * 60)
print("  LangSmith 实时追踪测试")
print("=" * 60)

print("\n📋 LangSmith 配置:")
print(f"   LANGSMITH_TRACING: {os.getenv('LANGSMITH_TRACING', '未设置')}")
print(f"   LANGSMITH_PROJECT: {os.getenv('LANGSMITH_PROJECT', '未设置')}")
print(f"   LANGSMITH_API_KEY: {os.getenv('LANGSMITH_API_KEY', '未设置')[:10]}...")

if os.getenv('LANGSMITH_TRACING') != 'true':
    print("\n⚠️  警告: LANGSMITH_TRACING 未设置为 true")
    print("   请在 .env 文件中设置: LANGSMITH_TRACING=true")
    sys.exit(1)

# 测试 MiniMax 适配器
print("\n" + "=" * 60)
print("  1. 初始化 MiniMax 适配器")
print("=" * 60)

try:
    from app.agent_framework.llm.minimax_adapter import MiniMaxAdapter
    from app.schemas.message import Message
    
    adapter = MiniMaxAdapter(
        api_key=os.getenv('MINIMAX_API_KEY'),
        model=os.getenv('MINIMAX_MODEL', 'MiniMax-Text-01')
    )
    print("✅ MiniMax 适配器初始化成功")
    print(f"   模型: {adapter.model_name}")
    print(f"   Base URL: {adapter.base_url}")
    
except Exception as e:
    print(f"❌ MiniMax 适配器初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 执行真实的 LLM 调用
print("\n" + "=" * 60)
print("  2. 执行真实 LLM 调用（触发 LangSmith 追踪）")
print("=" * 60)

try:
    import asyncio
    from datetime import datetime
    
    async def run_test():
        messages = [
            Message(role="user", content="你好，请用一句话介绍自己。")
        ]
        
        print("\n📤 发送请求...")
        print(f"   模型: {adapter.model_name}")
        print(f"   消息: {messages[0].content}")
        print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 记录开始时间
        import time
        start_time = time.time()
        
        # 调用 LLM（这里会触发 LangSmith 追踪！）
        response = await adapter.chat(messages)
        
        # 计算耗时
        elapsed = time.time() - start_time
        
        print("\n📥 收到响应:")
        print(f"   内容: {response.content[:100]}...")
        print(f"   Token 使用: {response.usage}")
        print(f"   耗时: {elapsed:.2f}秒")
        print(f"   完成原因: {response.finish_reason}")
        
        return response
    
    # 运行测试
    response = asyncio.run(run_test())
    print("\n✅ LLM 调用成功！")
    
except Exception as e:
    print(f"\n❌ LLM 调用失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 验证 LangSmith 追踪
print("\n" + "=" * 60)
print("  3. 验证 LangSmith 追踪")
print("=" * 60)

try:
    from app.langsmith_integration import get_tracer
    
    tracer = get_tracer()
    
    if tracer and tracer.client:
        print("✅ LangSmith 追踪器已就绪")
        print(f"   项目: {tracer.project_name}")
        print(f"   追踪状态: {tracer.is_enabled}")
        
        # 检查追踪记录数
        print("\n📊 追踪状态:")
        print("   ✅ 追踪记录已发送")
        print("   ⏱️  可能在 5-10 秒后出现在 LangSmith Dashboard")
        print("\n🌐 请访问: https://smith.langchain.com")
        print(f"   📁 项目: {os.getenv('LANGSMITH_PROJECT', 'financial_rag')}")
    else:
        print("⚠️  LangSmith 追踪器未就绪")
        
except Exception as e:
    print(f"⚠️  追踪器检查失败: {e}")

print("\n" + "=" * 60)
print("  测试完成")
print("=" * 60)
print("\n💡 提示:")
print("   1. 打开浏览器访问: https://smith.langchain.com")
print("   2. 登录后选择项目: financial_rag")
print("   3. 等待 5-10 秒刷新页面")
print("   4. 应该能看到刚才的 LLM 调用追踪")
print("   5. 点击追踪记录查看详细信息（输入、输出、Token 使用等）")
print("\n" + "=" * 60)
