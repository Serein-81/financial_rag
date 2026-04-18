"""
Agent 工具注册器

负责将 MCP 工具、本地工具和业务工具注册到 ToolManager
"""

import logging
from typing import List

from app.agent_framework.tools.tool_manager import ToolManager
from app.agent_framework.tools.tool_router import TOOL_ROUTING_CONFIG, get_mcp_tools

logger = logging.getLogger(__name__)


def register_business_tools(tool_manager: ToolManager) -> List[str]:
    """
    注册所有业务工具到 ToolManager
    
    注册的工具有：
    - 财务分析工具（FinancialIndicatorTool, FinancialHealthAnalyzer）
    - 税务合规工具（TaxCalculationTool, TaxComplianceChecker）
    - 法律合规工具（ContractEssentialsChecker, LegalClauseMatcher, LaborComplianceChecker, IPRiskChecker）
    - 文档检索工具（DocumentChunkRetrievalTool）
    
    这些工具继承 ToolBase，需要通过 register_tool 方法注册

    Args:
        tool_manager: 工具管理器实例

    Returns:
        已注册的工具名称列表
    """
    from app.agent_framework.tools.base import ToolBase
    from app.agent_framework.tools.financial_analysis_tools import (
        FinancialIndicatorTool,
        FinancialHealthAnalyzer
    )
    from app.agent_framework.tools.tax_compliance_tools import (
        TaxCalculationTool,
        TaxComplianceChecker
    )
    from app.agent_framework.tools.legal_compliance_tools import (
        ContractEssentialsChecker,
        LegalClauseMatcher,
        LaborComplianceChecker,
        IPRiskChecker
    )
    from app.agent_framework.tools.document_retrieval_tools import (
        DocumentChunkRetrievalTool
    )

    business_tools = [
        FinancialIndicatorTool(),
        FinancialHealthAnalyzer(),
        TaxCalculationTool(),
        TaxComplianceChecker(),
        ContractEssentialsChecker(),
        LegalClauseMatcher(),
        LaborComplianceChecker(),
        IPRiskChecker(),
        DocumentChunkRetrievalTool(),
    ]

    registered_tools = []

    for tool in business_tools:
        try:
            if isinstance(tool, ToolBase):
                metadata = tool.get_metadata()
                tool_manager.register_tool(tool)
                registered_tools.append(metadata.name)
                logger.info(f"✅ 注册业务工具: {metadata.name} - {metadata.description[:50]}...")
            else:
                logger.warning(f"⚠️ 跳过非 ToolBase 实例: {type(tool)}")
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 注册业务工具数据错误: {getattr(tool, 'name', 'unknown')} - {e}")
        except (OSError, IOError) as e:
            logger.error(f"❌ 注册业务工具IO错误: {getattr(tool, 'name', 'unknown')} - {e}")
        except Exception as e:
            logger.error(f"❌ 注册业务工具失败: {getattr(tool, 'name', 'unknown')} - {e}")

    return registered_tools


async def register_all_mcp_tools(tool_manager: ToolManager) -> List[str]:
    """
    注册所有 MCP 工具到 ToolManager

    Args:
        tool_manager: 工具管理器实例

    Returns:
        已注册的工具名称列表
    """
    from app.mcp.mcp_tool_proxy import create_mcp_tool_wrapper

    registered_tools = []
    mcp_tools = get_mcp_tools()

    for tool_name in mcp_tools:
        config = TOOL_ROUTING_CONFIG.get(tool_name)
        if not config:
            continue

        try:
            lc_tool = create_mcp_tool_wrapper(tool_name, config)
            tool_manager.register_langchain_tool(lc_tool)
            registered_tools.append(tool_name)
            logger.debug(f"✅ 注册 MCP 工具: {tool_name}")
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 注册 MCP 工具数据错误: {tool_name} - {e}")
        except (OSError, IOError) as e:
            logger.error(f"❌ 注册 MCP 工具IO错误: {tool_name} - {e}")
        except Exception as e:
            logger.error(f"❌ 注册 MCP 工具失败: {tool_name} - {e}")

    return registered_tools


def register_local_tools(tool_manager: ToolManager, tenant_id: str = "default") -> List[str]:
    """
    注册本地工具到 ToolManager

    Args:
        tool_manager: 工具管理器实例
        tenant_id: 租户ID

    Returns:
        已注册的工具名称列表
    """
    from app.tools.agent_tools import get_all_tools

    registered_tools = []

    try:
        local_tools = get_all_tools()

        for lc_tool in local_tools:
            try:
                tool_manager.register_langchain_tool(lc_tool)
                registered_tools.append(lc_tool.name)
                logger.debug(f"✅ 注册本地工具: {lc_tool.name}")
            except (ValueError, KeyError) as e:
                logger.error(f"❌ 注册本地工具数据错误: {lc_tool.name} - {e}")
            except (OSError, IOError) as e:
                logger.error(f"❌ 注册本地工具IO错误: {lc_tool.name} - {e}")
            except Exception as e:
                logger.error(f"❌ 注册本地工具失败: {lc_tool.name} - {e}")

    except (ValueError, KeyError) as e:
        logger.error(f"❌ 注册本地工具数据错误: {e}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 注册本地工具IO错误: {e}")
    except Exception as e:
        logger.error(f"❌ 注册本地工具失败: {e}")

    return registered_tools


async def initialize_tool_manager(
    tool_manager: ToolManager,
    include_mcp: bool = True,
    include_local: bool = True,
    tenant_id: str = "default"
) -> dict:
    """
    初始化工具管理器，注册所有可用工具
    
    根据 TOOL_SOURCE 配置决定工具来源：
    - cloud: 只注册 MCP 工具
    - local: 只注册本地工具
    - auto: 两者都注册，MCP 优先

    Args:
        tool_manager: 工具管理器实例
        include_mcp: 是否包含 MCP 工具
        include_local: 是否包含本地工具
        tenant_id: 租户ID

    Returns:
        注册结果统计
    """
    from app.core.config import settings
    
    tool_source = getattr(settings, 'MCP_MODE', 'cloud')
    
    result = {
        "mcp_tools": [],
        "local_tools": [],
        "total_count": 0,
        "tool_source": tool_source
    }

    logger.info(f"🔧 工具来源配置: {tool_source}")

    if tool_source == "cloud":
        if include_mcp:
            mcp_tools = await register_all_mcp_tools(tool_manager)
            result["mcp_tools"] = mcp_tools
            logger.info(f"☁️ 已注册 {len(mcp_tools)} 个 MCP 工具")
    elif tool_source == "local":
        if include_local:
            local_tools = register_local_tools(tool_manager, tenant_id)
            result["local_tools"] = local_tools
            logger.info(f"📦 已注册 {len(local_tools)} 个本地工具")
    else:
        if include_mcp:
            mcp_tools = await register_all_mcp_tools(tool_manager)
            result["mcp_tools"] = mcp_tools
            logger.info(f"☁️ 已注册 {len(mcp_tools)} 个 MCP 工具")
        
        if include_local:
            local_tools = register_local_tools(tool_manager, tenant_id)
            result["local_tools"] = local_tools
            logger.info(f"📦 已注册 {len(local_tools)} 个本地工具")

    result["total_count"] = len(result["mcp_tools"]) + len(result["local_tools"])

    return result


def get_receptionist_tools_config() -> dict:
    """
    获取接待智能体专用工具配置

    接待智能体需要：
    1. 天气查询
    2. 位置查询
    3. 网络搜索
    4. 知识库检索

    Returns:
        工具配置字典
    """
    return {
        "mcp_tools": ["get_weather", "get_location_info", "search_web"],
        "local_tools": [
            "search_enterprise_knowledge",
            "search_keywords_in_knowledge",
            "search_documents_by_topic",
            "get_knowledge_statistics"
        ]
    }


def get_specialist_tools_config(specialty: str = "general") -> dict:
    """
    获取专家智能体专用工具配置

    Args:
        specialty: 专业领域 (finance/tax/legal/general 或 财务/税务/法律/通用)

    Returns:
        工具配置字典
    """
    specialty_mapping = {
        "finance": "finance",
        "财务": "finance",
        "tax": "tax",
        "税务": "tax",
        "legal": "legal",
        "法律": "legal",
        "general": "general",
        "通用": "general",
    }

    normalized_specialty = specialty_mapping.get(specialty.lower(), "general")

    base_config = {
        "mcp_tools": ["search_web"],
        "local_tools": [
            "search_enterprise_knowledge",
            "search_keywords_in_knowledge",
            "search_documents_by_topic"
        ]
    }

    if normalized_specialty == "finance":
        base_config["mcp_tools"].extend([
            "calculate_asset_liability_ratio",
            "calculate_current_ratio",
            "calculate_quick_ratio",
            "calculate_profit_margin",
            "search_enterprise_info",
            "get_enterprise_detail",
            "assess_enterprise_risk"
        ])

    elif normalized_specialty == "tax":
        base_config["mcp_tools"].extend([
            "calculate_tax_vat",
            "calculate_corporate_tax",
            "calculate_personal_tax"
        ])

    elif normalized_specialty == "legal":
        base_config["mcp_tools"].extend([
            "check_contract_essentials",
            "match_legal_provisions"
        ])

    return base_config
