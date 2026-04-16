#!/usr/bin/env python3
"""
测试增强版上下文构建器

验证Token管理和统一上下文结构的改进效果
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.memory_system.context_builder import EnhancedContextBuilder, ContextConfig, ContextPacket
from app.memory_system.memory_manager import MemoryManager
from datetime import datetime


async def test_context_builder():
    """测试上下文构建器的各项功能"""
    
    print("🧪 开始测试增强版上下文构建器")
    print("=" * 60)
    
    # 1. 初始化配置和构建器
    config = ContextConfig(
        max_tokens=1000,
        relevance_weight=0.7,
        recency_weight=0.3,
        min_relevance=0.3
    )
    
    builder = EnhancedContextBuilder(config)
    
    # 2. 创建模拟记忆管理器
    memory_manager = MemoryManager("test_session", "test_user")
    
    # 添加一些测试记忆
    await memory_manager.add_message("user", "我想了解财务报表分析", importance=0.8)
    await memory_manager.add_message("assistant", "财务报表分析包括资产负债表、利润表和现金流量表的分析", importance=0.7)
    await memory_manager.add_message("user", "现金流量表怎么看？", importance=0.6)
    
    # 3. 测试上下文构建
    user_query = "请帮我分析一下现金流量表的关键指标"
    knowledge_context = "现金流量表反映企业现金流入和流出情况，包括经营活动、投资活动和筹资活动三部分。"
    system_instructions = "你是一个专业的财务分析师，请提供准确的财务建议。"
    
    print(f"📝 用户查询: {user_query}")
    print(f"📚 知识库上下文: {knowledge_context[:50]}...")
    print(f"⚙️ 系统指令: {system_instructions[:50]}...")
    print()
    
    # 4. 构建上下文
    context = await builder.build_context(
        user_query=user_query,
        memory_manager=memory_manager,
        knowledge_context=knowledge_context,
        system_instructions=system_instructions,
        max_tokens=1000
    )
    
    print("📋 生成的结构化上下文:")
    print("-" * 60)
    print(context)
    print("-" * 60)
    
    # 5. 验证Token管理
    token_count = builder._count_tokens(context)
    print(f"📊 Token统计: {token_count}/1000")
    
    if token_count <= 1000:
        print("✅ Token管理测试通过")
    else:
        print("❌ Token管理测试失败")
    
    # 6. 测试压缩功能
    print("\n🗜️ 测试压缩功能...")
    
    # 创建一个超长上下文
    long_context = context + "\n\n" + "这是额外的长文本内容。" * 200
    long_tokens = builder._count_tokens(long_context)
    print(f"压缩前Token数: {long_tokens}")
    
    compressed = builder._compress(long_context, 800)
    compressed_tokens = builder._count_tokens(compressed)
    print(f"压缩后Token数: {compressed_tokens}")
    
    if compressed_tokens <= 800:
        print("✅ 压缩功能测试通过")
    else:
        print("❌ 压缩功能测试失败")
    
    print("\n" + "=" * 60)
    print("🎉 测试完成！")


async def test_relevance_calculation():
    """测试相关性计算功能"""
    
    print("\n🔍 测试相关性计算功能")
    print("-" * 40)
    
    builder = EnhancedContextBuilder()
    
    # 测试用例
    test_cases = [
        {
            "content": "现金流量表分析是财务分析的重要组成部分",
            "query": "现金流量表怎么分析",
            "expected": "高相关性"
        },
        {
            "content": "今天天气很好，适合出门散步",
            "query": "现金流量表怎么分析", 
            "expected": "低相关性"
        },
        {
            "content": "企业财务报表包括资产负债表、利润表和现金流量表",
            "query": "财务报表有哪些",
            "expected": "高相关性"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        relevance = await builder._calculate_relevance(case["content"], case["query"])
        print(f"测试 {i}: {case['expected']}")
        print(f"  内容: {case['content'][:30]}...")
        print(f"  查询: {case['query']}")
        print(f"  相关性: {relevance:.3f}")
        print()


async def main():
    """主测试函数"""
    try:
        await test_context_builder()
        await test_relevance_calculation()
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())