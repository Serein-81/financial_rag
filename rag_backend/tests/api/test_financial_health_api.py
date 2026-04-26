#!/usr/bin/env python3
"""
财务健康 API 诊断脚本
直接调用 API 端点并显示详细错误信息
"""

import requests
import json
import sys
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

def test_financial_health_monitor():
    """测试财务健康监控 API"""
    print("=" * 60)
    print("测试财务健康监控 API")
    print("=" * 60)
    
    # 首先登录获取 token
    print("\n1. 尝试登录获取 token...")
    login_data = {
        "email": "admin@example.com",  # 请根据实际情况修改
        "password": "admin123"  # 请根据实际情况修改
    }
    
    try:
        login_response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data, timeout=10)
        print(f"   登录响应状态: {login_response.status_code}")
        
        if login_response.status_code != 200:
            print(f"   ❌ 登录失败: {login_response.text}")
            print("\n请先确保后端服务正在运行，并且提供有效的登录凭据")
            return False
        
        login_result = login_response.json()
        token = login_result.get("access_token")
        
        if not token:
            print(f"   ❌ 未获取到 token: {login_result}")
            return False
        
        print("   ✅ 登录成功")
        
    except requests.exceptions.ConnectionError:
        print(f"   ❌ 无法连接到后端服务 {BASE_URL}")
        print("   请确保后端服务正在运行 (uvicorn)")
        return False
    except Exception as e:
        print(f"   ❌ 登录请求失败: {e}")
        return False
    
    # 测试财务健康监控 API
    print("\n2. 测试 /financial-health/monitor API...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    request_data = {
        "tenant_id": "test-tenant",
        "user_id": "test-user",
        "period_start": (datetime.now() - timedelta(days=90)).date().isoformat(),
        "period_end": datetime.now().date().isoformat(),
        "include_anomaly_detection": True,
        "include_trend_analysis": True
    }
    
    print(f"   请求数据: {json.dumps(request_data, indent=2, ensure_ascii=False)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/financial-health/monitor",
            json=request_data,
            headers=headers,
            timeout=30
        )
        
        print(f"\n   响应状态码: {response.status_code}")
        print(f"   响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("   ✅ API 调用成功!")
            result = response.json()
            print("\n   响应数据:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return True
        else:
            print("   ❌ API 调用失败!")
            print("\n   错误响应:")
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2, ensure_ascii=False))
            except:
                print(f"   {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("   ❌ 请求超时 (30秒)")
        return False
    except requests.exceptions.ConnectionError:
        print("   ❌ 无法连接到后端服务")
        return False
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_financial_health_monitor()
    sys.exit(0 if success else 1)
