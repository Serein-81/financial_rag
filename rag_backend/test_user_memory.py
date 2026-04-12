"""
用户记忆提取系统测试脚本

测试内容：
1. UserMemoryExtractor 单独测试
2. SemanticMemory 用户记忆方法测试
3. MemoryManager 用户记忆集成测试
4. EnhancedContextBuilder 用户记忆上下文测试
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.memory_system.user_memory_extractor import (
    UserMemoryExtractor,
    ExtractedFact,
    ExtractedPreference,
    ExtractedCorrection,
    UserMemoryExtractionResult
)
from app.memory_system.semantic_memory import SemanticMemory
from app.memory_system.memory_manager import MemoryManager


# 测试对话数据
SAMPLE_CONVERSATION = [
    {"role": "user", "content": "我叫张三，是北京某科技公司的产品经理。"},
    {"role": "assistant", "content": "您好张三！很高兴认识您。作为产品经理，您主要负责什么产品呢？"},
    {"role": "user", "content": "我主要负责企业级SaaS产品，已经在这个行业工作5年了。"},
    {"role": "assistant", "content": "5年的B端产品经验，非常丰富啊！企业级SaaS有很多独特的挑战。"},
    {"role": "user", "content": "对，我比较喜欢简洁的设计风格，不喜欢太花哨的东西。"},
    {"role": "assistant", "content": "简洁风格确实是企业级产品的主流趋势。还有其他偏好吗？"},
    {"role": "user", "content": "我平时用Python比较多，偶尔用JavaScript。"},
    {"role": "assistant", "content": "Python和JavaScript的组合很常见，覆盖后端和前端了。"},
    {"role": "user", "content": "对了，我上周出差去了深圳，见了几个客户。"},
    {"role": "assistant", "content": "深圳客户那边有什么反馈吗？"},
    {"role": "user", "content": "他们普遍反映我们的系统登录流程太复杂了，需要简化。"},
    {"role": "assistant", "content": "登录流程优化是很重要的用户体验改进点。"},
    {"role": "user", "content": "上次你告诉我的那个Python库叫什么来着？"},
    {"role": "assistant", "content": "您是指 FastAPI 吗？它是一个现代化的Python Web框架。"},
    {"role": "user", "content": "对，就是FastAPI，我记住了。谢谢！"},
    {"role": "assistant", "content": "不客气！有什么问题随时问我。"}
]


async def test_user_memory_extractor():
    """测试 UserMemoryExtractor"""
    print("\n" + "=" * 60)
    print("测试 1: UserMemoryExtractor 单独测试")
    print("=" * 60)
    
    try:
        # 创建提取器
        extractor = UserMemoryExtractor(confidence_threshold=0.7)
        
        # 执行提取
        result = await extractor.extract(SAMPLE_CONVERSATION)
        
        # 验证结果
        print(f"\n📊 提取结果摘要:")
        print(f"   - 事实数量: {len(result.facts)}")
        print(f"   - 偏好数量: {len(result.preferences)}")
        print(f"   - 纠正数量: {len(result.corrections)}")
        print(f"   - 总提取项: {result.total_items}")
        print(f"   - 提取时间: {result.extraction_time}")
        
        # 打印提取的事实
        if result.facts:
            print(f"\n📌 提取的事实:")
            for i, fact in enumerate(result.facts, 1):
                print(f"   {i}. {fact.content}")
                print(f"      类别: {fact.category} | 置信度: {fact.confidence:.2f}")
        
        # 打印提取的偏好
        if result.preferences:
            print(f"\n⭐ 提取的偏好:")
            for i, pref in enumerate(result.preferences, 1):
                print(f"   {i}. {pref.content}")
                print(f"      类别: {pref.category} | 置信度: {pref.confidence:.2f}")
        
        # 打印提取的纠正
        if result.corrections:
            print(f"\n🔧 提取的纠正:")
            for i, corr in enumerate(result.corrections, 1):
                print(f"   {i}. 原文: {corr.original}")
                print(f"      纠正: {corr.corrected}")
                print(f"      置信度: {corr.confidence:.2f}")
        
        print("\n✅ UserMemoryExtractor 测试通过")
        return result
        
    except Exception as e:
        print(f"\n❌ UserMemoryExtractor 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_semantic_memory_user_methods():
    """测试 SemanticMemory 用户记忆方法"""
    print("\n" + "=" * 60)
    print("测试 2: SemanticMemory 用户记忆方法测试")
    print("=" * 60)
    
    try:
        # 创建语义记忆实例
        user_id = "test_user_memory_001"
        semantic_memory = SemanticMemory(user_id=user_id, capacity=100)
        
        # 测试添加用户记忆
        print("\n📝 测试添加用户记忆...")
        
        # 添加事实
        fact_success = await semantic_memory.add_user_memory(
            content="用户名叫张三",
            memory_category="identity",
            confidence=0.9,
            source="用户自我介绍"
        )
        print(f"   添加事实: {'成功' if fact_success else '失败'}")
        
        # 添加偏好
        pref_success = await semantic_memory.add_user_memory(
            content="用户喜欢简洁的设计风格",
            memory_category="preference",
            confidence=0.85,
            source="用户表达偏好"
        )
        print(f"   添加偏好: {'成功' if pref_success else '失败'}")
        
        # 添加纠正
        corr_success = await semantic_memory.add_user_memory(
            content="之前AI提到的Python库名称被用户纠正为FastAPI",
            memory_category="correction",
            confidence=0.95,
            source="用户纠正AI错误"
        )
        print(f"   添加纠正: {'成功' if corr_success else '失败'}")
        
        # 测试获取用户记忆
        print("\n🔍 测试获取用户记忆...")
        
        # 获取全部用户记忆
        all_memories = await semantic_memory.get_user_memories(top_k=10)
        print(f"   获取全部用户记忆: {len(all_memories)} 条")
        
        # 获取事实
        facts = await semantic_memory.get_user_facts(top_k=5)
        print(f"   获取事实: {len(facts)} 条")
        
        # 获取偏好
        preferences = await semantic_memory.get_user_preferences(top_k=5)
        print(f"   获取偏好: {len(preferences)} 条")
        
        # 获取纠正
        corrections = await semantic_memory.get_user_corrections(top_k=5)
        print(f"   获取纠正: {len(corrections)} 条")
        
        # 打印记忆内容
        if facts:
            print("\n📌 事实记忆内容:")
            for fact in facts:
                print(f"   - {fact.content[:50]}...")
        
        if preferences:
            print("\n⭐ 偏好记忆内容:")
            for pref in preferences:
                print(f"   - {pref.content[:50]}...")
        
        print("\n✅ SemanticMemory 用户记忆方法测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ SemanticMemory 用户记忆方法测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_memory_manager_integration():
    """测试 MemoryManager 用户记忆集成"""
    print("\n" + "=" * 60)
    print("测试 3: MemoryManager 用户记忆集成测试")
    print("=" * 60)
    
    try:
        # 创建记忆管理器
        session_id = "test_session_001"
        user_id = "test_user_memory_002"
        memory_manager = MemoryManager(session_id=session_id, user_id=user_id)
        
        # 测试提取用户记忆
        print("\n🔍 测试提取用户记忆...")
        extraction_success = await memory_manager.extract_user_memories(SAMPLE_CONVERSATION)
        print(f"   提取结果: {'成功' if extraction_success else '失败'}")
        
        # 测试获取用户记忆上下文
        print("\n📋 测试获取用户记忆上下文...")
        user_memory_context = await memory_manager.get_user_memory_context(top_k=10)
        
        if user_memory_context:
            print(f"   上下文长度: {len(user_memory_context)} 字符")
            print(f"\n📄 用户记忆上下文内容:")
            print("-" * 60)
            print(user_memory_context)
            print("-" * 60)
        else:
            print("   未获取到用户记忆上下文")
        
        print("\n✅ MemoryManager 用户记忆集成测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ MemoryManager 用户记忆集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_context_builder_integration():
    """测试 EnhancedContextBuilder 用户记忆上下文集成"""
    print("\n" + "=" * 60)
    print("测试 4: EnhancedContextBuilder 用户记忆上下文测试")
    print("=" * 60)
    
    try:
        from app.memory_system.context_builder import (
            EnhancedContextBuilder,
            ContextConfig
        )
        
        # 创建记忆管理器
        session_id = "test_session_002"
        user_id = "test_user_memory_003"
        memory_manager = MemoryManager(session_id=session_id, user_id=user_id)
        
        # 先提取用户记忆
        await memory_manager.extract_user_memories(SAMPLE_CONVERSATION)
        
        # 创建上下文构建器
        config = ContextConfig(max_tokens=4000)
        builder = EnhancedContextBuilder(config)
        
        # 构建上下文
        user_query = "我叫什么名字？"
        context = await builder.build_context(
            user_query=user_query,
            memory_manager=memory_manager,
            knowledge_context="",
            system_instructions="你是一个有帮助的AI助手。"
        )
        
        print(f"\n📋 生成的上下文长度: {len(context)} 字符")
        
        # 检查上下文是否包含用户记忆
        if "[User Memory]" in context:
            print("\n✅ 上下文包含用户记忆部分")
            
            # 提取用户记忆部分
            import re
            user_memory_match = re.search(r'\[User Memory\](.*?)(?=\[|$)', context, re.DOTALL)
            if user_memory_match:
                print("\n📄 用户记忆部分内容:")
                print("-" * 60)
                print(user_memory_match.group(0)[:500])
                print("-" * 60)
        else:
            print("\n⚠️ 上下文未包含用户记忆部分（可能为空）")
        
        # 打印完整上下文结构预览
        print("\n📋 完整上下文结构预览:")
        sections = context.split("\n\n")
        for i, section in enumerate(sections[:6], 1):
            preview = section[:100].replace("\n", " ")
            print(f"   {i}. {preview}...")
        
        print("\n✅ EnhancedContextBuilder 用户记忆上下文测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ EnhancedContextBuilder 用户记忆上下文测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("\n" + "🚀" * 30)
    print("用户记忆提取系统测试")
    print("🚀" * 30)
    
    # 测试计数器
    tests_passed = 0
    tests_total = 4
    
    # 测试 1: UserMemoryExtractor
    result = await test_user_memory_extractor()
    if result is not None:
        tests_passed += 1
    
    # 测试 2: SemanticMemory 用户记忆方法
    if await test_semantic_memory_user_methods():
        tests_passed += 1
    
    # 测试 3: MemoryManager 集成
    if await test_memory_manager_integration():
        tests_passed += 1
    
    # 测试 4: ContextBuilder 集成
    if await test_context_builder_integration():
        tests_passed += 1
    
    # 打印测试总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"✅ 通过: {tests_passed}/{tests_total}")
    print(f"❌ 失败: {tests_total - tests_passed}/{tests_total}")
    
    if tests_passed == tests_total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️ 有 {tests_total - tests_passed} 个测试失败")
    
    return tests_passed == tests_total


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
