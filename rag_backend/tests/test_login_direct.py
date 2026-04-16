"""
直接测试登录API
"""

import asyncio
import httpx
import json


async def test_login():
    """测试登录API"""
    
    print("=" * 60)
    print("🧪 测试登录API")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        
        # 1. 先注册一个测试用户
        print("\n1. 注册测试用户...")
        
        register_data = {
            "email": "test_login@example.com",
            "password": "test123456",
            "nickname": "测试用户"
        }
        
        try:
            register_response = await client.post(
                f"{base_url}/api/v1/auth/register",
                json=register_data
            )
            
            if register_response.status_code == 200:
                user_info = register_response.json()
                print(f"✅ 用户注册成功: {user_info.get('email')}")
            else:
                print(f"⚠️ 用户可能已存在: {register_response.status_code}")
                
        except Exception as e:
            print(f"注册异常: {e}")
        
        # 2. 测试登录
        print("\n2. 测试登录...")
        
        login_data = {
            "email": "test_login@example.com",
            "password": "test123456"
        }
        
        try:
            login_response = await client.post(
                f"{base_url}/api/v1/auth/login",
                json=login_data
            )
            
            print(f"登录状态码: {login_response.status_code}")
            
            if login_response.status_code == 200:
                login_result = login_response.json()
                print("✅ 登录成功!")
                print(f"响应数据: {json.dumps(login_result, indent=2, ensure_ascii=False)}")
                
                # 3. 测试获取用户信息
                print("\n3. 测试获取用户信息...")
                
                token = login_result.get('access_token')
                headers = {"Authorization": f"Bearer {token}"}
                
                me_response = await client.get(
                    f"{base_url}/api/v1/auth/me",
                    headers=headers
                )
                
                if me_response.status_code == 200:
                    me_data = me_response.json()
                    print("✅ 获取用户信息成功!")
                    print(f"用户信息: {json.dumps(me_data, indent=2, ensure_ascii=False)}")
                else:
                    print(f"❌ 获取用户信息失败: {me_response.status_code}")
                    print(f"错误: {me_response.text}")
                    
            else:
                print("❌ 登录失败!")
                print(f"错误响应: {login_response.text}")
                
        except Exception as e:
            print(f"❌ 登录异常: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_login())