"""
工具路由配置

定义工具分类和调用策略：
- LOCAL: 本地工具（数据库访问、RAG检索、文件操作等）
- MCP: 云端 MCP 工具（计算、查询外部API等）

Agent 根据工具类型决定何时使用本地工具，何时使用 MCP 工具
"""

from enum import Enum
from typing import Dict, List, Optional


class ToolCategory(Enum):
    """工具分类枚举"""
    LOCAL = "local"          # 本地工具（必须）
    MCP = "mcp"              # MCP 远程工具
    COMPUTATION = "computation"  # 计算类工具


TOOL_ROUTING_CONFIG: Dict[str, Dict] = {
    # ==========================================
    # 本地工具（LOCAL）- 数据库、RAG、文件操作、网络搜索
    # ==========================================
    "search_enterprise_knowledge": {
        "category": ToolCategory.LOCAL,
        "description": "企业知识库检索 - 搜索公司制度、业务文档等内部资料",
        "fallback": None,
        "retry": True,
    },
    "search_keywords_in_knowledge": {
        "category": ToolCategory.LOCAL,
        "description": "关键词精确搜索 - 在知识库中查找包含特定关键词的文档",
        "fallback": None,
        "retry": True,
    },
    "search_documents_by_topic": {
        "category": ToolCategory.LOCAL,
        "description": "文档级搜索 - 按主题查找相关文档列表",
        "fallback": None,
        "retry": True,
    },
    "list_knowledge_documents": {
        "category": ToolCategory.LOCAL,
        "description": "列出知识库文档 - 查看知识库中已上传的所有文档列表",
        "fallback": None,
        "retry": True,
    },
    "get_knowledge_statistics": {
        "category": ToolCategory.LOCAL,
        "description": "知识库统计 - 获取关键词在知识库中的统计信息",
        "fallback": None,
        "retry": True,
    },
    "get_enterprise_kb_overview": {
        "category": ToolCategory.LOCAL,
        "description": "企业知识库概览 - 查询企业拥有多少个知识库，以及每个知识库中有多少文档",
        "fallback": None,
        "retry": True,
    },

    # ==========================================
    # 本地财务数据库查询工具（LOCAL）- 直接访问本地财务数据库
    # ==========================================
    "query_financial_data": {
        "category": ToolCategory.LOCAL,
        "description": "财务数据查询 - 从数据库查询详细财务记录，支持聚合分析",
        "fallback": None,
        "retry": True,
    },
    "get_financial_overview": {
        "category": ToolCategory.LOCAL,
        "description": "财务概览 - 获取企业财务汇总信息（总收入、总支出、利润等）",
        "fallback": None,
        "retry": True,
    },
    "get_financial_trend": {
        "category": ToolCategory.LOCAL,
        "description": "财务趋势 - 获取财务数据趋势分析（同比、环比变化）",
        "fallback": None,
        "retry": True,
    },
    "search_financial_data": {
        "category": ToolCategory.LOCAL,
        "description": "财务搜索 - 按关键词或条件搜索财务数据记录",
        "fallback": None,
        "retry": True,
    },
    
    "search_web": {
        "category": ToolCategory.MCP,
        "description": "网络搜索工具 - 搜索互联网获取实时信息和最新资讯",
        "input_params": ["query", "max_results"],
        "example": "search_web(query='最新税法政策 2024', max_results=5)",
    },

    # ==========================================
    # MCP 远程工具（MCP）- 纯计算类
    # ==========================================
    "calculate_tax_vat": {
        "category": ToolCategory.MCP,
        "description": "增值税计算器 - 根据含税销售额计算增值税税额",
        "input_params": ["taxable_amount", "tax_rate"],
        "example": "calculate_tax_vat(taxable_amount=10000, tax_rate=0.13)",
    },
    "calculate_corporate_tax": {
        "category": ToolCategory.MCP,
        "description": "企业所得税计算器 - 计算企业所得税，支持小微企业优惠",
        "input_params": ["revenue", "deductible_expenses", "is_small_enterprise"],
        "example": "calculate_corporate_tax(revenue=1000000, deductible_expenses=600000, is_small_enterprise=true)",
    },
    "calculate_personal_tax": {
        "category": ToolCategory.MCP,
        "description": "个人所得税计算器 - 使用超额累进税率计算个税",
        "input_params": ["monthly_income", "special_deductions"],
        "example": "calculate_personal_tax(monthly_income=30000, special_deductions=5000)",
    },
    "check_contract_essentials": {
        "category": ToolCategory.MCP,
        "description": "合同必备条款检查 - 检查合同是否包含法律要求的必备条款",
        "input_params": ["contract_text"],
        "example": "check_contract_essentials(contract_text='甲乙双方...')",
    },
    "match_legal_provisions": {
        "category": ToolCategory.MCP,
        "description": "法律条款智能匹配 - 根据合同内容匹配相关法律条款",
        "input_params": ["contract_text", "law_type"],
        "example": "match_legal_provisions(contract_text='...', law_type='contract')",
    },
    "extract_contract_clauses": {
        "category": ToolCategory.MCP,
        "description": "合同条款精确提取 - 从合同审核报告中提取特定类型的法律条款原文",
        "input_params": ["tenant_id", "report_id", "clause_category"],
        "example": "extract_contract_clauses(tenant_id='xxx', report_id='yyy', clause_category='breach_of_contract')",
    },
    "verify_compliance_rule": {
        "category": ToolCategory.MCP,
        "description": "合规性交叉比对 - 将业务动作与法规库比对，验证合规性",
        "input_params": ["tenant_id", "action_summary", "domain"],
        "example": "verify_compliance_rule(tenant_id='xxx', action_summary='收集用户浏览记录', domain='privacy')",
    },
    "trace_entity_risk_network": {
        "category": ToolCategory.MCP,
        "description": "实体风险网络追踪 - 利用知识图谱进行股权穿透和风险关联分析",
        "input_params": ["tenant_id", "entity_name", "penetration_depth"],
        "example": "trace_entity_risk_network(tenant_id='xxx', entity_name='阿里巴巴', penetration_depth=3)",
    },
    "calculate_asset_liability_ratio": {
        "category": ToolCategory.MCP,
        "description": "资产负债率计算 - 评估企业长期偿债能力和风险水平",
        "input_params": ["total_liabilities", "total_assets"],
        "example": "calculate_asset_liability_ratio(total_liabilities=5000000, total_assets=10000000)",
    },
    "calculate_current_ratio": {
        "category": ToolCategory.MCP,
        "description": "流动比率计算 - 评估企业短期偿债能力",
        "input_params": ["current_assets", "current_liabilities"],
        "example": "calculate_current_ratio(current_assets=3000000, current_liabilities=1500000)",
    },
    "calculate_quick_ratio": {
        "category": ToolCategory.MCP,
        "description": "速动比率计算 - 评估企业立即偿债能力（不含存货）",
        "input_params": ["current_assets", "inventory", "current_liabilities"],
        "example": "calculate_quick_ratio(current_assets=3000000, inventory=800000, current_liabilities=1500000)",
    },
    "calculate_profit_margin": {
        "category": ToolCategory.MCP,
        "description": "净利润率计算 - 评估企业盈利能力",
        "input_params": ["net_profit", "total_revenue"],
        "example": "calculate_profit_margin(net_profit=500000, total_revenue=5000000)",
    },
    "search_enterprise_info": {
        "category": ToolCategory.MCP,
        "description": "企业信息搜索 - 根据名称或信用代码搜索企业基本信息",
        "input_params": ["keyword"],
        "example": "search_enterprise_info(keyword='阿里巴巴')",
    },
    "get_enterprise_detail": {
        "category": ToolCategory.MCP,
        "description": "企业详细信息查询 - 获取企业的工商信息、股东结构等",
        "input_params": ["enterprise_id"],
        "example": "get_enterprise_detail(enterprise_id='91110000xxxx')",
    },
    "assess_enterprise_risk": {
        "category": ToolCategory.MCP,
        "description": "企业风险评估 - 综合评估企业的经营风险、法律风险、财务风险",
        "input_params": ["enterprise_id", "risk_types"],
        "example": "assess_enterprise_risk(enterprise_id='91110000xxxx', risk_types=['operational', 'legal'])",
    },

    # ==========================================
    # MCP 外部服务工具 - 天气、位置（这些是真正的 MCP 工具）
    # ==========================================
    "get_weather": {
        "category": ToolCategory.MCP,
        "description": "天气查询工具 - 查询指定城市的实时天气，包括温度、湿度、风向等",
        "input_params": ["city_name"],
        "example": "get_weather(city_name='北京')",
    },
    "get_location_info": {
        "category": ToolCategory.MCP,
        "description": "地理位置查询工具 - 查询地址的经纬度和行政区划信息",
        "input_params": ["address"],
        "example": "get_location_info(address='北京市海淀区中关村大街1号')",
    },
    # ⚠️ search_web 已移至 agent_tools.py 作为本地工具，直接调用 Tavily API
}


def get_local_tools() -> List[str]:
    """获取所有本地工具名称"""
    return [
        name for name, config in TOOL_ROUTING_CONFIG.items()
        if config["category"] == ToolCategory.LOCAL
    ]


def get_mcp_tools() -> List[str]:
    """获取所有 MCP 工具名称"""
    return [
        name for name, config in TOOL_ROUTING_CONFIG.items()
        if config["category"] == ToolCategory.MCP
    ]


def get_tool_config(tool_name: str) -> Optional[Dict]:
    """获取工具配置"""
    return TOOL_ROUTING_CONFIG.get(tool_name)


def is_mcp_tool(tool_name: str) -> bool:
    """判断是否为 MCP 工具"""
    config = get_tool_config(tool_name)
    return config is not None and config["category"] == ToolCategory.MCP


def is_local_tool(tool_name: str) -> bool:
    """判断是否为本地工具"""
    config = get_tool_config(tool_name)
    return config is not None and config["category"] == ToolCategory.LOCAL


def get_tools_by_category(category: ToolCategory) -> Dict[str, Dict]:
    """按分类获取工具配置"""
    return {
        name: config
        for name, config in TOOL_ROUTING_CONFIG.items()
        if config["category"] == category
    }


def get_tool_system_instruction() -> str:
    """
    生成工具使用指南，用于注入到 Agent 的 System Prompt
    
    Returns:
        工具使用指南文本
    """
    local_tools = get_local_tools()
    mcp_tools = get_mcp_tools()
    
    local_desc = "\n".join([
        f"  - {name}: {TOOL_ROUTING_CONFIG[name]['description']}"
        for name in local_tools
    ])
    
    mcp_desc = "\n".join([
        f"  - {name}: {TOOL_ROUTING_CONFIG[name]['description']}"
        for name in mcp_tools
    ])
    
    return f"""
## 🔧 工具使用策略

### 📍 本地工具（立即可用，无需网络）
这些工具直接访问本地数据库和知识库，请优先使用：

{local_desc}

### ☁️ MCP 远程工具（需要调用云端服务）
这些工具进行复杂计算或查询外部数据：

{mcp_desc}

### 📌 调用原则
1. **知识检索**：始终使用本地工具（search_enterprise_knowledge 等）
2. **计算任务**：使用 MCP 工具（calculate_tax_vat、calculate_* 等）
3. **企业查询**：使用 MCP 工具（search_enterprise_info、assess_enterprise_risk 等）
4. **复杂分析**：先本地检索背景资料，再调用 MCP 工具进行计算
"""
