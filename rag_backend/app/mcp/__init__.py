"""
MCP 统一入口

所有智能体工具统一通过 MCP 协议提供
使用 @local_tool/@cloud_tool 装饰器标记工具类型

架构：
- @local_tool: 本地 STDIO MCP（访问本地数据库）
- @cloud_tool: 云端 MCP HTTP（访问外部 API）
- 云端连接失败自动回退到本地实现
"""

import logging

from app.mcp.decorators import (
    local_tool,
    cloud_tool,
    ToolSource,
    get_registry,
    get_tool_metadata,
    get_tool_source,
    clear_registry,
)

logger = logging.getLogger(__name__)

__all__ = [
    "local_tool",
    "cloud_tool",
    "ToolSource",
    "get_registry",
    "get_tool_metadata",
    "get_tool_source",
    "clear_registry",
    "create_financial_tools",
    "create_financial_health_tools",
    "create_database_tools",
    "create_business_tools",
    "create_cloud_tools",
    "create_orchestrator_tools",
    "create_foundation_tools",
    "get_all_local_tools",
    "get_all_cloud_tools",
    "get_unified_tools",
]


def create_financial_tools():
    """创建财务数据工具"""
    from app.mcp.financial_tools import create_financial_tools as _create
    return _create()


def create_financial_health_tools():
    """创建财务健康报告工具"""
    from app.mcp.financial_health_tools import create_financial_health_tools as _create
    return _create()


def create_database_tools():
    """创建数据库工具"""
    from app.mcp.database_tools import create_database_tools as _create
    return _create()


def create_business_tools():
    """创建业务工具"""
    from app.mcp.business_tools import create_business_tools as _create
    return _create()


def create_cloud_tools():
    """创建云端工具"""
    from app.mcp.cloud_tools import create_cloud_tools as _create
    return _create()


def create_legal_compliance_tools():
    """创建法律合规工具"""
    from app.mcp.legal_compliance_mcp_tools import create_legal_compliance_tools as _create
    return _create()


def create_legal_compliance_tools_v2():
    """创建法律合规增强工具（企业政策匹配）"""
    from app.mcp.legal_compliance_mcp_tools_v2 import (
        contract_compliance_deadline,
        enterprise_policy_matcher,
        enterprise_policy_match_reader,
        dispute_resolution_advisor,
        contract_template_matcher,
        contract_risk_trend_analyzer,
    )
    return [
        contract_compliance_deadline,
        enterprise_policy_matcher,
        enterprise_policy_match_reader,
        dispute_resolution_advisor,
        contract_template_matcher,
        contract_risk_trend_analyzer,
    ]


def create_orchestrator_tools():
    """创建 Orchestrator Agent 专用工具（任务拆解和报告生成）"""
    from app.mcp.orchestrator_tools import create_orchestrator_tools as _create
    return _create()


def create_foundation_tools():
    """创建基础设施工具（时间锚点和派单印章）"""
    from app.mcp.foundation_tools import create_foundation_tools as _create
    return _create()


def get_all_local_tools():
    """获取所有本地工具"""
    tools = []
    tools.extend(create_financial_tools())
    tools.extend(create_financial_health_tools())
    tools.extend(create_database_tools())
    tools.extend(create_business_tools())
    tools.extend(create_legal_compliance_tools())
    tools.extend(create_legal_compliance_tools_v2())
    tools.extend(create_orchestrator_tools())
    tools.extend(create_foundation_tools())
    try:
        from app.services.custom_tool_service import get_published_custom_tool_callables

        tools.extend(get_published_custom_tool_callables())
    except Exception as e:
        logger.warning(f"Failed to load published custom tools: {e}")
    logger.info(f"📦 本地 MCP 工具: {len(tools)} 个")
    return tools


def get_all_cloud_tools():
    """获取所有云端工具"""
    tools = create_cloud_tools()
    logger.info(f"☁️ 云端 MCP 工具: {len(tools)} 个")
    return tools


def get_unified_tools():
    """获取所有工具"""
    local = get_all_local_tools()
    cloud = get_all_cloud_tools()
    logger.info(f"🔧 统一 MCP: 本地 {len(local)} + 云端 {len(cloud)} = {len(local) + len(cloud)} 个")
    return {
        "local": local,
        "cloud": cloud,
        "all": local + cloud
    }
