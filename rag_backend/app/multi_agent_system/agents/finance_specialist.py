"""
财务专家智能体 (Finance Specialist Agent)
处理企业财务相关问题，包括投资分析、贷款计算、预算管理、财务报表分析等

【MCP 工具集成】
财务数据存储在数据库中，不在 RAG 知识库。本 Agent 使用 MCP 工具直接查询数据库：
- query_financial_data: 查询详细财务记录
- get_financial_overview: 获取财务概览摘要
- get_financial_trend: 获取财务趋势数据
- search_financial_data: 搜索财务数据
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

from pydantic import BaseModel, Field, model_validator

from .base_specialist import BaseSpecialistAgent
from .base_agent_prompt import load_agent_prompt
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
    
    @model_validator(mode='after')
    def validate_and_clean_indicators(self) -> 'FinancialAnalysisResult':
        """
        模型验证器：作为最后防线，确保所有浮点数字段类型正确
        
        如果解析时未正确清理，这里会尝试修复
        """
        if self.financial_indicators:
            cleaned = {}
            for key, value in self.financial_indicators.items():
                if isinstance(value, (int, float)):
                    cleaned[key] = float(value)
                elif isinstance(value, str):
                    percent_match = re.match(r'^([-+]?\d*\.?\d+)%?$', value.strip())
                    if percent_match:
                        try:
                            num = float(percent_match.group(1))
                            if '%' in value:
                                num = num / 100.0
                            cleaned[key] = num
                        except ValueError:
                            pass
                    else:
                        try:
                            cleaned[key] = float(value)
                        except ValueError:
                            pass
                else:
                    cleaned[key] = value
            self.financial_indicators = cleaned
        
        if self.confidence < 0:
            self.confidence = 0.0
        elif self.confidence > 1:
            self.confidence = 1.0
            
        return self


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
        system_prompt = self._load_system_prompt()
        
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
        
        self._register_financial_mcp_tools()
    
    def _register_financial_mcp_tools(self):
        """
        注册 MCP 财务数据查询工具
        
        这些工具直接从数据库查询财务数据，包含上下文优化机制
        """
        try:
            from app.mcp.financial_tools import create_financial_tools
            
            financial_tools = create_financial_tools()
            for tool in financial_tools:
                try:
                    self.tool_manager.register_langchain_tool(tool)
                    logger.info(f"✅ [财务专家] 注册 MCP 工具: {tool.name}")
                except Exception as e:
                    logger.warning(f"⚠️ [财务专家] 注册工具失败 {tool.name}: {e}")
            
            logger.info(f"📊 [财务专家] MCP 财务工具注册完成，共 {len(financial_tools)} 个工具")
            
        except ImportError as e:
            logger.warning(f"⚠️ [财务专家] 无法导入 MCP 财务工具: {e}")
        except Exception as e:
            logger.error(f"❌ [财务专家] 注册 MCP 工具时出错: {e}")
    
    def _load_system_prompt(self) -> str:
        """从外部文件加载系统提示词"""
        try:
            return load_agent_prompt(
                agent_name="finance",
                filename="finance_agent.md",
                context=self._get_prompt_context()
            )
        except Exception as e:
            print(f"⚠️ [财务专家智能体] 加载提示词失败，使用默认提示词: {e}")
            return self._build_default_prompt()
    
    def _get_prompt_context(self) -> Dict[str, Any]:
        """获取提示词渲染上下文"""
        return {
            "financial_domains": [d.value for d in FinancialDomain],
        }
    
    def _build_default_prompt(self) -> str:
        """构建默认提示词"""
        return """你是一位专业的财务顾问，具有以下能力：
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
    
    async def _query_user_financial_data(self, context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        查询用户的企业财务数据（使用 MCP 工具）
        
        Args:
            context: 上下文信息，包含 tenant_id、user_id 等
            
        Returns:
            用户的财务数据，如果没有则返回 None
        """
        try:
            tenant_id = None
            user_id = None
            fiscal_year = None
            
            if context:
                tenant_id = context.get("tenant_id")
                user_id = context.get("user_id")
                fiscal_year = context.get("fiscal_year")
            
            if not tenant_id or not user_id or tenant_id == "default" or user_id == "default":
                logger.debug("🔍 [FinanceSpecialist] 跳过财务数据查询：未提供有效的 tenant_id 或 user_id")
                return None
            
            from app.mcp.financial_tools import get_financial_overview
            
            logger.debug(f"🔍 [FinanceSpecialist] 正在通过 MCP 工具查询财务数据: tenant={tenant_id}, year={fiscal_year}")
            
            result = await get_financial_overview.ainvoke(
                {
                    "tenant_id": tenant_id,
                    "fiscal_year": fiscal_year if fiscal_year else None
                }
            )
            
            if result.get("status") == "success":
                logger.info(f"✅ [FinanceSpecialist] 成功通过 MCP 工具获取用户财务数据")
                return result
            
            logger.warning(f"⚠️ [FinanceSpecialist] 未能获取用户财务数据: {result.get('message', '未知错误')}")
            return None
            
        except ImportError as e:
            logger.warning(f"⚠️ [FinanceSpecialist] MCP 财务工具不可用: {e}")
            return None
        except Exception as e:
            logger.warning(f"⚠️ [FinanceSpecialist] 查询用户财务数据失败: {e}")
            return None
    
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
            "现金管理": FinancialDomain.TREASURY,
            "风险": FinancialDomain.FINANCIAL_STATEMENT,
            "财务风险": FinancialDomain.FINANCIAL_STATEMENT,
            "资产负债": FinancialDomain.FINANCIAL_STATEMENT,
            "盈利": FinancialDomain.FINANCIAL_STATEMENT,
            "利润": FinancialDomain.FINANCIAL_STATEMENT,
            "收益": FinancialDomain.INVESTMENT,
            "ROE": FinancialDomain.INVESTMENT,
            "ROA": FinancialDomain.INVESTMENT
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
        rag_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        处理财务咨询请求
        
        Args:
            user_input: 用户输入
            history: 对话历史
            context: 上下文信息
            rag_context: RAG检索到的上下文数据（包含企业财务数据）
            **kwargs: 其他参数
            
        Returns:
            处理结果
        """
        try:
            entities = self.extract_entities(user_input)
            domain = self.identify_domain(user_input)
            
            logger.debug(f"🔍 [FinanceSpecialist] domain={domain}, entities={entities}")
            logger.debug(f"🔍 [FinanceSpecialist] RAG上下文: {bool(rag_context)}")
            
            user_financial_data = await self._query_user_financial_data(context)
            
            financial_context = rag_context.copy() if rag_context else {}
            if user_financial_data:
                financial_context["user_financial_data"] = user_financial_data
            
            prompt = self._build_finance_prompt(user_input, entities, domain, financial_context)
            logger.debug(f"🔍 [FinanceSpecialist] 调用 LLM...")
            
            full_prompt = f"{self.system_prompt}\n\n{prompt}" if self.system_prompt else prompt
            llm_response = await self.llm_adapter.generate(
                prompt=full_prompt,
                temperature=0.3
            )
            
            logger.debug(f"🔍 [FinanceSpecialist] LLM响应: {type(llm_response)}")
            
            response_text = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
            logger.debug(f"🔍 [FinanceSpecialist] LLM响应文本长度: {len(response_text)}")
            
            analysis = self._parse_llm_response(response_text, domain, entities)
            
            logger.debug(f"🔍 [FinanceSpecialist] 分析完成: domain={analysis.domain}, indicators={len(analysis.financial_indicators)}, risks={len(analysis.risk_factors)}, metrics={len(analysis.key_metrics)}, recs={len(analysis.recommendations)}")
            
            risk_assessment = self.assess_financial_risk(analysis, entities)
            
            final_recommendations = analysis.recommendations if analysis.recommendations else self._generate_recommendations(analysis, domain)
            
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
                "financial_indicators": analysis.financial_indicators,
                "key_metrics": analysis.key_metrics,
                "risk_factors": analysis.risk_factors,
                "recommendations": final_recommendations,
                "confidence": analysis.confidence,
                "rag_enabled": rag_context is not None,
                "user_financial_data": user_financial_data
            }
            
        except (ValueError, KeyError) as e:
            logger.error(f"财务分析数据失败: {e}")
            return {
                "success": False,
                "error": f"数据错误: {str(e)}",
                "fallback": "建议您咨询专业财务顾问获取准确信息"
            }
        except (OSError, IOError) as e:
            logger.error(f"财务分析IO失败: {e}")
            return {
                "success": False,
                "error": f"IO错误: {str(e)}",
                "fallback": "建议您咨询专业财务顾问获取准确信息"
            }
        except Exception as e:
            logger.error(f"财务分析失败: {e}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "fallback": "建议您咨询专业财务顾问获取准确信息"
            }
    
    def _build_finance_prompt(
        self,
        user_input: str,
        entities: FinancialEntity,
        domain: FinancialDomain,
        rag_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建财务分析提示词"""
        prompt_parts = [
            "# 财务分析任务\n\n",
            f"## 用户问题\n{user_input}\n\n",
            f"## 识别财务领域\n{domain.value}\n"
        ]
        
        if entities.amount or entities.percentage or entities.period:
            prompt_parts.append("\n## 提取的财务实体\n")
            if entities.amount:
                prompt_parts.append(f"- **涉及金额**：{entities.amount:,.2f} {entities.currency or 'CNY'}\n")
            if entities.percentage:
                prompt_parts.append(f"- **百分比/比率**：{entities.percentage}%\n")
            if entities.period:
                prompt_parts.append(f"- **期间**：{entities.period}\n")
        
        if rag_context:
            prompt_parts.extend([
                "\n## 企业相关财务数据（来自知识库）\n"
            ])
            if rag_context.get('documents'):
                for i, doc in enumerate(rag_context['documents'][:5], 1):
                    content = doc.get('content', '')
                    metadata = doc.get('metadata', {})
                    title = metadata.get('title', f'文档{i}')
                    prompt_parts.append(f"### {title}\n{content[:500]}\n\n")
            
            if rag_context.get('summary'):
                prompt_parts.append(f"\n### 数据摘要\n{rag_context['summary']}\n")
        
        user_financial_data = rag_context.get('user_financial_data') if rag_context else None
        if user_financial_data and user_financial_data.get('status') == 'success':
            prompt_parts.extend([
                "\n## 用户企业真实财务数据（来自企业数据库）\n",
                "以下是该企业的真实财务数据，请务必基于这些实际数据进行深入分析：\n\n"
            ])
            
            data = user_financial_data.get('data', {})
            fiscal_year = user_financial_data.get('fiscal_year', '当前')
            
            prompt_parts.append(f"### {fiscal_year}年度财务概览\n")
            
            if data.get('summary'):
                summary = data['summary']
                prompt_parts.append(f"- **营业收入**: {summary.get('total_revenue', 0):,.2f} 元\n")
                prompt_parts.append(f"- **营业成本**: {summary.get('total_cost', 0):,.2f} 元\n")
                prompt_parts.append(f"- **毛利润**: {summary.get('gross_profit', 0):,.2f} 元\n")
                prompt_parts.append(f"- **毛利率**: {summary.get('gross_margin', 0):.2f}%\n")
                prompt_parts.append(f"- **净利润**: {summary.get('net_profit', 0):,.2f} 元\n")
                prompt_parts.append(f"- **净利率**: {summary.get('net_margin', 0):.2f}%\n")
                prompt_parts.append(f"- **营业费用**: {summary.get('operating_expenses', 0):,.2f} 元\n")
                prompt_parts.append(f"- **财务费用**: {summary.get('financial_expenses', 0):,.2f} 元\n")
            
            if data.get('revenue_breakdown'):
                prompt_parts.append("\n### 收入构成\n")
                for item in data['revenue_breakdown']:
                    revenue_type = item.get('revenue_type', '其他')
                    amount = item.get('amount', 0)
                    prompt_parts.append(f"- **{revenue_type}**: {amount:,.2f} 元\n")
            
            if data.get('expense_breakdown'):
                prompt_parts.append("\n### 费用构成\n")
                for item in data['expense_breakdown']:
                    expense_type = item.get('expense_type', '其他')
                    amount = item.get('amount', 0)
                    prompt_parts.append(f"- **{expense_type}**: {amount:,.2f} 元\n")
            
            if data.get('tax_info'):
                prompt_parts.append("\n### 税务信息\n")
                tax_info = data['tax_info']
                if tax_info.get('vat'):
                    vat = tax_info['vat']
                    prompt_parts.append(f"- **增值税**: 销项税 {vat.get('output_tax', 0):,.2f} 元，进项税 {vat.get('input_tax', 0):,.2f} 元，应纳税额 {vat.get('taxable_amount', 0):,.2f} 元\n")
                if tax_info.get('corporate_tax'):
                    ct = tax_info['corporate_tax']
                    prompt_parts.append(f"- **企业所得税**: 应税收入 {ct.get('taxable_income', 0):,.2f} 元，应纳税额 {ct.get('tax_amount', 0):,.2f} 元\n")
            
            prompt_parts.append("\n⚠️ **重要提示**：以上数据为企业真实财务记录，请基于这些实际数据进行分析，不要使用假设性数据。\n")
        
        prompt_parts.extend([
            "\n## 分析要求\n\n",
            "请对上述财务问题进行全面、深入的分析，**必须**遵循以下要求：\n\n",
            "### 1. 财务指标分析\n",
            "- 计算或分析相关财务比率（如：流动比率、速动比率、资产负债率、毛利率、净利率、ROE、ROA等）\n",
            "- 对比行业标准或历史数据\n",
            "- 使用具体数值而非模糊描述\n\n",
            "### 2. 风险因素识别\n",
            "- **必须**列出至少3-5个具体的风险因素\n",
            "- 分析每个风险的可能性和影响程度\n",
            "- 引用具体的财务数据作为证据\n\n",
            "### 3. 关键指标提取\n",
            "- 识别并列出关键财务指标\n",
            "- 说明每个指标的正常范围和当前状态\n",
            "- 提供具体的数值和建议阈值\n\n",
            "### 4. 改进建议\n",
            "- 基于分析结果提出**具体的**、**可操作的**建议\n",
            "- 区分短期和长期建议\n",
            "- 量化建议的潜在收益\n\n",
            "## 输出格式\n\n",
            "请按以下JSON格式返回分析结果（**不要**使用markdown代码块包裹）：\n\n",
            "```json\n",
            "{\n",
            '  "financial_indicators": {\n',
            '    "指标名称1": 数值,\n',
            '    "指标名称2": "描述性内容"\n',
            "  },\n",
            '  "key_metrics": [\n',
            '    "关键指标1：具体数值和说明",\n',
            '    "关键指标2：具体数值和说明"\n',
            "  ],\n",
            '  "risk_factors": [\n',
            '    "风险1：具体描述和影响分析（引用数据）",\n',
            '    "风险2：具体描述和影响分析（引用数据）"\n',
            "  ],\n",
            '  "recommendations": [\n',
            '    "建议1：具体内容和预期效果（量化）",\n',
            '    "建议2：具体内容和预期效果（量化）"\n',
            "  ],\n",
            '  "confidence": 0.85\n',
            "}\n",
            "```\n\n",
            "**重要提醒**：\n",
            "1. 所有风险因素和建议必须**具体**、**可操作**，避免泛泛而谈\n",
            "2. 必须包含至少3个风险因素和3个建议\n",
            "3. 使用实际数据和分析支撑结论，不要仅使用模板语言\n",
            "4. 如果企业数据不足，应基于通用财务知识和最佳实践提供分析\n"
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
            recommendations = []
            confidence = 0.8
            
            if entities.amount:
                financial_indicators["涉及金额"] = entities.amount
            if entities.percentage:
                financial_indicators["相关比率"] = entities.percentage
            
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if json_match:
                try:
                    parsed_data = json.loads(json_match.group())
                    
                    if "financial_indicators" in parsed_data:
                        financial_indicators.update(parsed_data["financial_indicators"])
                    elif "indicators" in parsed_data:
                        financial_indicators.update(parsed_data["indicators"])
                    elif "metrics" in parsed_data:
                        financial_indicators.update(parsed_data["metrics"])
                    
                    if "key_metrics" in parsed_data:
                        key_metrics = parsed_data["key_metrics"]
                    elif "metrics" in parsed_data and isinstance(parsed_data["metrics"], list):
                        key_metrics = parsed_data["metrics"]
                    elif "关键指标" in parsed_data:
                        key_metrics = parsed_data["关键指标"]
                    
                    if "risk_factors" in parsed_data:
                        risk_factors = parsed_data["risk_factors"]
                    elif "风险因素" in parsed_data:
                        risk_factors = parsed_data["风险因素"]
                    elif "risks" in parsed_data:
                        risk_factors = parsed_data["risks"]
                    
                    if "recommendations" in parsed_data:
                        recommendations = parsed_data["recommendations"]
                    elif "建议" in parsed_data:
                        recommendations = parsed_data["建议"]
                    elif "recommend" in parsed_data:
                        recommendations = parsed_data["recommend"]
                    
                    if "confidence" in parsed_data:
                        confidence = float(parsed_data["confidence"])
                    elif "置信度" in parsed_data:
                        confidence = float(parsed_data["置信度"])
                    else:
                        confidence = 0.85
                        
                except json.JSONDecodeError:
                    pass
            
            if not financial_indicators or len(financial_indicators) <= 2:
                lines = response.split('\n')
                for line in lines:
                    if '：' in line or ':' in line:
                        parts = line.replace('：', ':').split(':', 1)
                        if len(parts) == 2:
                            key = parts[0].strip().replace('**', '')
                            value = parts[1].strip().replace('**', '')
                            if any(unit in value for unit in ['%', '元', '万', '亿', '比例', '率', '倍']):
                                try:
                                    num_match = re.search(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', value)
                                    if num_match:
                                        financial_indicators[key] = float(num_match.group())
                                except (ValueError, AttributeError):
                                    pass
            
            if not risk_factors:
                risk_patterns = [
                    r'(?:风险|隐患|问题|不足|缺陷)[:：]\s*(.+)',
                    r'(?:发现|识别|检测到)(?:的)?(.+?风险)',
                    r'(- .+风险.+)',
                    r'(?:需要关注|应当重视)[:：]\s*(.+)'
                ]
                for pattern in risk_patterns:
                    matches = re.findall(pattern, response)
                    for match in matches:
                        if isinstance(match, tuple):
                            risk_factors.extend([m.strip() for m in match if m.strip()])
                        elif isinstance(match, str) and match.strip():
                            risk_factors.append(match.strip())
            
            if not key_metrics:
                metric_patterns = [
                    r'(?:指标|比率|系数)[:：]\s*(.+)',
                    r'(- .+(?:率|比|指数|指标).+)',
                    r'((?:ROI|ROE|ROA|NPM|毛利率|净利率|负债率).*?(?:\d+\.?\d*%?))'
                ]
                for pattern in metric_patterns:
                    matches = re.findall(pattern, response, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            key_metrics.extend([m.strip() for m in match if m.strip()])
                        elif isinstance(match, str) and match.strip():
                            key_metrics.append(match.strip())
            
            if not recommendations:
                rec_patterns = [
                    r'(?:建议|推荐)[:：]\s*(.+)',
                    r'(- .+)',
                    r'((?:建议|推荐)进行.+?[\n。])'
                ]
                for pattern in rec_patterns:
                    matches = re.findall(pattern, response)
                    for match in matches:
                        if isinstance(match, tuple):
                            recommendations.extend([m.strip() for m in match if m.strip() and len(m.strip()) > 5])
                        elif isinstance(match, str) and match.strip() and len(match.strip()) > 5:
                            recommendations.append(match.strip())
            
            risk_keywords = ['高风险', '风险', '隐患', '问题', '不足', '缺陷', '威胁', '脆弱']
            if not risk_factors and any(kw in response for kw in risk_keywords):
                risk_factors.append("基于内容分析发现潜在的财务风险点")
            
            if entities.amount and entities.percentage:
                confidence = 0.9
            if financial_indicators and len(financial_indicators) > 2:
                confidence = 0.9
            if risk_factors and len(risk_factors) > 0:
                confidence = max(confidence, 0.85)
            if key_metrics and len(key_metrics) > 2:
                confidence = max(confidence, 0.92)
            if recommendations and len(recommendations) > 0:
                confidence = max(confidence, 0.88)
            
            financial_indicators = self._clean_financial_indicators(financial_indicators)
            
            return FinancialAnalysisResult(
                domain=domain,
                financial_indicators=financial_indicators,
                key_metrics=key_metrics[:10],
                risk_factors=risk_factors[:10],
                recommendations=recommendations[:10],
                confidence=confidence
            )
        except (ValueError, KeyError) as e:
            logger.warning(f"解析财务响应数据失败: {e}")
            traceback.print_exc()
            return FinancialAnalysisResult(
                domain=FinancialDomain.OTHER,
                confidence=0.0
            )
    
    def _clean_financial_indicators(self, indicators: Dict[str, Any]) -> Dict[str, float]:
        """
        清理财务指标数据，将字符串转换为浮点数
        
        Args:
            indicators: 原始财务指标字典
            
        Returns:
            清理后的财务指标字典，所有值都是浮点数
        """
        cleaned = {}
        
        for key, value in indicators.items():
            if value is None or value == '' or value == []:
                continue
            
            if isinstance(value, (int, float)):
                cleaned[key] = float(value)
            elif isinstance(value, str):
                value = value.strip()
                if not value:
                    continue
                
                percent_match = re.match(r'^([-+]?\d*\.?\d+)%?$', value)
                if percent_match:
                    num_str = percent_match.group(1)
                    try:
                        num = float(num_str)
                        if '%' in value:
                            num = num / 100.0
                        cleaned[key] = num
                    except ValueError:
                        cleaned[key] = value
                else:
                    cleaned[key] = value
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, (int, float)):
                        cleaned[f"{key}_{sub_key}"] = float(sub_value)
                    elif isinstance(sub_value, str):
                        percent_match = re.match(r'^([-+]?\d*\.?\d+)%?$', sub_value.strip())
                        if percent_match:
                            try:
                                num = float(percent_match.group(1))
                                if '%' in sub_value:
                                    num = num / 100.0
                                cleaned[f"{key}_{sub_key}"] = num
                            except ValueError:
                                pass
                    elif isinstance(sub_value, dict):
                        for sub_sub_key, sub_sub_value in sub_sub_value.items():
                            if isinstance(sub_sub_value, (int, float)):
                                cleaned[f"{key}_{sub_key}_{sub_sub_key}"] = float(sub_sub_value)
            
            if key not in cleaned:
                cleaned[key] = value
        
        return cleaned
    
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
                    id=f"FIN_AMT_{len(findings) + 1}",
                    agent_name="finance",
                    category="金额信息",
                    description=f"发现财务金额：{entities.amount}",
                    risk_level=RiskLevel.INFO,
                    risk_score=10.0,
                    confidence=0.8,
                    evidence=[],
                    recommendations=["核实金额的准确性"]
                ))
            
            if entities.percentage and (entities.percentage < 0 or entities.percentage > 100):
                findings.append(Finding(
                    id=f"FIN_PCT_{len(findings) + 1}",
                    agent_name="finance",
                    category="百分比异常",
                    description=f"发现异常百分比：{entities.percentage}%",
                    risk_level=RiskLevel.MEDIUM,
                    risk_score=40.0,
                    confidence=0.7,
                    evidence=[],
                    recommendations=["核实百分比的合理性"]
                ))
            
            for rule in self.knowledge_base:
                if rule.get("rule_id", "").startswith("FIN"):
                    if any(keyword in content for keyword in ["不符", "异常", "错误", "亏损"]):
                        findings.append(Finding(
                            id=f"FIN_KB_{len(findings) + 1}",
                            agent_name="finance",
                            category=rule.get("category", "财务合规"),
                            description=rule.get("description", ""),
                            risk_level=RiskLevel.HIGH,
                            risk_score=70.0,
                            confidence=0.8,
                            evidence=[],
                            recommendations=["进行财务合规性检查"]
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
    
    def get_key_metrics(self, domain: FinancialDomain) -> List[str]:
        """获取指定领域的关键指标"""
        metrics_map = {
            FinancialDomain.INVESTMENT: ["ROI", "IRR", "NPV", "回收期"],
            FinancialDomain.LOAN: ["利率", "还款额", "杠杆率", "负债率"],
            FinancialDomain.BUDGET: ["预算执行率", "差异率", "调整次数"],
            FinancialDomain.FINANCIAL_STATEMENT: ["毛利率", "净利率", "资产负债率", "流动比率"],
            FinancialDomain.COST_CONTROL: ["成本率", "变动成本率", "固定成本占比"],
            FinancialDomain.CASH_FLOW: ["经营活动现金流", "自由现金流", "现金转化率"],
            FinancialDomain.TREASURY: ["资金周转率", "资金利用率", "备付金率"],
        }
        return metrics_map.get(domain, ["利润率", "周转率", "负债率"])
    
    def get_recommendations(self, domain: FinancialDomain) -> List[str]:
        """获取指定领域的建议"""
        recommendations_map = {
            FinancialDomain.INVESTMENT: ["进行尽职调查", "分散投资风险", "关注现金流"],
            FinancialDomain.LOAN: ["比较利率方案", "注意还款能力", "关注抵押担保"],
            FinancialDomain.BUDGET: ["建立预算预警", "定期执行分析", "及时调整偏差"],
            FinancialDomain.FINANCIAL_STATEMENT: ["关注关键财务比率", "纵向对比历史数据", "横向对标行业"],
            FinancialDomain.COST_CONTROL: ["识别成本动因", "优化采购流程", "提高运营效率"],
            FinancialDomain.CASH_FLOW: ["加强应收账款管理", "合理安排付款节奏", "保持现金储备"],
            FinancialDomain.TREASURY: ["集中资金管理", "合理配置资产期限", "控制流动性风险"],
        }
        return recommendations_map.get(domain, ["加强财务管理", "定期分析报表", "关注现金流"])
    
    async def stream_run(
        self,
        user_input: str,
        history: List[Dict] = None,
        **kwargs
    ):
        domain = self.identify_domain(user_input)
        entities = self.extract_entities(user_input)
        
        financial_data = {
            "domain": domain.value,
            "entities": {
                "amount": entities.amount,
                "percentage": entities.percentage,
                "period": entities.period,
                "company_name": entities.company_name
            },
            "key_metrics": self.get_key_metrics(domain),
            "recommendations": self.get_recommendations(domain)
        }
        
        result_str = json.dumps(financial_data, ensure_ascii=False, indent=2)
        
        for char in result_str:
            yield char
