"""
Agent 工具注册器

统一采用 MCP 装饰器（@local_tool/@cloud_tool）注册所有工具
自动使用装饰器元数据获取工具描述和参数
"""

import logging
from typing import List

from app.agent_framework.tools.tool_manager import ToolManager

logger = logging.getLogger(__name__)


async def register_tools(
    tool_manager: ToolManager,
    include_mcp: bool = True,
    include_local: bool = True
) -> dict:
    """
    注册所有 MCP 工具到 ToolManager
    
    自动使用装饰器元数据（@local_tool/@cloud_tool）
    
    Args:
        tool_manager: 工具管理器实例
        include_mcp: 是否包含MCP工具
        include_local: 是否包含本地工具
    
    Returns:
        注册结果统计
    """
    result = {
        "local_tools": [],
        "cloud_tools": [],
        "total_count": 0
    }
    
    logger.info("🔧 注册 MCP 工具...")
    
    from app.mcp import get_unified_tools
    
    unified = get_unified_tools()
    
    if include_local:
        for tool_func in unified["local"]:
            try:
                tool_manager.register_langchain_tool(tool_func)
                result["local_tools"].append(tool_func.name)
                logger.debug(f"✅ 注册本地工具: {tool_func.name}")
            except Exception as e:
                logger.error(f"❌ 注册本地工具失败: {tool_func.name} - {e}")
    
    if include_mcp:
        for tool_func in unified["cloud"]:
            try:
                tool_manager.register_langchain_tool(tool_func)
                result["cloud_tools"].append(tool_func.name)
                logger.debug(f"✅ 注册云端工具: {tool_func.name}")
            except Exception as e:
                logger.error(f"❌ 注册云端工具失败: {tool_func.name} - {e}")
    
    result["total_count"] = len(result["local_tools"]) + len(result["cloud_tools"])
    
    logger.info(f"✅ 工具注册完成：本地 {len(result['local_tools'])} + 云端 {len(result['cloud_tools'])} = {result['total_count']} 个")
    
    return result


async def initialize_tool_manager(
    tool_manager: ToolManager,
    include_mcp: bool = True,
    include_local: bool = True,
    tenant_id: str = "default"
) -> dict:
    """
    初始化工具管理器
    
    Args:
        tool_manager: 工具管理器实例
        include_mcp: 是否包含MCP工具
        include_local: 是否包含本地工具
        tenant_id: 租户ID
    
    Returns:
        注册结果统计
    """
    return await register_tools(
        tool_manager,
        include_mcp=include_mcp,
        include_local=include_local
    )


def get_receptionist_tools_config() -> dict:
    """接待智能体工具配置"""
    return {
        "mcp_tools": ["get_weather", "get_location_info", "search_web"],
        "local_tools": ["search_enterprise_knowledge", "search_keywords_in_knowledge"]
    }


def get_specialist_tools_config(specialty: str = "general") -> dict:
    """专家智能体工具配置"""
    specialty_aliases = {
        "财务": "finance",
        "财经": "finance",
        "finance": "finance",
        "financial": "finance",
        "税务": "tax",
        "税法": "tax",
        "tax": "tax",
        "法律": "legal",
        "法务": "legal",
        "legal": "legal",
        "通用": "general",
        "general": "general",
    }
    specialty_key = specialty_aliases.get((specialty or "general").lower(), specialty or "general")

    mapping = {
        "finance": [
            "calculate_asset_liability_ratio",
            "calculate_current_ratio",
            "calculate_quick_ratio",
            "get_financial_health_snapshot",
            "get_critical_anomalies",
            "analyze_metric_safety_trend",
            "search_web",
        ],
        "tax": [
            "calculate_tax_vat",
            "calculate_corporate_tax",
            "calculate_personal_tax",
            "search_web",
        ],
        "legal": [
            "check_contract_essentials",
            "match_legal_provisions",
            "extract_contract_clauses",
            "verify_compliance_rule",
            "trace_entity_risk_network",
            "search_web",
        ],
    }
    
    if specialty_key.lower() == "general":
        return {
            "mcp_tools": ["*"],
            "local_tools": ["*"]
        }

    tools = mapping.get(specialty_key.lower(), [])
    
    return {
        "mcp_tools": tools,
        "local_tools": ["search_enterprise_knowledge"]
    }
