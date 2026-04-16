#!/usr/bin/env python3
"""
测试情景记忆 consolidate 方法修复
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.memory_system.memory_manager import MemoryManager
from app.memory_system.episodic_memory import EpisodicMemory
from app.memory_system.base_memory import MemoryItem


async def test_consolidate_method():
    """测试 consolidate 方法是否存在并可以调用"""
    
    print("🧪 测试情景记忆 consolidate 方法修复")
    print("=" * 50)
    
    # 1. 测试 EpisodicMemory 是否有 consolidate 方法
    print("1. 检查 EpisodicMemory 类是否有 consolidate 方法...")
    
    episodic_memory = EpisodicMemory("test_session", "test_user")
    
    # 检查方法是否存在
    if hasattr(episodic_memory, 'consolidate'):
        print("✅ EpisodicMemory.consolidate 方法存在")
    else:
        print("❌ EpisodicMemory.consolidate 方法不存在")
        return False
    
    # 2. 测试方法是否可以调用
    print("2. 测试 consolidate 方法调用...")
    
    try:
        await episodic_memory.consolidate()
        print("✅ EpisodicMemory.consolidate() 调用成功")
    except Exception as e:
        print(f"❌ EpisodicMemory.consolidate() 调用失败: {e}")
        return False
    
    # 3. 测试 MemoryManager 的 consolidate_memories 方法
    print("3. 测试 MemoryManager.consolidate_memories 方法...")
    
    try:
        memory_manager = MemoryManager("test_session", "test_user")
        await memory_manager.consolidate_memories()
        print("✅ MemoryManager.consolidate_memories() 调用成功")
    except Exception as e:
        print(f"❌ MemoryManager.consolidate_memories() 调用失败: {e}")
        return False
    
    print("=" * 50)
    print("🎉 所有测试通过！consolidate 方法修复成功")
    return True


if __name__ == "__main__":
    asyncio.run(test_consolidate_method())