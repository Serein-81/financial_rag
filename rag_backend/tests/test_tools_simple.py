#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单的工具管理演示（不依赖其他模块）
"""

from pathlib import Path

print("=" * 80)
print("🛠️ Agent 工具管理演示")
print("=" * 80)
print()

# 1. 展示工具文件结构
print("📁 工具文件结构:")
print("   app/tools/")
print("   ├── __init__.py")
print("   └── agent_tools.py  (所有工具定义)")
print()

# 2. 展示工具定义方式
print("📝 工具定义示例:")
print("""
@tool(description="天气查询工具...")
async def get_weather(city_name: str) -> str:
    '''根据城市名称查询实时天气'''
    # 工具实现代码
    return result
""")
print()

# 3. 展示工具注册方式
print("📋 工具注册方式:")
print("""
def get_all_tools():
    '''获取所有可用的工具'''
    return [
        search_enterprise_knowledge,
        get_weather,
        get_location_info,
        # 添加新工具只需在这里添加即可
    ]
""")
print()

# 4. 展示 Skills 文件对应关系
print("🔗 工具与 Skills 文件对应关系:")
skills_dir = Path("app/prompts/skills")

if skills_dir.exists():
    skill_files = sorted(skills_dir.glob("*.txt"))
    for skill_file in skill_files:
        tool_name = skill_file.stem
        print(f"   ✓ {tool_name} → {skill_file.name}")
else:
    print("   ⚠️ Skills 目录不存在")

print()

# 5. 展示使用方式
print("💡 在 agent_service.py 中使用:")
print("""
from app.tools import get_all_tools, get_tools_info

class EnterpriseAgentService:
    def __init__(self):
        # 自动获取所有工具
        self.tools = get_all_tools()
        
        # 获取工具信息（用于提示词）
        tools_info = get_tools_info()
""")
print()

# 6. 展示添加新工具的步骤
print("=" * 80)
print("✨ 添加新工具的步骤")
print("=" * 80)
print()
print("步骤 1: 在 app/tools/agent_tools.py 中定义新工具")
print("   @tool(description='新工具描述')")
print("   async def new_tool(param: str) -> str:")
print("       return result")
print()
print("步骤 2: 在 get_all_tools() 函数中注册")
print("   return [")
print("       search_enterprise_knowledge,")
print("       get_weather,")
print("       new_tool,  # 添加这一行")
print("   ]")
print()
print("步骤 3: 创建对应的 skill 文件")
print("   app/prompts/skills/new_tool.txt")
print()
print("步骤 4: 重启服务，新工具自动生效 ✅")
print()

print("=" * 80)
print("✅ 演示完成")
print("=" * 80)
print()
print("📚 相关文件:")
print("   - app/tools/agent_tools.py (工具定义)")
print("   - app/tools/__init__.py (工具导出)")
print("   - app/prompts/skills/*.txt (工具使用说明)")
print("   - app/services/agent_service.py (工具使用)")
print()
