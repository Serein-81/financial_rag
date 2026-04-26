#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
短信验证码服务测试脚本
"""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.sms_service import sms_service
from app.services.redis_service import redis_service


async def test_send_sms():
    """测试发送短信验证码"""
    print("📱 测试发送短信验证码...")
    
    test_phone = "13800138000"
    
    # 第一次发送
    print(f"\n1️⃣ 第一次发送验证码到 {test_phone}")
    result = await sms_service.send_verification_code(test_phone)
    print(f"结果: {result}")
    
    # 立即再次发送（应该被限制）
    print("\n2️⃣ 立即再次发送（应该被限制）")
    result = await sms_service.send_verification_code(test_phone)
    print(f"结果: {result}")
    
    # 验证验证码
    print("\n3️⃣ 验证验证码")
    # 从Redis获取验证码
    code_key = f"sms:code:{test_phone}"
    stored_code = redis_service.get(code_key)
    if stored_code:
        print(f"存储的验证码: {stored_code}")
        
        # 测试正确的验证码
        verify_result = sms_service.verify_code(test_phone, stored_code)
        print(f"验证结果: {verify_result}")
    else:
        print("未找到存储的验证码")
    
    # 测试错误的验证码
    print("\n4️⃣ 测试错误的验证码")
    verify_result = sms_service.verify_code(test_phone, "000000")
    print(f"验证结果: {verify_result}")


async def test_frequency_limit():
    """测试频率限制"""
    print("\n⏰ 测试频率限制...")
    
    test_phone = "13900139000"
    
    # 发送第一次
    print("\n发送第1次")
    result = await sms_service.send_verification_code(test_phone)
    print(f"结果: {result['success']} - {result['message']}")
    
    # 清除验证码，但保留限制
    code_key = f"sms:code:{test_phone}"
    redis_service.delete(code_key)
    
    # 尝试再次发送（应该被1小时限制）
    print("\n发送第2次（应该被1小时限制）")
    result = await sms_service.send_verification_code(test_phone)
    print(f"结果: {result['success']} - {result['message']}")


async def test_daily_limit():
    """测试每日限制"""
    print("\n📅 测试每日限制...")
    
    test_phone = "13700137000"
    
    # 模拟已经发送了3次
    daily_key = f"sms:daily:{test_phone}"
    redis_service.set_with_expire(daily_key, "3", 86400)
    
    # 尝试再次发送（应该被每日限制）
    print("\n尝试发送（已达每日上限）")
    result = await sms_service.send_verification_code(test_phone)
    print(f"结果: {result['success']} - {result['message']}")
    
    # 清理
    redis_service.delete(daily_key)


async def main():
    """主函数"""
    print("🚀 开始测试短信验证码服务...")
    print("="*60)
    
    try:
        # 测试发送和验证
        await test_send_sms()
        
        # 测试频率限制
        await test_frequency_limit()
        
        # 测试每日限制
        await test_daily_limit()
        
        print("\n" + "="*60)
        print("✅ 所有测试完成！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())