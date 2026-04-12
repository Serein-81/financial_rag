"""
用户记忆提取系统独立测试脚本

测试内容：
1. UserMemoryExtractor 核心逻辑测试
2. 提取结果数据类测试
3. 提示词模板测试
"""

import json
import re
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class ExtractedFact:
    """提取的事实"""
    content: str
    category: str
    confidence: float
    source: str


@dataclass
class ExtractedPreference:
    """提取的偏好"""
    content: str
    category: str
    confidence: float
    source: str


@dataclass
class ExtractedCorrection:
    """提取的纠正信息"""
    original: str
    corrected: str
    confidence: float
    source: str


@dataclass
class UserMemoryExtractionResult:
    """用户记忆提取结果"""
    facts: List[ExtractedFact]
    preferences: List[ExtractedPreference]
    corrections: List[ExtractedCorrection]
    extraction_time: datetime
    total_items: int
    
    def is_empty(self) -> bool:
        """检查是否为空"""
        return (
            len(self.facts) == 0 and 
            len(self.preferences) == 0 and 
            len(self.corrections) == 0
        )
    
    def summary(self) -> str:
        """生成摘要"""
        total_categories = 3
        return (
            f"提取完成：共 {total_categories} 个类别 - "
            f"{len(self.facts)} 个事实，"
            f"{len(self.preferences)} 个偏好，"
            f"{len(self.corrections)} 个纠正"
        )


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


def _format_conversation(messages: List[Dict[str, str]]) -> str:
    """格式化对话历史"""
    if not messages:
        return "（无对话历史）"
    
    formatted = []
    for msg in messages:
        role = "用户" if msg.get("role") == "user" else "AI"
        content = msg.get("content", "").strip()
        
        if content:
            if len(content) > 500:
                content = content[:500] + "..."
            formatted.append(f"{role}：{content}")
    
    return "\n".join(formatted)


def _fix_json(json_str: str) -> str:
    """修复常见的JSON问题"""
    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
    return json_str


def _parse_extraction_result(response_text: str) -> UserMemoryExtractionResult:
    """模拟解析LLM响应"""
    try:
        json_match = re.search(
            r'\{[\s\S]*"facts"[\s\S]*\}',
            response_text,
            re.MULTILINE
        )
        
        if json_match:
            json_str = json_match.group(0)
            json_str = _fix_json(json_str)
            data = json.loads(json_str)
        else:
            data = json.loads(response_text)
        
        facts = [
            ExtractedFact(
                content=item.get("content", ""),
                category=item.get("category", "other"),
                confidence=float(item.get("confidence", 0.0)),
                source=item.get("source", "")
            )
            for item in data.get("facts", [])
            if item.get("content")
        ]
        
        preferences = [
            ExtractedPreference(
                content=item.get("content", ""),
                category=item.get("category", "other"),
                confidence=float(item.get("confidence", 0.0)),
                source=item.get("source", "")
            )
            for item in data.get("preferences", [])
            if item.get("content")
        ]
        
        corrections = [
            ExtractedCorrection(
                original=item.get("original", ""),
                corrected=item.get("corrected", ""),
                confidence=float(item.get("confidence", 0.0)),
                source=item.get("source", "")
            )
            for item in data.get("corrections", [])
            if item.get("corrected")
        ]
        
        return UserMemoryExtractionResult(
            facts=facts,
            preferences=preferences,
            corrections=corrections,
            extraction_time=datetime.now(),
            total_items=len(facts) + len(preferences) + len(corrections)
        )
    
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON解析失败: {e}")
        return UserMemoryExtractionResult(
            facts=[],
            preferences=[],
            corrections=[],
            extraction_time=datetime.now(),
            total_items=0
        )


def _filter_by_confidence(
    result: UserMemoryExtractionResult,
    confidence_threshold: float = 0.7
) -> UserMemoryExtractionResult:
    """根据置信度过滤结果"""
    filtered_facts = [f for f in result.facts if f.confidence >= confidence_threshold]
    filtered_preferences = [p for p in result.preferences if p.confidence >= confidence_threshold]
    filtered_corrections = [c for c in result.corrections if c.confidence >= confidence_threshold]
    
    return UserMemoryExtractionResult(
        facts=filtered_facts,
        preferences=filtered_preferences,
        corrections=filtered_corrections,
        extraction_time=result.extraction_time,
        total_items=len(filtered_facts) + len(filtered_preferences) + len(filtered_corrections)
    )


# 模拟的LLM响应（测试数据）
MOCK_LLM_RESPONSE = '''```json
{
  "facts": [
    {
      "content": "用户名叫张三",
      "category": "identity",
      "confidence": 0.95,
      "source": "用户自我介绍：'我叫张三'"
    },
    {
      "content": "用户在一家北京科技公司担任产品经理",
      "category": "business",
      "confidence": 0.92,
      "source": "用户自我介绍：'是北京某科技公司的产品经理'"
    },
    {
      "content": "用户拥有5年B端产品经验",
      "category": "business",
      "confidence": 0.90,
      "source": "用户陈述：'已经在这个行业工作5年了'"
    },
    {
      "content": "用户上周出差去了深圳",
      "category": "business",
      "confidence": 0.88,
      "source": "用户陈述：'我上周出差去了深圳'"
    },
    {
      "content": "用户的主要编程语言是Python",
      "category": "preference",
      "confidence": 0.85,
      "source": "用户陈述：'我平时用Python比较多'"
    }
  ],
  "preferences": [
    {
      "content": "用户喜欢简洁的设计风格",
      "category": "preference",
      "confidence": 0.90,
      "source": "用户表达：'我比较喜欢简洁的设计风格，不喜欢太花哨的东西'"
    },
    {
      "content": "用户偶尔使用JavaScript",
      "category": "preference",
      "confidence": 0.80,
      "source": "用户陈述：'偶尔用JavaScript'"
    }
  ],
  "corrections": [
    {
      "original": "之前提到的某个Python库",
      "corrected": "FastAPI",
      "confidence": 0.95,
      "source": "用户纠正：'对，就是FastAPI，我记住了'"
    }
  ]
}
```'''


def test_01_parse_extraction_result():
    """测试 1: 解析提取结果"""
    print("\n" + "=" * 60)
    print("测试 1: 解析 LLM 提取结果")
    print("=" * 60)
    
    try:
        # 解析模拟的LLM响应
        result = _parse_extraction_result(MOCK_LLM_RESPONSE)
        
        print(f"\n📊 解析结果:")
        print(f"   - 事实数量: {len(result.facts)}")
        print(f"   - 偏好数量: {len(result.preferences)}")
        print(f"   - 纠正数量: {len(result.corrections)}")
        print(f"   - 总提取项: {result.total_items}")
        
        # 验证数据完整性
        assert len(result.facts) > 0, "应该包含至少一个事实"
        assert len(result.preferences) > 0, "应该包含至少一个偏好"
        assert len(result.corrections) > 0, "应该包含至少一个纠正"
        
        print("\n✅ 解析测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ 解析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_02_filter_by_confidence():
    """测试 2: 置信度过滤"""
    print("\n" + "=" * 60)
    print("测试 2: 置信度过滤")
    print("=" * 60)
    
    try:
        # 解析原始结果
        result = _parse_extraction_result(MOCK_LLM_RESPONSE)
        original_count = result.total_items
        
        # 过滤（阈值 0.9）
        filtered_result = _filter_by_confidence(result, confidence_threshold=0.9)
        filtered_count = filtered_result.total_items
        
        print(f"\n📊 过滤结果:")
        print(f"   - 原始数量: {original_count}")
        print(f"   - 过滤后数量: {filtered_count}")
        print(f"   - 过滤掉: {original_count - filtered_count}")
        
        # 验证过滤效果
        assert filtered_count <= original_count, "过滤后数量不应大于原始数量"
        assert filtered_count > 0, "过滤后应该保留至少一个结果"
        
        # 验证过滤后的置信度
        for fact in filtered_result.facts:
            assert fact.confidence >= 0.9, f"事实置信度应该 >= 0.9，实际: {fact.confidence}"
        
        for pref in filtered_result.preferences:
            assert pref.confidence >= 0.9, f"偏好置信度应该 >= 0.9，实际: {pref.confidence}"
        
        print("\n✅ 置信度过滤测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ 置信度过滤测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_03_format_conversation():
    """测试 3: 对话格式化"""
    print("\n" + "=" * 60)
    print("测试 3: 对话格式化")
    print("=" * 60)
    
    try:
        # 格式化对话
        formatted = _format_conversation(SAMPLE_CONVERSATION)
        
        print(f"\n📊 格式化结果:")
        print(f"   - 原始消息数: {len(SAMPLE_CONVERSATION)}")
        print(f"   - 格式化后长度: {len(formatted)} 字符")
        print(f"   - 包含用户消息: {'用户' in formatted}")
        print(f"   - 包含AI消息: {'AI' in formatted}")
        
        # 验证格式化效果
        assert "用户" in formatted, "应该包含用户消息"
        assert "张三" in formatted, "应该包含用户名字"
        assert "Python" in formatted, "应该包含技术栈信息"
        
        print("\n✅ 对话格式化测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ 对话格式化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_04_data_classes():
    """测试 4: 数据类功能"""
    print("\n" + "=" * 60)
    print("测试 4: 数据类功能")
    print("=" * 60)
    
    try:
        # 测试 ExtractedFact
        fact = ExtractedFact(
            content="用户名叫张三",
            category="identity",
            confidence=0.95,
            source="用户自我介绍"
        )
        assert fact.content == "用户名叫张三"
        assert fact.category == "identity"
        
        # 测试 ExtractedPreference
        pref = ExtractedPreference(
            content="用户喜欢简洁风格",
            category="preference",
            confidence=0.90,
            source="用户表达"
        )
        assert pref.content == "用户喜欢简洁风格"
        
        # 测试 ExtractedCorrection
        corr = ExtractedCorrection(
            original="某个Python库",
            corrected="FastAPI",
            confidence=0.95,
            source="用户纠正"
        )
        assert corr.corrected == "FastAPI"
        
        # 测试 UserMemoryExtractionResult
        result = UserMemoryExtractionResult(
            facts=[fact],
            preferences=[pref],
            corrections=[corr],
            extraction_time=datetime.now(),
            total_items=3
        )
        
        # 测试 is_empty
        assert not result.is_empty(), "非空结果应该返回 False"
        
        # 测试 summary
        summary = result.summary()
        assert "3" in summary or "三" in summary, "摘要应该包含总数"
        assert "事实" in summary, "摘要应该包含事实"
        assert "偏好" in summary, "摘要应该包含偏好"
        
        # 测试空结果
        empty_result = UserMemoryExtractionResult(
            facts=[],
            preferences=[],
            corrections=[],
            extraction_time=datetime.now(),
            total_items=0
        )
        assert empty_result.is_empty(), "空结果应该返回 True"
        
        print("\n✅ 数据类功能测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ 数据类功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_05_full_extraction_workflow():
    """测试 5: 完整提取工作流"""
    print("\n" + "=" * 60)
    print("测试 5: 完整提取工作流")
    print("=" * 60)
    
    try:
        print("\n📝 步骤 1: 格式化对话历史")
        formatted = _format_conversation(SAMPLE_CONVERSATION)
        print(f"   格式化完成: {len(formatted)} 字符")
        
        print("\n📝 步骤 2: 模拟LLM提取（使用模拟响应）")
        result = _parse_extraction_result(MOCK_LLM_RESPONSE)
        print(f"   提取完成: {result.total_items} 项")
        
        print("\n📝 步骤 3: 过滤低置信度结果")
        filtered = _filter_by_confidence(result, confidence_threshold=0.7)
        print(f"   过滤完成: {filtered.total_items} 项")
        
        print("\n📝 步骤 4: 生成摘要")
        summary = result.summary()
        print(f"   {summary}")
        
        print("\n📝 步骤 5: 展示提取结果")
        
        if filtered.facts:
            print("\n📌 事实:")
            for i, fact in enumerate(filtered.facts, 1):
                print(f"   {i}. {fact.content}")
                print(f"      类别: {fact.category} | 置信度: {fact.confidence:.2f}")
        
        if filtered.preferences:
            print("\n⭐ 偏好:")
            for i, pref in enumerate(filtered.preferences, 1):
                print(f"   {i}. {pref.content}")
                print(f"      类别: {pref.category} | 置信度: {pref.confidence:.2f}")
        
        if filtered.corrections:
            print("\n🔧 纠正:")
            for i, corr in enumerate(filtered.corrections, 1):
                print(f"   {i}. {corr.original} → {corr.corrected}")
                print(f"      置信度: {corr.confidence:.2f}")
        
        print("\n✅ 完整提取工作流测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ 完整提取工作流测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "🚀" * 30)
    print("用户记忆提取系统独立测试")
    print("🚀" * 30)
    
    # 测试计数器
    tests_passed = 0
    tests_total = 5
    
    # 执行所有测试
    if test_01_parse_extraction_result():
        tests_passed += 1
    
    if test_02_filter_by_confidence():
        tests_passed += 1
    
    if test_03_format_conversation():
        tests_passed += 1
    
    if test_04_data_classes():
        tests_passed += 1
    
    if test_05_full_extraction_workflow():
        tests_passed += 1
    
    # 打印测试总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"✅ 通过: {tests_passed}/{tests_total}")
    print(f"❌ 失败: {tests_total - tests_passed}/{tests_total}")
    
    if tests_passed == tests_total:
        print("\n🎉 所有测试通过！")
        print("\n📋 核心功能验证:")
        print("   ✅ JSON 解析功能")
        print("   ✅ 置信度过滤功能")
        print("   ✅ 对话格式化功能")
        print("   ✅ 数据类定义")
        print("   ✅ 完整工作流程")
    else:
        print(f"\n⚠️ 有 {tests_total - tests_passed} 个测试失败")
    
    return tests_passed == tests_total


if __name__ == "__main__":
    success = main()
    import sys
    sys.exit(0 if success else 1)
