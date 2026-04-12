#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试变量替换"""

import re

template_line = '  "reflection_round": {reflection_round},'
context = {
    'reflection_round': 1,
}

pattern = r'\{([^}]+)\}'

print("原始行:")
print(template_line)
print()

matches = list(re.finditer(pattern, template_line))
print(f"找到 {len(matches)} 个匹配:")
for i, match in enumerate(matches, 1):
    print(f"  匹配 {i}: '{match.group(0)}' -> 组1: '{match.group(1)}'")
print()

# 手动替换
def replace_var(match):
    var_path = match.group(1).strip()
    value = context.get(var_path)
    if value is None:
        return match.group(0)
    return str(value)

result = re.sub(pattern, replace_var, template_line)
print("替换后:")
print(result)
print()

if '{reflection_round}' in result:
    print("❌ 仍然包含 {reflection_round}")
else:
    print("✅ 已正确替换")
