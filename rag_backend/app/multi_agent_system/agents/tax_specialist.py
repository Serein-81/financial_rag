"""
税务专家智能体 (Tax Specialist Agent)
处理企业税务相关问题，包括增值税、企业所得税、个人所得税等
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass

from pydantic import BaseModel, Field

from .base_specialist import BaseSpecialistAgent
from .base_agent_prompt import load_agent_prompt
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from ..state import AuditState, Finding, RiskLevel

logger = logging.getLogger(__name__)


class TaxType(str, Enum):
    """税种类型"""
    VAT = "vat"  # 增值税
    INCOME_TAX = "income_tax"  # 企业所得税
    PERSONAL_INCOME_TAX = "personal_income_tax"  # 个人所得税
    CONSUMPTION_TAX = "consumption_tax"  # 消费税
    BUSINESS_TAX = "business_tax"  # 营业税（已废止）
    PROPERTY_TAX = "property_tax"  # 房产税
    LAND_USE_TAX = "land_use_tax"  # 城镇土地使用税
    STAMP_TAX = "stamp_tax"  # 印花税
    ENVIRONMENT_TAX = "environment_tax"  # 环境保护税
    OTHER = "other"


class TaxAnalysisResult(BaseModel):
    """税务分析结果"""
    tax_type: TaxType = Field(description="识别的税种类型")
    tax_rate: Optional[float] = Field(default=None, description="适用税率")
    tax_amount: Optional[float] = Field(default=None, description="税额计算结果")
    tax_period: Optional[str] = Field(default=None, description="税务期间")
    deductions: List[str] = Field(default_factory=list, description="可扣除项目")
    exemptions: List[str] = Field(default_factory=list, description="免税项目")
    risk_points: List[str] = Field(default_factory=list, description="风险点")
    compliance_status: str = Field(default="compliant", description="合规状态")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")


@dataclass
class TaxEntity:
    """税务实体"""
    tax_type: Optional[str] = None
    tax_rate: Optional[float] = None
    tax_amount: Optional[float] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    company_name: Optional[str] = None
    tax_id: Optional[str] = None
    period: Optional[str] = None


class TaxSpecialist(BaseSpecialistAgent):
    """
    税务专家智能体
    
    职责：
    1. 税务政策咨询与解读
    2. 税务计算与申报指导
    3. 发票管理与合规检查
    4. 税务风险识别与预警
    5. 税收筹划建议
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        specialty: str = "tax"
    ):
        """
        初始化税务专家
        
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
        self.tax_calculations = self._load_tax_calculations()
    
    def _load_system_prompt(self) -> str:
        """从外部文件加载系统提示词"""
        try:
            return load_agent_prompt(
                agent_name="tax",
                filename="tax_agent.md",
                context=self._get_prompt_context()
            )
        except Exception as e:
            logger.debug(f"[税务专家智能体] 加载提示词失败，使用默认提示词: {e}")
            return self._build_default_prompt()
    
    def _get_prompt_context(self) -> Dict[str, Any]:
        """获取提示词渲染上下文"""
        return {
            "tax_types": [t.value for t in TaxType],
        }
    
    def _build_default_prompt(self) -> str:
        """构建默认提示词"""
        return """你是一位专业的税务顾问，具有以下能力：
1. 精通中国现行税制，包括增值税、企业所得税、个人所得税等
2. 熟悉最新税收政策和法规
3. 能够进行税务计算和风险评估
4. 提供合规的税收筹划建议

在回答时，请：
- 引用相关法规条款
- 提供具体的计算过程
- 指出潜在的合规风险
- 建议合理的筹划方案（合法合规范围内）
"""
    
    def _compile_entity_patterns(self) -> Dict[str, re.Pattern]:
        """编译税务实体提取正则表达式"""
        return {
            "tax_rate": re.compile(
                r'(\d+(?:\.\d+)?)\s*%',
                re.IGNORECASE
            ),
            "money": re.compile(
                r'(?:CNY|yuan|RMB|￥|¥)?\s*[\d,]+(?:\.\d{2})?',
                re.IGNORECASE
            ),
            "invoice_number": re.compile(
                r'\b\d{10,}\b'
            ),
            "tax_id": re.compile(
                r'\b\d{15,18}\b'
            ),
            "date": re.compile(
                r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?'
            ),
            "period": re.compile(
                r'(?:20\d{2}[-/年])?\d{1,2}月?',
                re.IGNORECASE
            )
        }
    
    def _load_tax_calculations(self) -> Dict[str, Dict[str, Any]]:
        """加载税务计算规则"""
        return {
            "vat_general": {
                "rate": 0.13,
                "formula": "税额 = 含税金额 / (1 + 税率) × 税率",
                "description": "一般纳税人增值税计算"
            },
            "vat_small": {
                "rate": 0.03,
                "formula": "税额 = 含税金额 × 3%",
                "description": "小规模纳税人增值税计算"
            },
            "income_tax_general": {
                "rate": 0.25,
                "formula": "应纳税所得额 × 25%",
                "description": "企业所得税基本税率"
            },
            "income_tax_small": {
                "rate": 0.20,
                "formula": "应纳税所得额 × 20%",
                "description": "小型微利企业优惠税率"
            }
        }
    
    def extract_entities(self, text: str) -> TaxEntity:
        """
        提取税务实体
        
        Args:
            text: 输入文本
            
        Returns:
            提取的税务实体
        """
        entity = TaxEntity()
        
        for pattern_name, pattern in self.entity_patterns.items():
            matches = pattern.findall(text)
            if matches:
                if pattern_name == "tax_rate":
                    entity.tax_rate = float(matches[0])
                elif pattern_name == "money":
                    amount_str = matches[0].replace(',', '')
                    entity.tax_amount = float(re.sub(r'[^\d.]', '', amount_str))
                elif pattern_name == "invoice_number":
                    entity.invoice_number = matches[0]
                elif pattern_name == "tax_id":
                    entity.tax_id = matches[0]
                elif pattern_name == "date":
                    entity.invoice_date = matches[0]
                elif pattern_name == "period":
                    entity.period = matches[0]
        
        tax_type_keywords = {
            "增值税": TaxType.VAT,
            "企业所得税": TaxType.INCOME_TAX,
            "个人所得税": TaxType.PERSONAL_INCOME_TAX,
            "消费税": TaxType.CONSUMPTION_TAX,
            "房产税": TaxType.PROPERTY_TAX,
            "印花税": TaxType.STAMP_TAX,
            "环保税": TaxType.ENVIRONMENT_TAX
        }
        
        general_tax_keywords = ["税务", "纳税", "税金", "报税", "合规"]
        
        for keyword, tax_type in tax_type_keywords.items():
            if keyword in text:
                entity.tax_type = tax_type.value
                break
        else:
            for keyword in general_tax_keywords:
                if keyword in text:
                    entity.tax_type = TaxType.OTHER.value
                    break
        
        return entity
    
    async def calculate_vat(
        self,
        amount: float,
        rate: float = 0.13,
        is_small_scale: bool = False
    ) -> Dict[str, float]:
        """
        计算增值税
        
        Args:
            amount: 含税金额
            rate: 税率
            is_small_scale: 是否小规模纳税人
            
        Returns:
            增值税计算结果
        """
        if is_small_scale:
            tax_rate = 0.03
            tax_amount = amount * tax_rate
        else:
            tax_rate = rate
            tax_amount = amount / (1 + tax_rate) * tax_rate
        
        pre_tax_amount = amount - tax_amount
        
        return {
            "含税金额": amount,
            "税率": tax_rate,
            "不含税金额": pre_tax_amount,
            "税额": tax_amount
        }
    
    async def calculate_income_tax(
        self,
        revenue: float,
        deductible_expenses: float,
        is_small_scale: bool = False
    ) -> Dict[str, float]:
        """
        计算企业所得税
        
        Args:
            revenue: 营业收入
            deductible_expenses: 可扣除费用
            is_small_scale: 是否小型微利企业
            
        Returns:
            企业所得税计算结果
        """
        taxable_income = revenue - deductible_expenses
        
        if taxable_income <= 0:
            return {
                "营业收入": revenue,
                "可扣除费用": deductible_expenses,
                "应纳税所得额": 0,
                "税率": 0,
                "应纳税额": 0
            }
        
        if is_small_scale and taxable_income <= 3000000:
            rate = 0.20
            deduction = taxable_income * 0.25
            tax_amount = taxable_income * rate - deduction
        else:
            rate = 0.25
            tax_amount = taxable_income * rate
        
        return {
            "营业收入": revenue,
            "可扣除费用": deductible_expenses,
            "应纳税所得额": taxable_income,
            "税率": rate,
            "应纳税额": tax_amount
        }
    
    async def run(
        self,
        user_input: str,
        history: List[Dict[str, Any]] = None,
        context: Dict[str, Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        处理税务咨询请求
        
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
            
            prompt = self._build_tax_prompt(user_input, entities)
            
            full_prompt = f"{self.system_prompt}\n\n{prompt}" if self.system_prompt else prompt
            llm_response = await self.llm_adapter.generate(
                prompt=full_prompt,
                temperature=0.3
            )
            
            response_text = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
            analysis = self._parse_llm_response(response_text, entities)
            
            risk_assessment = self.assess_tax_risk(analysis, entities)
            
            if not entities.tax_type and not entities.tax_rate and not entities.tax_amount:
                return {
                    "success": True,
                    "tax_type": analysis.tax_type,
                    "analysis": analysis.dict(),
                    "risk_assessment": risk_assessment,
                    "entities": {
                        "tax_rate": entities.tax_rate,
                        "tax_amount": entities.tax_amount,
                        "tax_id": entities.tax_id,
                        "period": entities.period
                    },
                    "recommendations": self._generate_recommendations(analysis),
                    "confidence": analysis.confidence,
                    "needs_more_info": True,
                    "missing_fields": ["tax_type", "tax_rate", "tax_amount"],
                    "suggestion": "为了提供更准确的税务分析，请提供以下信息：\n1. 具体税种（如增值税、企业所得税、个人所得税等）\n2. 税务金额或计算基数\n3. 适用税率（如已知）\n4. 税务期间（如季度、年度）\n5. 相关业务背景或特殊情况"
                }
            
            return {
                "success": True,
                "tax_type": analysis.tax_type,
                "analysis": analysis.dict(),
                "risk_assessment": risk_assessment,
                "entities": {
                    "tax_rate": entities.tax_rate,
                    "tax_amount": entities.tax_amount,
                    "tax_id": entities.tax_id,
                    "period": entities.period
                },
                "recommendations": self._generate_recommendations(analysis),
                "confidence": analysis.confidence
            }
            
        except (ValueError, KeyError) as e:
            logger.error(f"税务分析数据失败: {e}")
            return {
                "success": False,
                "error": f"数据错误: {str(e)}",
                "fallback": "建议您咨询专业税务顾问获取准确信息"
            }
        except (OSError, IOError) as e:
            logger.error(f"税务分析IO失败: {e}")
            return {
                "success": False,
                "error": f"IO错误: {str(e)}",
                "fallback": "建议您咨询专业税务顾问获取准确信息"
            }
        except Exception as e:
            logger.error(f"税务分析失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback": "建议您咨询专业税务顾问获取准确信息"
            }
    
    def _build_tax_prompt(self, user_input: str, entities: TaxEntity) -> str:
        """构建税务分析提示词"""
        prompt_parts = [
            f"用户问题：{user_input}\n",
            "提取的税务实体："
        ]
        
        if entities.tax_type:
            prompt_parts.append(f"- 税种：{entities.tax_type}")
        if entities.tax_rate:
            prompt_parts.append(f"- 税率：{entities.tax_rate}%")
        if entities.tax_amount:
            prompt_parts.append(f"- 金额：{entities.tax_amount}")
        if entities.period:
            prompt_parts.append(f"- 期间：{entities.period}")
        
        prompt_parts.extend([
            "\n请进行税务分析，包括：",
            "1. 相关税法条款",
            "2. 合规性检查要点",
            "3. 潜在风险点",
            "4. 建议的处理方式"
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_llm_response(
        self,
        response: str,
        entities: TaxEntity
    ) -> TaxAnalysisResult:
        """解析LLM响应"""
        try:
            if entities.tax_type:
                try:
                    tax_type = TaxType(entities.tax_type)
                except ValueError:
                    tax_type = TaxType.OTHER
            else:
                tax_type = TaxType.OTHER
            
            risk_points = []
            
            if not entities.tax_amount and not entities.tax_rate:
                risk_points.append("缺少关键税务信息，无法完整评估")
            elif "违规" in response or "不合规" in response or "违法行为" in response:
                risk_points.append("存在合规性问题")
            elif "警告" in response or "需关注" in response:
                risk_points.append("存在需要关注的事项")
            
            confidence = 0.8
            if entities.tax_type and entities.tax_rate:
                confidence = 0.95
            
            return TaxAnalysisResult(
                tax_type=tax_type,
                tax_rate=entities.tax_rate,
                tax_amount=entities.tax_amount,
                tax_period=entities.period,
                risk_points=risk_points,
                compliance_status="review_required" if risk_points else "compliant",
                confidence=confidence
            )
        except (ValueError, KeyError) as e:
            logger.warning(f"解析税务响应数据失败: {e}")
            return TaxAnalysisResult(
                tax_type=TaxType.OTHER,
                confidence=0.0,
                compliance_status="error"
            )
        except (OSError, IOError) as e:
            logger.warning(f"解析税务响应IO失败: {e}")
            return TaxAnalysisResult(
                tax_type=TaxType.OTHER,
                confidence=0.0,
                compliance_status="error"
            )
        except Exception as e:
            logger.warning(f"解析税务响应失败: {e}")
            return TaxAnalysisResult(
                tax_type=TaxType.OTHER,
                confidence=0.5
            )
    
    def assess_tax_risk(
        self,
        analysis: TaxAnalysisResult,
        entities: TaxEntity
    ) -> Dict[str, Any]:
        """
        评估税务风险
        
        Args:
            analysis: 税务分析结果
            entities: 税务实体
            
        Returns:
            风险评估结果
        """
        risk_level = "low"
        risk_factors = []
        
        if analysis.confidence < 0.7:
            risk_level = "medium"
            risk_factors.append("置信度较低，建议人工复核")
        
        if not entities.tax_rate and analysis.tax_type != TaxType.OTHER:
            risk_level = "medium"
            risk_factors.append("缺少税率信息")
        
        if analysis.risk_points:
            risk_level = "high"
            risk_factors.extend(analysis.risk_points)
        
        if entities.tax_amount and entities.tax_amount > 10000000:
            risk_level = "high"
            risk_factors.append("涉及金额较大，建议专业审核")
        
        return {
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "requires_professional_review": risk_level in ["high", "medium"]
        }
    
    def _generate_recommendations(
        self,
        analysis: TaxAnalysisResult
    ) -> List[str]:
        """生成税务建议"""
        recommendations = []
        
        if analysis.compliance_status == "review_required":
            recommendations.append("建议进行详细的合规性审查")
        
        if analysis.tax_type == TaxType.VAT:
            recommendations.append("确保进项税额已按规定抵扣")
            recommendations.append("注意发票的真实性核查")
        
        if analysis.tax_type == TaxType.INCOME_TAX:
            recommendations.append("确保成本费用合规扣除")
            recommendations.append("关注税收优惠政策的适用")
        
        recommendations.append("建议保留完整的税务档案")
        recommendations.append("如有大额税务事项，咨询专业税务顾问")
        
        return recommendations
    
    async def audit(
        self,
        state: AuditState,
        documents: List[Dict[str, Any]]
    ) -> List[Finding]:
        """
        执行税务审查
        
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
            
            if entities.invoice_number:
                findings.append(Finding(
                    id=f"TAX_INV_{len(findings) + 1}",
                    agent_name="tax",
                    category="发票管理",
                    description=f"发现发票号码：{entities.invoice_number}",
                    risk_level=RiskLevel.INFO,
                    risk_score=10.0,
                    confidence=0.8,
                    evidence=[],
                    recommendations=["核实发票真实性"]
                ))
            
            if entities.tax_rate and entities.tax_rate > 0.20:
                findings.append(Finding(
                    id=f"TAX_RATE_{len(findings) + 1}",
                    agent_name="tax",
                    category="税率合规",
                    description=f"发现异常高税率：{entities.tax_rate}%",
                    risk_level=RiskLevel.MEDIUM,
                    risk_score=40.0,
                    confidence=0.7,
                    evidence=[],
                    recommendations=["核实适用税率是否正确"]
                ))
            
            for rule in self.knowledge_base:
                if rule.get("rule_id", "").startswith("TAX"):
                    if any(keyword in content for keyword in ["不符", "异常", "错误"]):
                        findings.append(Finding(
                            id=f"TAX_KB_{len(findings) + 1}",
                            agent_name="tax",
                            category=rule.get("category", "税务合规"),
                            description=rule.get("description", ""),
                            risk_level=RiskLevel.HIGH,
                            risk_score=70.0,
                            confidence=0.8,
                            evidence=[],
                            recommendations=["进行税务合规性检查"]
                        ))
        
        return findings
    
    def get_tax_knowledge(self, tax_type: str) -> List[Dict[str, Any]]:
        """
        获取特定税种的税务知识
        
        Args:
            tax_type: 税种类型
            
        Returns:
            税务知识列表
        """
        tax_knowledge_map = {
            "vat": [
                {
                    "rule_id": "VAT_001",
                    "category": "进项抵扣",
                    "description": "增值税进项税额抵扣规则",
                    "valid_deduction": ["增值税专用发票", "海关缴款书", "机动车销售发票"]
                },
                {
                    "rule_id": "VAT_002",
                    "category": "税率适用",
                    "description": "不同业务类型的增值税税率",
                    "rates": {"general": 0.13, "small_scale": 0.03, "light": 0.09}
                }
            ],
            "income_tax": [
                {
                    "rule_id": "IT_001",
                    "category": "税前扣除",
                    "description": "企业所得税税前扣除标准",
                    "limits": {"招待费": "60%且不超过营业收入的0.5%", "广告费": "不超过营业收入15%"}
                },
                {
                    "rule_id": "IT_002",
                    "category": "优惠政策",
                    "description": "小型微利企业税收优惠",
                    "conditions": ["年度应纳税所得额≤300万", "从业人数≤300人", "资产总额≤5000万"]
                }
            ]
        }
        
        return tax_knowledge_map.get(tax_type, [])
    
    async def stream_run(
        self,
        user_input: str,
        history: List[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        流式执行税务专家智能体
        
        实现基类的抽象方法
        
        Args:
            user_input: 用户输入
            history: 对话历史
            
        Yields:
            处理结果片段
        """
        result = await self.run(user_input, history, **kwargs)
        result_str = json.dumps(result, ensure_ascii=False, indent=2)
        
        for char in result_str:
            yield char
