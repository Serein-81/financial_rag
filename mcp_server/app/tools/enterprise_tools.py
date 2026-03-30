"""
企业信息查询工具

基于本地模拟数据实现的企业工商信息查询
"""

import logging
from typing import Any, Dict, List, Optional

from app.tools.base import ToolBase, registry

logger = logging.getLogger(__name__)


MOCK_ENTERPRISE_DB = {
    "91110000XXXXXXXX": {
        "name": "示例科技有限公司",
        "credit_code": "91110000XXXXXXXX",
        "legal_person": "张三",
        "registered_capital": 10000000,
        "established_date": "2020-01-15",
        "address": "北京市海淀区中关村大街1号",
        "business_scope": "技术开发、技术咨询、技术服务、软件开发",
        "industry": "软件和信息技术服务业",
        "company_type": "有限责任公司",
        "status": "存续"
    },
    "91310000XXXXXXXX": {
        "name": "上海贸易集团有限公司",
        "credit_code": "91310000XXXXXXXX",
        "legal_person": "李四",
        "registered_capital": 50000000,
        "established_date": "2018-06-20",
        "address": "上海市浦东新区陆家嘴环路1000号",
        "business_scope": "货物进出口、技术进出口、代理进出口、销售",
        "industry": "批发和零售业",
        "company_type": "集团有限公司",
        "status": "存续"
    },
    "91440000XXXXXXXX": {
        "name": "广州制造业股份有限公司",
        "credit_code": "91440000XXXXXXXX",
        "legal_person": "王五",
        "registered_capital": 200000000,
        "established_date": "2015-03-10",
        "address": "广州市天河区珠江新城花城大道88号",
        "business_scope": "制造、加工、销售：电子产品、机械设备、五金制品",
        "industry": "制造业",
        "company_type": "股份有限公司",
        "status": "存续"
    }
}


class EnterpriseSearchTool(ToolBase):
    """企业信息搜索工具"""

    def __init__(self):
        super().__init__(
            name="search_enterprise_info",
            description="根据企业名称或信用代码搜索企业工商信息。",
            timeout=30
        )

    async def execute(
        self,
        query: str,
        search_type: str = "name",
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        搜索企业信息

        Args:
            query: 查询关键词（企业名称或信用代码）
            search_type: 查询类型（name 或 credit_code）
            tenant_id: 租户ID

        Returns:
            包含企业信息或搜索结果的字典
        """
        if not query or len(query.strip()) < 2:
            return {
                "success": False,
                "error": "查询关键词至少需要2个字符",
                "tenant_id": tenant_id
            }

        query_lower = query.lower().strip()
        results = []

        for credit_code, info in MOCK_ENTERPRISE_DB.items():
            if search_type == "credit_code":
                if query_lower in credit_code.lower():
                    results.append({**info, "credit_code": credit_code})
            else:
                if query_lower in info["name"].lower():
                    results.append({**info, "credit_code": credit_code})

        return {
            "query": query,
            "search_type": search_type,
            "total_results": len(results),
            "results": results,
            "tenant_id": tenant_id
        }


class EnterpriseDetailTool(ToolBase):
    """企业详细信息查询工具"""

    def __init__(self):
        super().__init__(
            name="get_enterprise_detail",
            description="根据信用代码获取企业详细信息。",
            timeout=30
        )

    async def execute(
        self,
        credit_code: str,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        获取企业详细信息

        Args:
            credit_code: 企业统一社会信用代码
            tenant_id: 租户ID

        Returns:
            包含企业详细信息的字典
        """
        if not credit_code:
            return {
                "success": False,
                "error": "信用代码不能为空",
                "tenant_id": tenant_id
            }

        enterprise = MOCK_ENTERPRISE_DB.get(credit_code)

        if not enterprise:
            return {
                "success": False,
                "error": f"未找到信用代码为 {credit_code} 的企业",
                "credit_code": credit_code,
                "tenant_id": tenant_id
            }

        return {
            "found": True,
            "credit_code": credit_code,
            **enterprise,
            "tenant_id": tenant_id
        }


class EnterpriseRiskAssessmentTool(ToolBase):
    """企业风险评估工具"""

    def __init__(self):
        super().__init__(
            name="assess_enterprise_risk",
            description="根据企业信息进行风险评估。",
            timeout=30
        )

    async def execute(
        self,
        credit_code: Optional[str] = None,
        registered_capital: Optional[float] = None,
        company_type: Optional[str] = None,
        industry: Optional[str] = None,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        评估企业风险

        Args:
            credit_code: 企业信用代码（可选）
            registered_capital: 注册资本（万元）
            company_type: 公司类型
            industry: 所属行业
            tenant_id: 租户ID

        Returns:
            包含风险评估结果的字典
        """
        risk_factors = []
        total_score = 100

        if registered_capital is not None:
            if registered_capital < 100:
                risk_factors.append({"factor": "注册资本", "level": "high", "detail": "注册资本较低"})
                total_score -= 20
            elif registered_capital < 500:
                risk_factors.append({"factor": "注册资本", "level": "medium", "detail": "注册资本一般"})
                total_score -= 10
            else:
                risk_factors.append({"factor": "注册资本", "level": "low", "detail": "注册资本充足"})
                total_score -= 0

        if company_type:
            high_risk_types = ["个人独资企业", "有限合伙"]
            if company_type in high_risk_types:
                risk_factors.append({"factor": "公司类型", "level": "high", "detail": f"{company_type}风险较高"})
                total_score -= 15

        high_risk_industries = ["投资", "金融", "典当", "担保"]
        if industry:
            for risk_industry in high_risk_industries:
                if risk_industry in industry:
                    risk_factors.append({"factor": "所属行业", "level": "medium", "detail": f"{industry}需要额外关注"})
                    total_score -= 10
                    break

        risk_level = "low"
        if total_score < 60:
            risk_level = "critical"
        elif total_score < 70:
            risk_level = "high"
        elif total_score < 85:
            risk_level = "medium"

        return {
            "credit_code": credit_code,
            "risk_score": total_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "recommendations": self._generate_recommendations(risk_level),
            "tenant_id": tenant_id
        }

    def _generate_recommendations(self, risk_level: str) -> List[str]:
        """生成建议"""
        recommendations = {
            "low": ["企业风险较低，可正常合作"],
            "medium": ["建议进行尽职调查，定期跟踪企业状况"],
            "high": ["建议进行深入尽职调查，设置合作风险控制措施"],
            "critical": ["风险较高，建议谨慎合作或寻求担保"]
        }
        return recommendations.get(risk_level, [])


def register_enterprise_tools():
    """注册所有企业信息工具"""
    registry.register(EnterpriseSearchTool())
    registry.register(EnterpriseDetailTool())
    registry.register(EnterpriseRiskAssessmentTool())


enterprise_tools = [
    EnterpriseSearchTool(),
    EnterpriseDetailTool(),
    EnterpriseRiskAssessmentTool()
]
