"""
测试修复后的API配置

专门测试之前失败的API是否已经修复
"""

import asyncio
import sys
import os
import httpx
import redis.asyncio as redis

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings


async def test_llm_service_simple():
    """简单测试LLM服务（避免导入模型）"""
    print("🤖 测试智谱API直接调用...")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.ZHIPU_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": settings.ZHIPU_MODEL,
                "messages": [
                    {"role": "user", "content": "你好，请回答：1+1等于几？"}
                ],
                "max_tokens": 50
            }
            
            response = await client.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                result = response.json()
                if "choices" in result and result["choices"]:
                    content = result["choices"][0]["message"]["content"]
                    print(f"   ✅ 智谱API调用成功: {content}")
                    return True
                else:
                    print(f"   ❌ 智谱API响应格式异常: {result}")
                    return False
            else:
                print(f"   ❌ 智谱API调用失败: {response.text}")
                return False
                
    except Exception as e:
        print(f"   ❌ 智谱API测试异常: {e}")
        return False


async def test_weather_api_simple():
    """简单测试和风天气API"""
    print("🌤️ 测试和风天气API...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 直接测试实时天气（使用北京的location ID）
            url = f"https://{settings.QWEATHER_WEATHER_HOST}/v7/weather/now"
            params = {
                "location": "101010100",  # 北京
                "key": settings.QWEATHER_API_KEY
            }
            
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("code") == "200" and data.get("now"):
                        now = data["now"]
                        print(f"   ✅ 和风天气API成功: {now['temp']}°C, {now['text']}")
                        return True
                    else:
                        print(f"   ❌ 和风天气API错误: {data}")
                        return False
                except Exception as e:
                    print(f"   ❌ 和风天气响应解析失败: {e}")
                    print(f"   原始响应: {response.text[:200]}...")
                    return False
            else:
                print(f"   ❌ 和风天气请求失败: HTTP {response.status_code}")
                print(f"   响应内容: {response.text[:200]}...")
                return False
                
    except Exception as e:
        print(f"   ❌ 和风天气API测试异常: {e}")
        return False


async def test_redis_simple():
    """简单测试Redis连接"""
    print("📦 测试Redis连接...")
    
    try:
        # 直接连接Redis
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            decode_responses=True
        )
        
        # 测试连接
        await redis_client.ping()
        print("   ✅ Redis连接成功")
        
        # 测试读写
        test_key = "test_fixed_api"
        test_value = "test_value_456"
        
        await redis_client.set(test_key, test_value, ex=10)
        retrieved_value = await redis_client.get(test_key)
        
        if retrieved_value == test_value:
            print("   ✅ Redis读写测试成功")
            await redis_client.delete(test_key)
            await redis_client.close()
            return True
        else:
            print(f"   ❌ Redis读写测试失败: 期望 {test_value}, 实际 {retrieved_value}")
            await redis_client.close()
            return False
        
    except Exception as e:
        print(f"   ❌ Redis连接测试异常: {e}")
        return False


async def test_gaode_api_info():
    """测试高德地图API并提供解决方案"""
    print("🗺️ 测试高德地图API...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = "https://restapi.amap.com/v3/geocode/geo"
            params = {
                "address": "北京市朝阳区",
                "key": settings.GAODE_API_KEY
            }
            
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "1":
                    print("   ✅ 高德地图API调用成功")
                    return True
                else:
                    error_info = data.get("info", "未知错误")
                    print(f"   ❌ 高德API错误: {error_info}")
                    
                    if "USERKEY_PLAT_NOMATCH" in error_info:
                        print("   💡 解决方案:")
                        print("      1. 访问: https://console.amap.com/dev/key/app")
                        print("      2. 找到你的应用，点击'设置'")
                        print("      3. 在'服务平台'中勾选'Web服务'")
                        print("      4. 点击'提交'保存配置")
                        print("      5. 等待几分钟后重新测试")
                    
                    return False
            else:
                print(f"   ❌ 高德地图请求失败: HTTP {response.status_code}")
                return False
                
    except Exception as e:
        print(f"   ❌ 高德地图API测试异常: {e}")
        return False


async def run_fixed_tests():
    """运行修复后的API测试"""
    print("🔧 测试修复后的API配置")
    print("=" * 60)
    
    results = {}
    
    # 测试各个API
    results["智谱LLM"] = await test_llm_service_simple()
    results["和风天气"] = await test_weather_api_simple()
    results["Redis"] = await test_redis_simple()
    results["高德地图"] = await test_gaode_api_info()
    
    # 统计结果
    total = len(results)
    passed = sum(1 for success in results.values() if success)
    
    print("\n" + "=" * 60)
    print("📊 修复测试结果")
    print("=" * 60)
    print(f"总测试数: {total}")
    print(f"通过测试: {passed}")
    print(f"成功率: {(passed / total * 100):.1f}%")
    
    print("\n📋 详细结果:")
    for api_name, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {api_name}")
    
    if passed == total:
        print("\n🎉 所有API修复成功！")
    else:
        print(f"\n⚠️ 还有 {total - passed} 个API需要进一步处理")


if __name__ == "__main__":
    try:
        asyncio.run(run_fixed_tests())
    except KeyboardInterrupt:
        print("\n\n❌ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试执行异常: {e}")