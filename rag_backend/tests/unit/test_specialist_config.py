"""测试专家工具配置"""
import sys
sys.path.insert(0, '.')

from app.agent_framework.tools.agent_tool_registry import get_specialist_tools_config

print("="*60)
print("各专家工具配置")
print("="*60)

for specialty in ["tax", "finance", "legal", "general"]:
    config = get_specialist_tools_config(specialty)
    print(f"\n【{specialty}】")
    print(f"  MCP 工具 ({len(config['mcp_tools'])}): {config['mcp_tools']}")
    print(f"  本地工具 ({len(config['local_tools'])}): {config['local_tools']}")
