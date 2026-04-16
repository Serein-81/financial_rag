#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简化的日志系统测试脚本

只测试日志记录功能，不涉及复杂的模型关系
"""

import asyncio
import sys
import os
import uuid
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.system_log import LogLevel, LogCategory


async def test_basic_logging():
    """测试基本日志记录"""
    print("📝 测试基本日志记录...")
    
    # 直接导入并测试日志服务
    from app.services.log_service import log_service
    
    # 使用有效的UUID格式
    test_user_id = str(uuid.uuid4())
    test_session_id = "test-session-456"
    
    # 创建不同级别的日志
    test_logs = [
        {
            "level": LogLevel.INFO,
            "category": LogCategory.SYSTEM_EVENT,
            "action": "test_info",
            "message": "这是一条信息日志"
        },
        {
            "level": LogLevel.WARNING,
            "category": LogCategory.USER_ACTION,
            "action": "test_warning",
            "message": "这是一条警告日志"
        },
        {
            "level": LogLevel.ERROR,
            "category": LogCategory.ERROR_TRACE,
            "action": "test_error",
            "message": "这是一条错误日志",
            "error_type": "TestError",
            "error_message": "测试错误消息"
        }
    ]
    
    for log_data in test_logs:
        try:
            log = await log_service.create_system_log(
                user_id=None,  # 不关联用户，测试系统日志
                session_id=test_session_id,
                **log_data
            )
            print(f"  ✅ 创建{log_data['level'].value}级别日志: {log.id}")
        except Exception as e:
            print(f"  ❌ 创建日志失败: {e}")


async def test_user_action_logging():
    """测试用户操作日志"""
    print("\n👤 测试用户操作日志...")
    
    from app.services.log_service import log_service
    
    # 使用有效的UUID格式
    test_user_id = str(uuid.uuid4())
    test_session_id = "test-session-456"
    
    # 创建用户操作日志
    action_logs = [
        {
            "action_type": "DOCUMENT_UPLOAD",
            "action_name": "上传文档",
            "description": "用户上传了一个PDF文档",
            "resource_type": "document",
            "resource_id": "doc-123",
            "resource_name": "测试文档.pdf",
            "success": True
        },
        {
            "action_type": "KNOWLEDGE_SEARCH",
            "action_name": "知识搜索",
            "description": "用户搜索了相关知识",
            "resource_type": "knowledge_base",
            "resource_id": "kb-456",
            "success": True
        }
    ]
    
    for action_data in action_logs:
        try:
            log = await log_service.create_user_action_log(
                user_id=test_user_id,
                ip_address="192.168.1.100",
                session_id=test_session_id,
                **action_data
            )
            print(f"  ✅ 创建用户操作日志: {action_data['action_name']} - {log.id}")
        except Exception as e:
            print(f"  ❌ 创建用户操作日志失败: {e}")


async def test_log_queries():
    """测试日志查询"""
    print("\n🔍 测试日志查询...")
    
    from app.services.log_service import log_service
    
    # 使用有效的UUID格式
    test_user_id = str(uuid.uuid4())
    
    try:
        # 查询系统日志（不指定用户ID，查询所有日志）
        system_logs = await log_service.get_system_logs(
            user_id=None,
            is_admin=True,  # 管理员可以查看所有日志
            limit=10
        )
        print(f"  ✅ 查询到 {len(system_logs['logs'])} 条系统日志")
        
        # 查询用户操作日志（不指定用户ID）
        action_logs = await log_service.get_user_action_logs(
            user_id=None,
            is_admin=True,
            limit=10
        )
        print(f"  ✅ 查询到 {len(action_logs['logs'])} 条用户操作日志")
        
        # 按级别过滤
        error_logs = await log_service.get_system_logs(
            user_id=None,
            is_admin=True,
            level=LogLevel.ERROR,
            limit=10
        )
        print(f"  ✅ 查询到 {len(error_logs['logs'])} 条错误日志")
        
    except Exception as e:
        print(f"  ❌ 查询日志失败: {e}")


async def test_log_statistics():
    """测试日志统计"""
    print("\n📊 测试日志统计...")
    
    from app.services.log_service import log_service
    
    # 使用有效的UUID格式
    test_user_id = str(uuid.uuid4())
    
    try:
        # 获取统计信息（管理员查看所有日志）
        stats = await log_service.get_log_statistics(
            user_id=None,
            is_admin=True,
            days=7
        )
        
        print(f"  ✅ 统计周期: {stats['period']}")
        print(f"  ✅ 总日志数: {stats['total_logs']}")
        print(f"  ✅ 错误数量: {stats['error_count']}")
        print(f"  ✅ 级别统计: {stats['level_stats']}")
        print(f"  ✅ 分类统计: {stats['category_stats']}")
        
    except Exception as e:
        print(f"  ❌ 统计查询失败: {e}")


async def main():
    """主函数"""
    print("🚀 开始测试日志系统...")
    
    try:
        # 1. 测试基本日志记录
        await test_basic_logging()
        
        # 2. 测试用户操作日志
        await test_user_action_logging()
        
        # 3. 测试日志查询
        await test_log_queries()
        
        # 4. 测试日志统计
        await test_log_statistics()
        
        print("\n✅ 所有测试完成！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())