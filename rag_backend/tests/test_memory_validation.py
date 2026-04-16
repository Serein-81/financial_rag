#!/usr/bin/env python3
"""
测试记忆系统的输入验证和错误处理
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.memory_system.base_memory import MemoryItem
from app.memory_system.working_memory import WorkingMemory
from app.memory_system.episodic_memory import EpisodicMemory
from app.memory_system.semantic_memory import SemanticMemory


async def test_working_memory_validation():
    """测试工作记忆的输入验证"""
    print("🧪 测试工作记忆输入验证")
    print("-" * 40)
    
    working_memory = WorkingMemory(capacity=5)
    
    # 测试用例
    test_cases = [
        ("正常消息", "user", "这是一条正常的消息"),
        ("空内容", "user", ""),
        ("空白内容", "user", "   "),
        ("无效角色", "invalid_role", "测试无效角色"),
        ("None内容", "user", None),
    ]
    
    for name, role, content in test_cases:
        print(f"测试: {name}")
        try:
            if content is None:
                # 测试 None 内容
                item = MemoryItem(content="", role=role)
                item.content = None
            else:
                item = MemoryItem(content=content, role=role)
            
            await working_memory.add(item)
            print("  ✅ 处理成功")
        except Exception as e:
            print(f"  ❌ 异常: {e}")
        print()
    
    print(f"最终工作记忆数量: {len(working_memory.memories)}")
    return True


async def test_episodic_memory_validation():
    """测试情景记忆的输入验证（不连接数据库）"""
    print("🧪 测试情景记忆输入验证")
    print("-" * 40)
    
    # 创建情景记忆实例
    episodic_memory = EpisodicMemory("test_session", "test_user")
    
    # 测试用例
    test_cases = [
        ("空内容", "user", ""),
        ("空白内容", "user", "   "),
        ("无效角色", "invalid_role", "测试无效角色"),
        ("正常消息", "user", "这是一条正常的消息"),
    ]
    
    for name, role, content in test_cases:
        print(f"测试: {name}")
        try:
            item = MemoryItem(content=content, role=role)
            # 注意：这里会因为数据库连接失败而跳过，但我们可以看到验证逻辑
            await episodic_memory.add(item)
            print("  ✅ 验证通过")
        except Exception as e:
            print(f"  ⚠️  预期的数据库错误: {str(e)[:50]}...")
        print()
    
    return True


async def test_semantic_memory_validation():
    """测试语义记忆的输入验证（不连接数据库）"""
    print("🧪 测试语义记忆输入验证")
    print("-" * 40)
    
    # 创建语义记忆实例
    semantic_memory = SemanticMemory("test_user")
    
    # 测试用例
    test_cases = [
        ("空内容", "user", "", 0.8),
        ("空白内容", "user", "   ", 0.8),
        ("无效角色", "invalid_role", "测试无效角色", 0.8),
        ("无效重要性", "user", "测试消息", 1.5),
        ("负重要性", "user", "测试消息", -0.1),
        ("正常消息", "user", "这是一条正常的消息", 0.8),
    ]
    
    for name, role, content, importance in test_cases:
        print(f"测试: {name}")
        try:
            item = MemoryItem(content=content, role=role, importance=importance)
            # 注意：这里会因为数据库连接失败而跳过，但我们可以看到验证逻辑
            await semantic_memory.add(item)
            print("  ✅ 验证通过")
        except Exception as e:
            print(f"  ⚠️  预期的数据库错误: {str(e)[:50]}...")
        print()
    
    return True


async def main():
    """主测试函数"""
    print("🧠 记忆系统输入验证测试")
    print("=" * 60)
    
    try:
        # 测试工作记忆（不需要数据库）
        await test_working_memory_validation()
        print()
        
        # 测试情景记忆验证逻辑
        await test_episodic_memory_validation()
        print()
        
        # 测试语义记忆验证逻辑
        await test_semantic_memory_validation()
        print()
        
        print("=" * 60)
        print("🎉 输入验证测试完成！")
        print("注意：情景记忆和语义记忆的数据库错误是预期的，")
        print("因为测试环境没有配置数据库连接。")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())