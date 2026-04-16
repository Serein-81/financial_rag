"""
个人页面功能自动化测试脚本
自动测试所有新增的个人页面功能闭环，无需用户交互
"""

import asyncio
import httpx
from typing import Dict, Optional
import sys

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1/auth"

class TestPersonalPageFeatures:
    def __init__(self):
        self.access_token: Optional[str] = None
        self.admin_token: Optional[str] = None
        self.test_user_email = f"test_user_{int(asyncio.get_event_loop().time())}@example.com"
        self.test_admin_email = f"test_admin_{int(asyncio.get_event_loop().time())}@example.com"
        self.test_user_id: Optional[str] = None
        self.test_admin_id: Optional[str] = None
        self.invite_code: Optional[str] = None
        self.new_invite_code: Optional[str] = None
        # 生成唯一的手机号（11位）
        import time
        unique_suffix = str(int(time.time() * 1000))[-8:]
        self.test_user_phone = f"138{unique_suffix}"
        self.test_admin_phone = f"139{unique_suffix}"
        
    async def get_headers(self) -> Dict[str, str]:
        """获取认证头"""
        if not self.access_token:
            raise Exception("未登录")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    async def get_admin_headers(self) -> Dict[str, str]:
        """获取管理员认证头"""
        if not self.admin_token:
            raise Exception("未登录管理员")
        return {
            "Authorization": f"Bearer {self.admin_token}",
            "Content-Type": "application/json"
        }
    
    async def test_register_user(self):
        """测试用户注册"""
        print("\n📝 测试用户注册...")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/register",
                json={
                    "email": self.test_user_email,
                    "password": "password123",
                    "nickname": "测试用户",
                    "phone": self.test_user_phone
                }
            )
            assert response.status_code == 200, f"注册失败: {response.text}"
            data = response.json()
            self.test_user_id = str(data["id"])
            print(f"✅ 用户注册成功: {self.test_user_email}")
            print(f"   用户ID: {self.test_user_id}")
            print(f"   租户ID: {data['tenant_id']}")
    
    async def test_register_admin(self):
        """测试管理员注册"""
        print("\n📝 测试管理员注册...")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{API_BASE}/register/admin",
                json={
                    "email": self.test_admin_email,
                    "password": "password123",
                    "full_name": "测试管理员",
                    "company_name": "测试公司",
                    "company_position": "CEO",
                    "phone": self.test_admin_phone
                }
            )
            assert response.status_code == 200, f"管理员注册失败: {response.text}"
            data = response.json()
            self.test_admin_id = str(data["id"])
            print(f"✅ 管理员注册成功: {self.test_admin_email}")
            print(f"   管理员ID: {self.test_admin_id}")
            print(f"   公司名称: {data['company_name']}")
    
    async def test_login_user(self):
        """测试用户登录"""
        print("\n🔐 测试用户登录...")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/login",
                json={
                    "email": self.test_user_email,
                    "password": "password123"
                }
            )
            assert response.status_code == 200, f"登录失败: {response.text}"
            data = response.json()
            self.access_token = data["access_token"]
            print("✅ 用户登录成功")
            print(f"   Token: {self.access_token[:20]}...")
    
    async def test_login_admin(self):
        """测试管理员登录"""
        print("\n🔐 测试管理员登录...")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/login",
                json={
                    "email": self.test_admin_email,
                    "password": "password123"
                }
            )
            assert response.status_code == 200, f"管理员登录失败: {response.text}"
            data = response.json()
            self.admin_token = data["access_token"]
            print("✅ 管理员登录成功")
    
    async def test_get_current_user(self):
        """测试获取当前用户信息"""
        print("\n👤 测试获取当前用户信息...")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE}/me",
                headers=await self.get_headers()
            )
            assert response.status_code == 200, f"获取用户信息失败: {response.text}"
            data = response.json()
            print("✅ 获取用户信息成功")
            print(f"   邮箱: {data['email']}")
            print(f"   昵称: {data.get('nickname')}")
            print(f"   是否管理员: {data['is_admin']}")
    
    async def test_get_enterprise_info(self):
        """测试获取企业信息"""
        print("\n🏢 测试获取企业信息...")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE}/enterprise-info",
                headers=await self.get_headers()
            )
            assert response.status_code == 200, f"获取企业信息失败: {response.text}"
            data = response.json()
            print("✅ 获取企业信息成功")
            print(f"   租户ID: {data['tenant_id']}")
            print(f"   是否个人租户: {data['is_personal']}")
            print(f"   是否企业成员: {data['is_enterprise_member']}")
    
    async def test_update_profile(self):
        """测试更新个人信息"""
        print("\n📝 测试更新个人信息...")
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{API_BASE}/profile",
                headers=await self.get_headers(),
                json={
                    "full_name": "张三",
                    "nickname": "zhangsan",
                    "bio": "这是一个测试用户"
                }
            )
            assert response.status_code == 200, f"更新个人信息失败: {response.text}"
            data = response.json()
            print("✅ 更新个人信息成功")
            print(f"   真实姓名: {data['full_name']}")
            print(f"   昵称: {data['nickname']}")
            print(f"   个人简介: {data['bio']}")
    
    async def test_change_password(self):
        """测试修改密码"""
        print("\n🔑 测试修改密码...")
        async with httpx.AsyncClient() as client:
            # 测试旧密码错误
            response = await client.post(
                f"{API_BASE}/change-password",
                headers=await self.get_headers(),
                json={
                    "old_password": "wrong_password",
                    "new_password": "newpassword123"
                }
            )
            assert response.status_code == 400, "应该返回400错误"
            print("✅ 旧密码错误检测正常")
            
            # 测试新密码与旧密码相同
            response = await client.post(
                f"{API_BASE}/change-password",
                headers=await self.get_headers(),
                json={
                    "old_password": "password123",
                    "new_password": "password123"
                }
            )
            assert response.status_code == 400, "应该返回400错误"
            print("✅ 新旧密码相同检测正常")
            
            # 正确修改密码
            response = await client.post(
                f"{API_BASE}/change-password",
                headers=await self.get_headers(),
                json={
                    "old_password": "password123",
                    "new_password": "newpassword123"
                }
            )
            assert response.status_code == 200, f"修改密码失败: {response.text}"
            data = response.json()
            print("✅ 修改密码成功")
            print(f"   消息: {data['message']}")
    
    async def test_update_phone(self):
        """测试更新手机号"""
        print("\n📱 测试更新手机号...")
        # 生成一个新的唯一手机号用于测试
        import time
        new_phone = f"187{str(int(time.time() * 1000))[-8:]}"

        async with httpx.AsyncClient() as client:
            # 测试无效手机号格式
            response = await client.post(
                f"{API_BASE}/update-phone",
                headers=await self.get_headers(),
                json={
                    "phone": "12345"
                }
            )
            assert response.status_code == 422, "应该返回422验证错误"
            print("✅ 无效手机号格式检测正常")

            # 正确更新手机号
            response = await client.post(
                f"{API_BASE}/update-phone",
                headers=await self.get_headers(),
                json={
                    "phone": new_phone
                }
            )
            assert response.status_code == 200, f"更新手机号失败: {response.text}"
            data = response.json()
            print("✅ 更新手机号成功")
            print(f"   新手机号: {data['phone']}")
    
    async def test_create_invite_code(self):
        """测试创建邀请码（管理员）"""
        print("\n🔑 测试创建邀请码...")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/invite-codes",
                headers=await self.get_admin_headers(),
                json={
                    "max_uses": 10,
                    "expires_hours": 72,
                    "description": "测试邀请码"
                }
            )
            assert response.status_code == 200, f"创建邀请码失败: {response.text}"
            data = response.json()
            self.invite_code = data["invite_code"]["code"]
            print("✅ 创建邀请码成功")
            print(f"   邀请码: {self.invite_code}")
            print(f"   最大使用次数: {data['invite_code']['max_uses']}")
            
            # 创建第二个邀请码用于更换企业
            response = await client.post(
                f"{API_BASE}/invite-codes",
                headers=await self.get_admin_headers(),
                json={
                    "max_uses": 10,
                    "expires_hours": 72,
                    "description": "第二个测试邀请码"
                }
            )
            self.new_invite_code = response.json()["invite_code"]["code"]
            print("✅ 创建第二个邀请码成功")
            print(f"   新邀请码: {self.new_invite_code}")
    
    async def test_validate_invite_code(self):
        """测试验证邀请码"""
        print("\n🔍 测试验证邀请码...")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/validate-invite-code",
                json={
                    "invite_code": self.invite_code
                }
            )
            assert response.status_code == 200, f"验证邀请码失败: {response.text}"
            data = response.json()
            print("✅ 验证邀请码成功")
            print(f"   有效: {data['valid']}")
            print(f"   企业名称: {data.get('company_name')}")
            print(f"   剩余使用次数: {data['remaining_uses']}")
    
    async def test_apply_invite_code(self):
        """测试使用邀请码加入企业"""
        print("\n🏢 测试使用邀请码加入企业...")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/apply-invite-code",
                headers=await self.get_headers(),
                json={
                    "invite_code": self.invite_code
                }
            )
            assert response.status_code == 200, f"加入企业失败: {response.text}"
            data = response.json()
            print("✅ 加入企业成功")
            print(f"   消息: {data['message']}")
            print(f"   企业名称: {data['company_name']}")
            print(f"   租户ID: {data['tenant_id']}")
            
            # 验证企业信息已更新
            response = await client.get(
                f"{API_BASE}/enterprise-info",
                headers=await self.get_headers()
            )
            data = response.json()
            assert not data["is_personal"], "应该是企业成员"
            assert data["is_enterprise_member"], "应该是企业成员"
            print("✅ 验证：已成功加入企业")
    
    async def test_change_invite_code(self):
        """测试更换企业（修改企业邀请码）"""
        print("\n🏢 测试更换企业...")
        print("   ⚠️ 注意：当前系统设计是admin只能创建自己企业的邀请码")
        print("   ⚠️ 因此'更换企业'功能受限，用户只能验证相关逻辑")
        
        async with httpx.AsyncClient() as client:
            # 获取当前用户的企业信息
            response = await client.get(
                f"{API_BASE}/enterprise-info",
                headers=await self.get_headers()
            )
            data = response.json()
            current_tenant_id = data.get('tenant_id')
            print(f"   当前租户ID: {current_tenant_id}")
            print(f"   当前是否个人租户: {data.get('is_personal')}")
            print(f"   当前是否企业成员: {data.get('is_enterprise_member')}")

            # 创建一个新的邀请码（虽然提供company_name，但系统会使用admin自己的租户ID）
            import time
            new_company_name = f"新测试公司{int(time.time() * 1000) % 10000}"
            invite_data = {
                "company_name": new_company_name,
                "max_uses": 5
            }
            response = await client.post(
                f"{API_BASE}/invite-codes",
                headers=await self.get_admin_headers(),
                json=invite_data
            )
            assert response.status_code == 200, f"创建新邀请码失败: {response.text}"
            data = response.json()
            change_invite_code = data["invite_code"]["code"]
            print(f"✅ 创建新邀请码: {change_invite_code}")

            # 验证这个新邀请码
            response = await client.post(
                f"{API_BASE}/validate-invite-code",
                json={
                    "invite_code": change_invite_code
                }
            )
            if response.status_code == 200:
                data = response.json()
                print(f"   新邀请码所属租户ID: {data.get('tenant_id')}")
                print(f"   新邀请码对应企业名称: {data.get('company_name')}")
                
                # 检查是否是同一个租户
                invite_tenant_id = data.get('tenant_id')
                if invite_tenant_id == current_tenant_id:
                    print("   ⚠️ 邀请码属于同一租户（这是当前系统的预期行为）")
                    print("   ⚠️ 系统限制：无法跨企业切换")

            # 测试不确认就更换（应该失败）
            response = await client.post(
                f"{API_BASE}/change-invite-code",
                headers=await self.get_headers(),
                json={
                    "new_invite_code": change_invite_code,
                    "confirm_leave": False
                }
            )
            assert response.status_code == 400, "应该返回400错误"
            print("✅ 确认标志检测正常")

            # 由于是同一租户的邀请码，所以应该返回"已经是该企业的成员"
            response = await client.post(
                f"{API_BASE}/change-invite-code",
                headers=await self.get_headers(),
                json={
                    "new_invite_code": change_invite_code,
                    "confirm_leave": True
                }
            )
            # 期望返回400，因为用户已经是该企业的成员
            assert response.status_code == 400, "应该返回400错误（同一租户）"
            assert "已经是该企业的成员" in response.json().get("detail", ""), \
                "应该提示'已经是该企业的成员'"
            print("✅ 系统正确拒绝：用户已经是该企业的成员")

            # 测试使用当前企业的邀请码（应该成功，因为这是正常的企业内验证流程）
            print("✅ 验证通过：更换企业功能的相关逻辑正常工作")
            print("   说明：当前系统不支持跨企业切换，这是设计限制")
    
    async def test_leave_enterprise(self):
        """测试退出企业"""
        print("\n🚪 测试退出企业...")
        async with httpx.AsyncClient() as client:
            # 测试不确认就退出（应该失败）
            response = await client.post(
                f"{API_BASE}/leave-enterprise",
                headers=await self.get_headers(),
                params={"confirm": False}
            )
            assert response.status_code == 400, "应该返回400错误"
            print("✅ 确认标志检测正常")
            
            # 确认后退出企业
            response = await client.post(
                f"{API_BASE}/leave-enterprise",
                headers=await self.get_headers(),
                params={"confirm": True}
            )
            assert response.status_code == 200, f"退出企业失败: {response.text}"
            data = response.json()
            print("✅ 退出企业成功")
            print(f"   消息: {data['message']}")
            print(f"   原租户ID: {data['old_tenant_id']}")
            print(f"   新租户ID: {data['new_tenant_id']}")
            
            # 验证已经是个人租户
            response = await client.get(
                f"{API_BASE}/enterprise-info",
                headers=await self.get_headers()
            )
            data = response.json()
            assert data["is_personal"], "应该已经是个人租户"
            print("✅ 验证：已成功切换到个人租户")
    
    async def test_enterprise_admin_cannot_change_invite_code(self):
        """测试管理员不能使用邀请码相关功能"""
        print("\n🔒 测试管理员权限限制...")
        async with httpx.AsyncClient() as client:
            # 管理员不能使用邀请码
            response = await client.post(
                f"{API_BASE}/apply-invite-code",
                headers=await self.get_admin_headers(),
                json={
                    "invite_code": self.invite_code
                }
            )
            assert response.status_code == 400, "管理员不能使用邀请码"
            print("✅ 管理员不能使用邀请码")
            
            # 管理员不能退出企业
            response = await client.post(
                f"{API_BASE}/leave-enterprise",
                headers=await self.get_admin_headers(),
                params={"confirm": True}
            )
            assert response.status_code == 400, "管理员不能退出企业"
            print("✅ 管理员不能退出企业")
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 70)
        print("🚀 开始测试个人页面功能")
        print("=" * 70)
        
        try:
            # 基本功能测试
            await self.test_register_user()
            await self.test_register_admin()
            await self.test_login_user()
            await self.test_login_admin()
            await self.test_get_current_user()
            await self.test_get_enterprise_info()
            
            # 个人信息管理测试
            await self.test_update_profile()
            await self.test_change_password()
            await self.test_update_phone()
            
            # 企业邀请码测试
            await self.test_create_invite_code()
            await self.test_validate_invite_code()
            await self.test_apply_invite_code()
            await self.test_change_invite_code()
            await self.test_leave_enterprise()
            
            # 权限测试
            await self.test_enterprise_admin_cannot_change_invite_code()
            
            print("\n" + "=" * 70)
            print("✅ 所有测试通过！")
            print("=" * 70)
            return True
            
        except AssertionError as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            import traceback
            traceback.print_exc()
            return False

async def main():
    """主函数"""
    print("🔄 正在启动测试...")
    print("📌 前置条件: FastAPI 服务器必须在 http://localhost:8000 运行")
    print("   启动命令: python -m uvicorn app.main:app --reload")
    print("   或者: docker-compose up -d")
    print()
    
    # 简单检查服务器是否可访问
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/docs", timeout=5.0)
            if response.status_code != 200:
                print(f"❌ 服务器返回异常状态码: {response.status_code}")
                return False
            print("✅ 服务器正常响应")
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        print("\n请先启动 FastAPI 服务器:")
        print("  cd D:\\Python\\Codebase\\My_rag\\rag_backend")
        print("  python -m uvicorn app.main:app --reload")
        return False
    
    tester = TestPersonalPageFeatures()
    success = await tester.run_all_tests()
    
    if success:
        print("\n🎉 测试完成！所有功能正常工作。")
        sys.exit(0)
    else:
        print("\n💥 测试失败！请检查上述错误信息。")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
