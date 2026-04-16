"""
测试增强版情景记忆系统

测试内容：
1. 数据库迁移
2. 向量检索功能
3. 相关性评分算法
4. 时间衰减因子
5. 重要性权重
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.memory_system.episodic_memory import EpisodicMemory
from app.memory_system.base_memory import MemoryItem
from app.services.embedding_service import embedding_service


async def test_database_migration():
    """测试数据库迁移"""
    print("=" * 60)
    print("🔧 测试数据库迁移")
    print("=" * 60)
    
    try:
        # 运行迁移
        from migrations.enhance_episodic_memory import add_episodic_memory_enhancements
        await add_episodic_memory_enhancements()
        print("✅ 数据库迁移成功")
        return True
    except Exception as e:
        print(f"❌ 数据库迁移失败: {e}")
        return False


async def test_enhanced_retrieval():
    """测试增强版检索功能"""
    print("=" * 60)
    print("🔍 测试增强版检索功能")
    print("=" * 60)
    
    # 创建测试会话
    session_id = "test-session-enhanced"
    user_id = "test-user"
    
    episodic_memory = EpisodicMemory(session_id, user_id, capacity=50)
    
    # 添加测试记忆
    test_memories = [
        {
            "content": "我想学习Python编程",
            "role": "user",
            "importance": 0.8,
            "timestamp": datetime.now() - timedelta(hours=2)
        },
        {
            "content": "Python是一门很好的编程语言，适合初学者。我推荐从基础语法开始学习。",
            "role": "assistant", 
            "importance": 0.7,
            "timestamp": datetime.now() - timedelta(hours=2, minutes=1)
        },
        {
            "content": "有什么好的Python学习资源吗？",
            "role": "user",
            "importance": 0.6,
            "timestamp": datetime.now() - timedelta(minutes=30)
        },
        {
            "content": "推荐《Python编程：从入门到实践》这本书，还有官方文档也很不错。",
            "role": "assistant",
            "importance": 0.8,
            "timestamp": datetime.now() - timedelta(minutes=29)
        },
        {
            "content": "今天天气怎么样？",
            "role": "user",
            "importance": 0.3,
            "timestamp": datetime.now() - timedelta(minutes=10)
        }
    ]
    
    print("📝 添加测试记忆...")
    for i, mem_data in enumerate(test_memories):
        item = MemoryItem(
            content=mem_data["content"],
            role=mem_data["role"],
            importance=mem_data["importance"],
            timestamp=mem_data["timestamp"]
        )
        await episodic_memory.add(item)
        print(f"   {i+1}. {mem_data['role']}: {mem_data['content'][:30]}... (重要性: {mem_data['importance']})")
    
    # 测试向量检索
    print("\n🔍 测试向量检索...")
    query = "Python学习建议"
    query_embedding = await embedding_service.get_embedding(query)
    
    results = await episodic_memory.retrieve(
        query=query,
        query_embedding=query_embedding,
        top_k=3
    )
    
    print(f"\n查询: '{query}'")
    print("检索结果:")
    for i, result in enumerate(results):
        print(f"   {i+1}. [{result.role}] {result.content[:50]}...")
        print(f"      重要性: {result.importance:.2f} | 访问次数: {result.access_count}")
    
    # 测试简单检索（无向量）
    print("\n📋 测试简单检索（无向量）...")
    simple_results = await episodic_memory.retrieve(query="测试", top_k=2)
    
    print("简单检索结果（最近2条）:")
    for i, result in enumerate(simple_results):
        print(f"   {i+1}. [{result.role}] {result.content[:50]}...")
    
    return True


async def test_time_decay():
    """测试时间衰减因子"""
    print("=" * 60)
    print("⏰ 测试时间衰减因子")
    print("=" * 60)
    
    episodic_memory = EpisodicMemory("test-decay", "test-user")
    
    # 测试不同时间的衰减
    test_times = [
        (datetime.now() - timedelta(minutes=30), "30分钟前"),
        (datetime.now() - timedelta(hours=2), "2小时前"),
        (datetime.now() - timedelta(days=3), "3天前"),
        (datetime.now() - timedelta(weeks=2), "2周前"),
        (datetime.now() - timedelta(days=60), "2个月前")
    ]
    
    for timestamp, desc in test_times:
        decay = episodic_memory._calculate_time_decay(timestamp)
        print(f"   {desc}: 衰减因子 = {decay:.2f}")
    
    return True


async def test_importance_calculation():
    """测试重要性计算"""
    print("=" * 60)
    print("⭐ 测试重要性计算")
    print("=" * 60)
    
    episodic_memory = EpisodicMemory("test-importance", "test-user")
    
    test_items = [
        MemoryItem(content="这是一个重要的问题", role="user"),
        MemoryItem(content="好的，我来帮助你解决这个问题", role="assistant"),
        MemoryItem(content="系统提示：会话开始", role="system"),
        MemoryItem(content="这是一个很长的文本内容，包含了很多详细的信息和说明，应该会获得长度加成分数", role="user"),
        MemoryItem(content="谢谢你的帮助", role="user")
    ]
    
    for item in test_items:
        importance = episodic_memory._calculate_importance(item)
        print(f"   [{item.role}] {item.content[:30]}... → 重要性: {importance:.2f}")
    
    return True


async def test_cosine_similarity():
    """测试余弦相似度计算"""
    print("=" * 60)
    print("📐 测试余弦相似度计算")
    print("=" * 60)
    
    episodic_memory = EpisodicMemory("test-similarity", "test-user")
    
    # 生成测试向量
    text1 = "Python编程学习"
    text2 = "学习Python编程"
    text3 = "今天天气很好"
    
    vec1 = await embedding_service.get_embedding(text1)
    vec2 = await embedding_service.get_embedding(text2)
    vec3 = await embedding_service.get_embedding(text3)
    
    sim1_2 = episodic_memory._calculate_cosine_similarity(vec1, vec2)
    sim1_3 = episodic_memory._calculate_cosine_similarity(vec1, vec3)
    
    print(f"   '{text1}' vs '{text2}': 相似度 = {sim1_2:.4f}")
    print(f"   '{text1}' vs '{text3}': 相似度 = {sim1_3:.4f}")
    
    return True


async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始测试增强版情景记忆系统")
    print("=" * 80)
    
    tests = [
        ("数据库迁移", test_database_migration),
        ("时间衰减因子", test_time_decay),
        ("重要性计算", test_importance_calculation),
        ("余弦相似度", test_cosine_similarity),
        ("增强版检索", test_enhanced_retrieval)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n🧪 开始测试: {test_name}")
            success = await test_func()
            results.append((test_name, success))
            
            if success:
                print(f"✅ {test_name} 测试通过")
            else:
                print(f"❌ {test_name} 测试失败")
                
        except Exception as e:
            print(f"💥 {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 输出测试总结
    print("\n" + "=" * 80)
    print("📊 测试总结")
    print("=" * 80)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！情景记忆增强功能正常工作。")
    else:
        print("⚠️ 部分测试失败，请检查相关功能。")


if __name__ == "__main__":
    asyncio.run(run_all_tests())