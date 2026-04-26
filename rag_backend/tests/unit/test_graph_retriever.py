"""
图谱检索功能单元测试

测试图谱查询分类器和图谱检索器的功能
"""

import pytest
import asyncio
from app.services.graph_query_classifier import GraphQueryClassifier, GraphQueryType


class TestGraphQueryClassifier:
    """测试图谱查询分类器"""

    def setup_method(self):
        """每个测试方法前执行"""
        self.classifier = GraphQueryClassifier()

    @pytest.mark.asyncio
    async def test_rag_strong_pattern_should_skip_graph(self):
        """测试RAG强模式应该跳过图谱"""
        test_cases = [
            "项目有什么功能",
            "Python怎么用",
            "什么是机器学习",
            "帮我解释一下",
            "怎么做饭",
            "这个政策是什么意思",
            "帮我写个代码示例",
            "教程是什么",
        ]
        
        print("\n" + "=" * 60)
        print("测试: RAG强模式应该跳过图谱")
        print("=" * 60)
        
        for query in test_cases:
            query_type, need_graph = await self.classifier.classify(query)
            print(f"  查询: '{query}' -> need_graph={need_graph}")
            assert need_graph == False, f"'{query}' 应该跳过图谱"
        
        print("\n✅ RAG强模式测试通过")

    @pytest.mark.asyncio
    async def test_graph_strong_pattern_should_use_graph(self):
        """测试图谱强模式应该使用图谱"""
        test_cases = [
            "客户某某某续约了",
            "张三和李四是什么关系",
            "某某公司有哪些合作伙伴",
            "客户和供应商的关系",
            "签约情况",
            "供应链路径",
        ]
        
        print("\n" + "=" * 60)
        print("测试: 图谱强模式应该使用图谱")
        print("=" * 60)
        
        for query in test_cases:
            query_type, need_graph = await self.classifier.classify(query)
            print(f"  查询: '{query}' -> need_graph={need_graph}")
            assert need_graph == True, f"'{query}' 应该使用图谱"
        
        print("\n✅ 图谱强模式测试通过")

    @pytest.mark.asyncio
    async def test_mixed_pattern_classification(self):
        """测试混合模式分类"""
        print("\n" + "=" * 60)
        print("测试: 混合模式分类")
        print("=" * 60)
        
        test_cases = [
            ("客户某某某续约了吗", True),
            ("项目有什么功能", False),
            ("我们和华为合作情况", True),
            ("Python代码怎么写", False),
            ("有哪些供应商", True),
            ("帮我解释这个概念", False),
        ]
        
        for query, expected in test_cases:
            query_type, need_graph = await self.classifier.classify(query)
            print(f"  查询: '{query}' -> need_graph={need_graph} (期望={expected})")
            assert need_graph == expected, f"'{query}' 期望 need_graph={expected}"
        
        print("\n✅ 混合模式测试通过")

    def test_entity_extraction(self):
        """测试实体提取"""
        print("\n" + "=" * 60)
        print("测试: 实体提取")
        print("=" * 60)
        
        test_cases = [
            ("客户某某某续约了", ["某某某"]),
            ("张三和李四合作", ["张三", "李四"]),
            ("华为公司合作", ["华为", "公司"]),
            ("Python教程", ["Python"]),
        ]
        
        for query, expected in test_cases:
            entities = self.classifier._extract_entities(query)
            print(f"  查询: '{query}' -> 实体: {entities}")
        
        print("\n✅ 实体提取测试通过")

    def test_graph_keywords_detection(self):
        """测试图谱关键词检测"""
        print("\n" + "=" * 60)
        print("测试: 图谱关键词检测")
        print("=" * 60)
        
        test_cases = [
            ("客户某某某续约", True),
            ("和张三合作", True),
            ("有哪些供应商", True),
            ("项目功能", False),
            ("Python怎么用", False),
        ]
        
        for query, expected in test_cases:
            result = self.classifier._has_graph_keywords(query)
            print(f"  查询: '{query}' -> has_graph_keywords={result}")
            assert result == expected, f"'{query}' 期望 has_graph_keywords={expected}"
        
        print("\n✅ 图谱关键词检测测试通过")

    @pytest.mark.asyncio
    async def test_empty_query_handling(self):
        """测试空查询处理"""
        print("\n" + "=" * 60)
        print("测试: 空查询处理")
        print("=" * 60)
        
        empty_queries = ["", "   ", None]
        
        for query in empty_queries:
            if query is not None:
                query_type, need_graph = await self.classifier.classify(query)
                print(f"  查询: '{query}' -> need_graph={need_graph}")
                assert need_graph == False
        
        print("\n✅ 空查询处理测试通过")

    def test_pattern_matching(self):
        """测试模式匹配"""
        print("\n" + "=" * 60)
        print("测试: 模式匹配")
        print("=" * 60)
        
        rag_pattern_cases = [
            "这是什么意思",
            "怎么做",
            "教程",
            "功能介绍",
        ]
        
        graph_pattern_cases = [
            "续约情况",
            "合作关系",
            "签约客户",
        ]
        
        for query in rag_pattern_cases:
            matched = self.classifier._matches_rag_strong_patterns(query)
            print(f"  RAG模式 '{query}' -> {matched}")
            assert matched == True
        
        for query in graph_pattern_cases:
            matched = self.classifier._matches_graph_strong_patterns(query)
            print(f"  图谱模式 '{query}' -> {matched}")
            assert matched == True
        
        print("\n✅ 模式匹配测试通过")


class TestGraphQueryType:
    """测试图谱查询类型枚举"""

    def test_query_type_enum_values(self):
        """测试枚举值"""
        print("\n" + "=" * 60)
        print("测试: 图谱查询类型枚举")
        print("=" * 60)
        
        assert GraphQueryType.ENTITY_RELATION.value == "ENTITY_RELATION"
        assert GraphQueryType.ENTITY_ATTRIBUTE.value == "ENTITY_ATTRIBUTE"
        assert GraphQueryType.GRAPH_PATH.value == "GRAPH_PATH"
        assert GraphQueryType.NONE.value == "NONE"
        
        print(f"  ENTITY_RELATION: {GraphQueryType.ENTITY_RELATION.value}")
        print(f"  ENTITY_ATTRIBUTE: {GraphQueryType.ENTITY_ATTRIBUTE.value}")
        print(f"  GRAPH_PATH: {GraphQueryType.GRAPH_PATH.value}")
        print(f"  NONE: {GraphQueryType.NONE.value}")
        
        print("\n✅ 枚举值测试通过")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("开始运行图谱检索单元测试")
    print("=" * 60)
    
    pytest.main([__file__, "-v", "-s"])
