"""
API 配置测试工具

测试所有外部API服务是否配置正确并能正常工作
包括：数据库连接、LLM服务、天气API、地图API、搜索API等
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any, List

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings


class APITester:
    """API测试器"""
    
    def __init__(self):
        self.results = {}
        self.total_tests = 0
        self.passed_tests = 0
    
    def log_test(self, service: str, test_name: str, success: bool, message: str = "", data: Any = None):
        """记录测试结果"""
        if service not in self.results:
            self.results[service] = []
        
        self.results[service].append({
            "test": test_name,
            "success": success,
            "message": message,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
        
        self.total_tests += 1
        if success:
            self.passed_tests += 1
            print(f"✅ [{service}] {test_name}: {message}")
        else:
            print(f"❌ [{service}] {test_name}: {message}")
    
    async def test_database_connection(self):
        """测试数据库连接"""
        print("\n🔍 测试数据库连接...")
        
        try:
            from app.db import AsyncSessionLocal
            
            async with AsyncSessionLocal() as db:
                # 测试简单查询
                from sqlalchemy import text
                result = await db.execute(text("SELECT 1 as test"))
                test_value = result.scalar()
                
                if test_value == 1:
                    self.log_test("数据库", "连接测试", True, f"连接成功 | 数据库: {settings.POSTGRES_DB}")
                    
                    # 测试表是否存在
                    result = await db.execute(text("""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        ORDER BY table_name;
                    """))
                    tables = [row[0] for row in result.fetchall()]
                    
                    self.log_test("数据库", "表结构检查", True, f"发现 {len(tables)} 个表", tables)
                else:
                    self.log_test("数据库", "连接测试", False, "查询返回异常值")
                    
        except Exception as e:
            self.log_test("数据库", "连接测试", False, f"连接失败: {str(e)}")
    
    async def test_llm_service(self):
        """测试LLM服务"""
        print("\n🤖 测试LLM服务...")
        
        try:
            from app.services.llm_service import llm_service
            
            # 测试简单对话
            test_prompt = "请回答：1+1等于几？"
            response = await llm_service.get_answer(
                query=test_prompt,
                context_chunks=[],
                history=[]
            )
            
            if response and len(response.strip()) > 0:
                self.log_test("LLM服务", "对话测试", True, f"响应正常 | 长度: {len(response)}", response[:100])
            else:
                self.log_test("LLM服务", "对话测试", False, "响应为空")
                
        except Exception as e:
            self.log_test("LLM服务", "对话测试", False, f"调用失败: {str(e)}")
    
    async def test_weather_api(self):
        """测试和风天气API"""
        print("\n🌤️ 测试和风天气API...")
        
        try:
            import httpx
            
            # 测试地理位置查询
            geo_url = f"https://{settings.QWEATHER_GEO_HOST}/v7/weather/now"
            geo_params = {
                "location": "101010100",  # 北京的location ID
                "key": settings.QWEATHER_API_KEY
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(geo_url, params=geo_params)
                data = response.json()
                
                if data.get("code") == "200":
                    now = data["now"]
                    self.log_test("和风天气", "实时天气查询", True, 
                                f"查询成功 | 温度: {now['temp']}°C, 天气: {now['text']}", now)
                else:
                    self.log_test("和风天气", "实时天气查询", False, f"API错误: {data.get('code')}")
                    
        except Exception as e:
            self.log_test("和风天气", "API测试", False, f"请求失败: {str(e)}")
    
    async def test_gaode_api(self):
        """测试高德地图API"""
        print("\n🗺️ 测试高德地图API...")
        
        try:
            import httpx
            
            # 测试地理编码
            url = "https://restapi.amap.com/v3/geocode/geo"
            params = {
                "address": "北京市朝阳区",
                "key": settings.GAODE_API_KEY
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                data = response.json()
                
                if data.get("status") == "1" and data.get("geocodes"):
                    geocode = data["geocodes"][0]
                    self.log_test("高德地图", "地理编码", True, 
                                f"查询成功 | 坐标: {geocode['location']}", geocode)
                else:
                    self.log_test("高德地图", "地理编码", False, f"API错误: {data.get('info')}")
                    
        except Exception as e:
            self.log_test("高德地图", "API测试", False, f"请求失败: {str(e)}")
    
    async def test_tavily_api(self):
        """测试Tavily搜索API"""
        print("\n🔍 测试Tavily搜索API...")
        
        if not settings.TAVILY_API_KEY or settings.TAVILY_API_KEY == "your_tavily_api_key_here":
            self.log_test("Tavily搜索", "API测试", False, "API Key未配置")
            return
        
        try:
            import httpx
            
            url = "https://api.tavily.com/search"
            headers = {
                "Content-Type": "application/json"
            }
            data = {
                "api_key": settings.TAVILY_API_KEY,
                "query": "Python programming",
                "max_results": 3
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=data)
                result = response.json()
                
                if response.status_code == 200 and "results" in result:
                    self.log_test("Tavily搜索", "搜索测试", True, 
                                f"搜索成功 | 结果数: {len(result['results'])}", result["results"][:2])
                else:
                    self.log_test("Tavily搜索", "搜索测试", False, f"API错误: {result}")
                    
        except Exception as e:
            self.log_test("Tavily搜索", "API测试", False, f"请求失败: {str(e)}")
    
    async def test_redis_connection(self):
        """测试Redis连接"""
        print("\n📦 测试Redis连接...")
        
        try:
            from app.services.redis_service import redis_service
            
            # 测试连接
            await redis_service.set("test_key", "test_value", expire=10)
            value = await redis_service.get("test_key")
            
            if value == "test_value":
                self.log_test("Redis", "连接测试", True, "连接正常，读写成功")
                
                # 清理测试数据
                await redis_service.delete("test_key")
            else:
                self.log_test("Redis", "连接测试", False, "读写测试失败")
                
        except Exception as e:
            self.log_test("Redis", "连接测试", False, f"连接失败: {str(e)}")
    
    async def test_minio_connection(self):
        """测试MinIO连接"""
        print("\n🗄️ 测试MinIO连接...")
        
        try:
            from minio import Minio
            
            client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )
            
            # 测试连接
            buckets = client.list_buckets()
            bucket_names = [bucket.name for bucket in buckets]
            
            self.log_test("MinIO", "连接测试", True, f"连接成功 | 存储桶: {bucket_names}")
            
        except Exception as e:
            self.log_test("MinIO", "连接测试", False, f"连接失败: {str(e)}")
    
    async def test_embedding_service(self):
        """测试向量嵌入服务"""
        print("\n🔮 测试向量嵌入服务...")
        
        try:
            from app.services.embedding_service import embedding_service
            
            test_text = "这是一个测试文本"
            embedding = await embedding_service.get_embedding(test_text)
            
            if embedding and len(embedding) > 0:
                self.log_test("向量嵌入", "嵌入生成", True, 
                            f"生成成功 | 维度: {len(embedding)}", f"前5维: {embedding[:5]}")
            else:
                self.log_test("向量嵌入", "嵌入生成", False, "生成失败或返回空向量")
                
        except Exception as e:
            self.log_test("向量嵌入", "嵌入生成", False, f"生成失败: {str(e)}")
    
    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "=" * 80)
        print("📊 API配置测试报告")
        print("=" * 80)
        
        print(f"总测试数: {self.total_tests}")
        print(f"通过测试: {self.passed_tests}")
        print(f"失败测试: {self.total_tests - self.passed_tests}")
        print(f"成功率: {(self.passed_tests / self.total_tests * 100):.1f}%")
        
        print("\n📋 详细结果:")
        for service, tests in self.results.items():
            passed = sum(1 for test in tests if test["success"])
            total = len(tests)
            status = "✅" if passed == total else "⚠️" if passed > 0 else "❌"
            
            print(f"\n{status} {service} ({passed}/{total})")
            for test in tests:
                icon = "  ✅" if test["success"] else "  ❌"
                print(f"{icon} {test['test']}: {test['message']}")
        
        # 保存详细报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": self.total_tests,
                "passed_tests": self.passed_tests,
                "success_rate": self.passed_tests / self.total_tests * 100
            },
            "results": self.results
        }
        
        with open("api_test_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 详细报告已保存到: api_test_report.json")
        
        if self.passed_tests == self.total_tests:
            print("\n🎉 所有API配置测试通过！系统已准备就绪。")
        else:
            print(f"\n⚠️ 有 {self.total_tests - self.passed_tests} 个测试失败，请检查相关配置。")


async def run_all_tests():
    """运行所有API测试"""
    print("🚀 开始API配置测试")
    print("=" * 80)
    
    tester = APITester()
    
    # 测试列表
    tests = [
        ("数据库连接", tester.test_database_connection),
        ("LLM服务", tester.test_llm_service),
        ("和风天气API", tester.test_weather_api),
        ("高德地图API", tester.test_gaode_api),
        ("Tavily搜索API", tester.test_tavily_api),
        ("Redis连接", tester.test_redis_connection),
        ("MinIO连接", tester.test_minio_connection),
        ("向量嵌入服务", tester.test_embedding_service),
    ]
    
    for test_name, test_func in tests:
        try:
            await test_func()
        except Exception as e:
            tester.log_test("系统", test_name, False, f"测试执行异常: {str(e)}")
    
    # 打印摘要
    tester.print_summary()


if __name__ == "__main__":
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\n\n❌ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试执行异常: {e}")