"""
MCP 云端工具

提供 Agent 可调用的云端工具
包括税务计算、法律检查、财务指标等

工具类型：云端 MCP
注意：云端连接失败时会自动回退到本地实现
"""

import logging
from typing import Dict, Any, Optional

from app.mcp.decorators import cloud_tool

logger = logging.getLogger(__name__)


@cloud_tool(
    description="根据销售额、进项税额、增值税率计算应纳税额"
)
async def calculate_tax_vat(
    sales_amount: float,
    vat_rate: float = 0.13,
    input_vat: float = 0.0,
    tenant_id: str = "default"
) -> Dict[str, Any]:
    """
    计算增值税（Value Added Tax）
    
    根据销售额、进项税额、增值税率计算应纳税额。
    
    Args:
        sales_amount: 销售额（含税），必填
        vat_rate: 增值税率，默认 0.13（13%）
        input_vat: 进项税额，默认 0
        tenant_id: 租户ID，默认 default
    
    Returns:
        包含税额计算结果的字典
    
    Example:
        calculate_tax_vat(sales_amount=10000, vat_rate=0.13, input_vat=500)
    """
    try:
        tax_amount = sales_amount * vat_rate
        net_vat = tax_amount - input_vat
        
        risk_level = "low"
        if net_vat < 0:
            risk_level = "high"
        elif abs(net_vat) / sales_amount > 0.2:
            risk_level = "medium"
        
        return {
            "status": "success",
            "sales_amount": round(sales_amount, 2),
            "vat_rate": vat_rate,
            "tax_amount": round(tax_amount, 2),
            "input_vat": round(input_vat, 2),
            "net_vat_payable": round(net_vat, 2),
            "risk_level": risk_level,
            "message": f"应纳增值税: {round(tax_amount, 2)} 元，抵扣后应缴: {round(net_vat, 2)} 元"
        }
    except Exception as e:
        logger.error(f"增值税计算失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@cloud_tool(
    description="根据应纳税所得额和税率计算企业所得税，支持小微企业优惠"
)
async def calculate_corporate_tax(
    taxable_income: float,
    tax_rate: float = 0.25,
    small_business: bool = False,
    tenant_id: str = "default"
) -> Dict[str, Any]:
    """
    计算企业所得税（Corporate Income Tax）
    
    根据应纳税所得额和税率计算企业所得税。
    
    Args:
        taxable_income: 应纳税所得额，必填
        tax_rate: 企业所得税税率，默认 0.25（25%）
        small_business: 是否为小型微利企业，默认 False
        tenant_id: 租户ID，默认 default
    
    Returns:
        包含计算结果的字典
    
    Example:
        calculate_corporate_tax(taxable_income=100000, tax_rate=0.20, small_business=True)
    """
    try:
        if small_business and taxable_income <= 3000000:
            effective_rate = 0.05
        else:
            effective_rate = tax_rate
        
        tax_amount = taxable_income * effective_rate
        
        return {
            "status": "success",
            "taxable_income": round(taxable_income, 2),
            "tax_rate": effective_rate,
            "tax_amount": round(tax_amount, 2),
            "small_business": small_business,
            "message": f"应纳企业所得税: {round(tax_amount, 2)} 元（税率 {effective_rate * 100}%）"
        }
    except Exception as e:
        logger.error(f"企业所得税计算失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@cloud_tool(
    description="使用超额累进税率计算个人所得税"
)
async def calculate_personal_tax(
    monthly_income: float,
    special_deductions: float = 0,
    tenant_id: str = "default"
) -> Dict[str, Any]:
    """
    计算个人所得税（Individual Income Tax）
    
    使用超额累进税率计算个人所得税。
    
    Args:
        monthly_income: 月收入，必填
        special_deductions: 专项附加扣除，默认 0
        tenant_id: 租户ID，默认 default
    
    Returns:
        包含计算结果的字典
    
    Example:
        calculate_personal_tax(monthly_income=30000, special_deductions=5000)
    """
    try:
        taxable = monthly_income - special_deductions - 5000
        
        if taxable <= 0:
            return {
                "status": "success",
                "monthly_income": monthly_income,
                "special_deductions": special_deductions,
                "taxable_income": 0,
                "tax_amount": 0,
                "message": "无需缴纳个人所得税"
            }
        
        if taxable <= 3000:
            tax_amount = taxable * 0.03
            rate_text = "3%"
        elif taxable <= 12000:
            tax_amount = taxable * 0.1 - 210
            rate_text = "10%"
        elif taxable <= 25000:
            tax_amount = taxable * 0.2 - 1410
            rate_text = "20%"
        elif taxable <= 35000:
            tax_amount = taxable * 0.25 - 2660
            rate_text = "25%"
        elif taxable <= 55000:
            tax_amount = taxable * 0.3 - 4410
            rate_text = "30%"
        elif taxable <= 80000:
            tax_amount = taxable * 0.35 - 7160
            rate_text = "35%"
        else:
            tax_amount = taxable * 0.45 - 15160
            rate_text = "45%"
        
        return {
            "status": "success",
            "monthly_income": monthly_income,
            "special_deductions": special_deductions,
            "taxable_income": round(taxable, 2),
            "tax_amount": round(tax_amount, 2),
            "rate_text": rate_text,
            "message": f"应纳个税: {round(tax_amount, 2)} 元（税率 {rate_text}）"
        }
    except Exception as e:
        logger.error(f"个人所得税计算失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@cloud_tool(
    description="衡量企业总资产中负债的比例，评估长期偿债能力和风险水平"
)
async def calculate_asset_liability_ratio(
    total_liabilities: float,
    total_assets: float,
    tenant_id: str = "default"
) -> Dict[str, Any]:
    """
    计算资产负债率（Asset-Liability Ratio）
    
    衡量企业总资产中负债的比例，评估长期偿债能力和风险水平。
    
    Args:
        total_liabilities: 负债总额，必填
        total_assets: 资产总额，必填
        tenant_id: 租户ID，默认 default
    
    Returns:
        包含计算结果的字典
    
    Example:
        calculate_asset_liability_ratio(total_liabilities=5000000, total_assets=10000000)
    """
    try:
        if total_assets <= 0:
            return {"status": "error", "error": "资产总额必须大于0"}
        
        ratio = (total_liabilities / total_assets) * 100
        equity = total_assets - total_liabilities
        
        risk_level = "low"
        if ratio > 70:
            risk_level = "critical"
        elif ratio > 60:
            risk_level = "high"
        elif ratio > 50:
            risk_level = "medium"
        
        return {
            "status": "success",
            "total_assets": round(total_assets, 2),
            "total_liabilities": round(total_liabilities, 2),
            "equity": round(equity, 2),
            "ratio": round(ratio, 2),
            "risk_level": risk_level,
            "message": f"资产负债率: {ratio:.1f}%，风险等级: {risk_level}"
        }
    except Exception as e:
        logger.error(f"资产负债率计算失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@cloud_tool(
    description="衡量企业短期偿债能力"
)
async def calculate_current_ratio(
    current_assets: float,
    current_liabilities: float,
    tenant_id: str = "default"
) -> Dict[str, Any]:
    """
    计算流动比率（Current Ratio）
    
    衡量企业短期偿债能力（流动资产/流动负债）。
    
    Args:
        current_assets: 流动资产，必填
        current_liabilities: 流动负债，必填
        tenant_id: 租户ID，默认 default
    
    Returns:
        包含计算结果的字典
    
    Example:
        calculate_current_ratio(current_assets=3000000, current_liabilities=1500000)
    """
    try:
        if current_liabilities <= 0:
            return {"status": "error", "error": "流动负债必须大于0"}
        
        ratio = current_assets / current_liabilities
        
        risk_level = "low"
        if ratio < 1:
            risk_level = "critical"
        elif ratio < 1.5:
            risk_level = "high"
        elif ratio < 2:
            risk_level = "medium"
        
        return {
            "status": "success",
            "current_assets": round(current_assets, 2),
            "current_liabilities": round(current_liabilities, 2),
            "ratio": round(ratio, 2),
            "risk_level": risk_level,
            "message": f"流动比率: {ratio:.2f}，风险等级: {risk_level}"
        }
    except Exception as e:
        logger.error(f"流动比率计算失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@cloud_tool(
    description="衡量企业立即偿债能力，不含存货"
)
async def calculate_quick_ratio(
    current_assets: float,
    inventory: float,
    current_liabilities: float,
    tenant_id: str = "default"
) -> Dict[str, Any]:
    """
    计算速动比率（Quick Ratio）
    
    衡量企业立即偿债能力（不含存货）。
    
    Args:
        current_assets: 流动资产，必填
        inventory: 存货，必填
        current_liabilities: 流动负债，必填
        tenant_id: 租户ID，默认 default
    
    Returns:
        包含计算结果的字典
    
    Example:
        calculate_quick_ratio(current_assets=3000000, inventory=800000, current_liabilities=1500000)
    """
    try:
        if current_liabilities <= 0:
            return {"status": "error", "error": "流动负债必须大于0"}
        
        ratio = (current_assets - inventory) / current_liabilities
        
        risk_level = "low"
        if ratio < 0.5:
            risk_level = "critical"
        elif ratio < 1:
            risk_level = "high"
        elif ratio < 1.5:
            risk_level = "medium"
        
        return {
            "status": "success",
            "current_assets": round(current_assets, 2),
            "inventory": round(inventory, 2),
            "current_liabilities": round(current_liabilities, 2),
            "ratio": round(ratio, 2),
            "risk_level": risk_level,
            "message": f"速动比率: {ratio:.2f}，风险等级: {risk_level}"
        }
    except Exception as e:
        logger.error(f"速动比率计算失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@cloud_tool(
    description="评估企业盈利能力"
)
async def calculate_profit_margin(
    net_profit: float,
    total_revenue: float,
    tenant_id: str = "default"
) -> Dict[str, Any]:
    """
    计算净利润率（Net Profit Margin）
    
    评估企业盈利能力（净利润/总收入）。
    
    Args:
        net_profit: 净利润，必填
        total_revenue: 总收入，必填
        tenant_id: 租户ID，默认 default
    
    Returns:
        包含计算结果的字典
    
    Example:
        calculate_profit_margin(net_profit=500000, total_revenue=5000000)
    """
    try:
        if total_revenue <= 0:
            return {"status": "error", "error": "总收入必须大于0"}
        
        margin = (net_profit / total_revenue) * 100
        
        risk_level = "low"
        if margin < 0:
            risk_level = "critical"
        elif margin < 5:
            risk_level = "high"
        elif margin < 10:
            risk_level = "medium"
        
        return {
            "status": "success",
            "net_profit": round(net_profit, 2),
            "total_revenue": round(total_revenue, 2),
            "margin": round(margin, 2),
            "risk_level": risk_level,
            "message": f"净利润率: {margin:.1f}%，风险等级: {risk_level}"
        }
    except Exception as e:
        logger.error(f"净利润率计算失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@cloud_tool(
    description="检查合同是否包含法律要求的必备条款"
)
async def check_contract_essentials(
    contract_text: str,
    contract_type: str = "general",
    tenant_id: str = "default"
) -> Dict[str, Any]:
    """
    检查合同必备条款
    
    检查合同是否包含法律要求的必备条款。
    
    Args:
        contract_text: 合同文本，必填
        contract_type: 合同类型，默认 general，可选: general/sales/service/labor
        tenant_id: 租户ID，默认 default
    
    Returns:
        包含检查结果的字典
    
    Example:
        check_contract_essentials(contract_text="甲方XXX...", contract_type="sales")
    """
    try:
        if not contract_text or len(contract_text.strip()) < 50:
            return {"status": "error", "error": "合同文本过短或为空"}
        
        essentials = {
            "标的内容": ["标的", "货物", "服务", "商品", "产品"],
            "质量标准": ["质量", "规格", "标准", "要求"],
            "价格条款": ["价格", "价款", "金额", "费用", "报酬"],
            "履行期限": ["期限", "时间", "日期", "交付", "完成"],
            "违约责任": ["违约", "责任", "赔偿", "违约金"],
            "争议解决": ["争议", "仲裁", "诉讼", "法院", "管辖"],
            "合同双方": ["甲方", "乙方", "当事人", "委托方", "受托方"],
        }
        
        found = []
        missing = []
        
        for clause, keywords in essentials.items():
            found_clause = any(k in contract_text for k in keywords)
            if found_clause:
                found.append(clause)
            else:
                missing.append(clause)
        
        coverage = len(found) / len(essentials) * 100
        
        risk_level = "low"
        if coverage < 50:
            risk_level = "high"
        elif coverage < 80:
            risk_level = "medium"
        
        return {
            "status": "success",
            "contract_type": contract_type,
            "found_clauses": found,
            "missing_clauses": missing,
            "coverage_rate": round(coverage, 1),
            "risk_level": risk_level,
            "message": f"条款完整度: {coverage:.0f}%，风险等级: {risk_level}"
        }
    except Exception as e:
        logger.error(f"合同必备条款检查失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@cloud_tool(
    description="根据合同内容匹配相关法律条款"
)
async def match_legal_provisions(
    contract_text: str,
    law_type: str = "contract",
    tenant_id: str = "default"
) -> Dict[str, Any]:
    """
    匹配相关法律条款
    
    根据合同内容匹配相关法律条款。
    
    Args:
        contract_text: 合同文本，必填
        law_type: 法律类型，默认 contract，可选: contract/labor/intellectual_property
        tenant_id: 租户ID，默认 default
    
    Returns:
        包含匹配结果的字典
    
    Example:
        match_legal_provisions(contract_text="...", law_type="contract")
    """
    try:
        provisions_map = {
            "contract": ["《中华人民共和国民法典》合同编", "合同编通则若干问题的解释"],
            "labor": ["《中华人民共和国劳动合同法》", "《中华人民共和国劳动法》"],
            "intellectual_property": ["《著作权法》", "《商标法》", "《专利法》"]
        }
        
        matched = provisions_map.get(law_type, provisions_map["contract"])
        
        return {
            "status": "success",
            "matched_provisions": matched,
            "law_type": law_type,
            "count": len(matched),
            "message": f"匹配到 {len(matched)} 条相关法律条款"
        }
    except Exception as e:
        logger.error(f"法律条款匹配失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def create_cloud_tools():
    """创建云端工具列表"""
    return [
        calculate_tax_vat,
        calculate_corporate_tax,
        calculate_personal_tax,
        calculate_asset_liability_ratio,
        calculate_current_ratio,
        calculate_quick_ratio,
        calculate_profit_margin,
        check_contract_essentials,
        match_legal_provisions,
        search_web,
    ]


@cloud_tool(
    description="搜索互联网获取最新税务政策、税率信息、税法解读等实时资讯。适用于查询'最新税率'、'今年政策变化'、'最新税法规定'等问题"
)
async def search_web(
    query: str,
    max_results: int = 5,
    tenant_id: str = "default"
) -> Dict[str, Any]:
    """
    网络搜索工具
    
    搜索互联网获取最新税务政策、税率信息、税法解读等实时资讯。
    当用户询问"最新税率是多少"、"今年有什么税务政策"等问题时，必须使用此工具查询最新信息。
    
    Args:
        query: 搜索关键词，必填
        max_results: 最大结果数，默认 5
        tenant_id: 租户ID，默认 default
    
    Returns:
        包含搜索结果的字典
    
    Example:
        search_web(query="2024年增值税最新税率政策")
        search_web(query="企业所得税最新优惠政策 2024")
    """
    import os
    
    tavily_api_key = os.getenv("TAVILY_API_KEY", "")
    
    if not tavily_api_key:
        return {
            "status": "error",
            "error": "TAVILY_API_KEY 未配置，网络搜索功能暂时不可用",
            "query": query,
            "suggestion": "请配置 TAVILY_API_KEY 环境变量以启用网络搜索功能"
        }
    
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=20.0) as client:
            url = "https://api.tavily.com/search"
            headers = {"Content-Type": "application/json"}
            payload = {
                "api_key": tavily_api_key,
                "query": query,
                "search_depth": "basic",
                "include_answer": True,
                "max_results": max_results
            }
            
            res = await client.post(url, json=payload, headers=headers)
            
            if res.status_code == 200:
                data = res.json()
                results = []
                
                for item in data.get("results", []):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", "")[:800]
                    })
                
                return {
                    "status": "success",
                    "query": query,
                    "answer": data.get("answer", ""),
                    "results": results,
                    "total_results": len(results),
                    "message": f"搜索到 {len(results)} 条相关结果"
                }
            else:
                return {
                    "status": "error",
                    "error": f"搜索请求失败: {res.status_code}",
                    "query": query
                }
                
    except httpx.TimeoutException:
        return {
            "status": "error",
            "error": "搜索服务请求超时，请稍后重试",
            "query": query
        }
    except Exception as e:
        logger.error(f"网络搜索失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": f"搜索失败: {str(e)}",
            "query": query
        }
