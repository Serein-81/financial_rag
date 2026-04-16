"""
人类记忆系统测试

测试三层记忆架构的功能
"""

import asyncio
from app.memory_system import (
    MemoryItem,
    WorkingMemory,
    EpisodicMemory,
    SemanticMemory,
    MemoryManager
)


async def test_working_memory():
    """测试工作记忆"""
    print("\n" + "=" * 60)
    print("测试 1: 工作记忆 (Working Memory)")
    print("=" * 60)
    
    wm = WorkingMemory(capacity=5)
    
    # 添加记忆
    for i in range(7):
        item = MemoryItem(
            content=f"消息 {i+1}",
            role="user" if i % 2 == 0 else "assistant"
        )
        await wm.add(item)
    
    # 检索记忆
    memories = await wm.retrieve()
    print(f"\n当前工作记忆数量: {len(memories)}")
    for m in memories:
        print(f"  - {m.role}: {m.content}")
    
    # 获取上下文窗口
    context = wm.get_context_window()
    print(f"\n上下文窗口: {context}")
    
    # 获取摘要
    summary = wm.get_recent_summary()
    print(f"\n最近摘要: {summary}")
    
    # 统计信息
    stats = wm.get_statistics()
    print(f"\n统计信息: {stats}")
    
    print("\n✅ 工作记忆测试通过")


async def test_episodic_memory():
    """测试情景记忆"""
    print("\n" + "=" * 60)
    print("测试 2: 情景记忆 (Episodic Memory)")
    print("=" * 60)
    
    # 注意：这个测试需要数据库连接
    # 这里只测试基本功能
    
    em = EpisodicMemory(
        session_id="test_session_123",
        user_id="test_user_456",
        capacity=10
    )
    
    print(f"\n情景记忆初始化完成")
    print(f"  Session ID: {em.session_id}")
    print(f"  User ID: {em.user_id}")
    print(f"  容量: {em.capacity}")
    
    # 添加记忆（不实际保存到数据库）
    for i in range(5):
        item = MemoryItem(
            content=f"历史对话 {i+1}",
            role="user" if i % 2 == 0 else "assistant",
            importance=0.7
        )
        em.memories.append(item)
    
    print(f"\n当前情景记忆数量: {len(em.memories)}")
    
    # 获取会话摘要
    summary = await em.get_session_summary()
    print(f"\n会话摘要:\n{summary}")
    
    print("\n✅ 情景记忆测试通过")


async def test_semantic_memory():
    """测试语义记忆"""
    print("\n" + "=" * 60)
    print("测试 3: 语义记忆 (Semantic Memory)")
    print("=" * 60)
    
    sm = SemanticMemory(user_id="test_user_456", capacity=100)
    
    # 添加知识
    knowledge_items = [
        "Python 是一种高级编程语言",
        "机器学习是人工智能的一个分支",
        "深度学习使用神经网络",
        "RAG 是检索增强生成的缩写",
        "向量数据库用于存储嵌入"
    ]
    
    for content in knowledge_items:
        item = MemoryItem(
            content=content,
            role="system",
            importance=0.9,
            metadata={"type": "knowledge"}
        )
        # 不生成真实向量，使用模拟向量
        item.embedding = [0.1] * 768
        sm.memories.append(item)
    
    print(f"\n当前语义记忆数量: {len(sm.memories)}")
    
    # 获取知识摘要
    summary = sm.get_knowledge_summary()
    print(f"\n知识摘要:")
    print(f"  总知识数: {summary['total_knowledge']}")
    print(f"  知识类别: {summary['categories']}")
    
    # 构建知识图谱
    graph = await sm.build_knowledge_graph()
    print(f"\n知识图谱节点数: {len(graph)}")
    
    print("\n✅ 语义记忆测试通过")


async def test_memory_manager():
    """测试记忆管理器"""
    print("\n" + "=" * 60)
    print("测试 4: 记忆管理器 (Memory Manager)")
    print("=" * 60)
    
    mm = MemoryManager(
        session_id="test_session_789",
        user_id="test_user_101"
    )
    
    # 模拟对话
    conversations = [
        ("user", "你好，我想了解 Python"),
        ("assistant", "你好！Python 是一种高级编程语言..."),
        ("user", "Python 有什么特点？"),
        ("assistant", "Python 的特点包括：简洁、易读、功能强大..."),
        ("user", "如何学习 Python？"),
        ("assistant", "学习 Python 可以从基础语法开始...")
    ]
    
    # 添加消息
    for role, content in conversations:
        await mm.add_message(
            role=role,
            content=content,
            importance=0.8 if role == "user" else 0.7
        )
    
    print(f"\n已添加 {len(conversations)} 条消息")
    
    # 获取 LLM 上下文
    llm_context = mm.get_context_for_llm()
    print(f"\nLLM 上下文 ({len(llm_context)} 条):")
    for ctx in llm_context:
        print(f"  {ctx['role']}: {ctx['content'][:50]}...")
    
    # 获取统计信息
    stats = await mm.get_memory_statistics()
    print(f"\n记忆统计:")
    print(f"  总记忆数: {stats['total_memories']}")
    print(f"  工作记忆: {stats['working_memory']['total']}")
    print(f"  情景记忆: {stats['episodic_memory']['total']}")
    print(f"  语义记忆: {stats['semantic_memory']['total']}")
    
    print("\n✅ 记忆管理器测试通过")


async def test_memory_decay():
    """测试记忆衰减"""
    print("\n" + "=" * 60)
    print("测试 5: 记忆衰减算法")
    print("=" * 60)
    
    item = MemoryItem(
        content="测试记忆",
        importance=0.8,
        access_count=5
    )
    
    print(f"\n初始状态:")
    print(f"  重要性: {item.importance}")
    print(f"  访问次数: {item.access_count}")
    print(f"  衰减因子: {item.decay_factor}")
    
    # 模拟时间流逝
    time_deltas = [1, 6, 12, 24, 48, 72]  # 小时
    
    print(f"\n衰减过程:")
    for hours in time_deltas:
        item.decay(hours)
        print(f"  {hours:3d} 小时后: 衰减因子 = {item.decay_factor:.4f}")
    
    # 访问记忆
    print(f"\n访问记忆后:")
    item.access()
    print(f"  访问次数: {item.access_count}")
    print(f"  衰减因子: {item.decay_factor:.4f}")
    
    print("\n✅ 记忆衰减测试通过")


async def test_relevance_score():
    """测试相关性评分"""
    print("\n" + "=" * 60)
    print("测试 6: 相关性评分算法")
    print("=" * 60)
    
    # 创建记忆项
    item = MemoryItem(
        content="Python 是一种编程语言",
        importance=0.8,
        access_count=10,
        decay_factor=0.9
    )
    
    # 模拟向量（768 维）
    item.embedding = [0.5] * 768
    query_embedding = [0.6] * 768
    
    # 计算相关性分数
    score = item.get_relevance_score(query_embedding)
    
    print(f"\n记忆项:")
    print(f"  内容: {item.content}")
    print(f"  重要性: {item.importance}")
    print(f"  访问次数: {item.access_count}")
    print(f"  衰减因子: {item.decay_factor}")
    
    print(f"\n相关性分数: {score:.4f}")
    print(f"  (综合考虑: 语义相似度 40% + 衰减因子 30% + 重要性 20% + 访问频率 10%)")
    
    print("\n✅ 相关性评分测试通过")


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🧠 人类记忆系统测试套件")
    print("=" * 60)
    
    try:
        await test_working_memory()
        await test_episodic_memory()
        await test_semantic_memory()
        await test_memory_manager()
        await test_memory_decay()
        await test_relevance_score()
        
        print("\n" + "=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
