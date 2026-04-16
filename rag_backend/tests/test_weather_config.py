#!/usr/bin/env python3
"""测试和风天气配置是否正确加载"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings

print("=" * 60)
print("和风天气配置测试")
print("=" * 60)

print(f"\n✅ QWEATHER_API_KEY: {settings.QWEATHER_API_KEY}")
print(f"✅ QWEATHER_WEATHER_HOST: {settings.QWEATHER_WEATHER_HOST}")
print(f"✅ QWEATHER_GEO_HOST: {settings.QWEATHER_GEO_HOST}")

print("\n" + "=" * 60)
print("测试 API 调用")
print("=" * 60)

import httpx
import asyncio

async def test_weather_api():
    """测试天气 API"""
    city_name = "北京"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. 测试城市查询
        geo_url = f"{settings.QWEATHER_GEO_HOST}/geo/v2/city/lookup?location={city_name}&key={settings.QWEATHER_API_KEY}"
        print(f"\n🔍 请求城市信息: {geo_url}")
        
        try:
            geo_res = await client.get(geo_url)
            geo_data = geo_res.json()
            print(f"✅ 城市信息响应: {geo_data.get('code')}")
            
            if geo_data.get("code") == "200":
                location_id = geo_data["location"][0]["id"]
                location_name = geo_data["location"][0]["name"]
                print(f"✅ 城市ID: {location_id}, 城市名: {location_name}")
                
                # 2. 测试天气查询
                weather_url = f"{settings.QWEATHER_WEATHER_HOST}/v7/weather/now?location={location_id}&key={settings.QWEATHER_API_KEY}"
                print(f"\n🔍 请求天气信息: {weather_url}")
                
                weather_res = await client.get(weather_url)
                weather_data = weather_res.json()
                print(f"✅ 天气信息响应: {weather_data.get('code')}")
                
                if weather_data.get("code") == "200":
                    now = weather_data["now"]
                    print(f"\n🌤️ {location_name}当前天气：")
                    print(f"   天气: {now['text']}")
                    print(f"   气温: {now['temp']}°C")
                    print(f"   体感温度: {now['feelsLike']}°C")
                    print(f"   风向: {now['windDir']}")
                    print(f"   湿度: {now['humidity']}%")
                    print("\n✅ 天气 API 测试成功！")
                else:
                    print(f"❌ 天气查询失败: {weather_data}")
            else:
                print(f"❌ 城市查询失败: {geo_data}")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()

# 运行测试
asyncio.run(test_weather_api())

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
