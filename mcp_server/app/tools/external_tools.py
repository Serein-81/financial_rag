"""
外部服务工具

提供天气查询、地理位置查询、网络搜索等外部API服务
"""

import os
import logging
import httpx
from typing import Any, Dict, Optional

from app.tools.base import ToolBase, registry

logger = logging.getLogger(__name__)

QWEATHER_API_KEY = os.getenv("QWEATHER_API_KEY", "")
QWEATHER_GEO_HOST = os.getenv("QWEATHER_GEO_HOST", "https://geo.qweather.com")
QWEATHER_WEATHER_HOST = os.getenv("QWEATHER_WEATHER_HOST", "https://weather.qweather.com")

GAODE_API_KEY = os.getenv("GAODE_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")


class WeatherQueryTool(ToolBase):
    """天气查询工具"""

    def __init__(self):
        super().__init__(
            name="get_weather",
            description="查询指定城市的实时天气信息，包括温度、湿度、风向等",
            timeout=15
        )

    async def execute(
        self,
        city_name: str,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        查询城市天气

        Args:
            city_name: 城市名称
            tenant_id: 租户ID

        Returns:
            天气信息字典
        """
        if not QWEATHER_API_KEY:
            return {
                "success": False,
                "error": "QWEATHER_API_KEY 未配置",
                "city_name": city_name,
                "tenant_id": tenant_id
            }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                geo_url = f"{QWEATHER_GEO_HOST}/geo/v2/city/lookup?location={city_name}&key={QWEATHER_API_KEY}"
                geo_res = await client.get(geo_url)
                geo_data = geo_res.json()

                if geo_data.get("code") != "200":
                    return {
                        "success": False,
                        "error": f"未找到城市 {city_name}",
                        "city_name": city_name,
                        "tenant_id": tenant_id
                    }

                location_id = geo_data["location"][0]["id"]
                location_name = geo_data["location"][0]["name"]

                weather_url = f"{QWEATHER_WEATHER_HOST}/v7/weather/now?location={location_id}&key={QWEATHER_API_KEY}"
                weather_res = await client.get(weather_url)
                weather_data = weather_res.json()

                if weather_data.get("code") == "200":
                    now = weather_data["now"]
                    return {
                        "success": True,
                        "city_name": location_name,
                        "weather": now["text"],
                        "temperature": now["temp"],
                        "feels_like": now["feelsLike"],
                        "wind_direction": now["windDir"],
                        "wind_scale": now["windScale"],
                        "humidity": now["humidity"],
                        "tenant_id": tenant_id
                    }
                else:
                    return {
                        "success": False,
                        "error": "获取天气数据失败",
                        "city_name": city_name,
                        "tenant_id": tenant_id
                    }

            except httpx.TimeoutException:
                return {
                    "success": False,
                    "error": "天气服务请求超时",
                    "city_name": city_name,
                    "tenant_id": tenant_id
                }
            except Exception as e:
                logger.error(f"天气查询失败: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "city_name": city_name,
                    "tenant_id": tenant_id
                }


class LocationQueryTool(ToolBase):
    """地理位置查询工具"""

    def __init__(self):
        super().__init__(
            name="get_location_info",
            description="查询地址的经纬度和行政区划信息",
            timeout=10
        )

    async def execute(
        self,
        address: str,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        查询地址位置信息

        Args:
            address: 详细地址
            tenant_id: 租户ID

        Returns:
            位置信息字典
        """
        if not GAODE_API_KEY:
            return {
                "success": False,
                "error": "GAODE_API_KEY 未配置",
                "address": address,
                "tenant_id": tenant_id
            }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                url = f"https://restapi.amap.com/v3/geocode/geo?address={address}&key={GAODE_API_KEY}"
                res = await client.get(url)
                data = res.json()

                if data.get("status") == "1" and data.get("geocodes"):
                    geo = data["geocodes"][0]
                    return {
                        "success": True,
                        "address": address,
                        "formatted_address": geo.get("formatted_address", ""),
                        "province": geo.get("province", ""),
                        "city": geo.get("city", ""),
                        "district": geo.get("district", ""),
                        "location": geo.get("location", ""),
                        "tenant_id": tenant_id
                    }
                else:
                    return {
                        "success": False,
                        "error": "未找到该地址的位置信息",
                        "address": address,
                        "tenant_id": tenant_id
                    }

            except httpx.TimeoutException:
                return {
                    "success": False,
                    "error": "地图服务请求超时",
                    "address": address,
                    "tenant_id": tenant_id
                }
            except Exception as e:
                logger.error(f"位置查询失败: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "address": address,
                    "tenant_id": tenant_id
                }


class WebSearchTool(ToolBase):
    """网络搜索工具"""

    def __init__(self):
        super().__init__(
            name="search_web",
            description="搜索互联网获取实时信息和最新资讯",
            timeout=20
        )

    async def execute(
        self,
        query: str,
        max_results: int = 5,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        执行网络搜索

        Args:
            query: 搜索关键词
            max_results: 最大结果数
            tenant_id: 租户ID

        Returns:
            搜索结果字典
        """
        if not TAVILY_API_KEY:
            return {
                "success": False,
                "error": "TAVILY_API_KEY 未配置",
                "query": query,
                "tenant_id": tenant_id
            }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                url = "https://api.tavily.com/search"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": True,
                    "max_results": max_results
                }

                res = await client.post(url, json=payload, headers=headers)

                if res.status_code == 200:
                    data = res.json()
                    results = []

                    for item in data.get("results", []):
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "content": item.get("content", "")[:500]
                        })

                    return {
                        "success": True,
                        "query": query,
                        "answer": data.get("answer", ""),
                        "results": results,
                        "total_results": len(results),
                        "tenant_id": tenant_id
                    }
                else:
                    return {
                        "success": False,
                        "error": f"搜索请求失败: {res.status_code}",
                        "query": query,
                        "tenant_id": tenant_id
                    }

            except httpx.TimeoutException:
                return {
                    "success": False,
                    "error": "搜索服务请求超时",
                    "query": query,
                    "tenant_id": tenant_id
                }
            except Exception as e:
                logger.error(f"网络搜索失败: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "query": query,
                    "tenant_id": tenant_id
                }


def create_external_tools():
    """创建外部服务工具实例"""
    return [
        WeatherQueryTool(),
        LocationQueryTool(),
        WebSearchTool(),
    ]


external_tools = create_external_tools()

for tool in external_tools:
    registry.register(tool)

__all__ = ["external_tools", "create_external_tools"]
