"""
法律匹配工具
"""

import re
import logging
from typing import Any, Dict, List, Optional

from app.tools.base import ToolBase, registry

logger = logging.getLogger(__name__)


class ContractEssentialsChecker(ToolBase):
    """合同必备条款检查工具"""

    def __init__(self):
        super().__init__(
            name="check_contract_essentials",
            description="检查合同必备条款是否完整。检查标的、质量、价款、履行方式、违约责任等。",
            timeout=30
        )

        self._essentials = {
            "标的内容": [r"标的", r"货物", r"服务", r"商品", r"产品"],
            "质量标准": [r"质量", r"规格", r"标准", r"要求"],
            "价格条款": [r"价格", r"价款", r"金额", r"费用", r"报酬"],
            "履行期限": [r"期限", r"时间", r"日期", r"交付", r"完成"],
            "履行方式": [r"方式", r"地点", r"方式", r"送货", r"自提"],
            "违约责任": [r"违约", r"责任", r"赔偿", r"违约金"],
            "争议解决": [r"争议", r"仲裁", r"诉讼", r"法院", r"管辖"],
            "合同双方": [r"甲方", r"乙方", r"当事人", r"委托方", r"受托方"],
        }

    async def execute(
        self,
        contract_text: str,
        contract_type: str = "general",
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        检查合同必备条款

        Args:
            contract_text: 合同文本内容
            contract_type: 合同类型（general, sales, service, labor）
            tenant_id: 租户ID

        Returns:
            包含检查结果的字典
        """
        if not contract_text or len(contract_text.strip()) < 50:
            return {
                "success": False,
                "error": "合同文本过短或为空",
                "contract_type": contract_type,
                "tenant_id": tenant_id
            }

        results = {}
        missing_clauses = []
        found_clauses = []

        for clause_name, keywords in self._essentials.items():
            found = False
            matches = []
            for keyword in keywords:
                pattern = re.compile(keyword, re.IGNORECASE)
                if pattern.search(contract_text):
                    found = True
                    matches.append(keyword)

            results[clause_name] = {
                "found": found,
                "matched_keywords": matches if found else []
            }

            if found:
                found_clauses.append(clause_name)
            else:
                missing_clauses.append(clause_name)

        coverage = len(found_clauses) / len(self._essentials) * 100

        risk_level = "low"
        if coverage < 50:
            risk_level = "high"
        elif coverage < 80:
            risk_level = "medium"

        return {
            "contract_type": contract_type,
            "total_clauses": len(self._essentials),
            "found_clauses": found_clauses,
            "missing_clauses": missing_clauses,
            "coverage_rate": round(coverage, 1),
            "risk_level": risk_level,
            "details": results,
            "recommendations": self._generate_recommendations(missing_clauses),
            "tenant_id": tenant_id
        }

    def _generate_recommendations(self, missing: List[str]) -> List[str]:
        """生成补全建议"""
        recommendations = {
            "标的内容": "建议明确约定合同标的的具体内容、规格型号",
            "质量标准": "建议补充质量标准、验收标准、检验期限",
            "价格条款": "建议明确约定价款金额、支付方式、支付时间",
            "履行期限": "建议明确约定履行开始和结束时间",
            "履行方式": "建议明确约定交付方式、运输责任",
            "违约责任": "建议补充违约金数额或计算方式",
            "争议解决": "建议约定争议解决方式和管辖法院",
            "合同双方": "建议明确双方全称、地址、联系方式"
        }
        return [recommendations.get(m, f"建议补充{m}条款") for m in missing]


class LegalProvisionMatcher(ToolBase):
    """法律条款匹配工具"""

    def __init__(self):
        super().__init__(
            name="match_legal_provisions",
            description="根据文本内容和法律领域匹配相关法律条款。覆盖合同法、劳动法、公司法等。",
            timeout=30
        )

        self._legal_areas = {
            "合同法": {
                "keywords": ["合同", "违约", "解除", "变更", "转让", "标的", "履行"],
                "provisions": [
                    {"code": "民法典第465条", "name": "合同约束力", "content": "依法成立的合同,受法律保护"},
                    {"code": "民法典第577条", "name": "违约责任", "content": "当事人一方不履行合同义务或者履行不符合约定的,应当承担违约责任"},
                    {"code": "民法典第563条", "name": "合同解除", "content": "当事人一方迟延履行债务或者有其他违约行为致使不能实现合同目的,当事人可以解除合同"}
                ]
            },
            "劳动法": {
                "keywords": ["劳动合同", "工资", "社会保险", "加班", "解除合同", "试用期"],
                "provisions": [
                    {"code": "劳动合同法第10条", "name": "劳动合同订立", "content": "建立劳动关系,应当订立书面劳动合同"},
                    {"code": "劳动合同法第36条", "name": "协商解除", "content": "用人单位与劳动者协商一致,可以解除劳动合同"},
                    {"code": "劳动法第44条", "name": "加班工资", "content": "安排劳动者延长工作时间的,支付不低于工资150%的工资报酬"}
                ]
            },
            "公司法": {
                "keywords": ["股东", "股权", "董事会", "利润分配", "注册资本", "公司治理"],
                "provisions": [
                    {"code": "公司法第4条", "name": "股东权利", "content": "公司股东依法享有资产收益、参与重大决策和选择管理者等权利"},
                    {"code": "公司法第166条", "name": "利润分配", "content": "公司分配当年税后利润时,应当提取利润的百分之十列入公司法定公积金"},
                    {"code": "公司法第49条", "name": "经理职权", "content": "经理对董事会负责,主持公司的生产经营管理工作"}
                ]
            },
            "知识产权法": {
                "keywords": ["专利", "商标", "著作权", "知识产权", "侵权", "许可"],
                "provisions": [
                    {"code": "专利法第11条", "name": "专利权保护", "content": "发明和实用新型专利权被授予后,除本法另有规定的以外,任何单位或者个人未经专利权人许可,都不得实施其专利"},
                    {"code": "商标法第48条", "name": "商标使用", "content": "本法所称商标的使用,是指将商标用于商品、商品包装或者容器以及商品交易文书上,或者将商标用于广告宣传、展览以及其他商业活动中"}
                ]
            }
        }

    async def execute(
        self,
        text: str,
        legal_area: Optional[str] = None,
        max_results: int = 5,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        匹配法律条款

        Args:
            text: 待分析文本
            legal_area: 指定法律领域，不指定则自动匹配所有领域
            max_results: 最大返回结果数
            tenant_id: 租户ID

        Returns:
            包含匹配结果的字典
        """
        if not text or len(text.strip()) < 10:
            return {
                "success": False,
                "error": "分析文本过短",
                "tenant_id": tenant_id
            }

        matched_provisions = []
        matched_areas = []

        areas_to_search = (
            {legal_area: self._legal_areas[legal_area]}
            if legal_area and legal_area in self._legal_areas
            else self._legal_areas
        )

        for area_name, area_info in areas_to_search.items():
            area_score = 0
            area_matches = []

            for keyword in area_info["keywords"]:
                pattern = re.compile(keyword, re.IGNORECASE)
                matches = pattern.findall(text)
                if matches:
                    area_score += len(matches)
                    area_matches.append(keyword)

            if area_matches:
                matched_areas.append({
                    "area": area_name,
                    "matched_keywords": area_matches,
                    "match_count": len(area_matches),
                    "score": area_score
                })

                for provision in area_info["provisions"]:
                    provision_score = area_score
                    for keyword in area_matches:
                        if keyword in provision["content"]:
                            provision_score += 1

                    matched_provisions.append({
                        **provision,
                        "area": area_name,
                        "score": provision_score,
                        "matched_from_area": True
                    })

        matched_provisions.sort(key=lambda x: x["score"], reverse=True)
        top_provisions = matched_provisions[:max_results]

        matched_areas.sort(key=lambda x: x["score"], reverse=True)

        return {
            "total_matches": len(top_provisions),
            "matched_legal_areas": matched_areas,
            "provisions": top_provisions,
            "search_query_length": len(text),
            "tenant_id": tenant_id
        }


def register_legal_tools():
    """注册所有法律工具"""
    registry.register(ContractEssentialsChecker())
    registry.register(LegalProvisionMatcher())


legal_tools = [ContractEssentialsChecker(), LegalProvisionMatcher()]
