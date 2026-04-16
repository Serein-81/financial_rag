"""
LangSmith + MiniMax 独立测试（等待版）
添加 wait_for_all_tracers 确保追踪完全同步
"""
import os
import sys
import json
import time
import asyncio
import httpx
from datetime import datetime
from typing import Dict, List, Optional, Any

# 加载 .env 文件
from dotenv import load_dotenv
load_dotenv()

print("=" * 70)
print("  LangSmith + MiniMax 独立测试（等待版）")
print("=" * 70)

# 配置检查
print("\n📋 配置检查:")
MINIMAX_API_KEY = os.getenv('MINIMAX_API_KEY')
MINIMAX_MODEL = os.getenv('MINIMAX_MODEL', 'MiniMax-Text-01')
MINIMAX_BASE_URL = os.getenv('MINIMAX_BASE_URL', 'https://api.minimax.chat/v1')
MINIMAX_GROUP_ID = os.getenv('MINIMAX_GROUP_ID')

LANGSMITH_TRACING = os.getenv('LANGSMITH_TRACING', 'false')
LANGSMITH_API_KEY = os.getenv('LANGSMITH_API_KEY')
LANGSMITH_PROJECT = os.getenv('LANGSMITH_PROJECT', 'financial_rag')
LANGSMITH_ENDPOINT = os.getenv('LANGSMITH_ENDPOINT', 'https://api.smith.langchain.com')

print(f"   MiniMax API Key: {'✅ 已设置' if MINIMAX_API_KEY else '❌ 未设置'}")
print(f"   MiniMax Model: {MINIMAX_MODEL}")
print(f"   MiniMax Group ID: {'✅ 已设置' if MINIMAX_GROUP_ID else '❌ 未设置'}")
print(f"   LangSmith Tracing: {LANGSMITH_TRACING}")
print(f"   LangSmith Project: {LANGSMITH_PROJECT}")
print(f"   LangSmith API Key: {'✅ 已设置' if LANGSMITH_API_KEY else '❌ 未设置'}")

if not MINIMAX_API_KEY:
    print("\n❌ 错误: MINIMAX_API_KEY 未设置")
    sys.exit(1)

if not MINIMAX_GROUP_ID:
    print("\n❌ 错误: MINIMAX_GROUP_ID 未设置")
    sys.exit(1)

# 1. 初始化 LangSmith Client
print("\n" + "=" * 70)
print("  1. 初始化 LangSmith Client")
print("=" * 70)

langsmith_client = None
if LANGSMITH_TRACING.lower() == 'true' and LANGSMITH_API_KEY:
    try:
        from langsmith import Client
        
        langsmith_client = Client(
            api_key=LANGSMITH_API_KEY,
            api_url=LANGSMITH_ENDPOINT
        )
        print("✅ LangSmith Client 初始化成功")
        print(f"   项目: {LANGSMITH_PROJECT}")
        print(f"   端点: {LANGSMITH_ENDPOINT}")
        
    except ImportError:
        print("⚠️  langsmith 包未安装，运行: pip install langsmith")
    except Exception as e:
        print(f"❌ LangSmith Client 初始化失败: {e}")
else:
    print("⚠️  LangSmith 追踪未启用或 API Key 未设置")

# 2. 调用 MiniMax API
print("\n" + "=" * 70)
print("  2. 调用 MiniMax API")
print("=" * 70)

async def call_minimax(messages: List[Dict[str, str]], model: str, api_key: str, group_id: str) -> Dict[str, Any]:
    """直接调用 MiniMax API"""
    
    url = f"{MINIMAX_BASE_URL}/text/chatcompletion_v2"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    print(f"\n📤 发送请求...")
    print(f"   URL: {url}")
    print(f"   Model: {model}")
    print(f"   Messages: {len(messages)}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        start_time = time.time()
        response = await client.post(url, headers=headers, json=payload)
        elapsed = time.time() - start_time
        
        if response.status_code != 200:
            raise Exception(f"API 调用失败: {response.status_code} - {response.text}")
        
        result = response.json()
        print(f"\n📥 收到响应 (耗时: {elapsed:.2f}s)")
        
        return result, elapsed

try:
    messages = [
        {"role": "user", "content": "你好，请用一句话介绍自己。"}
    ]
    
    result, elapsed = asyncio.run(call_minimax(
        messages=messages,
        model=MINIMAX_MODEL,
        api_key=MINIMAX_API_KEY,
        group_id=MINIMAX_GROUP_ID
    ))
    
    # 解析响应
    choices = result.get('choices', [])
    if not choices:
        raise Exception("响应中没有 choices")

    choice = choices[0]
    response_content = choice.get('message', {}).get('content', '')
    finish_reason = choice.get('finish_reason', 'unknown')
    
    # Token 使用量
    usage = result.get('usage', {})
    prompt_tokens = usage.get('prompt_tokens', 0)
    completion_tokens = usage.get('completion_tokens', 0)
    total_tokens = usage.get('total_tokens', 0)
    
    print(f"\n✅ LLM 调用成功!")
    print(f"   📝 内容: {response_content[:150]}{'...' if len(response_content) > 150 else ''}")
    print(f"   ⏱️  耗时: {elapsed:.2f}秒")
    print(f"   📊 Token 使用:")
    print(f"      - Prompt: {prompt_tokens}")
    print(f"      - Completion: {completion_tokens}")
    print(f"      - Total: {total_tokens}")
    print(f"   🏁 完成原因: {finish_reason}")
    
except Exception as e:
    print(f"\n❌ LLM 调用失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. 创建 LangSmith 追踪记录
print("\n" + "=" * 70)
print("  3. 创建 LangSmith 追踪记录")
print("=" * 70)

if langsmith_client:
    try:
        print("\n📤 创建追踪记录...")
        
        # 创建 run
        run = langsmith_client.create_run(
            name="MiniMax-Chat",
            run_type="llm",
            project_name=LANGSMITH_PROJECT,
            inputs={
                "model": MINIMAX_MODEL,
                "messages": messages
            },
            outputs={
                "content": response_content,
                "finish_reason": finish_reason,
                "usage": usage
            },
            extra={
                "elapsed_time": elapsed,
                "temperature": 0.7,
                "max_tokens": 100
            },
            tags=["test", "minimax"]
        )
        
        print("✅ 追踪记录创建成功!")
        print(f"   项目: {LANGSMITH_PROJECT}")
        
    except Exception as e:
        print(f"⚠️  追踪记录创建失败: {e}")
        import traceback
        traceback.print_exc()
else:
    print("⚠️  跳过追踪 - LangSmith Client 未初始化")

# 4. 等待所有追踪完成
print("\n" + "=" * 70)
print("  4. 等待追踪同步")
print("=" * 70)

if langsmith_client:
    print("\n⏱️  等待 LangSmith 追踪完全同步...")
    print("   这可能需要 5-10 秒...")
    
    try:
        # 方法 1: 使用 flush 方法（如果有的话）
        if hasattr(langsmith_client, 'flush'):
            print("   调用 langsmith_client.flush()...")
            langsmith_client.flush()
            print("   ✅ flush() 调用成功")
        
        # 方法 2: 使用 wait_for_all_tracers（LangChain/LangSmith 标准方法）
        try:
            from langsmith.run_helpers import wait_for_all_tracers
            print("   调用 wait_for_all_tracers()...")
            wait_for_all_tracers(timeout=30)  # 等待最多 30 秒
            print("   ✅ wait_for_all_tracers() 完成")
        except ImportError:
            print("   ⚠️  wait_for_all_tracers 不可用，跳过")
        except Exception as e:
            print(f"   ⚠️  wait_for_all_tracers 失败: {e}")
        
        # 方法 3: 手动等待一段时间
        print("   ⏳ 额外等待 5 秒确保同步...")
        time.sleep(5)
        
        print("✅ 追踪同步完成!")
        
    except Exception as e:
        print(f"⚠️  等待过程出错: {e}")
        import traceback
        traceback.print_exc()
        print("   继续执行，追踪可能在后台继续同步...")
else:
    print("⚠️  跳过等待 - LangSmith Client 未初始化")

# 5. 完成
print("\n" + "=" * 70)
print("  测试完成")
print("=" * 70)

print("\n🎉 恭喜! LLM 调用成功完成!")

if langsmith_client:
    print("\n✅ LangSmith 追踪记录已发送并同步完成!")
    print("\n📋 查看追踪结果:")
    print("   1. 打开浏览器访问: https://smith.langchain.com")
    print("   2. 登录你的账号")
    print("   3. 点击左侧 'Projects'")
    print("   4. 选择项目: financial_rag")
    print("   5. 应该已经能看到追踪记录（无需再等待）")
    print("\n💡 提示:")
    print("   - 追踪记录现在应该已经同步完成")
    print("   - 如果仍然看不到，点击刷新按钮")
    print("   - 检查右上角时间范围（默认显示最近 6 小时）")
else:
    print("\n⚠️  LangSmith 追踪未启用")
    print("   要启用追踪，请在 .env 文件中设置:")
    print("   LANGSMITH_TRACING=true")

print("\n" + "=" * 70)
