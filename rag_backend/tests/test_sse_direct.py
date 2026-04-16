"""
SSE 连接直接测试脚本

测试 SSE 政策通知连接是否正常工作
"""

import asyncio
import httpx
import sys


async def test_sse_connection():
    """测试 SSE 连接"""

    # 测试数据
    base_url = "http://localhost:8000"
    token = "YOUR_TOKEN_HERE"  # 替换为实际 token
    tenant_id = "test_tenant_001"

    url = f"{base_url}/api/v1/policy-notifications/stream"
    params = {
        "token": token,
        "tenant_id": tenant_id
    }

    print(f"🔍 测试 SSE 连接")
    print(f"URL: {url}")
    print(f"参数: {params}")
    print()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            print("📡 发起 SSE 连接请求...")

            async with client.stream("GET", url, params=params) as response:
                print(f"✅ 状态码: {response.status_code}")
                print(f"响应头: {dict(response.headers)}")
                print()

                if response.status_code == 200:
                    print("🎉 SSE 连接成功！")
                    print()

                    # 接收前几条消息
                    message_count = 0
                    max_messages = 5

                    async for line in response.aiter_lines():
                        if line:
                            print(f"📨 收到消息: {line}")
                            message_count += 1

                            if message_count >= max_messages:
                                print(f"\n✅ 收到 {max_messages} 条消息，连接正常！")
                                break
                else:
                    print(f"❌ SSE 连接失败: {response.status_code}")
                    try:
                        error_text = await response.aread()
                        print(f"错误详情: {error_text.decode('utf-8')}")
                    except:
                        pass

                    # 检查错误详情
                    if response.status_code == 403:
                        print("\n🔍 诊断信息:")
                        print("1. 检查 token 是否有效")
                        print("2. 检查 tenant_id 是否正确")
                        print("3. 检查用户是否有权限访问该租户")
                    elif response.status_code == 401:
                        print("\n🔍 诊断信息:")
                        print("1. Token 已过期或无效")
                        print("2. 请重新登录获取新 token")

    except httpx.TimeoutException:
        print("❌ 连接超时")
        print("可能的原因:")
        print("1. 后端服务未启动")
        print("2. 网络连接问题")
        print("3. 请求超时设置太短")
    except httpx.ConnectError as e:
        print(f"❌ 无法连接到服务器: {e}")
        print("请确保后端服务正在运行")
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        token = sys.argv[1]
        asyncio.run(test_sse_connection())
    else:
        print("用法: python test_sse_direct.py <token>")
        print("\n请提供有效的 JWT token")
