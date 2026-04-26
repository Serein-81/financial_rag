"""
简单测试 Unstructured API 健康检查
"""
import httpx


def test_unstructured_health():
    """测试 Unstructured API 健康检查"""
    print("=" * 60)
    print("测试 Unstructured API 健康检查")
    print("=" * 60)
    
    api_url = "http://localhost:8001"
    
    # 尝试多个可能的健康检查端点
    health_endpoints = [
        ("/redoc", 200, "FastAPI 自动文档"),
        ("/general/v0/general", [200, 422], "主要 API 端点"),
        ("/docs", 200, "Swagger 文档"),
        ("/health", 404, "健康检查端点（可能不存在）"),
        ("/", 404, "根路径（可能不存在）"),
    ]
    
    print(f"\n测试 API: {api_url}\n")
    
    found_working = False
    
    for endpoint, expected_status, description in health_endpoints:
        try:
            response = httpx.get(f"{api_url}{endpoint}", timeout=5.0)
            
            if isinstance(expected_status, list):
                match = response.status_code in expected_status
            else:
                match = response.status_code == expected_status
            
            if match:
                icon = "✅" if response.status_code in [200, 422] else "⚠️"
                print(f"{icon} {endpoint:30s} -> {response.status_code} ({description})")
                
                if response.status_code in [200, 422]:
                    found_working = True
            else:
                print(f"❌ {endpoint:30s} -> {response.status_code} (期望: {expected_status})")
                
        except httpx.ConnectError:
            print(f"❌ {endpoint:30s} -> 连接失败（服务未运行）")
        except Exception as e:
            print(f"❌ {endpoint:30s} -> 错误: {str(e)[:50]}")
    
    print("\n" + "=" * 60)
    
    if found_working:
        print("✅ Unstructured API 正在运行！")
        print("\n主要端点:")
        print(f"  📄 文档解析: POST {api_url}/general/v0/general")
        print(f"  📖 API 文档: {api_url}/redoc")
        print(f"  📚 Swagger:   {api_url}/docs")
    else:
        print("❌ Unstructured API 不可用")
        print("\n请确保已启动服务:")
        print("  docker-compose --profile heavy up -d unstructured-api")
    
    print("=" * 60)


def test_actual_api():
    """测试实际的 API 端点"""
    print("\n" + "=" * 60)
    print("测试实际的文档解析 API")
    print("=" * 60)
    
    api_url = "http://localhost:8001"
    
    # 创建一个简单的测试文件
    test_content = """Invoice Test Document
Amount: 1000.00
Tax: 130.00
""".encode('utf-8')
    
    print("\n1. 测试上传文本文件（multipart/form-data）:")
    try:
        files = {"files": ("test.txt", test_content, "text/plain")}
        response = httpx.post(
            f"{api_url}/general/v0/general",
            files=files,
            timeout=30
        )
        
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 成功! 提取到 {len(result) if isinstance(result, list) else 1} 个元素")
            
            if isinstance(result, list) and len(result) > 0:
                print(f"   📝 第一个元素类型: {result[0].get('type', 'unknown')}")
                if 'text' in result[0]:
                    print(f"   📝 内容预览: {result[0]['text'][:100]}...")
        else:
            print(f"   ⚠️ 返回非 200 状态码: {response.status_code}")
            print(f"   响应: {response.text[:300]}")
            
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
    
    print("=" * 60)


if __name__ == "__main__":
    test_unstructured_health()
    test_actual_api()
