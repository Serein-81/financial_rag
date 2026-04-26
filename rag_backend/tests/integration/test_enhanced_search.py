"""
测试增强版搜索服务
对比基础搜索和增强搜索的效果
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.enhanced_search_service import enhanced_search_service


async def test_query_optimization():
    """测试查询优化功能"""
    print("=" * 60)
    print("测试 1: 查询优化功能")
    print("=" * 60)
    
    from app.services.query_optimizer import query_optimizer
    
    # 测试查询改写
    query = "RAG系统是什么？"
    print(f"\n原始查询: {query}")
    
    variants = await query_optimizer.rewrite_query(query, num_variants=3)
    print(f"\n改写后的查询 ({len(variants)} 个):")
    for i, v in enumerate(variants, 1):
        print(f"  {i}. {v}")
    
    # 测试意图检测
    print("\n查询意图检测:")
    intent = await query_optimizer.detect_query_intent(query)
    print(f"  类型: {intent['type']}")
    print(f"  建议 top_k: {intent['suggested_top_k']}")
    print(f"  建议阈值: {intent['suggested_threshold']}")
    
    # 测试总结类查询
    summary_query = "总结一下这篇文档的主要内容"
    intent2 = await query_optimizer.detect_query_intent(summary_query)
    print("\n总结类查询意图:")
    print(f"  查询: {summary_query}")
    print(f"  类型: {intent2['type']}")
    print(f"  建议 top_k: {intent2['suggested_top_k']}")


async def test_search_comparison():
    """测试搜索对比"""
    print("\n" + "=" * 60)
    print("测试 2: 基础搜索 vs 增强搜索")
    print("=" * 60)
    
    test_queries = [
        "RAG系统的工作原理",
        "如何提高检索准确率",
        "总结向量数据库的优势"
    ]
    
    for query in test_queries:
        print(f"\n查询: {query}")
        print("-" * 60)
        
        try:
            comparison = await enhanced_search_service.compare_search_methods(
                query=query,
                top_k=5
            )
            
            print("\n基础搜索:")
            print(f"  结果数: {comparison['basic']['count']}")
            print(f"  耗时: {comparison['basic']['time']}s")
            
            print("\n增强搜索:")
            print(f"  结果数: {comparison['enhanced']['count']}")
            print(f"  耗时: {comparison['enhanced']['time']}s")
            
            print("\n对比:")
            print(f"  时间增加: {comparison['comparison']['time_diff']}s ({comparison['comparison']['time_increase_pct']}%)")
            print(f"  结果重叠: {comparison['comparison']['result_overlap']}")
            print(f"  增强独有: {comparison['comparison']['unique_to_enhanced']}")
            
            # 显示前3个结果
            if comparison['enhanced']['results']:
                print("\n增强搜索 Top 3 结果:")
                for i, r in enumerate(comparison['enhanced']['results'][:3], 1):
                    print(f"  {i}. [分数: {r['score']}] {r['content'][:100]}...")
        
        except Exception as e:
            print(f"  ❌ 测试失败: {e}")


async def test_mmr_reranking():
    """测试 MMR 重排序"""
    print("\n" + "=" * 60)
    print("测试 3: MMR 重排序效果")
    print("=" * 60)
    
    from app.services.query_optimizer import query_optimizer
    from app.services.embedding_service import embedding_service
    
    # 模拟一些相似的结果
    query = "机器学习算法"
    query_embedding = await embedding_service.get_embedding(query)
    
    # 创建测试数据
    test_contents = [
        "机器学习是人工智能的一个分支",
        "机器学习算法包括监督学习和无监督学习",
        "深度学习是机器学习的一个子领域",
        "神经网络是深度学习的基础",
        "Python是机器学习最常用的编程语言"
    ]
    
    results = []
    for i, content in enumerate(test_contents):
        embedding = await embedding_service.get_embedding(content)
        results.append({
            'id': i,
            'content': content,
            'embedding': embedding,
            'score': 0.8 - i * 0.1  # 模拟递减的分数
        })
    
    print("\n原始排序 (按分数):")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [分数: {r['score']}] {r['content']}")
    
    # MMR 重排序
    reranked = query_optimizer.mmr_rerank(
        results,
        query_embedding,
        lambda_param=0.5,  # 平衡相关性和多样性
        top_k=5
    )
    
    print("\nMMR 重排序后:")
    for i, r in enumerate(reranked, 1):
        print(f"  {i}. [分数: {r['score']}] {r['content']}")


async def test_enhanced_search_features():
    """测试增强搜索的各项功能"""
    print("\n" + "=" * 60)
    print("测试 4: 增强搜索功能开关")
    print("=" * 60)
    
    query = "什么是向量数据库"
    
    # 测试不同配置
    configs = [
        {"query_rewrite": True, "hyde": False, "mmr": True, "name": "查询改写 + MMR"},
        {"query_rewrite": False, "hyde": False, "mmr": True, "name": "仅 MMR"},
        {"query_rewrite": True, "hyde": False, "mmr": False, "name": "仅查询改写"},
        {"query_rewrite": False, "hyde": False, "mmr": False, "name": "基础模式"}
    ]
    
    for config in configs:
        print(f"\n配置: {config['name']}")
        print("-" * 40)
        
        # 临时修改配置
        enhanced_search_service.enable_query_rewrite = config['query_rewrite']
        enhanced_search_service.enable_hyde = config['hyde']
        enhanced_search_service.enable_mmr = config['mmr']
        
        try:
            import time
            start = time.time()
            results = await enhanced_search_service.search(
                query=query,
                top_k=5,
                use_optimization=True
            )
            elapsed = time.time() - start
            
            print(f"  结果数: {len(results)}")
            print(f"  耗时: {elapsed:.4f}s")
            if results:
                print(f"  Top 1: [分数: {results[0].score}] {results[0].content[:80]}...")
        
        except Exception as e:
            print(f"  ❌ 失败: {e}")
    
    # 恢复默认配置
    enhanced_search_service.enable_query_rewrite = True
    enhanced_search_service.enable_hyde = False
    enhanced_search_service.enable_mmr = True


async def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("增强搜索服务测试")
    print("=" * 60)
    
    try:
        # 测试 1: 查询优化
        await test_query_optimization()
        
        # 测试 2: 搜索对比
        await test_search_comparison()
        
        # 测试 3: MMR 重排序
        await test_mmr_reranking()
        
        # 测试 4: 功能开关
        await test_enhanced_search_features()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试完成")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n❌ 测试过程出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
