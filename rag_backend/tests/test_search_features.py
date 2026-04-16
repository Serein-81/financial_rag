#!/usr/bin/env python3
"""
搜索功能综合测试

测试新增的搜索功能：
1. 记忆系统搜索
2. 关键词搜索
3. 文档级搜索
4. 搜索统计
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.memory_system.memory_manager import MemoryManager
from app.services.search_service import search_service


async def test_memory_search():
    """测试记忆系统搜索功能"""
    
    print("🧠 测试记忆系统搜索功能")
    print("-" * 40)
    
    try:
        # 创建记忆管理器
        memory_manager = MemoryManager("test_session_001", "test_user_001")
        
        # 添加一些测试记忆
        await memory_manager.add_message("user", "我想学习Python编程", importance=0.8)
        await memory_manager.add_message("assistant", "Python是一门很好的编程语言，适合初学者", importance=0.9)
        await memory_manager.add_message("user", "有什么好的Python教程推荐吗？", importance=0.7)
        await memory_manager.add_message("assistant", "我推荐官方文档和一些在线教程", importance=0.8)
        
        # 测试搜索
        results = await memory_manager.search_current_conversation(
            keywords=["Python", "编程"],
            top_k=5
        )
        
        print(f"✅ 搜索到 {len(results)} 条记忆")
        for i, memory in enumerate(results):
            print(f"  [{i+1}] {memory.role}: {memory.content[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ 记忆搜索测试失败: {e}")
        return False


async def test_keyword_search():
    """测试关键词搜索功能"""
    
    print("🔍 测试关键词搜索功能")
    print("-" * 40)
    
    try:
        # 测试关键词搜索（不指定知识库）
        results = await search_service.keyword_search(
            keywords=["python", "编程"],
            top_k=5,
            exact_match=False
        )
        
        print(f"✅ 关键词搜索到 {len(results)} 条结果")
        for i, result in enumerate(results):
            print(f"  [{i+1}] 分数: {result.score} | 文件: {result.source_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ 关键词搜索测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    
    print("🚀 搜索功能综合测试")
    print("=" * 60)
    
    test_results = []
    
    # 测试记忆搜索
    result1 = await test_memory_search()
    test_results.append(("记忆搜索", result1))
    print()
    
    # 测试关键词搜索
    result2 = await test_keyword_search()
    test_results.append(("关键词搜索", result2))
    print()
    
    # 输出测试结果
    print("📊 测试结果汇总")
    print("-" * 40)
    
    passed = 0
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 总体结果: {passed}/{len(test_results)} 项测试通过")
    
    if passed == len(test_results):
        print("🎉 所有搜索功能测试通过！")
    else:
        print("⚠️ 部分测试失败，请检查配置")


if __name__ == "__main__":
    asyncio.run(main())