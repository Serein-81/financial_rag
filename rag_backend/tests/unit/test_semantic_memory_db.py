#!/usr/bin/env python3
"""
语义记忆数据库功能测试

测试语义记忆的数据库持久化功能
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.memory_system.semantic_memory import SemanticMemory
from app.memory_system.base_memory import MemoryItem


async def test_semantic_memory_persistence():
    """测试语义记忆持久化功能"""
    print("🧪 测试语义记忆数据库持久化功能")
    print("=" * 60)
    
    # 模拟用户ID
    user_id = "test-user-123"
    
    # 创建语义记忆实例
    semantic_memory = SemanticMemory(user_id=user_id, capacity=10)
    
    # 测试数据
    test_knowledge = [
        {
            "content": "Python是一种高级编程语言，具有简洁的语法",
            "role": "system",
            "importance": 0.9,
            "metadata": {
                "memory_type": "knowledge",
                "tags": ["Python", "编程语言"],
                "source": "用户学习"
            }
        },
        {
            "content": "机器学习是人工智能的一个分支",
            "role": "system", 
            "importance": 0.8,
            "metadata": {
                "memory_type": "knowledge",
                "tags": ["机器学习", "人工智能"],
                "source": "技术讨论"
            }
        },
        {
            "content": "用户喜欢使用VSCode作为代码编辑器",
            "role": "user",
            "importance": 0.7,
            "metadata": {
                "memory_type": "preference",
                "tags": ["VSCode", "编辑器", "偏好"],
                "source": "用户行为"
            }
        }
    ]
    
    print("1. 添加测试知识到语义记忆...")
    for i, knowledge in enumerate(test_knowledge, 1):
        item = MemoryItem(
            content=knowledge["content"],
            role=knowledge["role"],
            importance=knowledge["importance"],
            metadata=knowledge["metadata"]
        )
        
        await semantic_memory.add(item)
        print(f"   ✅ 添加知识 {i}: {knowledge['content'][:30]}...")
    
    print(f"\n2. 当前内存中的记忆数量: {len(semantic_memory.memories)}")
    
    print("\n3. 测试知识检索...")
    # 测试检索
    results = await semantic_memory.retrieve("Python编程", top_k=3)
    print(f"   检索到 {len(results)} 条相关知识:")
    for i, result in enumerate(results, 1):
        print(f"   {i}. {result.content[:50]}... (重要性: {result.importance})")
    
    print("\n4. 创建新的语义记忆实例（测试持久化）...")
    # 创建新实例，测试是否能从数据库加载
    new_semantic_memory = SemanticMemory(user_id=user_id, capacity=10)
    await new_semantic_memory.load_from_db()
    
    print(f"   从数据库加载的记忆数量: {len(new_semantic_memory.memories)}")
    
    print("\n5. 测试相似知识合并...")
    # 添加相似知识，测试合并功能
    similar_item = MemoryItem(
        content="Python是一门简单易学的编程语言",  # 与第一条相似
        role="system",
        importance=0.8,
        metadata={"memory_type": "knowledge", "tags": ["Python"]}
    )
    
    original_count = len(new_semantic_memory.memories)
    await new_semantic_memory.add(similar_item)
    new_count = len(new_semantic_memory.memories)
    
    if new_count == original_count:
        print("   ✅ 相似知识成功合并，没有创建重复记录")
    else:
        print("   ⚠️ 相似知识未合并，创建了新记录")
    
    print("\n6. 测试知识更新...")
    if new_semantic_memory.memories:
        first_memory = new_semantic_memory.memories[0]
        original_importance = first_memory.importance
        
        success = await new_semantic_memory.update(
            first_memory.id,
            {"importance": 0.95, "tags": ["Python", "编程", "高级语言"]}
        )
        
        if success:
            print(f"   ✅ 知识更新成功 (重要性: {original_importance} → {first_memory.importance})")
        else:
            print("   ❌ 知识更新失败")
    
    print("\n7. 测试记忆统计...")
    stats = new_semantic_memory.get_statistics()
    print(f"   总记忆数: {stats['total']}")
    print(f"   平均重要性: {stats['avg_importance']:.2f}")
    print(f"   平均访问次数: {stats['avg_access_count']:.1f}")
    
    print("\n8. 测试知识摘要...")
    summary = new_semantic_memory.get_knowledge_summary()
    print(f"   知识类别: {summary['categories']}")
    print(f"   热门话题数: {len(summary['top_topics'])}")
    
    print("\n✅ 语义记忆数据库测试完成！")
    print("=" * 60)


async def test_user_isolation():
    """测试用户数据隔离"""
    print("\n🔒 测试用户数据隔离")
    print("=" * 60)
    
    # 创建两个不同用户的语义记忆
    user_a_memory = SemanticMemory(user_id="user-a", capacity=10)
    user_b_memory = SemanticMemory(user_id="user-b", capacity=10)
    
    # 为用户A添加知识
    item_a = MemoryItem(
        content="用户A喜欢Java编程",
        role="user",
        importance=0.8,
        metadata={"memory_type": "preference"}
    )
    await user_a_memory.add(item_a)
    
    # 为用户B添加知识
    item_b = MemoryItem(
        content="用户B喜欢Python编程",
        role="user", 
        importance=0.8,
        metadata={"memory_type": "preference"}
    )
    await user_b_memory.add(item_b)
    
    # 检查用户A是否能访问用户B的数据
    user_a_results = await user_a_memory.retrieve("编程", top_k=5)
    user_b_results = await user_b_memory.retrieve("编程", top_k=5)
    
    print(f"用户A的记忆数量: {len(user_a_results)}")
    print(f"用户B的记忆数量: {len(user_b_results)}")
    
    # 验证数据隔离
    user_a_contents = [r.content for r in user_a_results]
    user_b_contents = [r.content for r in user_b_results]
    
    if "用户B喜欢Python编程" not in user_a_contents:
        print("✅ 用户A无法访问用户B的数据 - 数据隔离正常")
    else:
        print("❌ 数据隔离失败！用户A可以访问用户B的数据")
    
    if "用户A喜欢Java编程" not in user_b_contents:
        print("✅ 用户B无法访问用户A的数据 - 数据隔离正常")
    else:
        print("❌ 数据隔离失败！用户B可以访问用户A的数据")


async def cleanup_test_data():
    """清理测试数据"""
    print("\n🧹 清理测试数据...")
    
    from app.db import AsyncSessionLocal
    from app.models.semantic_memory import SemanticMemory as SemanticMemoryModel
    from sqlalchemy import delete
    
    async with AsyncSessionLocal() as db:
        # 删除测试用户的数据
        await db.execute(
            delete(SemanticMemoryModel)
            .where(SemanticMemoryModel.user_id.in_(["test-user-123", "user-a", "user-b"]))
        )
        await db.commit()
    
    print("✅ 测试数据清理完成")


async def main():
    """主测试函数"""
    try:
        await test_semantic_memory_persistence()
        await test_user_isolation()
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await cleanup_test_data()


if __name__ == "__main__":
    asyncio.run(main())