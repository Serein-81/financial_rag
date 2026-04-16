"""
测试知识图谱与语义记忆的集成（简化版，无数据库依赖）
注意：此测试需要 Neo4j 服务，仅在本地环境手动运行
"""
import asyncio
import os
import sys
import pytest
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))


@pytest.mark.skipif(
    os.getenv("CI") == "true",
    reason="需要 Neo4j 服务，仅在本地环境运行"
)
async def test_graph_builder_initialization():
    """测试图构建器初始化"""
    print("\n" + "="*60)
    print("测试图构建器初始化")
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
    
    try:
        from app.services.graph_builder import GraphBuilder
        from app.knowledge_graph.entity_extractor import EntityExtractor
        from app.knowledge_graph.relation_extractor import RelationExtractor
        from app.knowledge_graph.neo4j_manager import Neo4jManager
        
        print("\n✅ 成功导入所有模块")
        
        # 测试初始化
        entity_extractor = EntityExtractor()
        relation_extractor = RelationExtractor()
        neo4j_manager = Neo4jManager()
        
        print("✅ 成功创建所有组件")
        
        graph_builder = GraphBuilder(
            entity_extractor,
            relation_extractor,
            neo4j_manager
        )
        
        print("✅ 成功创建 GraphBuilder")
        
        # 获取图统计
        stats = graph_builder.get_stats()
        print(f"\n当前图统计:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_semantic_memory_initialization():
    """测试语义记忆初始化（不访问数据库）"""
    print("\n" + "="*60)
    print("测试语义记忆初始化")
    print("="*60)
    
    try:
        # 临时修改语义记忆类，跳过数据库加载
        from app.memory_system.semantic_memory import SemanticMemory
        
        # 创建实例
        semantic_memory = SemanticMemory(user_id="test_user", capacity=100)
        
        print(f"\n✅ 成功创建语义记忆实例")
        print(f"  用户ID: {semantic_memory.user_id}")
        print(f"  容量: {semantic_memory.capacity}")
        
        # 检查图构建器
        if semantic_memory.graph_builder:
            print("✅ GraphBuilder 已初始化")
            return True
        else:
            print("❌ GraphBuilder 未初始化")
            return False
            
    except Exception as e:
        print(f"\n❌ 语义记忆初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_entity_extraction():
    """测试实体提取"""
    print("\n" + "="*60)
    print("测试实体提取")
    print("="*60)
    
    try:
        from app.knowledge_graph.entity_extractor import EntityExtractor
        
        extractor = EntityExtractor()
        test_text = "王五是一名产品经理，在深圳的华为公司工作。"
        
        print(f"\n测试文本: {test_text}")
        print("开始提取实体...")
        
        entities = await extractor.extract(test_text)
        
        print(f"\n✅ 提取成功，找到 {len(entities)} 个实体:")
        for entity in entities:
            print(f"  - {entity['name']} ({entity['type']})")
        
        return len(entities) > 0
        
    except Exception as e:
        print(f"\n❌ 实体提取失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_relation_extraction():
    """测试关系提取"""
    print("\n" + "="*60)
    print("测试关系提取")
    print("="*60)
    
    try:
        from app.knowledge_graph.relation_extractor import RelationExtractor
        
        extractor = RelationExtractor()
        test_text = "王五是一名产品经理，在深圳的华为公司工作。"
        test_entities = [
            {"name": "王五", "type": "PERSON"},
            {"name": "产品经理", "type": "CONCEPT"},
            {"name": "深圳", "type": "LOCATION"},
            {"name": "华为", "type": "ORGANIZATION"}
        ]
        
        print(f"\n测试文本: {test_text}")
        print(f"输入实体: {len(test_entities)} 个")
        print("开始提取关系...")
        
        relations = await extractor.extract(test_text, test_entities)
        
        print(f"\n✅ 提取成功，找到 {len(relations)} 个关系:")
        for relation in relations:
            print(f"  - {relation['source']} -[{relation['type']}]-> {relation['target']}")
        
        return len(relations) > 0
        
    except Exception as e:
        print(f"\n❌ 关系提取失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_api_endpoints():
    """测试 API 端点结构"""
    print("\n" + "="*60)
    print("测试 API 端点结构")
    print("="*60)
    
    try:
        from app.api.v1.endpoints.knowledge_graph import router
        
        print("\n检查 API 路由:")
        routes = [route for route in router.routes]
        print(f"  总路由数: {len(routes)}")
        
        expected_routes = [
            ("/build", "POST"),
            ("/search", "POST"),
            ("/query-entity", "POST"),
            ("/stats", "GET"),
            ("/visualize", "GET")
        ]
        
        found_routes = []
        for route in routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                for method in route.methods:
                    if method != "OPTIONS":  # 跳过 OPTIONS
                        found_routes.append((route.path, method))
                        print(f"  ✅ {method:6} {route.path}")
        
        # 检查是否包含所有预期路由
        missing = []
        for expected in expected_routes:
            if expected not in found_routes:
                missing.append(expected)
        
        if missing:
            print(f"\n⚠️ 缺少路由: {missing}")
            return False
        else:
            print(f"\n✅ 所有预期路由都存在")
            return True
        
    except Exception as e:
        print(f"\n❌ API 端点测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("知识图谱集成测试（简化版）")
    print("="*60)
    
    results = {}
    
    # 测试 1: 图构建器初始化
    try:
        results["graph_builder_init"] = await test_graph_builder_initialization()
    except Exception as e:
        print(f"\n❌ 图构建器初始化测试失败: {e}")
        results["graph_builder_init"] = False
    
    # 测试 2: 语义记忆初始化
    try:
        results["semantic_memory_init"] = await test_semantic_memory_initialization()
    except Exception as e:
        print(f"\n❌ 语义记忆初始化测试失败: {e}")
        results["semantic_memory_init"] = False
    
    # 测试 3: 实体提取
    try:
        results["entity_extraction"] = await test_entity_extraction()
    except Exception as e:
        print(f"\n❌ 实体提取测试失败: {e}")
        results["entity_extraction"] = False
    
    # 测试 4: 关系提取
    try:
        results["relation_extraction"] = await test_relation_extraction()
    except Exception as e:
        print(f"\n❌ 关系提取测试失败: {e}")
        results["relation_extraction"] = False
    
    # 测试 5: API 端点
    try:
        results["api_endpoints"] = await test_api_endpoints()
    except Exception as e:
        print(f"\n❌ API 端点测试失败: {e}")
        results["api_endpoints"] = False
    
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
        print("\n✅ 知识图谱核心功能正常:")
        print("  1. GraphBuilder 初始化成功")
        print("  2. 语义记忆集成成功")
        print("  3. 实体提取功能正常")
        print("  4. 关系提取功能正常")
        print("  5. API 端点结构完整")
        print("\n🚀 可以进行完整的端到端测试！")
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息")
        
        # 提供修复建议
        if not results.get("graph_builder_init"):
            print("\n💡 修复建议:")
            print("  - 检查 Neo4j 是否运行: docker-compose up -d neo4j")
            print("  - 检查配置: ENABLE_KNOWLEDGE_GRAPH=True")
        
        if not results.get("entity_extraction") or not results.get("relation_extraction"):
            print("\n💡 修复建议:")
            print("  - 检查 LLM 配置: ZHIPU_API_KEY")
            print("  - 检查网络连接")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)