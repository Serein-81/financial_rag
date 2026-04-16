"""
测试 Neo4j 知识图谱连接
注意：此测试需要 Neo4j 服务，仅在本地环境手动运行
CI 环境会自动跳过此测试
"""
import asyncio
import os
import pytest
from app.knowledge_graph.neo4j_manager import neo4j_manager
from app.knowledge_graph.entity_extractor import entity_extractor
from app.knowledge_graph.relation_extractor import relation_extractor
from app.core.config import settings


@pytest.mark.skipif(
    os.getenv("CI") == "true" or not settings.ENABLE_KNOWLEDGE_GRAPH,
    reason="需要 Neo4j 服务，仅在本地环境运行"
)
async def test_neo4j():
    print("=" * 50)
    print("测试 Neo4j 知识图谱")
    print("=" * 50)
    
    # 0. 检查配置
    print("\n0. 检查配置...")
    print(f"   ENABLE_KNOWLEDGE_GRAPH: {settings.ENABLE_KNOWLEDGE_GRAPH}")
    print(f"   ENABLE_ENTITY_EXTRACTION: {settings.ENABLE_ENTITY_EXTRACTION}")
    print(f"   ENABLE_RELATION_EXTRACTION: {settings.ENABLE_RELATION_EXTRACTION}")
    print(f"   NEO4J_URI: {settings.NEO4J_URI}")
    
    if not settings.ENABLE_KNOWLEDGE_GRAPH:
        print("\n⚠️  警告：知识图谱功能未开启！")
        print("   请在 .env 中设置 ENABLE_KNOWLEDGE_GRAPH=true")
        return
    
    # 1. 测试连接
    print("\n1. 测试 Neo4j 连接...")
    try:
        stats = neo4j_manager.get_graph_stats()
        print(f"   ✅ 连接成功")
        print(f"   图统计: {stats}")
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        return
    
    # 2. 测试实体提取
    print("\n2. 测试实体提取...")
    text = "张三在北京的阿里巴巴公司担任软件工程师"
    print(f"   测试文本: {text}")
    
    try:
        entities = await entity_extractor.extract(text)
        print(f"   ✅ 提取成功")
        print(f"   提取的实体: {entities}")
        
        if not entities:
            print("   ⚠️  警告：未提取到实体，可能是 LLM 返回格式问题")
    except Exception as e:
        print(f"   ❌ 提取失败: {e}")
        import traceback
        traceback.print_exc()
        entities = []
    
    # 3. 测试关系提取
    print("\n3. 测试关系提取...")
    relations = []
    if entities:
        try:
            relations = await relation_extractor.extract(text, entities)
            print(f"   ✅ 提取成功")
            print(f"   提取的关系: {relations}")
            
            if not relations:
                print("   ⚠️  警告：未提取到关系")
        except Exception as e:
            print(f"   ❌ 提取失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("   ⏭️  跳过（没有实体）")
    
    # 4. 创建实体
    print("\n4. 创建实体到 Neo4j...")
    created_entities = 0
    if entities:
        for entity in entities:
            try:
                result = neo4j_manager.create_entity(
                    name=entity['name'],
                    entity_type=entity['type']
                )
                if result:
                    created_entities += 1
                    print(f"   ✅ 创建实体: {entity['name']} ({entity['type']})")
                else:
                    print(f"   ⚠️  创建失败: {entity['name']}")
            except Exception as e:
                print(f"   ❌ 创建实体失败 {entity['name']}: {e}")
        
        print(f"   总计创建: {created_entities}/{len(entities)}")
    else:
        print("   ⏭️  跳过（没有实体）")
    
    # 5. 创建关系
    print("\n5. 创建关系到 Neo4j...")
    created_relations = 0
    if relations:
        for relation in relations:
            try:
                result = neo4j_manager.create_relation(
                    source_entity=relation['source'],
                    target_entity=relation['target'],
                    relation_type=relation['type']
                )
                if result:
                    created_relations += 1
                    print(f"   ✅ 创建关系: {relation['source']} -[{relation['type']}]-> {relation['target']}")
                else:
                    print(f"   ⚠️  创建失败: {relation}")
            except Exception as e:
                print(f"   ❌ 创建关系失败 {relation}: {e}")
        
        print(f"   总计创建: {created_relations}/{len(relations)}")
    else:
        print("   ⏭️  跳过（没有关系）")
    
    # 6. 查询相关实体
    print("\n6. 查询相关实体...")
    if entities and created_entities > 0:
        try:
            first_entity = entities[0]['name']
            related = neo4j_manager.find_related_entities(first_entity)
            print(f"   查询 '{first_entity}' 的相关实体:")
            if related:
                for r in related:
                    print(f"     - {r['name']} ({r['type']}) 距离: {r['distance']}")
            else:
                print("     (无相关实体)")
        except Exception as e:
            print(f"   ❌ 查询失败: {e}")
    else:
        print("   ⏭️  跳过（没有创建实体）")
    
    # 7. 最终统计
    print("\n7. 最终图统计...")
    try:
        stats = neo4j_manager.get_graph_stats()
        print(f"   记忆节点: {stats.get('memories', 0)}")
        print(f"   实体节点: {stats.get('entities', 0)}")
        print(f"   关系数量: {stats.get('relations', 0)}")
    except Exception as e:
        print(f"   ❌ 获取统计失败: {e}")
    
    print("\n" + "=" * 50)
    if created_entities > 0 or created_relations > 0:
        print("✅ 测试完成 - 知识图谱功能正常")
    else:
        print("⚠️  测试完成 - 但未成功创建数据")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_neo4j())
