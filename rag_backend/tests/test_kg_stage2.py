"""
测试知识图谱阶段 2：核心组件
注意：此测试需要 Neo4j 服务，仅在本地环境手动运行
"""
import asyncio
import os
import sys
import pytest
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.graph_builder import GraphBuilder
from app.services.hybrid_retriever import HybridRetriever
from app.knowledge_graph.entity_extractor import EntityExtractor
from app.knowledge_graph.relation_extractor import RelationExtractor
from app.knowledge_graph.neo4j_manager import Neo4jManager
from app.agent_framework.llm.factory import LLMAdapterFactory
from app.core.config import settings


@pytest.mark.skipif(
    os.getenv("CI") == "true" or not settings.ENABLE_KNOWLEDGE_GRAPH,
    reason="需要 Neo4j 服务，仅在本地环境运行"
)
async def test_graph_builder():
    """测试图构建器"""
    print("\n" + "="*60)
    print("测试图构建器 (GraphBuilder)")
    print("="*60)
    
    # 初始化组件
    entity_extractor = EntityExtractor()
    relation_extractor = RelationExtractor()
    neo4j_manager = Neo4jManager()
    
    graph_builder = GraphBuilder(
        entity_extractor,
        relation_extractor,
        neo4j_manager
    )
    
    # 测试文本
    test_text = "李四是一名数据科学家，在上海的腾讯公司工作。他擅长机器学习和深度学习。"
    
    print(f"\n测试文本: {test_text}")
    print("\n开始构建图谱...")
    
    # 构建图谱
    result = await graph_builder.build_from_text(
        text=test_text,
        user_id=1,
        session_id="test_session_001"
    )
    
    if result.success:
        print(f"\n✅ {result.message}")
        print(f"\n创建的实体 ({len(result.entities)}):")
        for entity in result.entities:
            print(f"  - {entity.name} ({entity.type})")
        
        print(f"\n创建的关系 ({len(result.relations)}):")
        for relation in result.relations:
            print(f"  - {relation.source} -[{relation.type}]-> {relation.target}")
    else:
        print(f"\n❌ {result.message}")
    
    # 获取图统计
    print("\n图统计信息:")
    stats = graph_builder.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    return result.success


async def test_hybrid_retriever():
    """测试混合检索器"""
    print("\n" + "="*60)
    print("测试混合检索器 (HybridRetriever)")
    print("="*60)
    
    # 初始化
    neo4j_manager = Neo4jManager()
    retriever = HybridRetriever(neo4j_manager)
    
    # 测试实体检索
    print("\n1. 测试实体检索")
    entity_name = "李四"
    print(f"查询实体: {entity_name}")
    
    related = await retriever.retrieve_by_entity(
        entity_name=entity_name,
        max_depth=2,
        limit=10
    )
    
    print(f"\n找到 {len(related)} 个相关实体:")
    for entity in related:
        print(f"  - {entity['name']} ({entity['type']}) 距离: {entity.get('distance', 0)}")
    
    return len(related) > 0


async def test_schemas():
    """测试 Pydantic 模型"""
    print("\n" + "="*60)
    print("测试 Pydantic 模型")
    print("="*60)
    
    from app.schemas.knowledge_graph import (
        EntityCreate, RelationCreate, GraphBuildRequest,
        HybridSearchRequest, EntityQueryRequest
    )
    
    # 测试实体模型
    print("\n1. 测试实体模型")
    entity = EntityCreate(
        name="测试实体",
        type="PERSON",
        properties={"age": 30}
    )
    print(f"  ✅ EntityCreate: {entity.name} ({entity.type})")
    
    # 测试关系模型
    print("\n2. 测试关系模型")
    relation = RelationCreate(
        source="实体A",
        target="实体B",
        type="关联",
        properties={"weight": 0.8}
    )
    print(f"  ✅ RelationCreate: {relation.source} -[{relation.type}]-> {relation.target}")
    
    # 测试图构建请求
    print("\n3. 测试图构建请求")
    build_req = GraphBuildRequest(
        text="测试文本",
        user_id=1,
        extract_entities=True,
        extract_relations=True
    )
    print(f"  ✅ GraphBuildRequest: user_id={build_req.user_id}")
    
    # 测试混合检索请求
    print("\n4. 测试混合检索请求")
    search_req = HybridSearchRequest(
        query="测试查询",
        top_k=5,
        vector_weight=0.7,
        graph_weight=0.3
    )
    print(f"  ✅ HybridSearchRequest: top_k={search_req.top_k}")
    
    # 测试实体查询请求
    print("\n5. 测试实体查询请求")
    query_req = EntityQueryRequest(
        entity_name="测试实体",
        max_depth=2,
        limit=10
    )
    print(f"  ✅ EntityQueryRequest: entity={query_req.entity_name}")
    
    return True


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("知识图谱阶段 2 测试")
    print("="*60)
    
    results = {}
    
    # 测试 1: Pydantic 模型
    try:
        results["schemas"] = await test_schemas()
    except Exception as e:
        print(f"\n❌ Schemas 测试失败: {e}")
        results["schemas"] = False
    
    # 测试 2: 图构建器
    try:
        results["graph_builder"] = await test_graph_builder()
    except Exception as e:
        print(f"\n❌ GraphBuilder 测试失败: {e}")
        import traceback
        traceback.print_exc()
        results["graph_builder"] = False
    
    # 测试 3: 混合检索器
    try:
        results["hybrid_retriever"] = await test_hybrid_retriever()
    except Exception as e:
        print(f"\n❌ HybridRetriever 测试失败: {e}")
        import traceback
        traceback.print_exc()
        results["hybrid_retriever"] = False
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    for name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(results.values())
    if all_passed:
        print("\n🎉 所有测试通过！阶段 2 核心组件创建成功！")
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
