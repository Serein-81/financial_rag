#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日志系统测试脚本

测试日志记录、查询、统计等功能
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.log_service import log_service
from app.models.system_log import LogLevel, LogCategory
from app.utils.log_decorators import log_function_call, log_user_action


class LoggingSystemTester:
    """日志系统测试器"""
    
    def __init__(self):
        self.test_user_id = "test-user-123"
        self.test_session_id = "test-session-456"
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始测试日志系统...")
        
        try:
            # 1. 测试基本日志记录
            await self.test_basic_logging()
            
            # 2. 测试用户操作日志
            await self.test_user_action_logging()
            
            # 3. 测试日志查询
            await self.test_log_queries()
            
            # 4. 测试日志统计
            await self.test_log_statistics()
            
            # 5. 测试装饰器
            await self.test_decorators()
            
            print("✅ 所有测试完成！")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    async def test_basic_logging(self):
        """测试基本日志记录"""
        print("\n📝 测试基本日志记录...")
        
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
            log = await log_service.create_system_log(
                user_id=self.test_user_id,
                session_id=self.test_session_id,
                **log_data
            )
            print(f"  ✅ 创建{log_data['level'].value}级别日志: {log.id}")
    
    async def test_user_action_logging(self):
        """测试用户操作日志"""
        print("\n👤 测试用户操作日志...")
        
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
            },
            {
                "action_type": "CHAT_SESSION",
                "action_name": "开始对话",
                "description": "用户开始了新的对话会话",
                "success": False,
                "result_message": "会话创建失败：服务器繁忙"
            }
        ]
        
        for action_data in action_logs:
            log = await log_service.create_user_action_log(
                user_id=self.test_user_id,
                ip_address="192.168.1.100",
                session_id=self.test_session_id,
                **action_data
            )
            print(f"  ✅ 创建用户操作日志: {action_data['action_name']} - {log.id}")
    
    async def test_log_queries(self):
        """测试日志查询"""
        print("\n🔍 测试日志查询...")
        
        # 查询系统日志
        system_logs = await log_service.get_system_logs(
            user_id=self.test_user_id,
            is_admin=False,
            limit=10
        )
        print(f"  ✅ 查询到 {len(system_logs['logs'])} 条系统日志")
        
        # 查询用户操作日志
        action_logs = await log_service.get_user_action_logs(
            user_id=self.test_user_id,
            is_admin=False,
            limit=10
        )
        print(f"  ✅ 查询到 {len(action_logs['logs'])} 条用户操作日志")
        
        # 按级别过滤
        error_logs = await log_service.get_system_logs(
            user_id=self.test_user_id,
            is_admin=False,
            level=LogLevel.ERROR,
            limit=10
        )
        print(f"  ✅ 查询到 {len(error_logs['logs'])} 条错误日志")
        
        # 按分类过滤
        user_action_logs = await log_service.get_system_logs(
            user_id=self.test_user_id,
            is_admin=False,
            category=LogCategory.USER_ACTION,
            limit=10
        )
        print(f"  ✅ 查询到 {len(user_action_logs['logs'])} 条用户操作系统日志")
    
    async def test_log_statistics(self):
        """测试日志统计"""
        print("\n📊 测试日志统计...")
        
        # 获取统计信息
        stats = await log_service.get_log_statistics(
            user_id=self.test_user_id,
            is_admin=False,
            days=7
        )
        
        print(f"  ✅ 统计周期: {stats['period']}")
        print(f"  ✅ 总日志数: {stats['total_logs']}")
        print(f"  ✅ 错误数量: {stats['error_count']}")
        print(f"  ✅ 级别统计: {stats['level_stats']}")
        print(f"  ✅ 分类统计: {stats['category_stats']}")
    
    async def test_decorators(self):
        """测试装饰器"""
        print("\n🎭 测试日志装饰器...")
        
        # 测试函数调用装饰器
        @log_function_call(
            category=LogCategory.SYSTEM_EVENT,
            action="test_function",
            log_args=True,
            log_performance=True
        )
        async def test_function(param1: str, param2: int = 42):
            """测试函数"""
            await asyncio.sleep(0.1)  # 模拟一些处理时间
            return f"处理结果: {param1} - {param2}"
        
        result = await test_function("测试参数", param2=100)
        print(f"  ✅ 函数执行结果: {result}")
        
        # 测试用户操作装饰器
        @log_user_action(
            action_type="TEST_ACTION",
            action_name="测试操作",
            description="这是一个测试操作"
        )
        async def test_user_action(user_id: str, data: dict):
            """测试用户操作"""
            return {"status": "success", "data": data}
        
        result = await test_user_action(
            user_id=self.test_user_id,
            data={"test": "data"}
        )
        print(f"  ✅ 用户操作结果: {result}")


async def main():
    """主函数"""
    tester = LoggingSystemTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())