"""
测试智能记忆巩固功能
方案一 + 方案二：关键词识别 + 频率统计
"""
import asyncio
from app.memory_system.memory_manager import MemoryManager


async def test_smart_consolidation():
    """测试智能巩固功能"""
    
    print("=" * 80)
    print("🧪 测试智能记忆巩固功能")
    print("=" * 80)
    
    # 初始化记忆管理器
    manager = MemoryManager(
        session_id="test_session_123",
        user_id="test_user_456"
    )
    
    print("\n" + "=" * 80)
    print("📝 测试场景 1：用户意图关键词检测")
    print("=" * 80)
    
    # 场景1：用户明确要求记住
    await manager.add_message(
        role="user",
        content="记住我对花生过敏，这个很重要！",
        importance=0.7  # 基础重要性
    )
    
    await manager.add_message(
        role="user",
        content="别忘了提醒我明天下午3点开会",
        importance=0.7
    )
    
    print("\n" + "=" * 80)
    print("📝 测试场景 2：重要话题关键词检测")
    print("=" * 80)
    
    # 场景2：健康话题
    await manager.add_message(
        role="user",
        content="我最近确诊了糖尿病，需要注意饮食",
        importance=0.7
    )
    
    # 场景3：财务话题
    await manager.add_message(
        role="user",
        content="我的银行卡密码是123456",
        importance=0.7
    )
    
    print("\n" + "=" * 80)
    print("📝 测试场景 3：高频话题检测")
    print("=" * 80)
    
    # 场景4：连续提到同一话题
    await manager.add_message(
        role="user",
        content="我的膝盖有点疼",
        importance=0.7
    )
    
    await manager.add_message(
        role="user",
        content="膝盖还是疼，走路都困难",
        importance=0.7
    )
    
    await manager.add_message(
        role="user",
        content="膝盖疼得越来越厉害了",
        importance=0.7
    )
    
    print("\n" + "=" * 80)
    print("📝 测试场景 4：普通对话（不触发巩固）")
    print("=" * 80)
    
    # 场景5：普通对话
    await manager.add_message(
        role="user",
        content="今天天气真好",
        importance=0.7
    )
    
    await manager.add_message(
        role="user",
        content="你好吗",
        importance=0.7
    )
    
    print("\n" + "=" * 80)
    print("📊 话题频率统计")
    print("=" * 80)
    
    # 获取统计信息
    stats = manager.get_topic_frequency_stats()
    print(f"\n总话题数: {stats['total_topics']}")
    print(f"高频话题: {', '.join(stats['high_frequency_topics'])}")
    print("\nTop 10 话题:")
    for topic_info in stats['top_topics']:
        print(f"  - {topic_info['keyword']}: {topic_info['frequency']}次")
    
    print("\n" + "=" * 80)
    print("📈 记忆系统统计")
    print("=" * 80)
    
    # 获取记忆统计
    memory_stats = await manager.get_memory_statistics()
    print(f"\n工作记忆: {memory_stats['working_memory']['size']} 条")
    print(f"情景记忆: {memory_stats['episodic_memory']['size']} 条")
    print(f"语义记忆: {memory_stats['semantic_memory']['size']} 条")
    print(f"总计: {memory_stats['total_memories']} 条")
    
    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)
    
    print("\n📝 预期结果:")
    print("1. '记住我对花生过敏' → 应该被巩固到语义记忆（用户意图）")
    print("2. '别忘了提醒我' → 应该被巩固到语义记忆（用户意图）")
    print("3. '确诊了糖尿病' → 应该被巩固到语义记忆（健康话题）")
    print("4. '银行卡密码' → 应该被巩固到语义记忆（财务话题）")
    print("5. '膝盖疼'（3次） → 应该被巩固到语义记忆（高频话题）")
    print("6. '今天天气真好' → 不应该被巩固（普通对话）")
    print("7. '你好吗' → 不应该被巩固（普通对话）")


if __name__ == "__main__":
    asyncio.run(test_smart_consolidation())
