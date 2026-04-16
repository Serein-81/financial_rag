#!/usr/bin/env python3
"""
简单测试情景记忆 consolidate 方法是否存在
"""

import inspect
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 直接导入类，避免数据库依赖
from app.memory_system.episodic_memory import EpisodicMemory
from app.memory_system.base_memory import BaseMemory


def test_consolidate_method_exists():
    """测试 consolidate 方法是否存在"""
    
    print("🧪 测试情景记忆 consolidate 方法是否存在")
    print("=" * 50)
    
    # 1. 检查 BaseMemory 是否有 consolidate 方法
    print("1. 检查 BaseMemory 类...")
    base_methods = [method for method in dir(BaseMemory) if not method.startswith('_')]
    print(f"   BaseMemory 方法: {base_methods}")
    
    if 'consolidate' in base_methods:
        print("✅ BaseMemory 有 consolidate 方法")
    else:
        print("❌ BaseMemory 没有 consolidate 方法")
    
    # 2. 检查 EpisodicMemory 是否有 consolidate 方法
    print("\n2. 检查 EpisodicMemory 类...")
    episodic_methods = [method for method in dir(EpisodicMemory) if not method.startswith('_')]
    print(f"   EpisodicMemory 方法: {episodic_methods}")
    
    if 'consolidate' in episodic_methods:
        print("✅ EpisodicMemory 有 consolidate 方法")
    else:
        print("❌ EpisodicMemory 没有 consolidate 方法")
    
    # 3. 检查方法签名
    print("\n3. 检查方法签名...")
    
    if hasattr(EpisodicMemory, 'consolidate'):
        method = getattr(EpisodicMemory, 'consolidate')
        signature = inspect.signature(method)
        print(f"   EpisodicMemory.consolidate 签名: {signature}")
        
        # 检查是否是异步方法
        if inspect.iscoroutinefunction(method):
            print("✅ consolidate 是异步方法")
        else:
            print("❌ consolidate 不是异步方法")
    
    # 4. 检查方法来源
    print("\n4. 检查方法来源...")
    
    # 检查 EpisodicMemory 是否重写了 consolidate 方法
    if 'consolidate' in EpisodicMemory.__dict__:
        print("✅ EpisodicMemory 重写了 consolidate 方法")
    else:
        print("ℹ️  EpisodicMemory 使用继承的 consolidate 方法")
    
    print("=" * 50)
    print("🎉 方法检查完成！")


if __name__ == "__main__":
    test_consolidate_method_exists()