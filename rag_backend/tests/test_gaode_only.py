"""
专门测试高德地图API
注意：此测试需要高德地图API Key，仅在本地环境手动运行
"""
import asyncio
import os
import httpx
import pytest
from app.core.config import settings


@pytest.mark.skipif(
    os.getenv("CI") == "true" or not settings.GAODE_API_KEY,
    reason="需要高德地图API Key，仅在本地环境运行"
)
async def test_gaode_detailed():
    """详细测试高德地图API"""
    print("🗺️ 测试高德地图API配置...")
    print(f"   API Key: {settings.GAODE_API_KEY}")
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 测试地理编码
            print("\n📍 测试地理编码...")
            url = "https://restapi.amap.com/v3/geocode/geo"
            params = {
                "address": "北京市朝阳区",
                "key": settings.GAODE_API_KEY
            }
            
            print(f"   请求URL: {url}")
            print(f"   请求参数: {params}")
            
            response = await client.get(url, params=params)
            print(f"   响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   响应数据: {data}")
                
                if data.get("status") == "1":
                    if data.get("geocodes"):
                        geocode = data["geocodes"][0]
                        print(f"   ✅ 地理编码成功!")
                        print(f"      地址: {geocode.get('formatted_address', '未知')}")
                        print(f"      坐标: {geocode.get('location', '未知')}")
                        print(f"      行政区: {geocode.get('district', '未知')}")
                        return True
                    else:
                        print(f"   ⚠️ 地理编码无结果")
                        return False
                else:
                    error_info = data.get("info", "未知错误")
                    print(f"   ❌ 高德API错误: {error_info}")
                    
                    if "USERKEY_PLAT_NOMATCH" in error_info:
                        print("   💡 平台不匹配错误，可能需要等待几分钟让配置生效")
                    elif "INVALID_USER_KEY" in error_info:
                        print("   💡 API Key无效，请检查Key是否正确")
                    elif "DAILY_QUERY_OVER_LIMIT" in error_info:
                        print("   💡 今日查询次数已用完")
                    
                    return False
            else:
                print(f"   ❌ 请求失败: HTTP {response.status_code}")
                print(f"   响应内容: {response.text}")
                return False
                
    except Exception as e:
        print(f"   ❌ 高德地图API测试异常: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(test_gaode_detailed())