"""
直接测试短信API端点
"""

import asyncio
import httpx
import json


async def test_sms_api():
    """直接测试短信API"""
    
    print("=" * 60)
    print("🧪 直接测试短信API端点")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    test_phone = "13800138000"
    
    async with httpx.AsyncClient() as client:
        
        # 1. 测试发送短信验证码
        print("\n1. 测试发送短信验证码...")
        
        try:
            response = await client.post(
                f"{base_url}/api/v1/auth/sms/send",
                json={"phone": test_phone},
                timeout=10.0
            )
            
            print(f"状态码: {response.status_code}")
            print(f"响应头: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                print("✅ 短信发送成功!")
                print(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                # 如果有debug_code，测试验证
                if "debug_code" in data:
                    print("\n2. 测试验证码验证...")
                    verify_response = await client.post(
                        f"{base_url}/api/v1/auth/sms/verify",
                        json={"phone": test_phone, "code": data["debug_code"]},
                        timeout=10.0
                    )
                    
                    print(f"验证状态码: {verify_response.status_code}")
                    if verify_response.status_code == 200:
                        verify_data = verify_response.json()
                        print("✅ 验证码验证成功!")
                        print(f"验证响应: {json.dumps(verify_data, indent=2, ensure_ascii=False)}")
                    else:
                        print(f"❌ 验证码验证失败: {verify_response.text}")
                        
            else:
                print("❌ 短信发送失败!")
                print(f"错误响应: {response.text}")
                
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_sms_api())