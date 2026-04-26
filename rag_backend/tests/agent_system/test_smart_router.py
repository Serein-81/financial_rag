"""
测试智能路由功能
"""
import asyncio
from app.services.smart_router import smart_router, RouteMode


async def test_smart_router():
    """测试智能路由器"""
    
    print("=" * 80)
    print("🧪 测试智能路由功能")
    print("=" * 80)
    
    # 测试用例
    test_cases = [
        # RAG_ONLY 场景
        ("什么是变压器原理？", RouteMode.RAG_ONLY),
        ("Python generator 的定义是什么？", RouteMode.RAG_ONLY),
        ("解释一下机器学习的基本概念", RouteMode.RAG_ONLY),
        
        # MEMORY_ONLY 场景
        ("我昨天问了什么？", RouteMode.MEMORY_ONLY),
        ("提醒我上次说的事情", RouteMode.MEMORY_ONLY),
        ("根据我之前的习惯", RouteMode.MEMORY_ONLY),
        
        # HYBRID 场景
        ("根据我的偏好推荐 Python 教程", RouteMode.HYBRID),
        ("结合我的情况分析这个问题", RouteMode.HYBRID),
        ("我之前学过的知识有哪些相关内容？", RouteMode.HYBRID),
    ]
    
    print("\n📝 开始测试...")
    print("=" * 80)
    
    correct_count = 0
    total_count = len(test_cases)
    
    for idx, (query, expected_mode) in enumerate(test_cases, 1):
        print(f"\n测试 {idx}/{total_count}")
        print(f"问题: {query}")
        print(f"期望: {expected_mode.value}")
        
        try:
            # 调用路由器
            result = await smart_router.route(query)
            
            # 判断是否正确
            is_correct = result == expected_mode
            if is_correct:
                correct_count += 1
                print(f"✅ 正确: {result.value}")
            else:
                print(f"❌ 错误: {result.value} (期望: {expected_mode.value})")
                
        except Exception as e:
            print(f"❌ 异常: {e}")
        
        print("-" * 80)
    
    # 统计结果
    print("\n" + "=" * 80)
    print("📊 测试结果统计")
    print("=" * 80)
    print(f"总测试数: {total_count}")
    print(f"正确数: {correct_count}")
    print(f"准确率: {correct_count/total_count*100:.1f}%")
    
    if correct_count == total_count:
        print("\n🎉 所有测试通过！")
    elif correct_count >= total_count * 0.7:
        print("\n✅ 大部分测试通过，路由器工作正常")
    else:
        print("\n⚠️ 准确率较低，可能需要优化 prompt")
    
    print("=" * 80)


async def test_route_with_explanation():
    """测试带解释的路由"""
    
    print("\n" + "=" * 80)
    print("🧪 测试带解释的路由")
    print("=" * 80)
    
    test_queries = [
        "什么是 Python 装饰器？",
        "我昨天学了什么？",
        "根据我的学习进度推荐下一步内容"
    ]
    
    for query in test_queries:
        print(f"\n问题: {query}")
        result = await smart_router.route_with_explanation(query)
        print(f"模式: {result['mode']}")
        print(f"解释: {result['explanation']}")
        print("-" * 80)


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_smart_router())
    asyncio.run(test_route_with_explanation())
