"""
税务专家智能体 (Tax Specialist Agent)
处理企业税务相关问题，包括增值税、企业所得税、个人所得税等
"""

import re
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from enum import Enum
from dataclasses import dataclass

from pydantic import BaseModel, Field

from .base_specialist import BaseSpecialistAgent
from .base_agent_prompt import load_agent_prompt
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from ..state import AuditState, Finding, RiskLevel

if TYPE_CHECKING:
    from app.skills.skill_registry import SkillRegistry

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


@dataclass
class TaxQueryResult:
    """税务数据查询结果"""
    has_data: bool = False
    tax_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    fiscal_year: Optional[int] = None


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
        specialty: str = "tax",
        skill_registry: Optional['SkillRegistry'] = None,  # 🆕 技能系统
    ):
        """
        初始化税务专家

        Args:
            llm_adapter: 大模型适配器
            tool_manager: 工具管理器
            specialty: 专业领域标识
            skill_registry: 技能注册表 (可选)
        """
        # 必须在 _load_system_prompt() 之前设置 skill_registry
        # 因为 _get_prompt_context() 会访问它
        self.skill_registry = skill_registry
        system_prompt = self._load_system_prompt()

        super().__init__(
            specialty=specialty,
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=10,
            timeout=60.0,
            skill_registry=skill_registry,  # 🆕 技能系统
        )
        
        self.entity_patterns = self._compile_entity_patterns()
        self.tax_calculations = self._load_tax_calculations()
        
        self._register_mcp_tools()
    
    def _register_mcp_tools(self):
        """
        注册 MCP 工具（财务数据查询 + 时间锚点）
        
        税务专家需要访问财务数据库进行税务分析
        """
        try:
            from app.mcp.foundation_tools import get_current_time_and_context
            from app.mcp.financial_tools import create_financial_tools
            from app.mcp.financial_health_tools import create_financial_health_tools
            
            # 1. 注册财务数据查询工具（关键修复）
            try:
                financial_tools = create_financial_tools()
                for tool in financial_tools:
                    try:
                        self.tool_manager.register_langchain_tool(tool)
                        logger.info(f"✅ [税务专家] 注册财务工具: {tool.name}")
                    except Exception as e:
                        logger.warning(f"⚠️ [税务专家] 注册财务工具失败 {tool.name}: {e}")
            except ImportError as e:
                logger.warning(f"⚠️ [税务专家] 无法导入财务工具: {e}")
            
            # 2. 注册财务健康工具
            try:
                health_tools = create_financial_health_tools()
                for tool in health_tools:
                    try:
                        self.tool_manager.register_langchain_tool(tool)
                        logger.info(f"✅ [税务专家] 注册健康工具: {tool.name}")
                    except Exception as e:
                        logger.warning(f"⚠️ [税务专家] 注册健康工具失败 {tool.name}: {e}")
            except ImportError as e:
                logger.warning(f"⚠️ [税务专家] 无法导入健康工具: {e}")
            
            # 3. 注册时间锚点工具（所有专家 Agent 都需要）
            try:
                self.tool_manager.register_langchain_tool(get_current_time_and_context)
                logger.info(f"✅ [税务专家] 注册时间锚点工具: get_current_time_and_context")
            except Exception as e:
                logger.warning(f"⚠️ [税务专家] 注册时间锚点工具失败: {e}")
            
            logger.info(f"📊 [税务专家] MCP 工具注册完成")
            
        except ImportError as e:
            logger.warning(f"⚠️ [税务专家] 无法导入 MCP 工具: {e}")
        except Exception as e:
            logger.error(f"❌ [税务专家] 注册 MCP 工具时出错: {e}")
    
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
        tools_description = ""
        if self.tool_manager:
            tools_description = self.tool_manager.get_tools_description()

        # 获取领域技能描述 (Level 1: 仅名称+说明, 完整内容按需加载)
        skill_descriptions = ""
        try:
            if self.skill_registry and self.skill_registry.is_initialized():
                skill_descriptions = self.skill_registry.format_domain_skill_descriptions("tax")
        except Exception:
            pass

        return {
            "tax_types": [t.value for t in TaxType],
            "available_tools": tools_description or "无可用工具",
            "skill_descriptions": skill_descriptions or "暂无可用技能",
        }
    
    def _build_default_prompt(self) -> str:
        """构建默认提示词"""
        return """你是一位专业的税务顾问，具有以下能力：
1. 精通中国现行税制，包括增值税、企业所得税、个人所得税等
2. 熟悉最新税收政策和法规
3. 能够进行税务计算和风险评估
4. 提供合规的税收筹划建议

## 可用工具
- 时间锚点工具 get_current_time_and_context（【重要】处理时间相关查询时必须使用）

## 时间感知原则
大模型没有生物钟，当处理以下场景时，必须先调用 get_current_time_and_context：
- 用户询问"今年最新政策"、"去年税率变化"等相对时间
- 需要分析"本季度税务情况"、"去年同期对比"等时间对比
- 任何涉及时间范围的税务分析（如"近3年税务趋势"）
- 查询"最新税收优惠政策"或"近期政策变化"

## 税务时间敏感性
- 税务政策每年可能变化（如企业所得税优惠）
- 税收申报有严格的时间截止日期
- 不同税种有不同的申报周期（月度、季度、年度）
- 历史税务数据需要准确的时间锚定

## 工作流程
1. 当用户查询包含相对时间词时，先调用 get_current_time_and_context 获取准确时间基准
2. 根据时间基准查询对应时期的税务政策
3. 执行税务分析和计算
4. 提供基于准确时间的专业建议

在回答时，请：
- 引用相关法规条款（注明生效日期）
- 提供具体的计算过程（基于准确时间）
- 指出潜在的合规风险（考虑时效性）
- 建议合理的筹划方案（合法合规范围内）
- 明确说明时间基准（例如："基于当前 2026 年 4 月的时间，根据 2026 年最新政策..."）
"""
    
    async def _query_user_tax_data(
        self,
        context: Optional[Dict[str, Any]]
    ) -> TaxQueryResult:
        """
        查询用户的企业税务和财务数据（使用 MCP 工具）

        Args:
            context: 上下文信息，包含 tenant_id、user_id 等
            
        Returns:
            TaxQueryResult：税务数据查询结果
        """
        tenant_id = None
        user_id = None
        fiscal_year = None
        
        if context:
            tenant_id = context.get("tenant_id")
            user_id = context.get("user_id")
            fiscal_year = context.get("fiscal_year")
        
        logger.info(f"🔍 [税务专家] _query_user_tax_data 接收到的 tenant_id = '{tenant_id}', user_id = '{user_id}'")
        
        if not tenant_id or not user_id or tenant_id == "default" or user_id == "default":
            logger.warning(f"🔍 [税务专家] 跳过税务数据查询：tenant_id='{tenant_id}', user_id='{user_id}'")
            return TaxQueryResult(
                has_data=False,
                error_message=f"未提供有效的 tenant_id 或 user_id (tenant_id='{tenant_id}', user_id='{user_id}')"
            )
        
        # ─── 通过 ToolManager 路由工具调用（保证追踪/统计完整性） ───
        max_retries = 2
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"🔍 [税务专家] 正在通过 ToolManager 查询税务数据 "
                    f"(尝试 {attempt}/{max_retries}): tenant='{tenant_id}', year={fiscal_year}"
                )

                tool_params = {
                    "tenant_id": tenant_id,
                    "fiscal_year": fiscal_year if fiscal_year else None,
                }

                overview_result = await self.tool_manager.call_tool_raw(
                    "get_financial_overview",
                    **tool_params
                )

                logger.info(f"🔍 [税务专家] ToolManager 返回原始结果:")
                logger.info(f"   - status: {overview_result.get('status')}")
                logger.info(f"   - has 'data': {overview_result.get('data') is not None}")
                logger.info(f"   - has 'summary': {overview_result.get('summary') is not None}")

                if overview_result.get('status') == 'success' and overview_result.get('data'):
                    data = overview_result['data']
                    logger.info(f"   - data keys: {list(data.keys())}")

                    # 提取税务相关数据
                    tax_data = {
                        "fiscal_year": overview_result.get('fiscal_year'),
                        "total_revenue": data.get("total_revenue"),
                        "total_vat": data.get("total_vat"),
                        "total_corporate_tax": data.get("total_corporate_tax"),
                        "vat_rate": data.get("vat_rate"),
                        "corporate_tax_rate": data.get("corporate_tax_rate"),
                        "taxable_sales": data.get("taxable_sales"),
                        "input_tax": data.get("input_tax"),
                        "output_tax": data.get("output_tax"),
                        "is_small_enterprise": data.get("is_small_enterprise"),
                        "data_status": data.get("data_status"),
                    }

                    logger.info(f"✅ [税务专家] 成功提取税务数据: revenue={tax_data.get('total_revenue')}, vat={tax_data.get('total_vat')}")

                    return TaxQueryResult(
                        has_data=True,
                        tax_data=tax_data,
                        fiscal_year=overview_result.get('fiscal_year')
                    )
                else:
                    logger.warning(f"⚠️ [税务专家] 税务数据为空或查询失败")
                    return TaxQueryResult(
                        has_data=False,
                        error_message=overview_result.get('message', '税务数据为空'),
                        fiscal_year=overview_result.get('fiscal_year')
                    )

            except Exception as e:
                last_error = str(e)
                logger.error(f"❌ [税务专家] 第 {attempt} 次查询失败: {e}")
                if attempt < max_retries:
                    import asyncio
                    await asyncio.sleep(0.5)  # 重试前等待

        logger.error(f"❌ [税务专家] 税务数据查询最终失败: {last_error}")
        return TaxQueryResult(
            has_data=False,
            error_message=f"查询失败: {last_error}"
        )
    
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
        rag_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        LLM 驱动模式 — 给 LLM 完整的 system prompt（含边界规则+工具列表+技能列表），
        让 LLM 自行判断如何回答。

        Args:
            user_input: 用户输入
            history: 对话历史
            context: 上下文信息
            rag_context: RAG检索到的上下文数据
            **kwargs: 其他参数

        Returns:
            处理结果
        """
        try:
            # 🆕 注册表守卫：当用户问技能/能力且该领域无注册技能时，直接返回，不调 LLM
            _meta_kw = ["技能", "能力", "会做什么", "擅长", "功能介绍"]
            if any(kw in user_input.lower() for kw in _meta_kw):
                # 只查领域专有技能（不包含 public 公共技能）
                has_domain_skills = False
                if self.skill_registry and self.skill_registry.is_initialized():
                    domain_entries = self.skill_registry.list_skills_by_domain("tax")
                    if domain_entries:
                        has_domain_skills = True
                if not has_domain_skills:
                    logger.info("[TaxSpecialist] 领域无注册技能，直接返回")
                    return {
                        "success": True,
                        "domain": "skill_inquiry",
                        "text_answer": "当前暂无可用技能。",
                        "analysis": {"domain": "skill_inquiry", "confidence": 1.0},
                        "confidence": 1.0,
                    }

            # 改用 chat() 方式发消息（不再拼大字符串，避免 OpenRouter 超时）
            chat_messages = []
            if self.system_prompt:
                chat_messages.append({"role": "system", "content": self.system_prompt})

            if rag_context and rag_context.get("documents"):
                doc_texts = []
                for i, doc in enumerate(rag_context["documents"][:3], 1):
                    c = doc.get("content", "")
                    if c:
                        doc_texts.append(f"### 文档{i}\n{c[:1000]}")
                if doc_texts:
                    chat_messages.append({
                        "role": "system",
                        "content": "## 企业知识库相关文档\n" + "\n".join(doc_texts)
                    })

            tenant_id = "default"
            user_id = "default"
            if context:
                tenant_id = context.get("tenant_id", "default")
                user_id = context.get("user_id", "default")
            from datetime import datetime
            current_time_str = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
            chat_messages.append({
                "role": "system",
                "content": f"tenant_id: {tenant_id}\nuser_id: {user_id}\n当前准确时间: {current_time_str}"
            })
            chat_messages.append({"role": "user", "content": user_input})

            logger.info(f"[TaxSpecialist] chat messages: {len(chat_messages)}, system: {len(self.system_prompt or '')} chars")

            llm_response = await asyncio.wait_for(
                self.llm_adapter.chat(messages=chat_messages, temperature=0.3),
                timeout=60.0,
            )
            response_text = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
            logger.info(f"[TaxSpecialist] response: {len(response_text)} chars")

            return {
                "success": True,
                "domain": "general",
                "text_answer": response_text,
                "analysis": {"domain": "general", "confidence": 1.0,
                             "key_metrics": [], "risk_factors": [], "recommendations": []},
                "confidence": 1.0,
                "has_tax_db_data": False,
            }

        except asyncio.TimeoutError:
            logger.error(f"[TaxSpecialist] LLM 调用超时")
            return {
                "success": False,
                "error": "LLM 调用超时",
                "error_type": "timeout",
                "text_answer": "税务分析请求超时，请稍后重试或简化问题。"
            }
        except Exception as e:
            logger.error(f"[TaxSpecialist] run failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_type": "unknown",
                "text_answer": f"税务分析处理失败: {str(e)[:200]}"
            }

    def _should_query_enterprise_data(
        self,
        user_input: str,
        entities: TaxEntity,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """判断本次税务咨询是否需要读取企业数据库。"""
        if context and context.get("force_enterprise_data") is True:
            return True
        if context and context.get("skip_enterprise_data") is True:
            return False

        text = user_input or ""
        data_keywords = (
            "我司", "本公司", "我们公司", "本企业", "企业数据", "财务数据",
            "税负", "税额", "测算", "计算", "风险评估", "风险分析",
            "收入", "营收", "利润", "成本", "费用", "应纳税", "应交税",
            "申报表", "本月", "本季", "本季度", "今年", "年度", "202",
        )
        guidance_keywords = (
            "指导", "流程", "怎么", "如何", "怎么办", "办理", "材料",
            "步骤", "政策", "规定", "说明", "介绍", "注意事项",
        )

        has_data_intent = any(keyword in text for keyword in data_keywords)
        has_guidance_intent = any(keyword in text for keyword in guidance_keywords)

        if has_guidance_intent and not has_data_intent:
            return False
        if has_data_intent:
            return True
        return bool(entities.tax_amount or entities.tax_rate or entities.period)

    def _format_llm_report(
        self,
        response_text: str,
        user_input: str,
        analysis: TaxAnalysisResult,
        entities: TaxEntity,
        risk_assessment: Dict[str, Any],
        tax_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """将 LLM 输出整理成面向用户的 Markdown 报告。"""
        cleaned = self._clean_llm_markdown(response_text)
        if cleaned and len(cleaned) >= 80:
            return cleaned
        return self._generate_analysis_report(analysis, entities, risk_assessment)

    def _clean_llm_markdown(self, text: str) -> str:
        if not text:
            return ""
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:markdown|md)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        internal_markers = (
            "TaxAnalysisResult",
            "TaxQueryResult",
            "has_tax_db_data",
            "tax_data",
            "tax_data_error",
            "query_result",
            "ToolManager",
            "TaxType.",
            "<TaxType.",
        )
        if any(marker in cleaned for marker in internal_markers):
            return ""

        if not cleaned.startswith("#"):
            cleaned = f"## 税务申报指导\n\n{cleaned}"
        return cleaned
    
    def _build_tax_prompt(self, user_input: str, entities: TaxEntity, tax_context: Optional[Dict[str, Any]] = None) -> str:
        """
        构建税务分析提示词

        Args:
            user_input: 用户输入
            entities: 提取的税务实体
            tax_context: 税务上下文（包含数据库查询结果）
            
        Returns:
            构建好的提示词
        """
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
        
        if tax_context and tax_context.get("has_tax_data"):
            tax_data = tax_context.get("tax_data", {})
            prompt_parts.extend([
                "\n\n【企业真实税务数据】",
                f"- 财务年度：{tax_data.get('fiscal_year', 'N/A')}",
                f"- 总营收：¥{tax_data.get('total_revenue', 0):,.2f}" if tax_data.get('total_revenue') else "- 总营收：暂无数据",
                f"- 应税销售额：¥{tax_data.get('taxable_sales', 0):,.2f}" if tax_data.get('taxable_sales') else "- 应税销售额：暂无数据",
                f"- 增值税总额：¥{tax_data.get('total_vat', 0):,.2f}" if tax_data.get('total_vat') else "- 增值税总额：暂无数据",
                f"- 企业所得税总额：¥{tax_data.get('total_corporate_tax', 0):,.2f}" if tax_data.get('total_corporate_tax') else "- 企业所得税总额：暂无数据",
                f"- 增值税率：{tax_data.get('vat_rate', 0):%}" if tax_data.get('vat_rate') else "- 增值税率：暂无数据",
                f"- 企业所得税率：{tax_data.get('corporate_tax_rate', 0):%}" if tax_data.get('corporate_tax_rate') else "- 企业所得税率：暂无数据",
                f"- 进项税额：¥{tax_data.get('input_tax', 0):,.2f}" if tax_data.get('input_tax') else "- 进项税额：暂无数据",
                f"- 销项税额：¥{tax_data.get('output_tax', 0):,.2f}" if tax_data.get('output_tax') else "- 销项税额：暂无数据",
                f"- 是否小微企业：{'是' if tax_data.get('is_small_enterprise') else '否'}",
                f"- 数据状态：{tax_data.get('data_status', 'unknown')}",
                "\n⚠️ 【重要】请基于上述真实数据进行分析，而非假设数据。"
            ])
        elif tax_context and tax_context.get("data_query_skipped"):
            prompt_parts.extend([
                "\n\n【分析范围】",
                "- 本次问题属于通用税务咨询或申报指导，不需要读取企业数据库。",
                "- 请基于通用税务申报规则、操作流程和风险控制要点作答。",
                "- 不要声称缺少企业数据导致无法回答；如涉及测算，再提示需要补充数据。"
            ])
        else:
            error_msg = tax_context.get("tax_error", "未知错误") if tax_context else "无可用数据"
            prompt_parts.extend([
                "\n\n【注意】无法获取企业真实税务数据：",
                f"- 错误信息：{error_msg}",
                "\n⚠️ 请基于用户提供的信息进行分析，并在报告中明确说明缺少哪些数据。"
            ])

        if tax_context and tax_context.get("repair_mode"):
            prompt_parts.extend([
                "\n\n【质量审查修复要求】",
                f"- 上一版回答：{tax_context.get('previous_answer', '')[:1200]}",
                f"- 审查意见：{tax_context.get('repair_instructions', '')}",
                "- 请针对审查意见重新组织答案，补齐缺失内容，不要重复输出内部字段或调试信息。"
            ])
        
        prompt_parts.extend([
            "\n\n请直接输出面向用户的 Markdown 正文，不要输出 JSON、Python 字典、内部字段名或调试信息。",
            "请使用以下层次：",
            "## 结论概览",
            "## 适用场景",
            "## 办理流程",
            "## 材料清单",
            "## 风险提示",
            "## 下一步建议",
            "如果用户问题过于宽泛，请先给出通用指导，再列出需要用户补充的信息。"
        ])
        
        return "\n".join(prompt_parts)
    
    def _generate_analysis_report(
        self,
        analysis: TaxAnalysisResult,
        entities: TaxEntity,
        risk_assessment: Dict[str, Any]
    ) -> str:
        """
        生成完整的税务分析报告
        
        Args:
            analysis: 税务分析结果
            entities: 提取的税务实体
            risk_assessment: 风险评估结果
            
        Returns:
            格式化的分析报告
        """
        try:
            # 构建报告标题
            report = f"""# 📋 税务分析报告

## 1. 税种识别
- **税种类型**: {analysis.tax_type.value if hasattr(analysis.tax_type, 'value') else analysis.tax_type}
- **适用税率**: {analysis.tax_rate if analysis.tax_rate is not None else "未提供"}
- **税额估算**: {analysis.tax_amount if analysis.tax_amount is not None else "未提供"}
- **税务期间**: {analysis.tax_period if analysis.tax_period else "未指定"}

## 2. 合规性评估
- **合规状态**: {analysis.compliance_status}
- **置信度**: {analysis.confidence:.2%}
- **可扣除项目**: {', '.join(analysis.deductions) if analysis.deductions else "无"}
- **免税项目**: {', '.join(analysis.exemptions) if analysis.exemptions else "无"}

## 3. 风险点分析"""
            
            if analysis.risk_points:
                for i, risk in enumerate(analysis.risk_points, 1):
                    report += f"\n{i}. {risk}"
            else:
                report += "\n- 未发现明显风险点"
            
            # 添加风险评估
            if risk_assessment:
                report += f"\n\n## 4. 风险评估"
                for key, value in risk_assessment.items():
                    if value is not None:
                        report += f"\n- **{key}**: {value}"
            
            # 添加实体信息
            if entities.tax_rate or entities.tax_amount or entities.tax_id or entities.period:
                report += "\n\n## 5. 提取信息"
                if entities.tax_rate:
                    report += f"\n- **税率**: {entities.tax_rate}%"
                if entities.tax_amount:
                    report += f"\n- **金额**: {entities.tax_amount}"
                if entities.tax_id:
                    report += f"\n- **税号**: {entities.tax_id}"
                if entities.period:
                    report += f"\n- **期间**: {entities.period}"
            
            # 添加建议部分
            recommendations = self._generate_recommendations(analysis)
            if recommendations:
                report += "\n\n## 6. 专业建议"
                for i, rec in enumerate(recommendations, 1):
                    report += f"\n{i}. {rec}"
            
            # 添加总结
            report += f"\n\n## 7. 总结\n"
            if analysis.compliance_status == "compliant":
                report += "✅ 税务合规性良好，建议继续保持并关注政策变化。"
            elif analysis.compliance_status == "review_required":
                report += "⚠️ 需要进一步审查，建议咨询专业税务顾问。"
            else:
                report += "❌ 存在合规风险，建议立即采取纠正措施。"
            
            return report
            
        except Exception as e:
            logger.error(f"生成税务分析报告失败: {e}")
            # 返回简化版本
            return f"""# 📋 税务分析报告

## 分析结果
- **税种**: {analysis.tax_type.value if hasattr(analysis.tax_type, 'value') else analysis.tax_type}
- **合规状态**: {analysis.compliance_status}
- **置信度**: {analysis.confidence:.2%}

## 风险点
{chr(10).join(f"- {risk}" for risk in analysis.risk_points) if analysis.risk_points else "- 未发现明显风险点"}"""
    
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
