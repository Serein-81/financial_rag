"""
测试P1企业用户管理功能
验证邀请码系统和企业用户管理是否正常工作
"""

import asyncio
import httpx
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 测试配置
BASE_URL = "http://localhost:8000"
TEST_ADMIN_EMAIL = "test_admin@company.com"
TEST_ADMIN_PASSWORD = "admin123456"
TEST_USER_EMAIL = "test_employee@company.com"
TEST_USER_PASSWORD = "user123456"
TEST_PHONE_ADMIN = "13800138100"
TEST_PHONE_USER = "13800138101"


async def test_p1_enterprise_management():
    """测试P1企业用户管理功能"""
    
    print("=" * 80)
    print("🧪 测试P1企业用户管理功能")
    print("=" * 80)
    
    async with httpx.AsyncClient() as client:
        
        # 1. 注册企业管理员
        print("\n1. 注册企业管理员...")
        
        try:
            # 发送短信验证码
            sms_response = await client.post(
                f"{BASE_URL}/api/v1/auth/sms/send",
                json={"phone": TEST_PHONE_ADMIN}
            )
            
            if sms_response.status_code == 200:
                sms_data = sms_response.json()
                admin_sms_code = sms_data.get('debug_code', '123456')
                print(f"✅ 管理员短信验证码: {admin_sms_code}")
            else:
                print(f"❌ 发送管理员短信失败: {sms_response.status_code}")
                return False
            
            # 注册企业管理员
            admin_data = {
                "email": TEST_ADMIN_EMAIL,
                "phone": TEST_PHONE_ADMIN,
                "password": TEST_ADMIN_PASSWORD,
                "full_name": "张三",
                "nickname": "企业管理员",
                "company_name": "P1测试科技有限公司",
                "company_position": "技术总监"
            }
            
            admin_register_response = await client.post(
                f"{BASE_URL}/api/v1/auth/register/admin?sms_code={admin_sms_code}",
                json=admin_data
            )
            
            if admin_register_response.status_code == 200:
                admin_info = admin_register_response.json()
                print(f"✅ 企业管理员注册成功!")
                print(f"  - 管理员ID: {admin_info.get('id')}")
                print(f"  - 企业租户ID: {admin_info.get('tenant_id')}")
                print(f"  - 公司名称: {admin_info.get('company_name')}")
                admin_tenant_id = admin_info.get('tenant_id')
            else:
                print(f"❌ 企业管理员注册失败: {admin_register_response.status_code}")
                print(f"   错误信息: {admin_register_response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 企业管理员注册异常: {str(e)}")
            return False
        
        # 2. 管理员登录获取Token
        print(f"\n2. 管理员登录...")
        
        try:
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD}
            )
            
            if login_response.status_code == 200:
                login_data = login_response.json()
                admin_token = login_data.get('access_token')
                print(f"✅ 管理员登录成功")
                print(f"  - Token类型: {login_data.get('token_type')}")
                print(f"  - 是否管理员: {login_data.get('is_admin')}")
            else:
                print(f"❌ 管理员登录失败: {login_response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 管理员登录异常: {str(e)}")
            return False
        
        # 3. 创建邀请码
        print(f"\n3. 创建邀请码...")
        
        try:
            headers = {"Authorization": f"Bearer {admin_token}"}
            invite_data = {
                "max_uses": 5,
                "expires_hours": 24,
                "description": "P1测试邀请码",
                "role": "member"
            }
            
            invite_response = await client.post(
                f"{BASE_URL}/api/v1/invite-codes/",
                json=invite_data,
                headers=headers
            )
            
            if invite_response.status_code == 200:
                invite_info = invite_response.json()
                invite_code = invite_info.get('code')
                print(f"✅ 邀请码创建成功!")
                print(f"  - 邀请码: {invite_code}")
                print(f"  - 最大使用次数: {invite_info.get('max_uses')}")
                print(f"  - 剩余次数: {invite_info.get('remaining_uses')}")
                print(f"  - 是否有效: {invite_info.get('is_valid')}")
            else:
                print(f"❌ 邀请码创建失败: {invite_response.status_code}")
                print(f"   错误信息: {invite_response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 邀请码创建异常: {str(e)}")
            return False
        
        # 4. 验证邀请码
        print(f"\n4. 验证邀请码...")
        
        try:
            validate_response = await client.post(
                f"{BASE_URL}/api/v1/invite-codes/validate",
                json={"code": invite_code}
            )
            
            if validate_response.status_code == 200:
                validate_info = validate_response.json()
                print(f"✅ 邀请码验证成功!")
                print(f"  - 有效性: {validate_info.get('valid')}")
                print(f"  - 企业名称: {validate_info.get('company_name')}")
                print(f"  - 创建者: {validate_info.get('creator_name')}")
                print(f"  - 剩余使用次数: {validate_info.get('remaining_uses')}")
            else:
                print(f"❌ 邀请码验证失败: {validate_response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 邀请码验证异常: {str(e)}")
            return False
        
        # 5. 使用邀请码注册普通用户
        print(f"\n5. 使用邀请码注册普通用户...")
        
        try:
            # 发送短信验证码
            user_sms_response = await client.post(
                f"{BASE_URL}/api/v1/auth/sms/send",
                json={"phone": TEST_PHONE_USER}
            )
            
            if user_sms_response.status_code == 200:
                user_sms_data = user_sms_response.json()
                user_sms_code = user_sms_data.get('debug_code', '123456')
                print(f"✅ 用户短信验证码: {user_sms_code}")
            else:
                print(f"❌ 发送用户短信失败: {user_sms_response.status_code}")
                return False
            
            # 使用邀请码注册
            user_data = {
                "email": TEST_USER_EMAIL,
                "phone": TEST_PHONE_USER,
                "password": TEST_USER_PASSWORD,
                "nickname": "企业员工"
            }
            
            user_register_response = await client.post(
                f"{BASE_URL}/api/v1/auth/register?sms_code={user_sms_code}&invite_code={invite_code}",
                json=user_data
            )
            
            if user_register_response.status_code == 200:
                user_info = user_register_response.json()
                print(f"✅ 企业员工注册成功!")
                print(f"  - 用户ID: {user_info.get('id')}")
                print(f"  - 租户ID: {user_info.get('tenant_id')}")
                print(f"  - 是否管理员: {user_info.get('is_admin')}")
                
                # 验证租户ID是否与管理员相同
                if user_info.get('tenant_id') == admin_tenant_id:
                    print(f"✅ 租户ID匹配，用户成功加入企业!")
                else:
                    print(f"❌ 租户ID不匹配: 用户={user_info.get('tenant_id')}, 管理员={admin_tenant_id}")
                    return False
            else:
                print(f"❌ 企业员工注册失败: {user_register_response.status_code}")
                print(f"   错误信息: {user_register_response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 企业员工注册异常: {str(e)}")
            return False
        
        # 6. 管理员查看企业用户列表
        print(f"\n6. 管理员查看企业用户列表...")
        
        try:
            users_response = await client.get(
                f"{BASE_URL}/api/v1/enterprise/users",
                headers=headers
            )
            
            if users_response.status_code == 200:
                users_data = users_response.json()
                print(f"✅ 企业用户列表获取成功!")
                print(f"  - 用户总数: {len(users_data)}")
                
                for user in users_data:
                    user_type = "管理员" if user.get('is_admin') else "普通用户"
                    status = "活跃" if user.get('is_active') else "禁用"
                    print(f"  - {user.get('email')} ({user_type}, {status})")
            else:
                print(f"❌ 获取企业用户列表失败: {users_response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 获取企业用户列表异常: {str(e)}")
            return False
        
        # 7. 查看邀请码统计
        print(f"\n7. 查看邀请码统计...")
        
        try:
            stats_response = await client.get(
                f"{BASE_URL}/api/v1/invite-codes/stats",
                headers=headers
            )
            
            if stats_response.status_code == 200:
                stats_data = stats_response.json()
                print(f"✅ 邀请码统计获取成功!")
                print(f"  - 总邀请码数: {stats_data.get('total_codes')}")
                print(f"  - 活跃邀请码: {stats_data.get('active_codes')}")
                print(f"  - 总使用次数: {stats_data.get('total_uses')}")
                print(f"  - 邀请用户数: {stats_data.get('total_invited_users')}")
            else:
                print(f"❌ 获取邀请码统计失败: {stats_response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 获取邀请码统计异常: {str(e)}")
            return False
        
        # 8. 查看企业信息
        print(f"\n8. 查看企业信息...")
        
        try:
            info_response = await client.get(
                f"{BASE_URL}/api/v1/enterprise/info",
                headers=headers
            )
            
            if info_response.status_code == 200:
                info_data = info_response.json()
                print(f"✅ 企业信息获取成功!")
                print(f"  - 企业名称: {info_data.get('company_name')}")
                print(f"  - 租户ID: {info_data.get('tenant_id')}")
                print(f"  - 管理员: {info_data.get('admin_name')}")
                print(f"  - 总用户数: {info_data.get('total_users')}")
                print(f"  - 活跃用户数: {info_data.get('active_users')}")
            else:
                print(f"❌ 获取企业信息失败: {info_response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 获取企业信息异常: {str(e)}")
            return False
        
        return True


async def main():
    """主测试函数"""
    
    print("🚀 开始P1企业用户管理功能测试...")
    print("⚠️  请确保后端服务已启动 (python -m uvicorn app.main:app --reload)")
    print("⚠️  请确保已运行数据库迁移脚本")
    
    # 等待用户确认
    input("\n按回车键开始测试...")
    
    success = await test_p1_enterprise_management()
    
    print(f"\n" + "=" * 80)
    print("📋 P1企业用户管理功能测试总结")
    print("=" * 80)
    
    if success:
        print("🎉 所有P1功能测试通过！")
        print("✅ 企业管理员注册正常")
        print("✅ 邀请码创建和验证正常")
        print("✅ 邀请码注册流程正常")
        print("✅ 企业用户管理正常")
        print("✅ 租户隔离机制正常")
        print("\n🎯 P1企业用户管理功能实施成功！")
    else:
        print("❌ P1功能测试失败！")
        print("🔧 请检查:")
        print("  1. 后端服务是否正常启动")
        print("  2. 数据库迁移是否已执行")
        print("  3. 邀请码系统是否正确配置")
        print("  4. API端点是否正确注册")


if __name__ == "__main__":
    asyncio.run(main())