#!/usr/bin/env python3
"""测试问候语检测修复"""

import sys
sys.path.insert(0, '/app')

from app.services.smart_router import is_greeting_query, _clean_query_for_greeting_check

test_cases = [
    # (输入, 期望结果, 描述)
    ("你好", True, "基础问候"),
    ("你好吗", True, "带语气词"),
    ("你好''", True, "带单引号"),
    ("你好\"", True, "带双引号"),
    ("'你好'", True, "带首尾引号"),
    ("\"你好\"", True, "带首尾双引号"),
    ("你好15", True, "带数字"),
    ("你好..", True, "带重复标点"),
    ("您好", True, "您好"),
    ("hi", True, "hi问候"),
    ("hello", True, "hello问候"),
    ("嗨", True, "嗨"),
    ("在吗", True, "在吗"),
    ("请问你是谁", True, "问身份"),
    ("你是谁", True, "问身份2"),
    ("什么是Python", False, "实际问题"),
    ("如何学习编程", False, "学习问题"),
    ("123测试", False, "测试数据"),
]

print("=" * 80)
print("测试问候语检测修复")
print("=" * 80)

all_passed = True
for test_input, expected, description in test_cases:
    result = is_greeting_query(test_input)
    status = "✅" if result == expected else "❌"
    if result != expected:
        all_passed = False

    print(f"{status} {description:20s} | 输入: {test_input:15s} | 期望: {str(expected):5s} | 实际: {str(result):5s}")

print("=" * 80)
if all_passed:
    print("✅ 所有测试通过!")
else:
    print("❌ 部分测试失败")
print("=" * 80)

# 额外测试清理函数
print("\n清理函数测试:")
print("-" * 80)
clean_tests = [
    ("你好''", "你好"),
    ("你好\"", "你好"),
    ("'你好'", "你好"),
    ("你好15", "你好"),
    ("你好..", "你好"),
    ("  你好  ", "你好"),
]

for input_str, expected_clean in clean_tests:
    cleaned = _clean_query_for_greeting_check(input_str)
    status = "✅" if cleaned == expected_clean else "❌"
    print(f"{status} '{input_str}' -> '{cleaned}' (期望: '{expected_clean}')")
