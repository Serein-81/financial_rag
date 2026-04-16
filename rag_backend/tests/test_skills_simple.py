#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单的 Skills 加载演示
"""

from pathlib import Path

# 模拟加载 skills
skills_dir = Path("app/prompts/skills")

print("=" * 80)
print("Skills 动态加载演示")
print("=" * 80)
print()

# 1. 列出所有可用的 skills
print("📁 可用的 Skills 文件:")
if skills_dir.exists():
    for skill_file in sorted(skills_dir.glob("*.txt")):
        print(f"   ✓ {skill_file.name}")
else:
    print("   ⚠️ Skills 目录不存在")

print()

# 2. 演示动态加载
print("🔧 模拟工具列表:")
tools = [
    {"name": "search_enterprise_knowledge"},
    {"name": "get_weather"},
    {"name": "get_location_info"}
]

for tool in tools:
    print(f"   - {tool['name']}")

print()

# 3. 加载对应的 skills
print("📖 动态加载 Skills:")
for tool in tools:
    skill_path = skills_dir / f"{tool['name']}.txt"
    if skill_path.exists():
        print(f"   ✅ 已加载: {tool['name']}.txt")
        # 读取前3行预览
        with open(skill_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()[:3]
            for line in lines:
                print(f"      {line.rstrip()}")
    else:
        print(f"   ❌ 未找到: {tool['name']}.txt")
    print()

print("=" * 80)
print("✅ 演示完成")
print("=" * 80)
