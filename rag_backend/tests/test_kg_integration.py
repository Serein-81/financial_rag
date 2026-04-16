"""
测试知识图谱与语义记忆的集成
注意：此测试需要 Neo4j 服务，仅在本地环境手动运行
"""
import asyncio
import os
import sys
import pytest
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from app.memory_system.semantic_memory import SemanticMemory
from app.memory_system.base_memory import MemoryItem
from app.core.config import settings
from datetime import datetime


@pytest.mark.skipif(
    os.getenv("CI") == "true" or not settings.ENABLE_KNOWLEDGE_GRAPH,
    reason="需要 Neo4j 服务，仅在本地环境运行"
)
async def test_semantic_memory_with_kg():
    """测试语义记忆与知识图谱集成"""
    print("\n" + "="*60)
    print("测试语义记忆与知识图谱集成")
    print("="*60)
    
    # 创建语义记忆实例
    semantic_memory = SemanticMemory(user_id="test_user_kg", capacity=100)
    
    # 测试数据
    test_memories = [
        {
            "content": "王五是一名产品经理，在深圳的华为公司工作。",
            "role": "user",
            "importance": 0.9
        },
        {
            "content": "华为公司位于深圳，是一家全球领先的科技公司。",
            "role": "assistant",
            "importance": 0.8
        },
        {
            "content": "产品经理需要具备良好的沟通能力和市场洞察力。",
            "role": "system",
            "importance": 0.7
        }
    ]
    
    print("\n1. 添加记忆并构建知识图谱")
    for i, mem_data in enumerate(test_memories, 1):
        item = MemoryItem(
            content=mem_data["content"],
            role=mem_data["role"],
            importance=mem_data["importance"],
            timestamp=datetime.now(),
            metadata={"test_id": i}
        )
        
        print(f"\n添加记忆 {i}:")
        print(f"  内容: {item.content}")
        await semantic_memory.add(item)
    
    print("\n2. 测试检索（向量 + 图谱）")
    queries = [
        "产品经理",
        "华为",
        "深圳的公司"
    ]
    
    for query in queries:
        print(f"\n查询: {query}")
        results = await semantic_memory.retrieve(
            query=query,
            top_k=3,
            use_graph=True
        )
        
        print(f"  找到 {len(results)} 条结果:")
        for j, result in enumerate(results, 1):
            print(f"  {j}. {result.content[:50]}...")
            print(f"     重要性: {result.importance:.2f}")
            if "source" in result.metadata:
                print(f"     来源: {result.metadata['source']}")
    
    print("\n3. 测试纯向量检索（不使用图谱）")
    query = "产品经理"
    print(f"\n查询: {query} (仅向量)")
    results = await semantic_memory.retrieve(
        query=query,
        top_k=3,
        use_graph=False
    )
    
    print(f"  找到 {len(results)} 条结果:")
    for j, result in enumerate(results, 1):
        print(f"  {j}. {result.content[:50]}...")
    
    return True


async def test_graph_builder_integration():
    """测试图构建器集成"""
    print("\n" + "="*60)
    print("测试图构建器集成")
    print("="*60)
    
    from app.core.config import settings
    
    print(f"\n配置检查:")
    print(f"  ENABLE_KNOWLEDGE_GRAPH: {settings.ENABLE_KNOWLEDGE_GRAPH}")
    print(f"  ENABLE_ENTITY_EXTRACTION: {settings.ENABLE_ENTITY_EXTRACTION}")
    print(f"  ENABLE_RELATION_EXTRACTION: {settings.ENABLE_RELATION_EXTRACTION}")
    print(f"  NEO4J_URI: {settings.NEO4J_URI}")
    
    if not settings.ENABLE_KNOWLEDGE_GRAPH:
        print("\n⚠️ 知识图谱未启用，跳过测试")
        return False
    
    # 创建语义记忆
    semantic_memory = SemanticMemory(user_id="test_graph_builder", capacity=50)
    
    # 检查 graph_builder 是否初始化
    if semantic_memory.graph_builder:
        print("\n✅ GraphBuilder 已初始化")
        
        # 获取图统计
        stats = semantic_memory.graph_builder.get_stats()
        print(f"\n当前图统计:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        return True
    else:
        print("\n❌ GraphBuilder 未初始化")
        return False


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("知识图谱集成测试")
    print("="*60)
    
    results = {}
    
    # 测试 1: 图构建器集成
    try:
        results["graph_builder"] = await test_graph_builder_integration()
    except Exception as e:
        print(f"\n❌ 图构建器集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        results["graph_builder"] = False
    
    # 测试 2: 语义记忆与知识图谱集成
    try:
        results["semantic_memory_kg"] = await test_semantic_memory_with_kg()
    except Exception as e:
        print(f"\n❌ 语义记忆集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        results["semantic_memory_kg"] = False
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    for name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(results.values())
    if all_passed:
        print("\n🎉 所有集成测试通过！")
        print("\n✅ 知识图谱已成功集成到语义记忆系统")
        print("\n功能说明:")
        print("  1. 添加记忆时自动提取实体和关系")
        print("  2. 检索时支持向量 + 图谱混合检索")
        print("  3. 可通过 use_graph 参数控制是否使用图谱")
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
