"""
LangSmith 实时追踪测试（直接版）
绕过复杂的依赖导入，直接测试 MiniMax 适配器和 LangSmith 追踪
"""
import os
import sys
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import json

# 加载 .env 文件
from dotenv import load_dotenv
load_dotenv()

print("=" * 70)
print("  LangSmith 实时追踪测试（直接版）")
print("=" * 70)

print("\n📋 环境配置检查:")
print(f"   MINIMAX_API_KEY: {'✅ 已设置' if os.getenv('MINIMAX_API_KEY') else '❌ 未设置'}")
print(f"   MINIMAX_MODEL: {os.getenv('MINIMAX_MODEL', 'MiniMax-Text-01')}")
print(f"   LANGSMITH_TRACING: {os.getenv('LANGSMITH_TRACING', '❌ 未设置')}")
print(f"   LANGSMITH_PROJECT: {os.getenv('LANGSMITH_PROJECT', '❌ 未设置')}")
print(f"   LANGSMITH_API_KEY: {'✅ 已设置' if os.getenv('LANGSMITH_API_KEY') else '❌ 未设置'}")

if not os.getenv('MINIMAX_API_KEY'):
    print("\n❌ 错误: MINIMAX_API_KEY 未设置")
    sys.exit(1)

if os.getenv('LANGSMITH_TRACING') != 'true':
    print("\n⚠️  警告: LANGSMITH_TRACING 未设置为 true，追踪将不会生效")
    print("   继续运行，但不进行追踪...")

# 1. 初始化 LangSmith 追踪器
print("\n" + "=" * 70)
print("  1. 初始化 LangSmith 追踪器")
print("=" * 70)

langsmith_tracer = None
try:
    sys.path.insert(0, str(Path(__file__).parent))
    from app.langsmith_integration import get_tracer
    
    langsmith_tracer = get_tracer()
    
    if langsmith_tracer and langsmith_tracer.client:
        print("✅ LangSmith 追踪器初始化成功")
        print(f"   项目: {langsmith_tracer.project_name}")
        print(f"   状态: {'已启用' if langsmith_tracer.is_enabled else '未启用'}")
    else:
        print("⚠️  LangSmith 追踪器未就绪")
        
except Exception as e:
    print(f"❌ LangSmith 追踪器初始化失败: {e}")
    import traceback
    traceback.print_exc()

# 2. 导入 MiniMax 适配器
print("\n" + "=" * 70)
print("  2. 初始化 MiniMax 适配器")
print("=" * 70)

try:
    sys.path.insert(0, str(Path(__file__).parent / "app" / "agent_framework" / "llm"))
    
    # 直接导入 MiniMax 适配器
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "minimax_adapter", 
        Path(__file__).parent / "app" / "agent_framework" / "llm" / "minimax_adapter.py"
    )
    minimax_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(minimax_module)
    
    MiniMaxAdapter = minimax_module.MiniMaxAdapter
    Message = minimax_module.Message
    
    # 初始化适配器
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

# 3. 执行真实的 LLM 调用
print("\n" + "=" * 70)
print("  3. 执行真实 LLM 调用（触发 LangSmith 追踪）")
print("=" * 70)

async def run_llm_call():
    messages = [
        Message(role="user", content="你好，请用一句话介绍自己。")
    ]
    
    print(f"\n📤 发送 LLM 请求...")
    print(f"   模型: {adapter.model_name}")
    print(f"   消息: {messages[0].content}")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   ⏱️  等待响应...")
    
    # 记录开始时间
    start_time = time.time()
    
    # 执行 LLM 调用
    response = await adapter._chat(messages, temperature=0.7, max_tokens=100)
    
    # 计算耗时
    elapsed = time.time() - start_time
    
    return response, elapsed

try:
    response, elapsed = asyncio.run(run_llm_call())
    
    print("\n📥 收到 LLM 响应:")
    print(f"   ✅ 状态: 成功")
    print(f"   📝 内容: {response.content[:150]}{'...' if len(response.content) > 150 else ''}")
    print(f"   ⏱️  耗时: {elapsed:.2f}秒")
    
    if response.usage:
        print(f"   📊 Token 使用:")
        print(f"      - Prompt: {response.usage.get('prompt_tokens', 0)}")
        print(f"      - Completion: {response.usage.get('completion_tokens', 0)}")
        print(f"      - Total: {response.usage.get('total_tokens', 0)}")
    
    print(f"   🏁 完成原因: {response.finish_reason}")
    
except Exception as e:
    print(f"\n❌ LLM 调用失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. 手动追踪 LLM 调用
print("\n" + "=" * 70)
print("  4. 发送 LangSmith 追踪记录")
print("=" * 70)

if langsmith_tracer and langsmith_tracer.client:
    try:
        print("\n📤 追踪 LLM 调用...")
        
        langsmith_tracer.trace_llm_call(
            model_name=adapter.model_name,
            prompt="你好，请用一句话介绍自己。",
            response=response.content,
            token_usage={
                "prompt": response.usage.get('prompt_tokens', 0) if response.usage else 0,
                "completion": response.usage.get('completion_tokens', 0) if response.usage else 0,
                "total": response.usage.get('total_tokens', 0) if response.usage else 0
            },
            metadata={
                "temperature": 0.7,
                "max_tokens": 100,
                "base_url": adapter.base_url,
                "finish_reason": response.finish_reason,
                "elapsed_time": elapsed
            }
        )
        
        print("✅ 追踪记录已发送！")
        print(f"   ⏱️  等待 5-10 秒后刷新 LangSmith Dashboard")
        
    except Exception as e:
        print(f"⚠️  追踪失败: {e}")
        import traceback
        traceback.print_exc()
else:
    print("⚠️  跳过追踪 - LangSmith 追踪器未就绪")

# 5. 总结
print("\n" + "=" * 70)
print("  测试完成")
print("=" * 70)

print("\n🎉 恭喜！LLM 调用成功完成！")
print("\n📋 查看 LangSmith 追踪结果:")
print("   1. 打开浏览器访问: https://smith.langchain.com")
print("   2. 登录你的 LangChain 账号")
print("   3. 点击左侧菜单的 'Projects'")
print("   4. 选择项目: financial_rag")
print("   5. 等待 5-10 秒后点击刷新按钮 🔄")
print("   6. 应该能看到新的追踪记录")
print("\n📊 追踪记录包含:")
print("   - LLM 输入/输出内容")
print("   - Token 使用统计")
print("   - 请求耗时")
print("   - 模型参数")
print("   - 完整调用链")

print("\n💡 小提示:")
print("   - 如果看不到记录，等待 30 秒后重试")
print("   - 检查右上角的时间范围（默认显示最近 6 小时）")
print("   - 点击单条记录查看详细信息")
print("   - 使用过滤器筛选追踪类型（LLM/Tool）")

print("\n" + "=" * 70)
