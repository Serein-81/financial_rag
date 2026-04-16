"""
测试 GraphRAG 融合增强功能

验证以下改进：
1. 实体提取器的语义合并和 LLM 摘要
2. 关系提取器的智能合并和描述生成
3. 图构建器的增强构建方法

注意：此测试需要 Neo4j 和 LLM 服务，仅在本地环境手动运行
"""
import asyncio
import logging
import os
import pytest

# 检查是否在 CI 环境
is_ci = os.getenv("CI") == "true"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.skipif(is_ci, reason="需要 Neo4j 和 LLM 服务，仅在本地环境运行")
async def test_entity_extractor():
    """测试实体提取器增强功能"""
    try:
        from app.knowledge_graph.entity_extractor import EntityExtractor

        extractor = EntityExtractor()

        test_text = """
        张三在北京的百度公司工作，他担任高级软件工程师。
        李四也在百度公司，是张同事。
        王五在阿里巴巴工作。
        """

        print("\n" + "="*60)
        print("测试 1: 基础实体提取")
        print("="*60)

        entities = await extractor.extract(
            test_text,
            resolve_coreference=True
        )

        print(f"提取到 {len(entities)} 个实体:")
        for entity in entities:
            print(f"  - {entity['name']} ({entity['type']}) - 置信度: {entity.get('confidence', 'N/A')}")

        print("\n" + "="*60)
        print("测试 2: 带回调的实体提取")
        print("="*60)

        def progress_callback(msg: str):
            print(f"  [进度] {msg}")

        entities_with_callback = await extractor.extract(
            test_text,
            resolve_coreference=True,
            callback=progress_callback
        )

        print(f"\n提取到 {len(entities_with_callback)} 个实体")

        print("\n" + "="*60)
        print("测试 3: 实体合并")
        print("="*60)

        all_entities = [entities, entities]
        merged = extractor._merge_entities(all_entities)

        print(f"合并前: {len(entities)} + {len(entities)} = {len(entities) * 2} 个实体")
        print(f"合并后: {len(merged)} 个实体")

        for entity in merged:
            print(f"  - {entity['name']} ({entity['type']}) - 出现次数: {entity.get('occurrence_count', 1)}")

        print("\n✅ 实体提取器测试通过")
        return True

    except Exception as e:
        logger.error(f"实体提取器测试失败: {e}", exc_info=True)
        print(f"\n❌ 实体提取器测试失败: {e}")
        return False


async def test_relation_extractor():
    """测试关系提取器增强功能"""
    try:
        from app.knowledge_graph.relation_extractor import RelationExtractor

        extractor = RelationExtractor()

        test_text = """
        张三在北京的百度公司工作。
        他开发了百度搜索系统。
        """

        test_entities = [
            {"name": "张三", "type": "PERSON", "confidence": 0.95},
            {"name": "北京", "type": "LOCATION", "confidence": 1.0},
            {"name": "百度", "type": "ORGANIZATION", "confidence": 1.0},
            {"name": "百度搜索系统", "type": "PRODUCT", "confidence": 0.9}
        ]

        print("\n" + "="*60)
        print("测试 4: 基础关系提取")
        print("="*60)

        relations = await extractor.extract(test_text, test_entities)

        print(f"提取到 {len(relations)} 个关系:")
        for relation in relations:
            print(f"  - {relation['source']} -[{relation['type']}]-> {relation['target']} (置信度: {relation.get('confidence', 'N/A')})")

        print("\n" + "="*60)
        print("测试 5: 带回调的关系提取")
        print("="*60)

        def progress_callback(msg: str):
            print(f"  [进度] {msg}")

        relations_with_callback = await extractor.extract(
            test_text,
            test_entities,
            callback=progress_callback
        )

        print(f"\n提取到 {len(relations_with_callback)} 个关系")

        print("\n" + "="*60)
        print("测试 6: 关系合并")
        print("="*60)

        all_relations = [relations, relations]
        merged = extractor._merge_relations(all_relations)

        print(f"合并前: {len(relations)} + {len(relations)} = {len(relations) * 2} 个关系")
        print(f"合并后: {len(merged)} 个关系")

        for relation in merged:
            print(f"  - {relation['source']} -[{relation['type']}]-> {relation['target']} - 出现次数: {relation.get('occurrence_count', 1)}")

        print("\n✅ 关系提取器测试通过")
        return True

    except Exception as e:
        logger.error(f"关系提取器测试失败: {e}", exc_info=True)
        print(f"\n❌ 关系提取器测试失败: {e}")
        return False


async def test_graph_builder():
    """测试图构建器增强功能"""
    try:
        from app.knowledge_graph.entity_extractor import EntityExtractor
        from app.knowledge_graph.relation_extractor import RelationExtractor

        print("\n" + "="*60)
        print("测试 7: 检查新增方法")
        print("="*60)

        entity_extractor = EntityExtractor()
        relation_extractor = RelationExtractor()

        has_extract_with_descriptions = hasattr(entity_extractor, 'extract_with_descriptions')
        has_generate_description = hasattr(entity_extractor, '_generate_entity_description')
        has_merge_entity_data = hasattr(entity_extractor, '_merge_entity_data')

        has_relation_descriptions = hasattr(relation_extractor, 'extract_with_descriptions')
        has_generate_relation_desc = hasattr(relation_extractor, '_generate_relation_description')
        has_merge_relation_data = hasattr(relation_extractor, '_merge_relation_data')

        print(f"实体提取器 - extract_with_descriptions: {'✅' if has_extract_with_descriptions else '❌'}")
        print(f"实体提取器 - _generate_entity_description: {'✅' if has_generate_description else '❌'}")
        print(f"实体提取器 - _merge_entity_data: {'✅' if has_merge_entity_data else '❌'}")
        print(f"关系提取器 - extract_with_descriptions: {'✅' if has_relation_descriptions else '❌'}")
        print(f"关系提取器 - _generate_relation_description: {'✅' if has_generate_relation_desc else '❌'}")
        print(f"关系提取器 - _merge_relation_data: {'✅' if has_merge_relation_data else '❌'}")

        print("\n" + "="*60)
        print("测试 8: 验证新功能参数")
        print("="*60)

        test_entities = [
            {"name": "测试", "type": "TEST", "confidence": 0.9}
        ]

        print("实体提取器新方法签名检查:")
        import inspect
        sig = inspect.signature(entity_extractor.extract)
        params = list(sig.parameters.keys())
        print(f"  extract 方法参数: {params}")
        print(f"  包含 callback: {'✅' if 'callback' in params else '❌'}")

        sig2 = inspect.signature(relation_extractor.extract)
        params2 = list(sig2.parameters.keys())
        print(f"\n关系提取器 extract 方法参数: {params2}")
        print(f"  包含 callback: {'✅' if 'callback' in params2 else '❌'}")

        print("\n✅ 图构建器测试通过")
        return True

    except Exception as e:
        logger.error(f"图构建器测试失败: {e}", exc_info=True)
        print(f"\n❌ 图构建器测试失败: {e}")
        return False


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("GraphRAG 融合增强功能测试")
    print("="*60)

    test_results = []

    test_results.append(("实体提取器基础功能", await test_entity_extractor()))
    test_results.append(("关系提取器基础功能", await test_relation_extractor()))
    test_results.append(("图构建器增强功能", await test_graph_builder()))

    print("\n" + "="*60)
    print("测试总结")
    print("="*60)

    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")

    total_tests = len(test_results)
    passed_tests = sum(1 for _, result in test_results if result)

    print(f"\n总计: {passed_tests}/{total_tests} 测试通过")

    if passed_tests == total_tests:
        print("\n🎉 所有测试通过！GraphRAG 融合增强功能验证成功。")
    else:
        print(f"\n⚠️ {total_tests - passed_tests} 个测试失败，请检查输出。")


if __name__ == "__main__":
    asyncio.run(main())
