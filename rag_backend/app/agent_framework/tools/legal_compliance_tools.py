"""
法律合规检查工具集

整合法律条款匹配、合同检查和合规性评估功能
提供全面的企业法律风险管理能力
"""

import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import ToolBase

logger = logging.getLogger(__name__)


class ContractEssentialsChecker(ToolBase):
    """
    合同必备条款检查工具
    
    检查合同是否包含法律要求的必备条款
    """
    
    def __init__(self):
        super().__init__(
            name="contract_essentials_checker",
            description="检查合同必备条款的完整性，评估合同法律风险",
            timeout=30,
            tags=["法律", "合同", "合规", "检查"]
        )
        
        self.contract_essentials = [
            "当事人名称",
            "标的",
            "数量",
            "质量",
            "价款或者报酬",
            "履行期限",
            "履行地点",
            "履行方式",
            "违约责任"
        ]
    
    async def execute(
        self,
        contract_text: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        检查合同必备条款
        
        Args:
            contract_text: 合同文本
            tenant_id: 租户ID
            
        Returns:
            必备条款检查结果
        """
        try:
            missing_clauses = []
            found_clauses = []
            
            for essential in self.contract_essentials:
                if self._check_clause_exists(contract_text, essential):
                    found_clauses.append(essential)
                else:
                    missing_clauses.append(essential)
            
            completeness_score = (len(found_clauses) / len(self.contract_essentials)) * 100
            
            if len(missing_clauses) == 0:
                risk_level = "low"
                risk_description = "合同必备条款完整"
            elif len(missing_clauses) <= 2:
                risk_level = "medium"
                risk_description = "合同缺少部分必备条款"
            else:
                risk_level = "high"
                risk_description = "合同缺少多个必备条款，存在法律风险"
            
            return {
                "tenant_id": tenant_id,
                "completeness_score": round(completeness_score, 1),
                "risk_level": risk_level,
                "risk_description": risk_description,
                "found_clauses": found_clauses,
                "missing_clauses": missing_clauses,
                "total_essentials": len(self.contract_essentials),
                "recommendations": self._generate_contract_recommendations(missing_clauses),
                "check_date": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"合同必备条款检查失败: {str(e)}", exc_info=True)
            return {
                "tenant_id": tenant_id,
                "error": f"合同必备条款检查失败: {str(e)}",
                "completeness_score": 0,
                "check_date": datetime.now().isoformat()
            }
    
    def _check_clause_exists(self, text: str, clause: str) -> bool:
        """检查条款是否存在"""
        keywords_map = {
            "当事人名称": ["甲方", "乙方", "当事人", "委托方", "受托方"],
            "标的": ["标的", "合同标的", "交易标的", "服务内容"],
            "数量": ["数量", "件数", "批次", "规格"],
            "质量": ["质量", "质量标准", "技术要求", "验收标准"],
            "价款或者报酬": ["价款", "报酬", "费用", "金额", "价格"],
            "履行期限": ["履行期限", "完成时间", "交付时间", "期限"],
            "履行地点": ["履行地点", "交付地点", "服务地点", "地点"],
            "履行方式": ["履行方式", "交付方式", "付款方式", "方式"],
            "违约责任": ["违约责任", "违约", "责任", "赔偿", "损失"]
        }
        
        keywords = keywords_map.get(clause, [clause])
        
        for keyword in keywords:
            if keyword in text:
                return True
        
        return False
    
    def _generate_contract_recommendations(self, missing_clauses: List[str]) -> List[str]:
        """生成合同建议"""
        if not missing_clauses:
            return ["合同条款完整，建议定期审查更新"]
        
        recommendations = []
        for clause in missing_clauses:
            recommendations.append(f"建议补充{clause}相关条款")
        
        recommendations.append("建议咨询专业律师完善合同条款")
        return recommendations


class LegalClauseMatcher(ToolBase):
    """
    法律条款匹配工具
    
    提供法律条款的智能匹配和检索
    """
    
    def __init__(self):
        super().__init__(
            name="legal_clause_matcher",
            description="根据文本内容匹配相关法律条款，支持合同法、劳动法、公司法等",
            timeout=30,
            tags=["法律", "匹配", "条款", "检索"]
        )
        
        self.legal_clauses = self._load_legal_clauses()
    
    def _load_legal_clauses(self) -> Dict[str, List[Dict[str, Any]]]:
        """加载法律条款库"""
        return {
            "contract_law": [
                {
                    "article": "第12条",
                    "content": "合同的内容由当事人约定，一般包括以下条款：(一)当事人的名称或者姓名和住所；(二)标的；(三)数量；(四)质量；(五)价款或者报酬；(六)履行期限、地点和方式；(七)违约责任；(八)解决争议的方法。",
                    "keywords": ["合同内容", "必备条款", "当事人", "标的", "违约责任"]
                },
                {
                    "article": "第52条",
                    "content": "有下列情形之一的，合同无效：(一)一方以欺诈、胁迫的手段订立合同，损害国家利益；(二)恶意串通，损害国家、集体或者第三人利益；(三)以合法形式掩盖非法目的；(四)损害社会公共利益；(五)违反法律、行政法规的强制性规定。",
                    "keywords": ["合同无效", "欺诈", "胁迫", "违反法律", "强制性规定"]
                }
            ],
            "labor_law": [
                {
                    "article": "第17条",
                    "content": "劳动合同应当具备以下条款：(一)用人单位的名称、住所和法定代表人或者主要负责人；(二)劳动者的姓名、住址和居民身份证或者其他有效身份证件号码；(三)劳动合同期限；(四)工作内容和工作地点；(五)工作时间和休息休假；(六)劳动报酬；(七)社会保险；(八)劳动保护、劳动条件和职业危害防护；(九)法律、法规规定应当纳入劳动合同的其他事项。",
                    "keywords": ["劳动合同", "必备条款", "工作内容", "劳动报酬", "社会保险"]
                },
                {
                    "article": "第36条",
                    "content": "国家实行劳动者每日工作时间不超过八小时、平均每周工作时间不超过四十四小时的工时制度。",
                    "keywords": ["工作时间", "八小时", "四十四小时", "工时制度"]
                }
            ],
            "company_law": [
                {
                    "article": "第25条",
                    "content": "有限责任公司章程应当载明下列事项：(一)公司名称和住所；(二)公司经营范围；(三)公司注册资本；(四)股东的姓名或者名称；(五)股东的出资方式、出资额和出资时间；(六)公司的机构及其产生办法、职权、议事规则；(七)公司法定代表人；(八)股东会会议认为需要规定的其他事项。",
                    "keywords": ["公司章程", "公司名称", "经营范围", "注册资本", "股东"]
                }
            ]
        }
    
    async def execute(
        self,
        text: str,
        legal_area: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        匹配相关法律条款
        
        Args:
            text: 待匹配文本
            legal_area: 法律领域 (contract_law/labor_law/company_law)
            tenant_id: 租户ID
            
        Returns:
            匹配的法律条款
        """
        try:
            if legal_area not in self.legal_clauses:
                return {
                    "tenant_id": tenant_id,
                    "error": f"不支持的法律领域: {legal_area}",
                    "matched_provisions": [],
                    "available_areas": list(self.legal_clauses.keys())
                }
            
            matched_provisions = []
            provisions = self.legal_clauses[legal_area]
            
            for provision in provisions:
                relevance_score = self._calculate_relevance(text, provision["keywords"])
                
                if relevance_score > 0:
                    matched_provisions.append({
                        "article": provision["article"],
                        "content": provision["content"],
                        "relevance_score": relevance_score,
                        "matched_keywords": [kw for kw in provision["keywords"] if kw in text]
                    })
            
            matched_provisions.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            return {
                "tenant_id": tenant_id,
                "legal_area": legal_area,
                "total_matches": len(matched_provisions),
                "matched_provisions": matched_provisions[:5],
                "match_date": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"法律条款匹配失败: {str(e)}", exc_info=True)
            return {
                "tenant_id": tenant_id,
                "error": f"法律条款匹配失败: {str(e)}",
                "matched_provisions": [],
                "match_date": datetime.now().isoformat()
            }
    
    def _calculate_relevance(self, text: str, keywords: List[str]) -> float:
        """计算相关性分数"""
        matched_count = sum(1 for keyword in keywords if keyword in text)
        return matched_count / len(keywords) if keywords else 0


class LaborComplianceChecker(ToolBase):
    """
    劳动法合规检查工具
    
    检查劳动合同和用工文档的合规性
    """
    
    def __init__(self):
        super().__init__(
            name="labor_compliance_checker",
            description="检查劳动用工合规性，包括工作时间、社会保险、劳动报酬等",
            timeout=30,
            tags=["法律", "劳动", "合规", "检查"]
        )
    
    async def execute(
        self,
        labor_text: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        检查劳动法合规性
        
        Args:
            labor_text: 劳动合同或用工文档文本
            tenant_id: 租户ID
            
        Returns:
            劳动法合规检查结果
        """
        try:
            compliance_issues = []
            compliance_score = 100
            
            if "工作时间" in labor_text:
                if re.search(r"[9-9]小时|10小时|11小时|12小时", labor_text):
                    compliance_issues.append({
                        "type": "工作时间",
                        "issue": "工作时间可能超过法定标准（8小时/天）",
                        "severity": "high",
                        "legal_basis": "《劳动法》第36条"
                    })
                    compliance_score -= 20
            
            if "社保" not in labor_text and "社会保险" not in labor_text:
                compliance_issues.append({
                    "type": "社会保险",
                    "issue": "未明确约定社会保险缴纳",
                    "severity": "high",
                    "legal_basis": "《社会保险法》"
                })
                compliance_score -= 25
            
            if "工资" not in labor_text and "报酬" not in labor_text and "薪酬" not in labor_text:
                compliance_issues.append({
                    "type": "劳动报酬",
                    "issue": "未明确约定劳动报酬",
                    "severity": "high",
                    "legal_basis": "《劳动合同法》第17条"
                })
                compliance_score -= 20
            
            if "试用期" in labor_text:
                if re.search(r"试用期.*[7-9]个月|试用期.*1[0-9]个月", labor_text):
                    compliance_issues.append({
                        "type": "试用期",
                        "issue": "试用期可能超过法定期限",
                        "severity": "medium",
                        "legal_basis": "《劳动合同法》第19条"
                    })
                    compliance_score -= 15
            
            compliance_level = self._get_compliance_level(compliance_score)
            
            return {
                "tenant_id": tenant_id,
                "compliance_score": compliance_score,
                "compliance_level": compliance_level,
                "total_issues": len(compliance_issues),
                "issues": compliance_issues,
                "recommendations": self._generate_labor_recommendations(compliance_issues),
                "check_date": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"劳动法合规检查失败: {str(e)}", exc_info=True)
            return {
                "tenant_id": tenant_id,
                "error": f"劳动法合规检查失败: {str(e)}",
                "compliance_score": 0,
                "check_date": datetime.now().isoformat()
            }
    
    def _get_compliance_level(self, score: int) -> str:
        """确定合规等级"""
        if score >= 90:
            return "优秀"
        elif score >= 80:
            return "良好"
        elif score >= 70:
            return "一般"
        else:
            return "较差"
    
    def _generate_labor_recommendations(self, issues: List[Dict[str, Any]]) -> List[str]:
        """生成劳动法建议"""
        if not issues:
            return ["劳动用工合规情况良好"]
        
        recommendations = []
        for issue in issues:
            if issue["type"] == "工作时间":
                recommendations.append("建议调整工作时间安排，确保符合法定标准（8小时/天，44小时/周）")
            elif issue["type"] == "社会保险":
                recommendations.append("建议明确约定社会保险缴纳义务，依法为员工缴纳社保")
            elif issue["type"] == "劳动报酬":
                recommendations.append("建议明确约定劳动报酬标准、支付方式和支付时间")
            elif issue["type"] == "试用期":
                recommendations.append("建议核查试用期设置是否符合法律规定（劳动合同3个月-1年，试用期不超过1个月）")
        
        return recommendations


class IPRiskChecker(ToolBase):
    """
    知识产权风险检查工具
    
    检查文档中的知识产权风险
    """
    
    def __init__(self):
        super().__init__(
            name="ip_risk_checker",
            description="检查知识产权风险，包括商标、专利、著作权和商业秘密",
            timeout=30,
            tags=["法律", "知识产权", "风险", "合规"]
        )
    
    async def execute(
        self,
        text: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        检查知识产权风险
        
        Args:
            text: 文档文本
            tenant_id: 租户ID
            
        Returns:
            知识产权风险检查结果
        """
        try:
            ip_risks = []
            risk_score = 0
            
            if re.search(r"®|™|商标", text):
                if "授权" not in text and "许可" not in text:
                    ip_risks.append({
                        "type": "商标风险",
                        "description": "使用商标但未明确授权",
                        "severity": "medium"
                    })
                    risk_score += 30
            
            if "专利" in text:
                if "授权" not in text and "许可" not in text:
                    ip_risks.append({
                        "type": "专利风险",
                        "description": "涉及专利但未明确授权",
                        "severity": "high"
                    })
                    risk_score += 40
            
            if "版权" in text or "著作权" in text:
                if "原创" not in text and "授权" not in text:
                    ip_risks.append({
                        "type": "著作权风险",
                        "description": "涉及著作权但权属不明",
                        "severity": "medium"
                    })
                    risk_score += 25
            
            if "商业秘密" in text or "保密" in text:
                if "保密协议" not in text:
                    ip_risks.append({
                        "type": "商业秘密风险",
                        "description": "涉及商业秘密但缺少保密措施",
                        "severity": "medium"
                    })
                    risk_score += 20
            
            if risk_score == 0:
                risk_level = "low"
                risk_description = "未发现明显知识产权风险"
            elif risk_score <= 30:
                risk_level = "medium"
                risk_description = "存在一定知识产权风险"
            else:
                risk_level = "high"
                risk_description = "存在较高知识产权风险"
            
            return {
                "tenant_id": tenant_id,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "risk_description": risk_description,
                "total_risks": len(ip_risks),
                "risks": ip_risks,
                "recommendations": self._generate_ip_recommendations(ip_risks),
                "check_date": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"知识产权风险检查失败: {str(e)}", exc_info=True)
            return {
                "tenant_id": tenant_id,
                "error": f"知识产权风险检查失败: {str(e)}",
                "risk_score": 0,
                "check_date": datetime.now().isoformat()
            }
    
    def _generate_ip_recommendations(self, risks: List[Dict[str, Any]]) -> List[str]:
        """生成知识产权建议"""
        if not risks:
            return ["知识产权风险较低，建议继续保持"]
        
        recommendations = []
        for risk in risks:
            if risk["type"] == "商标风险":
                recommendations.append("建议获得商标使用授权或许可，避免商标侵权风险")
            elif risk["type"] == "专利风险":
                recommendations.append("建议核查专利权属，获得必要授权，避免专利侵权")
            elif risk["type"] == "著作权风险":
                recommendations.append("建议明确著作权权属，避免著作权侵权风险")
            elif risk["type"] == "商业秘密风险":
                recommendations.append("建议签署保密协议，加强商业秘密保护措施")
        
        return recommendations
