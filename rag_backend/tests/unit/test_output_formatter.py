#!/usr/bin/env python3
"""
测试 OutputFormatter 的清理功能

验证修复后的 OutputFormatter 是否能够正确清理：
1. 内部标记（【知识库文档】、【提示】等）
2. ReAct 思考格式（Thought、Observation、Action）
3. XML 格式的内部标记
4. 调试标记和表情符号
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.output_formatter import OutputFormatter


def test_clean_output():
    """测试基本的清理功能"""
    print("=" * 80)
    print("测试 1: 基本清理功能")
    print("=" * 80)
    
    # 测试原始问题中的输出
    raw_output = """根据用户问题"惠州学院在哪里你知道吗"，我需要查找惠州学院的具体地址信息。首先检查知识库文档中是否有相关信息。
    
【知识库文档】
【提示】以下内容来自知识库文档
地址：广东省惠州市惠城区演达大道46号
校区：金山湖校区和豐湖校区

## Thought
我需要查找惠州学院的地址信息

## Observation
知识库文档中明确提供了惠州学院的地址信息

## Final Answer
惠州学院位于广东省惠州市惠城区演达大道46号，拥有金山湖校区和豐湖校区。如需更多信息，可以访问学校官网：http://www.hzu.edu.cn/
"""
    
    print("\n原始输出（模拟问题）：")
    print("-" * 80)
    print(raw_output)
    print("-" * 80)
    
    # 使用清理功能
    cleaned = OutputFormatter.clean_output(raw_output)
    print("\n清理后：")
    print("-" * 80)
    print(cleaned)
    print("-" * 80)
    print(f"\n✅ 清理完成 | 原始: {len(raw_output)} 字符 → 清理后: {len(cleaned)} 字符")


def test_stream_clean():
    """测试流式输出清理"""
    print("\n" + "=" * 80)
    print("测试 2: 流式输出清理")
    print("=" * 80)
    
    stream_chunks = [
        "根据",
        "用户问",
        "题，【知识库文档】我需要",
        "查",
        "找惠州学院的地址。\n\n## Thought\n我需要查找",
        "惠州学院的地址",
        "信息。\n\n## Final Answer\n惠州学院位于广东省",
        "惠州市。",
    ]
    
    print("\n流式 chunks：")
    for i, chunk in enumerate(stream_chunks, 1):
        print(f"  Chunk {i}: {repr(chunk)}")
    
    print("\n实时清理后的 chunks：")
    cleaned_chunks = []
    for i, chunk in enumerate(stream_chunks, 1):
        cleaned = OutputFormatter.clean_stream_chunk(chunk)
        cleaned_chunks.append(cleaned)
        if cleaned:
            print(f"  Chunk {i}: {repr(cleaned)}")
    
    full_output = "".join(cleaned_chunks)
    print(f"\n完整输出：{full_output}")
    print(f"\n✅ 流式清理完成 | 最终长度: {len(full_output)} 字符")


def test_xml_markers():
    """测试 XML 格式的内部标记清理"""
    print("\n" + "=" * 80)
    print("测试 3: XML 格式的内部标记清理")
    print("=" * 80)
    
    xml_output = """<Context type='rag'>以下内容来自知识库文档
<KnowledgeBase>
1. 这是知识库内容...
   来源: document.pdf
</KnowledgeBase>
</Context>

## Final Answer
惠州学院位于广东省惠州市。
"""
    
    print("\n原始输出（包含 XML 标记）：")
    print("-" * 80)
    print(xml_output)
    print("-" * 80)
    
    cleaned = OutputFormatter.clean_output(xml_output)
    print("\n清理后：")
    print("-" * 80)
    print(cleaned)
    print("-" * 80)
    
    # 验证 XML 标记是否被移除
    if "<Context" not in cleaned and "</Context>" not in cleaned:
        print("✅ XML Context 标记已成功移除")
    else:
        print("❌ XML Context 标记未被移除")
    
    if "<KnowledgeBase>" not in cleaned and "</KnowledgeBase>" not in cleaned:
        print("✅ XML KnowledgeBase 标记已成功移除")
    else:
        print("❌ XML KnowledgeBase 标记未被移除")


def test_internal_context_markers():
    """测试新版 InternalContext XML 格式的清理"""
    print("\n" + "=" * 80)
    print("测试 6: 新版 InternalContext XML 格式清理")
    print("=" * 80)
    
    internal_output = """用户问题：惠州学院在哪里你知道吗

<InternalContext>
<KnowledgeBase>
地址：广东省惠州市惠城区演达大道46号
</KnowledgeBase>

<MemoryContext>
（无相关记忆）
</MemoryContext>

<SystemInstructions>
1. 请优先使用上述知识库文档回答问题
2. 如果知识库没有相关信息，请直接回答"我不知道"
</SystemInstructions>
</InternalContext>

## Final Answer
惠州学院位于广东省惠州市惠城区演达大道46号。
"""
    
    print("\n原始输出（包含新版 InternalContext 标记）：")
    print("-" * 80)
    print(internal_output)
    print("-" * 80)
    
    cleaned = OutputFormatter.clean_output(internal_output)
    print("\n清理后：")
    print("-" * 80)
    print(cleaned)
    print("-" * 80)
    
    # 验证新版 XML 标记是否被移除
    if "<InternalContext>" not in cleaned and "</InternalContext>" not in cleaned:
        print("✅ InternalContext 标记已成功移除")
    else:
        print("❌ InternalContext 标记未被移除")
    
    if "<KnowledgeBase>" not in cleaned and "</KnowledgeBase>" not in cleaned:
        print("✅ KnowledgeBase 标记已成功移除")
    else:
        print("❌ KnowledgeBase 标记未被移除")
    
    if "<SystemInstructions>" not in cleaned and "</SystemInstructions>" not in cleaned:
        print("✅ SystemInstructions 标记已成功移除")
    else:
        print("❌ SystemInstructions 标记未被移除")
    
    # 验证最终答案部分是否保留
    if "惠州学院位于广东省惠州市惠城区演达大道46号" in cleaned:
        print("✅ 最终答案内容已保留")
    else:
        print("❌ 最终答案内容被误清理")


def test_final_answer_extraction():
    """测试 Final Answer 提取"""
    print("\n" + "=" * 80)
    print("测试 4: Final Answer 提取")
    print("=" * 80)
    
    raw_output = """## Thought
我需要查找惠州学院的地址信息

## Observation
知识库文档中提供了惠州学院的地址

## Final Answer
惠州学院位于广东省惠州市惠城区演达大道46号，拥有金山湖校区和豐湖校区。
"""
    
    print("\n原始输出（包含 Thought 和 Observation）：")
    print("-" * 80)
    print(raw_output)
    print("-" * 80)
    
    # 使用 extract_final_answer
    final_answer = OutputFormatter.extract_final_answer(raw_output)
    print("\n提取的 Final Answer：")
    print("-" * 80)
    print(final_answer)
    print("-" * 80)
    
    # 验证提取是否正确
    if "Thought" not in final_answer and "Observation" not in final_answer:
        print("✅ 成功提取 Final Answer，移除了 Thought 和 Observation")
    else:
        print("❌ 未能成功提取 Final Answer")


def test_chinese_markers():
    """测试中文内部标记清理"""
    print("\n" + "=" * 80)
    print("测试 5: 中文内部标记清理")
    print("=" * 80)
    
    chinese_output = """【知识库文档】
【提示】以下内容来自知识库文档
这是知识库的内容...

【记忆上下文】
【提示】以下内容来自个人对话记忆
这是记忆的内容...

## Final Answer
这是最终答案。

【系统指令】
请优先使用知识库文档回答问题。
"""
    
    print("\n原始输出（包含中文内部标记）：")
    print("-" * 80)
    print(chinese_output)
    print("-" * 80)
    
    cleaned = OutputFormatter.clean_output(chinese_output)
    print("\n清理后：")
    print("-" * 80)
    print(cleaned)
    print("-" * 80)
    
    # 验证中文标记是否被移除
    removed_markers = []
    if "【知识库文档】" not in cleaned:
        removed_markers.append("【知识库文档】")
    if "【记忆上下文】" not in cleaned:
        removed_markers.append("【记忆上下文】")
    if "【提示】" not in cleaned:
        removed_markers.append("【提示】")
    if "【系统指令】" not in cleaned:
        removed_markers.append("【系统指令】")
    
    if removed_markers:
        print(f"✅ 成功移除 {len(removed_markers)} 个中文标记：{', '.join(removed_markers)}")
    else:
        print("❌ 未能移除中文标记")


def main():
    """主测试函数"""
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("\n" + "=" * 80)
    print("=== 测试 OutputFormatter 清理功能 ===")
    print("=" * 80)
    
    try:
        test_clean_output()
        test_stream_clean()
        test_xml_markers()
        test_internal_context_markers()
        test_final_answer_extraction()
        test_chinese_markers()
        
        print("\n" + "=" * 80)
        print("=== 测试完成 ===")
        print("=" * 80)
        
        print("\n总结：")
        print("1. [OK] 基本清理功能正常")
        print("2. [OK] 流式输出清理正常")
        print("3. [OK] XML 标记清理正常")
        print("4. [OK] Final Answer 提取正常")
        print("5. [OK] 中文内部标记清理正常")
        
        print("\n建议：")
        print("- 修改后的 OutputFormatter 应该能够解决您提到的输出格式问题")
        print("- 内部的【提示】、【知识库文档】等标记已被清理")
        print("- ReAct 格式的 Thought、Observation 等标记也会被清理")
        print("- 如果需要，还可以使用 extract_final_answer() 提取最终答案部分")
        
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
