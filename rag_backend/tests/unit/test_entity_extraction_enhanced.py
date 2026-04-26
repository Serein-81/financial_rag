"""测试增强版实体提取（置信度 + 消歧 + 指代消解）"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.knowledge_graph.entity_extractor import EntityExtractor
from app.knowledge_graph.coreference_resolver import CoreferenceResolver


async def test_coreference_resolution():
    """测试指代消解"""
    print("\n" + "="*60)
    print("测试 1: 指代消解")
    print("="*60)
    
    resolver = CoreferenceResolver()
    
    test_cases = [
        "张三买了手机。它很贵。",
        "苹果公司发布了新产品。它的销量很好。",
        "李四在阿里巴巴工作。他是工程师。",
        "北京是首都。这个城市很大。"
    ]
    
    for text in test_cases:
        print(f"\n原文: {text}")
        resolved = await resolver.resolve(text)
        print(f"消解后: {resolved}")


async def test_confidence_scoring():
    """测试置信度评分"""
    print("\n" + "="*60)
    print("测试 2: 置信度评分")
    print("="*60)
    
    extractor = EntityExtractor()
    
    test_cases = [
        "张三在北京的阿里巴巴公司担任软件工程师",
        "苹果发布了新款手机",
        "那个人在那个地方工作"  # 模糊表述，应该有低置信度
    ]
    
    for text in test_cases:
        print(f"\n文本: {text}")
        entities = await extractor.extract(text, resolve_coreference=False)
        
        if entities:
            print(f"提取到 {len(entities)} 个实体:")
            for entity in entities:
                confidence = entity.get('confidence', 1.0)
                disambiguated = entity.get('disambiguated_name', entity['name'])
                print(f"  - {entity['name']} ({entity['type']}) "
                      f"置信度: {confidence:.2f} "
                      f"消歧: {disambiguated if disambiguated != entity['name'] else '无'}")
        else:
            print("  未提取到实体")


async def test_disambiguation():
    """测试实体消歧"""
    print("\n" + "="*60)
    print("测试 3: 实体消歧")
    print("="*60)
    
    extractor = EntityExtractor()
    
    test_cases = [
        ("苹果发布了新款iPhone", "科技语境"),
        ("我买了一个苹果", "食品语境"),
        ("张三是软件工程师", "有职位信息"),
        ("张三在公司工作", "无职位信息")
    ]
    
    for text, context in test_cases:
        print(f"\n文本: {text} ({context})")
        entities = await extractor.extract(text, resolve_coreference=False)
        
        if entities:
            for entity in entities:
                original = entity.get('original_name', entity['name'])
                disambiguated = entity['name']
                if original != disambiguated:
                    print(f"  ✅ 消歧: {original} → {disambiguated}")
                else:
                    print(f"  - {entity['name']} ({entity['type']})")


async def test_full_pipeline():
    """测试完整流程：指代消解 + 实体提取 + 置信度 + 消歧"""
    print("\n" + "="*60)
    print("测试 4: 完整流程")
    print("="*60)
    
    extractor = EntityExtractor()
    
    test_text = "苹果公司发布了新产品。它的销量很好。张三是该公司的工程师。"
    
    print(f"\n原文: {test_text}")
    print("\n处理流程:")
    print("  1. 指代消解...")
    print("  2. 实体提取...")
    print("  3. 置信度评分...")
    print("  4. 实体消歧...")
    
    entities = await extractor.extract(test_text, resolve_coreference=True)
    
    print(f"\n最终结果: 提取到 {len(entities)} 个高置信度实体")
    for entity in entities:
        confidence = entity.get('confidence', 1.0)
        original = entity.get('original_name')
        print(f"  - {entity['name']} ({entity['type']}) "
              f"置信度: {confidence:.2f}"
              + (f" [原名: {original}]" if original else ""))


async def main():
    """运行所有测试"""
    print("\n🚀 开始测试增强版实体提取功能")
    
    try:
        await test_coreference_resolution()
        await test_confidence_scoring()
        await test_disambiguation()
        await test_full_pipeline()
        
        print("\n" + "="*60)
        print("✅ 所有测试完成")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
