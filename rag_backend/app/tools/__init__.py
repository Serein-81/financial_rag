# app/tools/__init__.py

"""
Agent 工具模块

集中管理所有 Agent 可用的工具：
- 本地工具：RAG检索、数据库访问等
- MCP工具：通过远程MCP服务器调用的计算类工具

工具分类：
- 本地工具 (LOCAL): RAG检索、数据库访问等需要本地资源的工具
- MCP工具 (MCP): 税务计算、财务分析、法律匹配、企业查询等通过远程MCP服务器调用的工具
"""

from .agent_tools import (
    get_all_tools,
    get_tool_names,
    get_tools_info,
    print_tools_summary,
    search_enterprise_knowledge,
)

from app.agent_framework.tools.tool_router import (
    get_local_tools,
    get_mcp_tools,
    get_tool_config,
    is_mcp_tool,
    is_local_tool,
    get_tool_system_instruction,
    ToolCategory,
)

__all__ = [
    # 本地工具
    "get_all_tools",
    "get_tool_names",
    "get_tools_info",
    "print_tools_summary",
    "search_enterprise_knowledge",
    # 工具路由
    "get_local_tools",
    "get_mcp_tools",
    "get_tool_config",
    "is_mcp_tool",
    "is_local_tool",
    "get_tool_system_instruction",
    "ToolCategory",
]
