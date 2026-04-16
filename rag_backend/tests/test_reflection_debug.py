#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""临时调试脚本，检查反思模板渲染"""

import sys
sys.path.insert(0, 'd:/Python/Codebase/My_rag/rag_backend')

from test_template_simple import SimplePromptEngine

engine = SimplePromptEngine()
context = {
    'original_task': '分析公司2024年的财务状况',
    'current_answer': '公司2024年收入增长10%',
    'reflection_round': 1,
    'max_reflections': 3,
    'previous_reflections': [],
    'tool_outputs': [
        {'name': '财务分析', 'content': '数据已提取'},
    ]
}
result = engine.render('reflection', context, load_skills=False)

# 打印包含 reflection_round 的行
print("包含 'reflection_round' 的行:")
print("-" * 60)
for i, line in enumerate(result.split('\n'), 1):
    if 'reflection_round' in line:
        print(f"行 {i}: {line}")

print("\n" + "=" * 60)
print("检查 {reflection_round} 是否在结果中:")
print("=" * 60)
if '{reflection_round}' in result:
    print("❌ {reflection_round} 仍然在结果中！")
else:
    print("✅ {reflection_round} 已被替换")

if '第 1 轮反思' in result:
    print("✅ '第 1 轮反思' 在结果中")
else:
    print("❌ '第 1 轮反思' 不在结果中")

print("\n" + "=" * 60)
print("打印完整的渲染结果 (JSON 部分附近):")
print("=" * 60)
lines = result.split('\n')
for i in range(65, 85):
    if i < len(lines):
        print(f"{i+1:3d}: {lines[i]}")
