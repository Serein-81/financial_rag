"""
邀请码API测试脚本
用于验证个人页面邀请码功能是否正常工作
"""

import requests
from typing import Optional

# API基础URL
BASE_URL = "http://localhost:8000/api/v1/auth"


class InviteCodeAPITester:
    """邀请码API测试器"""

    def __init__(self):
        self.admin_token: Optional[str] = None
        self.user_token: Optional[str] = None

    def get_headers(self, token: str) -> dict:
        """获取认证头"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

    def login_admin(self) -> bool:
        """管理员登录"""
        print("\n=== 管理员登录 ===")
        try:
            response = requests.post(
                f"{BASE_URL}/login",
                json={
                    "email": "admin@example.com",
                    "password": "admin123"
                }
            )

            if response.status_code == 200:
                data = response.json()
                self.admin_token = data["access_token"]
                print("✅ 管理员登录成功")
                print(f"   Token: {self.admin_token[:20]}...")
                return True
            else:
                print(f"❌ 管理员登录失败: {response.text}")
                return False
        except Exception as e:
            print(f"❌ 管理员登录失败: {e}")
            return False

    def login_user(self) -> bool:
        """普通用户登录"""
        print("\n=== 普通用户登录 ===")
        try:
            response = requests.post(
                f"{BASE_URL}/login",
                json={
                    "email": "user@example.com",
                    "password": "user123"
                }
            )

            if response.status_code == 200:
                data = response.json()
                self.user_token = data["access_token"]
                print("✅ 普通用户登录成功")
                print(f"   Token: {self.user_token[:20]}...")
                return True
            else:
                print(f"❌ 普通用户登录失败: {response.text}")
                return False
        except Exception as e:
            print(f"❌ 普通用户登录失败: {e}")
            return False

    def get_current_user(self) -> bool:
        """获取当前用户信息"""
        print("\n=== 获取当前用户信息 ===")
        if not self.admin_token:
            print("❌ 未登录管理员")
            return False

        try:
            response = requests.get(
                f"{BASE_URL}/me",
                headers=self.get_headers(self.admin_token)
            )

            if response.status_code == 200:
                user = response.json()
                print("✅ 当前用户信息:")
                print(f"   邮箱: {user.get('email')}")
                print(f"   姓名: {user.get('full_name') or user.get('nickname')}")
                print(f"   是否管理员: {user.get('is_admin')}")
                print(f"   租户ID: {user.get('tenant_id')}")
                return True
            else:
                print(f"❌ 获取用户信息失败: {response.text}")
                return False
        except Exception as e:
            print(f"❌ 获取用户信息失败: {e}")
            return False

    def create_invite_code(self) -> Optional[str]:
        """创建邀请码"""
        print("\n=== 创建邀请码（管理员） ===")
        if not self.admin_token:
            print("❌ 未登录管理员")
            return None

        try:
            response = requests.post(
                f"{BASE_URL}/invite-codes",
                headers=self.get_headers(self.admin_token),
                json={
                    "max_uses": 5,
                    "expires_hours": 24,
                    "description": "测试邀请码"
                }
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    invite_code = data["invite_code"]["code"]
                    print("✅ 邀请码创建成功")
                    print(f"   邀请码: {invite_code}")
                    print(f"   最大使用次数: {data['invite_code']['max_uses']}")
                    print(f"   过期时间: {data['invite_code']['expires_at']}")
                    return invite_code
                else:
                    print(f"❌ 创建失败: {data.get('message')}")
                    return None
            else:
                print(f"❌ 创建邀请码失败: {response.text}")
                return None
        except Exception as e:
            print(f"❌ 创建邀请码失败: {e}")
            return None

    def validate_invite_code(self, code: str) -> bool:
        """验证邀请码"""
        print(f"\n=== 验证邀请码: {code} ===")

        try:
            response = requests.post(
                f"{BASE_URL}/validate-invite-code",
                json={"invite_code": code}
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("valid"):
                    print("✅ 邀请码有效")
                    print(f"   企业名称: {data.get('company_name')}")
                    print(f"   剩余使用次数: {data.get('remaining_uses')}")
                    print(f"   过期时间: {data.get('expires_at')}")
                    return True
                else:
                    print(f"❌ 邀请码无效: {data.get('message')}")
                    return False
            else:
                print(f"❌ 验证失败: {response.text}")
                return False
        except Exception as e:
            print(f"❌ 验证邀请码失败: {e}")
            return False

    def apply_invite_code(self, code: str) -> bool:
        """使用邀请码"""
        print(f"\n=== 使用邀请码: {code} ===")
        if not self.user_token:
            print("❌ 未登录普通用户")
            return False

        try:
            response = requests.post(
                f"{BASE_URL}/apply-invite-code",
                headers=self.get_headers(self.user_token),
                json={"invite_code": code}
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    print("✅ 成功加入企业")
                    print(f"   企业名称: {data.get('company_name')}")
                    print(f"   租户ID: {data.get('tenant_id')}")
                    return True
                else:
                    print(f"❌ 加入企业失败: {data.get('message')}")
                    return False
            else:
                print(f"❌ 使用邀请码失败: {response.text}")
                return False
        except Exception as e:
            print(f"❌ 使用邀请码失败: {e}")
            return False

    def list_invite_codes(self) -> bool:
        """获取邀请码列表"""
        print("\n=== 获取邀请码列表（管理员） ===")
        if not self.admin_token:
            print("❌ 未登录管理员")
            return False

        try:
            response = requests.get(
                f"{BASE_URL}/invite-codes?limit=10",
                headers=self.get_headers(self.admin_token)
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    print(f"✅ 获取成功，共 {data.get('total')} 个邀请码")
                    for code in data.get("invite_codes", []):
                        print(f"   - {code['code']} "
                              f"(已使用: {code['used_count']}/{code['max_uses']}, "
                              f"有效: {code['is_valid']})")
                    return True
                else:
                    print(f"❌ 获取失败: {data.get('message')}")
                    return False
            else:
                print(f"❌ 获取邀请码列表失败: {response.text}")
                return False
        except Exception as e:
            print(f"❌ 获取邀请码列表失败: {e}")
            return False


def main():
    """主测试流程"""
    print("=" * 60)
    print("企业邀请码功能测试")
    print("=" * 60)

    tester = InviteCodeAPITester()

    # 1. 管理员登录
    if not tester.login_admin():
        print("\n⚠️  管理员登录失败，请检查账号密码")
        return

    # 2. 获取当前用户信息
    tester.get_current_user()

    # 3. 创建邀请码
    invite_code = tester.create_invite_code()
    if not invite_code:
        print("\n⚠️  创建邀请码失败")
        return

    # 4. 验证邀请码（无需登录）
    tester.validate_invite_code(invite_code)

    # 5. 普通用户登录
    if not tester.login_user():
        print("\n⚠️  普通用户登录失败，跳过使用邀请码测试")
        # 继续执行后续测试

    # 6. 使用邀请码
    if tester.user_token:
        tester.apply_invite_code(invite_code)

    # 7. 获取邀请码列表
    tester.list_invite_codes()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print("\n📝 注意事项：")
    print("1. 如果测试失败，请检查API服务是否启动")
    print("2. 请确保数据库中有管理员和普通用户账号")
    print("3. 可以在 http://localhost:8000/personal-page 访问Web界面")
    print("4. 更多API详情请查看文档：http://localhost:8000/docs")


if __name__ == "__main__":
    main()
