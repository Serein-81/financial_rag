#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
用户注册功能测试脚本
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.schemas.auth_request import UserRegister, AdminRegister


def test_user_register_validation():
    """测试普通用户注册数据验证"""
    print("📝 测试普通用户注册数据验证...")
    
    # 测试有效数据
    try:
        user_data = UserRegister(
            email="test@example.com",
            phone="13800138000",
            password="123456",
            nickname="测试用户"
        )
        print(f"  ✅ 有效数据验证通过: {user_data.email}")
    except Exception as e:
        print(f"  ❌ 验证失败: {e}")
    
    # 测试无效手机号
    try:
        invalid_phone = UserRegister(
            email="test@example.com",
            phone="12345678901",  # 无效手机号
            password="123456"
        )
        print("  ❌ 应该拒绝无效手机号")
    except Exception as e:
        print(f"  ✅ 正确拒绝无效手机号: {e}")
    
    # 测试短密码
    try:
        short_password = UserRegister(
            email="test@example.com",
            phone="13800138000",
            password="123"  # 密码太短
        )
        print("  ❌ 应该拒绝短密码")
    except Exception as e:
        print(f"  ✅ 正确拒绝短密码: {e}")


def test_admin_register_validation():
    """测试企业管理员注册数据验证"""
    print("\n👔 测试企业管理员注册数据验证...")
    
    # 测试有效数据
    try:
        admin_data = AdminRegister(
            email="admin@company.com",
            phone="13900139000",
            password="admin123",
            full_name="张三",
            company_name="测试科技有限公司",
            company_position="技术总监",
            nickname="张总"
        )
        print(f"  ✅ 有效数据验证通过: {admin_data.email}")
    except Exception as e:
        print(f"  ❌ 验证失败: {e}")


if __name__ == "__main__":
    test_user_register_validation()
    test_admin_register_validation()
    print("\n✅ 所有验证测试完成！")