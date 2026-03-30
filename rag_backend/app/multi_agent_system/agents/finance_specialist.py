"""
财务专家智能体 (Finance Specialist Agent)
处理企业财务相关问题，包括投资分析、贷款计算、预算管理、财务报表分析等
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

from pydantic import BaseModel, Field

from .base_specialist import BaseSpecialistAgent
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from ..state import AuditState, Finding, RiskLevel

logger = logging.getLogger(__name__)


class FinancialDomain(str, Enum):
    """财务领域"""
    INVESTMENT = "investment"  # 投资分析
    LOAN = "loan"  # 贷款融资
    BUDGET = "budget"  # 预算管理
    FINANCIAL_STATEMENT = "financial_statement"  # 财务报表
    COST_CONTROL = "cost_control"  # 成本控制
    CASH_FLOW = "cash_flow"  # 现金流管理
    TREASURY = "treasury"  # 资金管理
    OTHER = "other"


class FinancialAnalysisResult(BaseModel):
    """财务分析结果"""
    domain: FinancialDomain = Field(description="财务领域")
    financial_indicators: Dict[str, float] = Field(default_factory=dict, description="财务指标")
    key_metrics: List[str] = Field(default_factory=list, description="关键指标")
    risk_factors: List[str] = Field(default_factory=list, description="风险因素")
    recommendations: List[str] = Field(default_factory=list, description="建议")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")


@dataclass
class FinancialEntity:
    """财务实体"""
    amount: Optional[float] = None
    percentage: Optional[float] = None
    period: Optional[str] = None
    company_name: Optional[str] = None
    account_number: Optional[str] = None
    date: Optional[str] = None
    currency: Optional[str] = None


class FinanceSpecialist(BaseSpecialistAgent):
    """
    财务专家智能体
    
    职责：
    1. 投资分析与评估
    2. 贷款和融资咨询
    3. 预算编制与跟踪
    4. 财务报表分析
    5. 成本控制建议
    6. 现金流管理
    7. 资金运作优化
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        specialty: str = "finance"
    ):
        """
        初始化财务专家
        
        Args:
            llm_adapter: 大模型适配器
            tool_manager: 工具管理器
            specialty: 专业领域标识
        """
        system_prompt = """你是一位专业的财务顾问，具有以下能力：
        1. 精通企业财务管理，包括投资、融资、预算、成本等
        2. 熟悉财务报表分析和经济指标计算
        3. 能够进行财务风险评估
        4. 提供合理的财务规划建议
        
        在回答时，请：
        - 提供具体的计算过程和依据
        - 引用相关的财务指标和标准
        - 指出潜在的财务风险
        - 提供合理的改善建议
        - 明确说明假设条件和局限性
        """
        
        super().__init__(
            specialty=specialty,
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=10,
            timeout=60.0
        )
        
        self.entity_patterns = self._compile_entity_patterns()
        self.financial_ratios = self._load_financial_ratios()
        
    def _compile_entity_patterns(self) -> Dict[str, re.Pattern]:
        """编译财务实体提取正则表达式"""
        return {
            "money": re.compile(
                r'(?:CNY|RMB|￥|¥|USD|\$|EUR|€|GBP|£)?\s*[\d,]+(?:\.\d{2})?',
                re.IGNORECASE
            ),
            "percentage": re.compile(
                r'(\d+(?:\.\d+)?)\s*%',
                re.IGNORECASE
            ),
            "date": re.compile(
                r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?'
            ),
            "period": re.compile(
                r'(?:Q[1-4]|季度|[1234]季度|[12]\d{3}年|(?:20\d{2}[-/年])?\d{1,2}月)',
                re.IGNORECASE
            ),
            "ratio": re.compile(
                r'(?:比率|比例|率):\s*(\d+(?:\.\d+)?)'
            )
        }
    
    def _load_financial_ratios(self) -> Dict[str, Dict[str, Any]]:
        """加载财务比率知识"""
        return {
            "liquidity": {
                "current_ratio": {"good": 2.0, "acceptable": 1.5, "warning": 1.0},
                "quick_ratio": {"good": 1.0, "acceptable": 0.8, "warning": 0.5}
            },
            "solvency": {
                "debt_ratio": {"good": 0.5, "acceptable": 0.6, "warning": 0.7},
                "equity_ratio": {"good": 0.5, "acceptable": 0.4, "warning": 0.3}
            },
            "profitability": {
                "gross_margin": {"good": 0.3, "acceptable": 0.2, "warning": 0.1},
                "net_margin": {"good": 0.1, "acceptable": 0.05, "warning": 0.02}
            },
            "efficiency": {
                "asset_turnover": {"good": 1.5, "acceptable": 1.0, "warning": 0.5},
                "inventory_turnover": {"good": 6.0, "acceptable": 4.0, "warning": 2.0}
            }
        }
    
    def extract_entities(self, text: str) -> FinancialEntity:
        """
        提取财务实体
        
        Args:
            text: 输入文本
            
        Returns:
            提取的财务实体
        """
        entity = FinancialEntity()
        
        for pattern_name, pattern in self.entity_patterns.items():
            matches = pattern.findall(text)
            if matches:
                if pattern_name == "money":
                    amount_str = matches[0].replace(',', '')
                    entity.amount = float(re.sub(r'[^\d.]', '', amount_str))
                    if 'USD' in matches[0] or '$' in matches[0]:
                        entity.currency = 'USD'
                    elif 'EUR' in matches[0] or '€' in matches[0]:
                        entity.currency = 'EUR'
                    elif 'GBP' in matches[0] or '£' in matches[0]:
                        entity.currency = 'GBP'
                    else:
                        entity.currency = 'CNY'
                elif pattern_name == "percentage":
                    entity.percentage = float(matches[0])
                elif pattern_name == "period":
                    entity.period = matches[0]
                elif pattern_name == "date":
                    entity.date = matches[0]
        
        return entity
    
    def identify_domain(self, text: str) -> FinancialDomain:
        """
        识别财务领域
        
        Args:
            text: 输入文本
            
        Returns:
            财务领域
        """
        domain_keywords = {
            "投资": FinancialDomain.INVESTMENT,
            "收益率": FinancialDomain.INVESTMENT,
            "回报": FinancialDomain.INVESTMENT,
            "NPV": FinancialDomain.INVESTMENT,
            "IRR": FinancialDomain.INVESTMENT,
            "贷款": FinancialDomain.LOAN,
            "融资": FinancialDomain.LOAN,
            "利率": FinancialDomain.LOAN,
            "借款": FinancialDomain.LOAN,
            "预算": FinancialDomain.BUDGET,
            "预算编制": FinancialDomain.BUDGET,
            "预算执行": FinancialDomain.BUDGET,
            "财务报表": FinancialDomain.FINANCIAL_STATEMENT,
            "资产负债表": FinancialDomain.FINANCIAL_STATEMENT,
            "利润表": FinancialDomain.FINANCIAL_STATEMENT,
            "现金流量表": FinancialDomain.FINANCIAL_STATEMENT,
            "成本": FinancialDomain.COST_CONTROL,
            "费用": FinancialDomain.COST_CONTROL,
            "降本": FinancialDomain.COST_CONTROL,
            "现金流": FinancialDomain.CASH_FLOW,
            "资金": FinancialDomain.TREASURY,
            "现金管理": FinancialDomain.TREASURY
        }
        
        for keyword, domain in domain_keywords.items():
            if keyword in text:
                return domain
        
        return FinancialDomain.OTHER
    
    async def calculate_investment_metrics(
        self,
        initial_investment: float,
        cash_flows: List[float],
        discount_rate: float = 0.1
    ) -> Dict[str, float]:
        """
        计算投资指标
        
        Args:
            initial_investment: 初始投资
            cash_flows: 现金流列表
            discount_rate: 折现率
            
        Returns:
            投资指标
        """
        npv = -initial_investment
        
        for i, cf in enumerate(cash_flows):
            npv += cf / ((1 + discount_rate) ** (i + 1))
        
        cumulative_cash_flow = -initial_investment
        pay_back_period = len(cash_flows)
        for i, cf in enumerate(cash_flows):
            cumulative_cash_flow += cf
            if cumulative_cash_flow >= 0:
                pay_back_period = i + 1
                break
        
        total_positive_cash_flow = sum(cf for cf in cash_flows if cf > 0)
        roi = (total_positive_cash_flow - initial_investment) / initial_investment if initial_investment > 0 else 0
        
        return {
            "npv": round(npv, 2),
            "payback_period": pay_back_period,
            "roi": round(roi, 4),
            "total_investment": initial_investment,
            "total_return": round(total_positive_cash_flow, 2)
        }
    
    async def calculate_loan_metrics(
        self,
        principal: float,
        annual_rate: float,
        years: int,
        payment_frequency: str = "monthly"
    ) -> Dict[str, float]:
        """
        计算贷款指标
        
        Args:
            principal: 本金
            annual_rate: 年利率
            years: 贷款年限
            payment_frequency: 还款频率
            
        Returns:
            贷款指标
        """
        if payment_frequency == "monthly":
            periods_per_year = 12
        elif payment_frequency == "quarterly":
            periods_per_year = 4
        else:
            periods_per_year = 1
        
        total_periods = years * periods_per_year
        period_rate = annual_rate / periods_per_year
        
        if period_rate > 0:
            payment = principal * (period_rate * (1 + period_rate) ** total_periods) / ((1 + period_rate) ** total_periods - 1)
        else:
            payment = principal / total_periods
        
        total_payment = payment * total_periods
        total_interest = total_payment - principal
        
        return {
            "principal": principal,
            "annual_rate": annual_rate,
            "loan_term_years": years,
            "payment_per_period": round(payment, 2),
            "total_payment": round(total_payment, 2),
            "total_interest": round(total_interest, 2),
            "interest_to_principal_ratio": round(total_interest / principal, 4) if principal > 0 else 0
        }
    
    async def analyze_financial_ratios(
        self,
        current_assets: float,
        current_liabilities: float,
        total_assets: float,
        total_debt: float,
        revenue: float,
        net_income: float,
        gross_profit: float
    ) -> Dict[str, Any]:
        """
        分析财务比率
        
        Args:
            current_assets: 流动资产
            current_liabilities: 流动负债
            total_assets: 总资产
            total_debt: 总负债
            revenue: 营业收入
            net_income: 净利润
            gross_profit: 毛利润
            
        Returns:
            财务比率分析
        """
        ratios = {}
        assessments = {}
        
        if current_liabilities > 0:
            ratios["current_ratio"] = round(current_assets / current_liabilities, 2)
            if ratios["current_ratio"] >= 2.0:
                assessments["current_ratio"] = "良好"
            elif ratios["current_ratio"] >= 1.0:
                assessments["current_ratio"] = "可接受"
            else:
                assessments["current_ratio"] = "预警"
        
        if total_assets > 0:
            ratios["debt_ratio"] = round(total_debt / total_assets, 2)
            if ratios["debt_ratio"] <= 0.5:
                assessments["debt_ratio"] = "良好"
            elif ratios["debt_ratio"] <= 0.7:
                assessments["debt_ratio"] = "可接受"
            else:
                assessments["debt_ratio"] = "预警"
        
        if revenue > 0:
            ratios["gross_margin"] = round(gross_profit / revenue, 4)
            ratios["net_margin"] = round(net_income / revenue, 4)
            
            if ratios["gross_margin"] >= 0.3:
                assessments["gross_margin"] = "良好"
            elif ratios["gross_margin"] >= 0.2:
                assessments["gross_margin"] = "可接受"
            else:
                assessments["gross_margin"] = "预警"
            
            if ratios["net_margin"] >= 0.1:
                assessments["net_margin"] = "良好"
            elif ratios["net_margin"] >= 0.05:
                assessments["net_margin"] = "可接受"
            else:
                assessments["net_margin"] = "预警"
        
        return {
            "ratios": ratios,
            "assessments": assessments,
            "overall_health": "healthy" if all(v in ["良好", "可接受"] for v in assessments.values()) else "needs_attention"
        }
    
    async def run(
        self,
        user_input: str,
        history: List[Dict[str, Any]] = None,
        context: Dict[str, Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        处理财务咨询请求
        
        Args:
            user_input: 用户输入
            history: 对话历史
            context: 上下文信息
            **kwargs: 其他参数
            
        Returns:
            处理结果
        """
        try:
            entities = self.extract_entities(user_input)
            domain = self.identify_domain(user_input)
            
            prompt = self._build_finance_prompt(user_input, entities, domain)
            
            response = await self.llm_adapter.generate(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.3
            )
            
            analysis = self._parse_llm_response(response, domain, entities)
            
            risk_assessment = self.assess_financial_risk(analysis, entities)
            
            return {
                "success": True,
                "domain": domain,
                "analysis": analysis.dict(),
                "risk_assessment": risk_assessment,
                "entities": {
                    "amount": entities.amount,
                    "percentage": entities.percentage,
                    "period": entities.period,
                    "currency": entities.currency
                },
                "recommendations": self._generate_recommendations(analysis, domain),
                "confidence": analysis.confidence
            }
            
        except Exception as e:
            logger.error(f"财务分析失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback": "建议您咨询专业财务顾问获取准确信息"
            }
    
    def _build_finance_prompt(
        self,
        user_input: str,
        entities: FinancialEntity,
        domain: FinancialDomain
    ) -> str:
        """构建财务分析提示词"""
        prompt_parts = [
            f"用户问题：{user_input}\n",
            f"识别财务领域：{domain.value}",
            f"\n提取的财务实体："
        ]
        
        if entities.amount:
            prompt_parts.append(f"- 金额：{entities.amount} {entities.currency or 'CNY'}")
        if entities.percentage:
            prompt_parts.append(f"- 百分比：{entities.percentage}%")
        if entities.period:
            prompt_parts.append(f"- 期间：{entities.period}")
        
        prompt_parts.extend([
            "\n请进行财务分析，包括：",
            "1. 相关财务指标计算",
            "2. 财务状况评估",
            "3. 潜在风险因素",
            "4. 改进建议"
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_llm_response(
        self,
        response: str,
        domain: FinancialDomain,
        entities: FinancialEntity
    ) -> FinancialAnalysisResult:
        """解析LLM响应"""
        try:
            financial_indicators = {}
            key_metrics = []
            risk_factors = []
            
            if entities.amount:
                financial_indicators["amount"] = entities.amount
            if entities.percentage:
                financial_indicators["percentage"] = entities.percentage
            
            if "风险" in response or "风险因素" in response:
                risk_factors.append("发现潜在财务风险")
            
            confidence = 0.8
            if entities.amount and entities.percentage:
                confidence = 0.95
            
            return FinancialAnalysisResult(
                domain=domain,
                financial_indicators=financial_indicators,
                key_metrics=key_metrics,
                risk_factors=risk_factors,
                confidence=confidence
            )
        except Exception as e:
            logger.warning(f"解析财务响应失败: {e}")
            return FinancialAnalysisResult(
                domain=FinancialDomain.OTHER,
                confidence=0.5
            )
    
    def assess_financial_risk(
        self,
        analysis: FinancialAnalysisResult,
        entities: FinancialEntity
    ) -> Dict[str, Any]:
        """
        评估财务风险
        
        Args:
            analysis: 财务分析结果
            entities: 财务实体
            
        Returns:
            风险评估结果
        """
        risk_level = "low"
        risk_factors = []
        
        if analysis.confidence < 0.7:
            risk_level = "medium"
            risk_factors.append("置信度较低，建议人工复核")
        
        if analysis.risk_factors:
            risk_level = "high"
            risk_factors.extend(analysis.risk_factors)
        
        if entities.amount and entities.amount > 50000000:
            risk_level = "high"
            risk_factors.append("涉及金额较大，建议专业财务审核")
        
        if analysis.domain == FinancialDomain.INVESTMENT:
            if not entities.amount or not entities.percentage:
                risk_level = "medium"
                risk_factors.append("投资分析缺少关键参数")
        
        return {
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "requires_financial_review": risk_level in ["high", "medium"]
        }
    
    def _generate_recommendations(
        self,
        analysis: FinancialAnalysisResult,
        domain: FinancialDomain
    ) -> List[str]:
        """生成财务建议"""
        recommendations = []
        
        if analysis.domain == FinancialDomain.INVESTMENT:
            recommendations.append("进行详细的投资可行性研究")
            recommendations.append("考虑多种投资方案进行比较")
            recommendations.append("设置投资止损和止盈机制")
        
        if analysis.domain == FinancialDomain.LOAN:
            recommendations.append("比较不同融资渠道的成本")
            recommendations.append("合理安排还款计划")
            recommendations.append("关注利率变动风险")
        
        if analysis.domain == FinancialDomain.BUDGET:
            recommendations.append("建立预算执行监控机制")
            recommendations.append("定期进行预算差异分析")
            recommendations.append("预留适当的应急资金")
        
        if analysis.domain == FinancialDomain.FINANCIAL_STATEMENT:
            recommendations.append("关注关键财务指标的变化趋势")
            recommendations.append("定期进行财务健康检查")
            recommendations.append("建立财务预警机制")
        
        if analysis.risk_factors:
            recommendations.append("重点关注潜在的财务风险")
            recommendations.append("建议进行详细的尽职调查")
        
        recommendations.append("如涉及重大财务决策，建议咨询专业财务顾问")
        recommendations.append("保留完整的财务记录和凭证")
        
        return recommendations
    
    async def audit(
        self,
        state: AuditState,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        执行财务审查
        
        Args:
            state: 全局状态
            documents: 待审查文档
            
        Returns:
            审查发现列表
        """
        findings = []
        
        for doc in documents:
            content = doc.get("content", "")
            
            entities = self.extract_entities(content)
            domain = self.identify_domain(content)
            
            if entities.amount:
                findings.append(Finding(
                    finding_id=f"FIN_AMT_{len(findings) + 1}",
                    category="金额信息",
                    description=f"发现财务金额：{entities.amount}",
                    severity="info",
                    document_id=doc.get("doc_id"),
                    recommendation="核实金额的准确性"
                ))
            
            if entities.percentage and (entities.percentage < 0 or entities.percentage > 100):
                findings.append(Finding(
                    finding_id=f"FIN_PCT_{len(findings) + 1}",
                    category="百分比异常",
                    description=f"发现异常百分比：{entities.percentage}%",
                    severity="warning",
                    document_id=doc.get("doc_id"),
                    recommendation="核实百分比的合理性"
                ))
            
            for rule in self.knowledge_base:
                if rule.get("rule_id", "").startswith("FIN"):
                    if any(keyword in content for keyword in ["不符", "异常", "错误", "亏损"]):
                        findings.append(Finding(
                            finding_id=f"FIN_KB_{len(findings) + 1}",
                            category=rule.get("category", "财务合规"),
                            description=rule.get("description", ""),
                            severity="high",
                            document_id=doc.get("doc_id"),
                            recommendation="进行财务合规性检查"
                        ))
        
        return findings
    
    def get_financial_knowledge(self, domain: str) -> List[Dict[str, Any]]:
        """
        获取特定财务领域的知识
        
        Args:
            domain: 财务领域
            
        Returns:
            财务知识列表
        """
        financial_knowledge_map = {
            "investment": [
                {
                    "rule_id": "INV_001",
                    "category": "投资决策",
                    "description": "投资决策的关键指标",
                    "indicators": ["NPV", "IRR", "投资回收期", "ROI"]
                },
                {
                    "rule_id": "INV_002",
                    "category": "风险评估",
                    "description": "投资风险评估方法",
                    "methods": ["敏感性分析", "情景分析", "Monte Carlo模拟"]
                }
            ],
            "loan": [
                {
                    "rule_id": "LOAN_001",
                    "category": "贷款成本",
                    "description": "贷款成本计算方法",
                    "indicators": ["实际利率", "总利息", "还款压力"]
                },
                {
                    "rule_id": "LOAN_002",
                    "category": "融资结构",
                    "description": "最优融资结构建议",
                    "principles": ["期限匹配", "成本优化", "风险控制"]
                }
            ],
            "budget": [
                {
                    "rule_id": "BUD_001",
                    "category": "预算编制",
                    "description": "预算编制方法",
                    "methods": ["增量预算", "零基预算", "滚动预算"]
                },
                {
                    "rule_id": "BUD_002",
                    "category": "预算控制",
                    "description": "预算执行监控要点",
                    "checkpoints": ["实际vs预算", "差异分析", "调整机制"]
                }
            ]
        }
        
        return financial_knowledge_map.get(domain, [])
