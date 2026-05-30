"""
Agent 工具注册器

统一采用 MCP 装饰器（@local_tool/@cloud_tool）注册所有工具，
同时注册 ToolBase 领域工具类（确定性计算）。

重复工具说明
------------
cloud_tools.py 中的以下工具与 ToolBase 工具功能重复：
  - calculate_tax_vat / calculate_corporate_tax / calculate_personal_tax
    → 由 tax_calculator（ToolBase）和 calculate_tax（ToolBase）替代
  - check_contract_essentials → 由 contract_essentials_checker（ToolBase）替代
  - match_legal_provisions     → 由 legal_clause_matcher（ToolBase）替代

这些 cloud_tools 函数仍保留在 ToolManager 全局注册（供 general 和非专家场景），
但在 get_specialist_tools_config 中已从对应专家的工具列表中移除，
避免 LLM function calling 时看到语义相同的重复工具。
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
    注册所有 MCP 工具到 ToolManager。

    Returns:
        注册结果统计 dict
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
    logger.info(
        f"✅ MCP 工具注册完成：本地 {len(result['local_tools'])} + "
        f"云端 {len(result['cloud_tools'])} = {result['total_count']} 个"
    )
    return result


async def initialize_tool_manager(
    tool_manager: ToolManager,
    include_mcp: bool = True,
    include_local: bool = True,
    tenant_id: str = "default"
) -> dict:
    """
    初始化工具管理器：MCP 工具 + ToolBase 领域工具 + 代码解释器。
    """
    result = await register_tools(
        tool_manager,
        include_mcp=include_mcp,
        include_local=include_local
    )

    # ── 注册 ToolBase 领域工具类（确定性计算，不依赖 LLM）──
    toolbase_registered: list = []
    try:
        from app.agent_framework.tools.financial_data_tools import (
            FinancialDataQueryTool,   # query_user_financial_data  — 查询真实 DB
            TaxCalculationTool as FinTaxCalcTool,  # calculate_tax
            TaxRecommendationTool,    # get_tax_recommendations
        )
        from app.agent_framework.tools.tax_compliance_tools import (
            TaxCalculationTool as TaxCalcTool,  # tax_calculator（多税种/超额累进）
            TaxComplianceChecker,               # tax_compliance_checker
        )
        from app.agent_framework.tools.legal_compliance_tools import (
            ContractEssentialsChecker,  # contract_essentials_checker
            LegalClauseMatcher,         # legal_clause_matcher
            LaborComplianceChecker,     # labor_compliance_checker
            IPRiskChecker,              # ip_risk_checker
        )

        domain_tools = [
            FinancialDataQueryTool(),
            FinTaxCalcTool(),
            TaxRecommendationTool(),
            TaxCalcTool(),
            TaxComplianceChecker(),
            ContractEssentialsChecker(),
            LegalClauseMatcher(),
            LaborComplianceChecker(),
            IPRiskChecker(),
        ]
        for tool in domain_tools:
            try:
                tool_manager.register_tool(tool)
                toolbase_registered.append(tool.name)
            except Exception as e:
                logger.warning(f"[工具注册] ToolBase 工具注册失败: {tool.name} - {e}")

        logger.info(f"✅ ToolBase 领域工具注册完成：{len(toolbase_registered)} 个")
    except Exception as e:
        logger.error(f"❌ ToolBase 工具类导入失败: {e}")

    # ── 注册代码解释器（execute_python）──
    # code_interpreter.py 使用 @auto_register_tool，但该装饰器挂载在模块级全局列表上，
    # 必须显式导入模块触发装饰器，再手动把函数注册进 ToolManager。
    code_registered: list = []
    try:
        from app.agent_framework.tools.code_interpreter import execute_python
        from app.agent_framework.tools.decorators import get_auto_registered_tools

        for meta in get_auto_registered_tools():
            if meta.get("name") == "execute_python":
                tool_manager.register_function(
                    name="execute_python",
                    func=execute_python,
                    description=meta.get("description", "在沙箱中执行 Python 代码，支持 math/json/re/datetime 等安全模块"),
                )
                code_registered.append("execute_python")
                logger.info("✅ 代码解释器工具 execute_python 注册完成")
                break
    except Exception as e:
        logger.warning(f"[工具注册] execute_python 注册失败（非致命）: {e}")

    result["toolbase_tools"] = toolbase_registered
    result["code_tools"] = code_registered
    result["total_count"] = (
        result.get("total_count", 0) + len(toolbase_registered) + len(code_registered)
    )
    return result


def get_receptionist_tools_config() -> dict:
    """接待智能体工具配置"""
    return {
        "mcp_tools": ["search_web"],
        "local_tools": ["search_enterprise_knowledge", "search_keywords_in_knowledge",
                        "get_current_time_and_context"],
    }


def get_specialist_tools_config(specialty: str = "general") -> dict:
    """
    各专家 Agent 可用工具列表（用于 _build_openai_tools 过滤）。

    重复工具处理原则：
    - 税务专家：移除 cloud_tools 的 calculate_tax_vat/corporate/personal，
      改用 ToolBase 的 tax_calculator / calculate_tax（结果更可靠、支持合规检查）
    - 法律专家：移除 cloud_tools 的 check_contract_essentials / match_legal_provisions，
      改用 ToolBase 的 contract_essentials_checker / legal_clause_matcher
    - 财务专家：保留 cloud_tools 的资产负债/流动比率（纯公式计算，无 ToolBase 对应），
      移除 calculate_profit_margin（财务专家不走税务计算），
      ToolBase 的 query_user_financial_data 提供真实数据查询
    """
    specialty_aliases = {
        "财务": "finance", "财经": "finance", "finance": "finance", "financial": "finance",
        "税务": "tax", "税法": "tax", "tax": "tax",
        "法律": "legal", "法务": "legal", "legal": "legal",
        "通用": "general", "general": "general",
    }
    specialty_key = specialty_aliases.get((specialty or "general").lower(), specialty or "general")

    mapping = {
        "finance": {
            # MCP：财务比率计算（纯公式，无 ToolBase 对应）+ 财务健康快照 + 搜索
            "mcp_tools": [
                "calculate_asset_liability_ratio",
                "calculate_current_ratio",
                "calculate_quick_ratio",
                "get_financial_health_snapshot",
                "get_critical_anomalies",
                "analyze_metric_safety_trend",
                "get_financial_overview",
                "get_financial_trend",
                "search_web",
                "get_current_time_and_context",
            ],
            # ToolBase：查询真实 DB 数据 + 税务计算（财务报告场景）
            # 注：get_tax_recommendations 需要预处理数据，LLM 无法直接调用，已移除
            "local_tools": [
                "query_user_financial_data",
                "calculate_tax",
                "search_enterprise_knowledge",
            ],
        },
        "tax": {
            # MCP：联网搜索税法政策 + 时间基准
            "mcp_tools": [
                "search_web",
                "get_current_time_and_context",
            ],
            # ToolBase：查询真实数据 + 税种计算 + 代码计算
            # 注：tax_compliance_checker 和 get_tax_recommendations 需要预处理的复杂
            #      结构体入参（tax_data、financial_data+tax_results），LLM 无法直接构造，
            #      调用必然失败（0ms 即报错）。已从此列表移除，避免无效重试浪费时间。
            "local_tools": [
                "query_user_financial_data",
                "tax_calculator",
                "calculate_tax",
                "search_enterprise_knowledge",
                "execute_python",
            ],
        },
        "legal": {
            # MCP：合同条款提取（ToolBase 无对应）+ 合规验证 + 实体风险网络 + v2 增强工具 + 搜索
            # 注：check_contract_essentials / match_legal_provisions 已被 ToolBase 替代
            "mcp_tools": [
                "extract_contract_clauses",
                "verify_compliance_rule",
                "trace_entity_risk_network",
                "contract_compliance_deadline",
                "enterprise_policy_matcher",
                "dispute_resolution_advisor",
                "contract_template_matcher",
                "contract_risk_trend_analyzer",
                "search_web",
                "get_current_time_and_context",
            ],
            # ToolBase：合同必备条款检查 + 条款匹配 + 劳动合规 + 知识产权风险
            "local_tools": [
                "contract_essentials_checker",
                "legal_clause_matcher",
                "labor_compliance_checker",
                "ip_risk_checker",
                "search_enterprise_knowledge",
            ],
        },
    }

    if specialty_key.lower() == "general":
        # 通用智能体：全量工具，LLM 自行决策
        return {"mcp_tools": ["*"], "local_tools": ["*"]}

    return mapping.get(specialty_key.lower(), {"mcp_tools": [], "local_tools": []})
