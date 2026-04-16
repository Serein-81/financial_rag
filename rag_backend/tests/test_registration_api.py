"""
测试修复后的用户注册API接口
验证租户ID分配是否正常工作
"""

import asyncio
import httpx
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 测试配置
BASE_URL = "http://localhost:8000"
TEST_PHONE = "13800138000"
TEST_SMS_CODE = "123456"  # 开发模式下的测试验证码


async def test_sms_and_registration():
    """测试短信验证码和用户注册流程"""
    
    print("=" * 80)
    print("🧪 测试用户注册API接口")
    print("=" * 80)
    
    async with httpx.AsyncClient() as client:
        
        # 1. 测试发送短信验证码
        print("\n1. 测试发送短信验证码...")
        
        try:
            sms_response = await client.post(
                f"{BASE_URL}/api/v1/auth/sms/send",
                json={"phone": TEST_PHONE}
            )
            
            if sms_response.status_code == 200:
                sms_data = sms_response.json()
                print(f"✅ 短信发送成功: {sms_data.get('message')}")
                if sms_data.get('debug_code'):
                    print(f"🔧 开发模式验证码: {sms_data.get('debug_code')}")
                    TEST_SMS_CODE = sms_data.get('debug_code')
            else:
                print(f"❌ 短信发送失败: {sms_response.status_code} - {sms_response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 短信发送异常: {str(e)}")
            return False
        
        # 2. 测试普通用户注册
        print(f"\n2. 测试普通用户注册...")
        
        user_data = {
            "email": "test_p0_user@example.com",
            "phone": TEST_PHONE,
            "password": "test123456",
            "nickname": "P0测试用户"
        }
        
        try:
            register_response = await client.post(
                f"{BASE_URL}/api/v1/auth/register?sms_code={TEST_SMS_CODE}",
                json=user_data
            )
            
            if register_response.status_code == 200:
                user_info = register_response.json()
                print(f"✅ 普通用户注册成功!")
                print(f"  - 用户ID: {user_info.get('id')}")
                print(f"  - 邮箱: {user_info.get('email')}")
                print(f"  - 租户ID: {user_info.get('tenant_id')}")
                print(f"  - 是否管理员: {user_info.get('is_admin')}")
                
                # 验证租户ID格式
                tenant_id = user_info.get('tenant_id')
                if tenant_id and tenant_id.startswith('user_'):
                    print(f"✅ 个人租户ID格式正确: {tenant_id}")
                else:
                    print(f"❌ 个人租户ID格式错误: {tenant_id}")
                    return False
                    
            else:
                print(f"❌ 普通用户注册失败: {register_response.status_code}")
                print(f"   错误信息: {register_response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 普通用户注册异常: {str(e)}")
            return False
        
        # 3. 测试企业管理员注册
        print(f"\n3. 测试企业管理员注册...")
        
        # 使用不同的手机号避免重复
        admin_phone = "13800138001"
        
        # 先发送短信验证码
        try:
            admin_sms_response = await client.post(
                f"{BASE_URL}/api/v1/auth/sms/send",
                json={"phone": admin_phone}
            )
            
            if admin_sms_response.status_code == 200:
                admin_sms_data = admin_sms_response.json()
                admin_sms_code = admin_sms_data.get('debug_code', TEST_SMS_CODE)
                print(f"✅ 管理员短信发送成功")
            else:
                print(f"❌ 管理员短信发送失败: {admin_sms_response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 管理员短信发送异常: {str(e)}")
            return False
        
        # 注册企业管理员
        admin_data = {
            "email": "test_p0_admin@example.com",
            "phone": admin_phone,
            "password": "admin123456",
            "full_name": "张三",
            "nickname": "P0测试管理员",
            "company_name": "P0测试科技有限公司",
            "company_position": "技术总监"
        }
        
        try:
            admin_register_response = await client.post(
                f"{BASE_URL}/api/v1/auth/register/admin?sms_code={admin_sms_code}",
                json=admin_data
            )
            
            if admin_register_response.status_code == 200:
                admin_info = admin_register_response.json()
                print(f"✅ 企业管理员注册成功!")
                print(f"  - 用户ID: {admin_info.get('id')}")
                print(f"  - 邮箱: {admin_info.get('email')}")
                print(f"  - 租户ID: {admin_info.get('tenant_id')}")
                print(f"  - 是否管理员: {admin_info.get('is_admin')}")
                print(f"  - 公司名称: {admin_info.get('company_name')}")
                
                # 验证租户ID格式
                tenant_id = admin_info.get('tenant_id')
                if tenant_id and tenant_id.startswith('company_'):
                    print(f"✅ 企业租户ID格式正确: {tenant_id}")
                else:
                    print(f"❌ 企业租户ID格式错误: {tenant_id}")
                    return False
                    
            else:
                print(f"❌ 企业管理员注册失败: {admin_register_response.status_code}")
                print(f"   错误信息: {admin_register_response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 企业管理员注册异常: {str(e)}")
            return False
        
        # 4. 测试登录功能
        print(f"\n4. 测试用户登录...")
        
        login_data = {
            "email": "test_p0_user@example.com",
            "password": "test123456"
        }
        
        try:
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=login_data
            )
            
            if login_response.status_code == 200:
                login_info = login_response.json()
                print(f"✅ 用户登录成功!")
                print(f"  - Token类型: {login_info.get('token_type')}")
                print(f"  - 用户名: {login_info.get('user_name')}")
                print(f"  - 是否管理员: {login_info.get('is_admin')}")
                
                # 保存token用于后续测试
                access_token = login_info.get('access_token')
                
                # 5. 测试获取用户信息
                print(f"\n5. 测试获取用户信息...")
                
                headers = {"Authorization": f"Bearer {access_token}"}
                me_response = await client.get(
                    f"{BASE_URL}/api/v1/auth/me",
                    headers=headers
                )
                
                if me_response.status_code == 200:
                    me_info = me_response.json()
                    print(f"✅ 获取用户信息成功!")
                    print(f"  - 用户ID: {me_info.get('id')}")
                    print(f"  - 租户ID: {me_info.get('tenant_id')}")
                    print(f"  - 邮箱: {me_info.get('email')}")
                    print(f"  - 昵称: {me_info.get('nickname')}")
                else:
                    print(f"❌ 获取用户信息失败: {me_response.status_code}")
                    return False
                    
            else:
                print(f"❌ 用户登录失败: {login_response.status_code}")
                print(f"   错误信息: {login_response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 用户登录异常: {str(e)}")
            return False
        
        return True


async def main():
    """主测试函数"""
    
    print("🚀 开始API接口测试...")
    print("⚠️  请确保后端服务已启动 (python -m uvicorn app.main:app --reload)")
    
    # 等待用户确认
    input("\n按回车键开始测试...")
    
    success = await test_sms_and_registration()
    
    print(f"\n" + "=" * 80)
    print("📋 API接口测试总结")
    print("=" * 80)
    
    if success:
        print("🎉 所有API接口测试通过！")
        print("✅ 短信验证码发送正常")
        print("✅ 普通用户注册正常，租户ID格式正确")
        print("✅ 企业管理员注册正常，租户ID格式正确")
        print("✅ 用户登录功能正常")
        print("✅ 用户信息获取正常")
        print("\n🎯 P0问题修复完全成功！系统可以正常使用！")
    else:
        print("❌ API接口测试失败！")
        print("🔧 请检查:")
        print("  1. 后端服务是否正常启动")
        print("  2. 数据库连接是否正常")
        print("  3. Redis服务是否正常")
        print("  4. 短信服务配置是否正确")


if __name__ == "__main__":
    asyncio.run(main())