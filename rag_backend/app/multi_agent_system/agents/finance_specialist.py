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
import traceback
import asyncio
import time
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from enum import Enum
from dataclasses import dataclass

from pydantic import BaseModel, Field, model_validator

from app.services.context_optimizer import ContextOptimizer
from .base_specialist import BaseSpecialistAgent
from .base_agent_prompt import load_agent_prompt
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from ..state import AuditState, Finding, RiskLevel

if TYPE_CHECKING:
    from app.skills.skill_registry import SkillRegistry

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
                    # 检查是否是"无法计算"或类似的描述性字符串
                    if any(phrase in value for phrase in ["无法计算", "缺少", "未知", "未提供", "未找到", "无数据"]):
                        logger.debug(f"在验证器中跳过非数值财务指标: {key} = '{value}'")
                        continue
                    
                    percent_match = re.match(r'^([-+]?\d*\.?\d+)%?$', value.strip())
                    if percent_match:
                        try:
                            num = float(percent_match.group(1))
                            if '%' in value:
                                num = num / 100.0
                            cleaned[key] = num
                        except ValueError:
                            logger.debug(f"在验证器中无法将百分比字符串转换为浮点数: {key} = '{value}'")
                            continue
                    else:
                        try:
                            cleaned[key] = float(value)
                        except ValueError:
                            logger.debug(f"在验证器中无法将字符串转换为浮点数: {key} = '{value}'")
                            continue
                else:
                    logger.debug(f"在验证器中跳过非数值类型: {key} = {type(value)}")
                    continue
            self.financial_indicators = cleaned
        
        if self.confidence < 0:
            self.confidence = 0.0
        elif self.confidence > 1:
            self.confidence = 1.0
            
        return self


class FinancialToolOutput(BaseModel):
    """财务工具输出校验模型 - 节点间强类型哨卡

    工具输出数据必须经过此模型校验才能流入下一节点。
    校验失败立即抛出异常，绝不允许脏数据流入大模型。
    """
    status: str = Field(..., description="查询状态: success/failed")
    data: Optional[Dict[str, Any]] = Field(default=None, description="财务数据（详细记录）")
    summary: Optional[Dict[str, Any]] = Field(default=None, description="财务数据摘要（聚合）")
    fiscal_year: Optional[int] = Field(default=None, description="会计年度")
    message: Optional[str] = Field(default=None, description="状态消息")

    @model_validator(mode='after')
    def validate_data_integrity(self) -> 'FinancialToolOutput':
        if self.status == "success":
            has_data = self.data is not None
            has_summary = self.summary is not None
            
            if has_data:
                # data 是详细记录，必须有这些字段
                required_keys = {"total_revenue", "total_expenses"}
                missing_keys = required_keys - set(self.data.keys())
                if missing_keys:
                    logger.warning(f"⚠️ [FinancialToolOutput] data 字段缺少: {missing_keys}，继续使用")
            elif has_summary:
                # summary 是聚合数据，必须有这些字段
                required_keys = {"total_revenue", "total_expenses", "total_profit"}
                summary_keys = set(self.summary.keys())
                missing_keys = required_keys - summary_keys
                if missing_keys:
                    logger.warning(f"⚠️ [FinancialToolOutput] summary 字段缺少: {missing_keys}")
                else:
                    logger.debug(f"✅ [FinancialToolOutput] summary 数据完整，包含 {len(self.summary)} 个字段")
            else:
                logger.warning("⚠️ [FinancialToolOutput] 既没有 data 也没有 summary，数据可能为空")
        return self
    
    def get_financial_data(self) -> Optional[Dict[str, Any]]:
        """统一获取财务数据：优先使用 data，否则使用 summary"""
        if self.data:
            return self.data
        if self.summary:
            return self.summary
        return None


class FinancialQueryResult(BaseModel):
    """财务查询结果 - 在状态字典中传递的纯净元数据

    遵循原则1：状态字典只存元数据和中间结论。
    下游 Agent 如需原文，应使用 doc_id 调工具精准检索。
    """
    has_data: bool = Field(..., description="是否成功获取到财务数据")
    data_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="数据摘要（仅含关键元数据，不含原始记录）"
    )
    fiscal_year: Optional[int] = Field(default=None, description="查询的会计年度")
    error_message: Optional[str] = Field(default=None, description="查询失败原因")


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


def _load_finance_analysis_prompt_template() -> str:
    """从文件加载财务分析提示词模板"""
    prompts_dir = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "prompts", "agents", "finance"
    )
    prompt_file = os.path.join(prompts_dir, "system.md")
    
    if os.path.exists(prompt_file):
        with open(prompt_file, "r", encoding="utf-8") as f:
            template = f.read()
        logger.info(f"✅ [_load_finance_analysis_prompt] 从文件加载提示词: {prompt_file}")
        return template
    else:
        logger.warning(f"⚠️ [_load_finance_analysis_prompt] 提示词文件不存在: {prompt_file}")
        return _get_default_finance_prompt_template()


def _get_default_finance_prompt_template() -> str:
    """获取默认财务分析提示词模板（备用）"""
    return """# 财务分析任务

{user_input}

## 识别财务领域

{domain}

## 提取的财务实体

{entities}

## 用户企业真实财务数据

{financial_data}

## 分析要求

请对上述财务问题进行全面、深入的分析。

### ⚠️ 死命令级约束

1. **严禁模糊化数据**：所有财务数据必须精确到分位，如 `315,911,045.00元`
2. **严禁泄露工具名**：禁止在输出中出现 `get_financial_trend` 等内部工具名称
3. **税务合规必须精准**：年利润 > 300万元，不符合小微企业优惠

## 输出格式

请按JSON格式返回分析结果：
{
  "financial_indicators": {},
  "key_metrics": [],
  "risk_factors": [],
  "recommendations": [],
  "confidence": 0.85
}"""


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
        specialty: str = "finance",
        skill_registry: Optional['SkillRegistry'] = None,  # 🆕 技能系统
    ):
        """
        初始化财务专家

        Args:
            llm_adapter: 大模型适配器
            tool_manager: 工具管理器
            specialty: 专业领域标识
            skill_registry: 技能注册表 (可选)
        """
        super().__init__(
            specialty=specialty,
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            max_iterations=10,
            timeout=60.0,
            skill_registry=skill_registry,  # 🆕 技能系统
        )
        
        self._register_financial_mcp_tools()
        
        self.entity_patterns = self._compile_entity_patterns()
        self.financial_ratios = self._load_financial_ratios()
        
        system_prompt = self._load_system_prompt()
        self.system_prompt = system_prompt

        # 🆕 上下文优化器：防止多轮工具调用后 context window 溢出
        model_name = getattr(llm_adapter, "model_name", "default")
        self.context_optimizer = ContextOptimizer(model_name=model_name)

    def _register_financial_mcp_tools(self):
        """
        注册 MCP 财务数据查询工具和时间锚点工具

        这些工具直接从数据库查询财务数据，包含上下文优化机制
        """
        try:
            from app.mcp.financial_tools import create_financial_tools
            from app.mcp.financial_health_tools import create_financial_health_tools
            from app.mcp.foundation_tools import get_current_time_and_context

            financial_tools = create_financial_tools()
            health_tools = create_financial_health_tools()

            for tool in financial_tools:
                try:
                    self.tool_manager.register_langchain_tool(tool)
                    logger.info(f"✅ [财务专家] 注册财务数据工具: {tool.name}")
                except Exception as e:
                    logger.warning(f"⚠️ [财务专家] 注册财务数据工具失败 {tool.name}: {e}")

            for tool in health_tools:
                try:
                    self.tool_manager.register_langchain_tool(tool)
                    logger.info(f"✅ [财务专家] 注册财务健康工具: {tool.name}")
                except Exception as e:
                    logger.warning(f"⚠️ [财务专家] 注册财务健康工具失败 {tool.name}: {e}")
            
            # 注册时间锚点工具（所有专家 Agent 都需要）
            try:
                self.tool_manager.register_langchain_tool(get_current_time_and_context)
                logger.info(f"✅ [财务专家] 注册时间锚点工具: get_current_time_and_context")
            except Exception as e:
                logger.warning(f"⚠️ [财务专家] 注册时间锚点工具失败: {e}")
            
            logger.info(f"📊 [财务专家] MCP 工具注册完成，共 {len(financial_tools) + len(health_tools) + 1} 个工具")
            
        except ImportError as e:
            logger.warning(f"⚠️ [财务专家] 无法导入 MCP 财务工具: {e}")
        except Exception as e:
            logger.error(f"❌ [财务专家] 注册 MCP 工具时出错: {e}")
    
    def _load_system_prompt(self) -> str:
        """从外部文件加载系统提示词"""
        try:
            prompt = load_agent_prompt(
                agent_name="finance",
                context=self._get_prompt_context()
            )
            if prompt:
                logger.info("[财务专家智能体] 成功从 prompts/agents/finance/system.md 加载提示词")
                return prompt
            else:
                logger.warning("[财务专家智能体] 加载提示词返回空，使用默认提示词")
                return self._build_default_prompt()
        except Exception as e:
            logger.warning(f"[财务专家智能体] 加载提示词失败，使用默认提示词: {e}")
            return self._build_default_prompt()
    
    def _get_prompt_context(self) -> Dict[str, Any]:
        """获取提示词渲染上下文"""
        # 与 _build_tool_schemas() 保持同步——只暴露实际可调用的工具
        tools_description = "\n".join([
            "- get_current_time_and_context：获取当前准确的时间基准",
            "- get_financial_overview：获取企业财务概览摘要，包括营业收入、成本、利润等关键指标",
        ])

        # 获取领域技能描述 (Level 1: 仅名称+说明, 完整内容按需加载)
        skill_descriptions = ""
        try:
            if self.skill_registry and self.skill_registry.is_initialized():
                skill_descriptions = self.skill_registry.format_domain_skill_descriptions("finance")
        except Exception:
            pass

        return {
            "financial_domains": [d.value for d in FinancialDomain],
            "available_tools": tools_description or "无可用工具",
            "skill_descriptions": skill_descriptions or "暂无可用技能",
            "time_awareness_principle": """## 时间感知原则
大模型没有生物钟，当处理以下场景时，必须先调用 get_current_time_and_context：
- 用户询问"今年"、"去年"、"上个月"等相对时间
- 需要分析"本季度"、"去年同期"等时间对比
- 任何涉及时间范围的财务分析
- 查询"最新政策"或"近期趋势"

## 工作流程
1. 当用户查询包含相对时间词时，先调用 get_current_time_and_context 获取准确时间基准
2. 根据时间基准查询对应时期的财务数据
3. 执行财务分析和计算
4. 提供基于准确时间的专业建议"""
        }
    
    def _build_default_prompt(self) -> str:
        """构建默认提示词（当外部提示词文件加载失败时使用）"""
        time_principle = self._get_prompt_context().get("time_awareness_principle", "")
        return f"""你是一位专业的财务顾问，具有以下能力：
1. 精通企业财务管理，包括投资、融资、预算、成本等
2. 熟悉财务报表分析和经济指标计算
3. 能够进行财务风险评估
4. 提供合理的财务规划建议

## 可用工具
- 财务数据查询工具（query_financial_data, get_financial_overview 等）
- 财务健康分析工具（get_financial_health, analyze_cash_flow 等）
- 时间锚点工具 get_current_time_and_context（【重要】处理时间相关查询时必须使用）

{time_principle}

在回答时，请：
- 提供具体的计算过程和依据
- 引用相关的财务指标和标准
- 指出潜在的财务风险
- 提供合理的改善建议
- 明确说明假设条件和局限性
- 清晰说明时间基准（例如："基于当前 2026 年 4 月的时间..."）
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
    
    async def _query_user_financial_data(
        self,
        context: Optional[Dict[str, Any]]
    ) -> FinancialQueryResult:
        """
        查询用户的企业财务数据（使用 MCP 工具）

        原则2：数据从工具出来后，先经过 Pydantic 校验，
        如果发现是 Error 或缺少字段，立刻抛出异常触发回滚。

        原则3：为每一个可能失败的节点设计 Fallback 回路。
        查询失败时自动重试 1 次，仍失败则返回明确的错误元数据。

        Args:
            context: 上下文信息，包含 tenant_id、user_id 等

        Returns:
            FinancialQueryResult：仅含元数据的查询结果
        """
        tenant_id = None
        user_id = None
        fiscal_year = None

        if context:
            tenant_id = context.get("tenant_id")
            user_id = context.get("user_id")
            fiscal_year = context.get("fiscal_year")
        
        logger.debug(f"🔍 [FinanceSpecialist] _query_user_financial_data 接收到的 tenant_id = '{tenant_id}', user_id = '{user_id}'")

        if not tenant_id or not user_id or tenant_id == "default" or user_id == "default":
            logger.warning(f"🔍 [FinanceSpecialist] 跳过财务数据查询：tenant_id='{tenant_id}', user_id='{user_id}'")
            return FinancialQueryResult(
                has_data=False,
                error_message=f"未提供有效的 tenant_id 或 user_id (tenant_id='{tenant_id}', user_id='{user_id}')"
            )

        # ─── 通过 ToolManager 路由工具调用（保证追踪/统计完整性） ───
        max_retries = 2
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"🔍 [FinanceSpecialist] 正在通过 ToolManager 查询财务数据 "
                    f"(尝试 {attempt}/{max_retries}): tenant='{tenant_id}', year={fiscal_year}"
                )

                tool_params = {
                    "tenant_id": tenant_id,
                    "fiscal_year": fiscal_year if fiscal_year else None,
                }

                raw_result = await self.tool_manager.call_tool_raw(
                    "get_financial_overview",
                    trace_id=self.current_trace_id,
                    **tool_params
                )

                logger.debug(f"🔍 [FinanceSpecialist] ToolManager 返回原始结果:")
                logger.debug(f"   - status: {raw_result.get('status')}")
                logger.debug(f"   - has 'data': {raw_result.get('data') is not None}")
                logger.debug(f"   - has 'summary': {raw_result.get('summary') is not None}")
                logger.debug(f"   - message: {raw_result.get('message', 'N/A')[:100]}")

                if raw_result.get('data'):
                    logger.debug(f"   - data keys: {list(raw_result['data'].keys())}")
                    logger.debug(f"   - data.total_revenue: {raw_result['data'].get('total_revenue')}")
                    logger.debug(f"   - data.total_profit: {raw_result['data'].get('total_profit')}")
                if raw_result.get('summary'):
                    logger.debug(f"   - summary keys: {list(raw_result['summary'].keys())}")
                    logger.debug(f"   - summary.total_revenue: {raw_result['summary'].get('total_revenue')}")
                    logger.debug(f"   - summary.total_profit: {raw_result['summary'].get('total_profit')}")

                validated = FinancialToolOutput(**raw_result)
                logger.info("✅ [FinanceSpecialist] Pydantic 验证通过")

                financial_data = validated.get_financial_data()

                logger.debug(f"🔍 [FinanceSpecialist] get_financial_data() 返回:")
                logger.debug(f"   - financial_data is None: {financial_data is None}")
                if financial_data:
                    logger.debug(f"   - financial_data keys: {list(financial_data.keys())}")
                    logger.debug(f"   - total_revenue: {financial_data.get('total_revenue')}")
                    logger.debug(f"   - total_profit: {financial_data.get('total_profit')}")
                    logger.debug(f"   - avg_profit_margin: {financial_data.get('avg_profit_margin')}")

                data_summary = None
                if financial_data:
                    total_revenue = financial_data.get("total_revenue", 0) or 0
                    total_expenses = financial_data.get("total_expenses", 0) or 0
                    total_profit = financial_data.get("total_profit")

                    if total_profit is None:
                        total_profit = total_revenue - total_expenses
                    fiscal_years = financial_data.get("fiscal_years", [])
                    current_year = datetime.now().year
                    future_fiscal_years = [
                        year for year in fiscal_years
                        if isinstance(year, int) and year > current_year
                    ]

                    data_summary = {
                        "fiscal_year": validated.fiscal_year,
                        "total_revenue": total_revenue,
                        "total_expenses": total_expenses,
                        "total_profit": total_profit,
                        "profit_margin": (total_profit / total_revenue * 100) if total_revenue > 0 else 0,
                        "avg_profit_margin": financial_data.get("avg_profit_margin"),
                        "total_vat": financial_data.get("total_vat"),
                        "total_corporate_tax": financial_data.get("total_corporate_tax"),
                        "fiscal_years": fiscal_years,
                        "future_fiscal_years": future_fiscal_years,
                        "period_types": financial_data.get("period_types", []),
                    }
                    if future_fiscal_years:
                        data_summary["data_quality_notes"] = [
                            f"数据包含未来年度/测试年度：{', '.join(str(year) for year in future_fiscal_years)}。分析时应明确标注，避免当作已发生经营结果。"
                        ]
                    logger.info(f"✅ [FinanceSpecialist] 成功提取财务数据: revenue={total_revenue:,.2f}, profit={total_profit:,.2f}")
                else:
                    logger.warning("⚠️ [FinanceSpecialist] 财务工具返回了成功状态但 data 和 summary 都为空")
                    data_summary = {
                        "fiscal_year": validated.fiscal_year,
                        "message": validated.message or "财务数据为空"
                    }

                has_valid_data = financial_data is not None
                return FinancialQueryResult(
                    has_data=has_valid_data,
                    data_summary=data_summary,
                    fiscal_year=validated.fiscal_year
                )

            except ImportError as e:
                last_error = f"ToolManager 不可用: {e}"
                logger.warning(f"⚠️ [FinanceSpecialist] {last_error}")
                break

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"⚠️ [FinanceSpecialist] 查询财务数据失败 (尝试 {attempt}/{max_retries}): {last_error}"
                )
                if attempt < max_retries:
                    continue

        return FinancialQueryResult(
            has_data=False,
            error_message=last_error or "未知错误"
        )
    
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

    # =========================================================================
    # 🆕 财务数据查询守卫
    # =========================================================================

    @staticmethod
    def _should_query_financial_data(user_input: str, domain: FinancialDomain) -> bool:
        """
        判断是否需要查询数据库中的财务数据。

        规则：
        - domain=OTHER（无财务关键词）→ 不查数据（可能是元问题、技能询问等）
        - 用户输入包含"技能"、"能力"等元关键词 → 不查数据
        - 用户输入包含明确的财务关键词 → 查数据
        - 其他情况 → 不查（由 LLM 根据 system prompt 自行决定）

        Args:
            user_input: 用户输入
            domain: 识别的财务领域

        Returns:
            True 表示需要查询财务数据, False 表示不需要
        """
        # 规则 1: domain=OTHER 通常不是财务类问题
        if domain == FinancialDomain.OTHER:
            return False

        # 规则 2: 如果是关于技能/能力的元问题, 不查数据
        text_lower = user_input.lower()
        skill_keywords = [
            "技能", "能力", "功能", "你会做什么", "擅长",
            "skill", "capability", "feature",
        ]
        for kw in skill_keywords:
            if kw in text_lower:
                return False

        # 规则 3: 有明确的财务领域关键词 → 查数据
        return True

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
        LLM 驱动模式：通过原生函数调用（native function calling）让 LLM 自主决定调用工具。

        流程:
        1. 定义可用工具（JSON schema），通过 API tools 参数传给 LLM
        2. LLM 自主判断是否需要调用工具 → 返回结构化 tool_calls
        3. 执行工具，将结果加入对话历史
        4. LLM 基于工具返回的真实数据生成最终回答
        """
        try:
            tenant_id = "default"
            user_id = "default"
            if context:
                tenant_id = context.get("tenant_id", "default")
                user_id = context.get("user_id", "default")

            has_db_data = False
            tool_executed = False

            # ================================================================
            # 阶段 1: 构建消息 + 定义工具
            # ================================================================
            messages = []

            # 系统提示词
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})

            # 对话历史
            if history:
                for msg in history[-5:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")[:500]
                    if role in ("user", "assistant"):
                        messages.append({"role": role, "content": content})

            # RAG 上下文（作为 system 消息注入）
            if rag_context and rag_context.get("documents"):
                doc_texts = []
                for i, doc in enumerate(rag_context["documents"][:3], 1):
                    c = doc.get("content", "")
                    if c:
                        doc_texts.append(f"### 文档{i}\n{c[:1000]}")
                if doc_texts:
                    messages.append({
                        "role": "system",
                        "content": "## 企业知识库相关文档\n" + "\n".join(doc_texts)
                    })

            # 当前会话信息
            messages.append({
                "role": "system",
                "content": f"tenant_id: {tenant_id}\nuser_id: {user_id}"
            })

            # 用户问题
            messages.append({"role": "user", "content": user_input})

            # 定义可用工具（OpenAI 兼容的 function calling schema）
            financial_tools = self._build_tool_schemas()
            if not financial_tools:
                logger.warning("[FinanceSpecialist] 无可用工具定义，回退到纯文本模式")

            # ================================================================
            # 阶段 2: 多轮工具调用循环 — LLM 自主决策，可反复调用工具
            # ================================================================
            TOOLS_NEEDING_CONTEXT = {
                "get_financial_overview", "query_financial_data",
                "get_financial_trend", "search_financial_data",
                # ToolBase 工具也需要 tenant_id / user_id
                "query_user_financial_data", "calculate_tax",
                "get_tax_recommendations", "tax_compliance_checker",
            }
            MAX_TOOL_ROUNDS = 5
            final_answer = ""

            # 流式回调（由 orchestrator 挂载）：用于把最终回答实时推送到前端
            chunk_cb = None
            try:
                if getattr(self, "_orchestrator_ref", None):
                    chunk_cb = self._orchestrator_ref._chunk_callback
            except Exception:
                pass

            async def _push_stream(text: str) -> None:
                """把文本按小批次推送给前端，模拟流式打字机效果（零额外 API 消耗）。"""
                if not chunk_cb or not text:
                    return
                _BATCH = 4
                for _i in range(0, len(text), _BATCH):
                    try:
                        await chunk_cb(text[_i:_i + _BATCH])
                    except Exception:
                        pass
                    await asyncio.sleep(0)

            for round_idx in range(MAX_TOOL_ROUNDS):
                # 🆕 每次 chat() 前执行上下文优化（防止 context window 溢出）
                messages = self.context_optimizer.optimize(messages)

                # 每次循环都携带 tools，让 LLM 可以继续调用
                chat_kwargs = {"messages": messages, "temperature": 0.3}
                if financial_tools and len(financial_tools) > 0:
                    chat_kwargs["tools"] = financial_tools

                response = await asyncio.wait_for(
                    self.llm_adapter.chat(**chat_kwargs),
                    timeout=120.0,
                )

                # 检查 LLM 是否决定调用工具
                raw = response.raw_response
                tool_calls = None
                if raw:
                    choice = raw.get("choices", [{}])[0]
                    msg = choice.get("message", {})
                    tool_calls = msg.get("tool_calls", None)

                if not tool_calls or len(tool_calls) == 0:
                    # LLM 选择直接回答，退出循环
                    logger.info(f"[FinanceSpecialist] 第{round_idx+1}轮: LLM 直接回答，工具调用结束")
                    # content 可能为 None（空回复），用 `or ""` 兜底防 len(None)
                    final_answer = (getattr(response, 'content', None) or "").strip()
                    # 流式推送最终回答（分批模拟打字机，零额外 API 消耗）
                    await _push_stream(final_answer)
                    break

                logger.info(f"[FinanceSpecialist] 第{round_idx+1}轮: LLM 请求调用 {len(tool_calls)} 个工具")

                # 添加 assistant 消息（含 tool_calls）
                assistant_msg = {"role": "assistant", "content": response.content}
                # OpenAI 格式: tool_calls 需要 id, type, function
                normalized_calls = []
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        normalized_calls.append({
                            "id": tc.get("id", f"call_{round_idx}_{len(normalized_calls)}"),
                            "type": "function",
                            "function": {
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": tc.get("function", {}).get("arguments", "{}"),
                            }
                        })
                    else:
                        normalized_calls.append(tc)
                assistant_msg["tool_calls"] = normalized_calls
                messages.append(assistant_msg)

                # 执行每个工具
                for tc in normalized_calls:
                    func = tc.get("function", {})
                    tool_name = func.get("name", "")
                    try:
                        raw_args = func.get("arguments", "{}")
                        tool_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError:
                        tool_args = {}

                    # 补注上下文参数：tenant_id / user_id
                    if tool_name in TOOLS_NEEDING_CONTEXT:
                        if tenant_id:
                            tool_args.setdefault("tenant_id", tenant_id)
                        if user_id and tool_name == "query_user_financial_data":
                            tool_args.setdefault("user_id", user_id)

                    logger.info(f"[FinanceSpecialist] 执行工具: {tool_name}")

                    try:
                        tool_result = await self.tool_manager.call_tool_raw(
                            tool_name, trace_id=self.current_trace_id, **tool_args,
                        )
                        result_str = json.dumps(tool_result, ensure_ascii=False) if isinstance(tool_result, dict) else str(tool_result)
                        if isinstance(tool_result, dict) and tool_result.get("status") == "success":
                            has_db_data = True
                            tool_executed = True
                    except Exception as e:
                        error_msg = str(e)
                        logger.warning(f"[FinanceSpecialist] 工具 {tool_name} 执行失败: {error_msg}")
                        # 工具失败时明确告知 LLM 不要再重试同一个工具
                        result_str = json.dumps({
                            "status": "error",
                            "error": f"工具 {tool_name} 执行失败: {error_msg[:200]}",
                            "message": "此工具不可用，请基于已有知识或上下文信息直接回答，不要再次调用此工具"
                        }, ensure_ascii=False)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": result_str,
                    })
            else:
                # 循环正常结束（达到 MAX_TOOL_ROUNDS 仍未拿到最终回答）
                logger.warning(f"[FinanceSpecialist] 达到最大工具调用轮数 {MAX_TOOL_ROUNDS}")
                if not final_answer:
                    final_answer = "抱歉，系统处理超时。请稍后重试。"
                await _push_stream(final_answer)

            # 空答案兜底（模型偶发空回复，break 路径未覆盖）
            if not (final_answer or "").strip():
                final_answer = "抱歉，本次未能生成有效的分析结果，请稍后重试或换一种问法。"
                await _push_stream(final_answer)

            return {
                "success": True,
                "domain": "general",
                "text_answer": final_answer,
                "analysis": {"domain": "general", "confidence": 1.0,
                             "financial_indicators": {}, "key_metrics": [],
                             "risk_factors": [], "recommendations": []},
                "confidence": 1.0,
                "has_financial_db_data": has_db_data,
                "tool_executed": tool_executed,
            }

        except Exception as e:
            logger.error(f"[FinanceSpecialist] run failed: {e}", exc_info=True)
            return {"success": False, "error": str(e), "text_answer": "Processing error, please retry"}

    def _build_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        构建 OpenAI 兼容的工具定义（function calling schema）。
        合并：硬编码基础工具 + 领域 ToolBase 工具（来自 _build_openai_tools）。
        """
        if not self.tool_manager:
            return []

        base_tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_time_and_context",
                    "description": "获取当前准确的时间基准，处理时间相关查询时必须先调用此工具",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_financial_overview",
                    "description": "快速获取企业财务状况的高层摘要，包括营业收入、成本、利润等关键指标，自动聚合数据",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fiscal_year": {
                                "type": "integer",
                                "description": "会计年度，如 2024",
                            },
                        },
                    },
                },
            },
        ]

        # 加入领域 ToolBase 工具（确定性计算工具）
        domain_tools = self._build_openai_tools()
        existing_names = {t["function"]["name"] for t in base_tools}
        for dt in domain_tools:
            if dt["function"]["name"] not in existing_names:
                base_tools.append(dt)

        return base_tools

    @staticmethod
    def _is_financial_query(user_input: str) -> bool:
        """判断用户查询是否涉及财务数据，需要主动查库"""
        # 先排除元问题（技能询问、问候等）
        meta_keywords = ["技能", "能力", "会做什么", "擅长", "功能介绍", "你好", "你好吗"]
        text = user_input.lower()
        for mk in meta_keywords:
            if mk in text:
                # 但"财务能力分析"这类复合查询还是要放行
                if not any(fk in text for fk in ["分析", "评估", "查看", "查询", "报告"]):
                    return False

        # 财务数据相关关键词
        financial_keywords = [
            "利润", "营收", "收入", "成本", "费用", "资产", "负债",
            "现金流", "财务", "盈利", "亏损", "净利润", "毛利率",
            "净利率", "周转率", "回报率", "ROE", "ROI", "资产负债表",
            "利润表", "现金流量表", "财务比率", "增长率", "同比", "环比",
            "预算", "支出", "收益", "销售额", "营业额",
            "公司利润", "企业利润", "财务状况", "企业经营", "业绩",
        ]
        return any(kw in text for kw in financial_keywords)

    @staticmethod
    def _response_has_tool_call(response: str) -> bool:
        patterns = [
            r"Action:\s*\w+",
            r'\{\s*"name"\s*:',
            r"<invoke\s+name=",
            r"调用工具[:：]\s*\w+",
            r"查询[:：]\s*\w+",
        ]
        return any(re.search(p, response) for p in patterns)

    @staticmethod
    def _response_has_financial_intent(response: str) -> bool:
        """宽松检测：判断LLM响应是否表达了需要调用财务工具的意图"""
        patterns = [
            r"调用\s*(get_financial_overview|query_financial_data|get_financial_trend|search_financial_data)",
            r"查询\s*(财务|利润|营收|成本|收入|现金流|资产负债)",
            r"获取\s*(财务|利润|营收|成本|收入|现金流|资产负债)",
            r"(需要|应该|准备|让我)\s*(查询|获取|调用)",
            r"(get_financial_overview|query_financial_data)",
        ]
        return any(re.search(p, response) for p in patterns)

    @staticmethod
    def _extract_tool_call_from_text(text: str):
        """宽松模式：从文本中提取工具名称和参数"""
        import re

        # 常见财务工具名列表
        TOOL_NAMES = [
            "get_financial_overview", "query_financial_data",
            "get_financial_trend", "search_financial_data",
            "get_current_time_and_context",
        ]

        text_lower = text.lower()
        for tool in TOOL_NAMES:
            if tool in text_lower:
                # 尝试从附近提取参数（年份等）
                args = {}
                year_match = re.search(r'(20\d{2})', text)
                if year_match:
                    args["fiscal_year"] = int(year_match.group(1))
                return (tool, args)

        return None
    def _build_finance_prompt(
        self,
        user_input: str,
        entities: FinancialEntity,
        domain: FinancialDomain,
        rag_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建财务分析提示词"""
        # 🆕 技能询问检测：当用户询问"你有什么技能/能力"等元问题时，直接列出技能，不做分析
        text_lower = user_input.lower()
        _skill_keywords = ["技能", "能力", "会做什么", "擅长", "功能介绍"]
        _is_skill_query = any(kw in text_lower for kw in _skill_keywords)

        if _is_skill_query:
            logger.info(f"📝 [FinanceSpecialist] 检测到技能询问，直接返回技能列表")
            return (
                "\n## 用户询问可用技能\n\n"
                "用户正在询问你可用的技能。请直接列出你的技能清单，**不要做任何财务分析**，"
                "**不要调用任何工具**。\n\n"
                "你的技能在系统提示词的「可用技能」章节中已列出，直接引用即可。\n\n"
                "输出要求：\n"
                "- 用自然语言列出所有可用技能\n"
                "- 每个技能给出名称和简短说明\n"
                "- 提示用户可以进一步询问详情来激活技能\n"
            )

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
        
        user_financial_data = rag_context.get('data_summary') if rag_context else None
        has_financial_data = rag_context.get('has_financial_data', False) if rag_context else False
        data_error = rag_context.get('data_error') if rag_context else None

        logger.debug(f"📝 [_build_finance_prompt] 检查财务数据:")
        logger.debug(f"   - has_financial_data: {has_financial_data}")
        logger.debug(f"   - user_financial_data: {user_financial_data is not None}")
        if user_financial_data:
            logger.debug(f"   - 可用字段: {list(user_financial_data.keys())}")

        if has_financial_data and user_financial_data:
            prompt_parts.extend([
                "\n## 用户企业真实财务数据（来自企业数据库）\n",
                "以下是该企业的真实财务数据，请务必基于这些实际数据进行深入分析：\n\n"
            ])

            fiscal_year = user_financial_data.get('fiscal_year', '当前')

            prompt_parts.append(f"### {fiscal_year}年度财务概览\n")
            
            # 🔧 使用数据库实际字段，使用 or 0 处理数据库 NULL 值
            total_revenue = user_financial_data.get('total_revenue') or 0
            total_expenses = user_financial_data.get('total_expenses') or 0
            total_profit = user_financial_data.get('total_profit') or 0
            profit_margin = user_financial_data.get('profit_margin') or 0
            avg_profit_margin = user_financial_data.get('avg_profit_margin') or 0
            total_vat = user_financial_data.get('total_vat') or 0
            total_corporate_tax = user_financial_data.get('total_corporate_tax') or 0
            fiscal_years = user_financial_data.get('fiscal_years', [])
            period_types = user_financial_data.get('period_types', [])
            future_fiscal_years = user_financial_data.get('future_fiscal_years', [])
            data_quality_notes = user_financial_data.get('data_quality_notes', [])
            if future_fiscal_years:
                prompt_parts.append(
                    f"- **数据质量提示**: 包含未来年度/测试年度 {', '.join(str(y) for y in future_fiscal_years)}，"
                    "请在结论中明确说明这些年度属于测试或未发生数据，不要当作真实历史经营结果。\n"
                )
            for note in data_quality_notes:
                prompt_parts.append(f"- **数据备注**: {note}\n")
            
            prompt_parts.append(f"- **营业收入**: {total_revenue:,.2f} 元\n")
            prompt_parts.append(f"- **总支出**: {total_expenses:,.2f} 元\n")
            prompt_parts.append(f"- **营业利润**: {total_profit:,.2f} 元\n")
            prompt_parts.append(f"- **利润率**: {profit_margin:.2f}%\n")
            if avg_profit_margin:
                prompt_parts.append(f"- **平均利润率**: {avg_profit_margin:.2f}%\n")
            if total_vat:
                prompt_parts.append(f"- **增值税合计**: {total_vat:,.2f} 元\n")
            if total_corporate_tax:
                prompt_parts.append(f"- **企业所得税**: {total_corporate_tax:,.2f} 元\n")
            if fiscal_years:
                prompt_parts.append(f"- **财务年度**: {', '.join(str(y) for y in fiscal_years)}\n")
            if period_types:
                prompt_parts.append(f"- **周期类型**: {', '.join(period_types)}\n")

            prompt_parts.append("\n⚠️ **重要提示**：以上数据为企业真实财务记录，请基于这些实际数据进行分析，不要使用假设性数据。\n")
            logger.debug(f"✅ [_build_finance_prompt] 已添加真实财务数据到提示词")
        else:
            reason = f"（{data_error}）" if data_error else ""
            logger.warning(f"⚠️ [FinanceSpecialist] 无财务数据: {reason or '未提供企业名称或财务数据'}")
            
            prompt_parts.extend([
                f"\n## ⚠️ 无法获取企业真实财务数据 {reason}\n\n",
                "**重要指令（必须严格遵守）**：\n\n",
                "由于系统中没有该企业的真实财务数据记录，你**必须**采用以下策略：\n\n",
                "### 🎯 任务转变：从数据分析 → 方法论输出\n\n",
                "1. **禁止行为**：\n",
                "   - ❌ 不得编造任何具体的财务数值（如\"流动比率2.5\"）\n",
                "   - ❌ 不得生成基于假设数据的风险评分\n",
                "   - ❌ 不得使用\"根据企业数据显示\"等误导性表述\n\n",
                "2. **必须行为**：\n",
                "   - ✅ 直接输出一份**通用的企业财务风险管理方法论**\n",
                "   - ✅ 解释财务风险分析的标准框架和指标体系\n",
                "   - ✅ 说明如何正确获取和准备财务数据\n",
                "   - ✅ 提供实用的风险识别和防控建议\n\n",
                "3. **输出要求**：\n",
                "   - 生成一份**高质量的方法论指南**，而不是分析报告\n",
                "   - 使用通用行业标准和最佳实践\n",
                "   - 清晰告知用户：需要提供具体财务数据才能进行量化分析\n",
                "   - 在 JSON 输出中将所有指标值设为 0 或空数组\n\n",
                "### 📚 请按以下格式输出（JSON）：\n\n",
                "```json\n",
                "{\n",
                '  "financial_indicators": {},\n',
                '  "key_metrics": [\n',
                '    "方法论：财务风险分析需要企业实际财务数据，当前无法量化"\n',
                "  ],\n",
                '  "risk_factors": [\n',
                '    "方法论：通用的企业财务风险类型及识别方法"\n',
                "  ],\n",
                '  "recommendations": [\n',
                '    "建议用户提供企业财务报表以进行量化分析"\n',
                "  ]\n",
                "}\n",
                "```\n\n",
                "请开始输出通用的财务风险管理方法论：\n"
            ])
        
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
                "## ⚠️ 死命令级约束（违反将导致报告无效）\n\n",
                "1. **严禁模糊化数据**：所有财务数据必须精确到分位，如 `315,911,045.00元`，禁止使用\"约3.16亿元\"等模糊表述\n",
                "2. **严禁泄露工具名**：禁止在输出中出现 `get_financial_trend`、`MCP工具`、`API调用` 等内部工具名称\n",
                "3. **严禁技术术语**：禁止使用 `JSON`、`Dict`、`endpoint`、`数据库` 等开发术语\n",
                "4. **税务合规必须精准**：年利润 3.16亿元 > 300万元，**绝对不符合**小微企业优惠条件，不能出现\"若税务稽查认定\"等矛盾表述\n\n",
                "## 输出格式\n\n",
                "请按以下JSON格式返回分析结果（**不要**使用markdown代码块包裹）：\n\n",
                "```json\n",
                "{\n",
                '  "financial_indicators": {\n',
                '    "流动比率": 2.5,\n',
                '    "速动比率": 1.8,\n',
                '    "资产负债率": 0.6,\n',
                '    "毛利率": 0.35,\n',
                '    "净利率": 0.15,\n',
                '    "ROE": 0.12,\n',
                '    "ROA": 0.08\n',
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
                "4. 如果上文中标注了'⚠️ 无法获取企业真实财务数据'，则必须如实告知用户无数据\n",
                "5. **所有财务指标必须是数值**，不能是描述性字符串（如'无法计算'、'缺少数据'等）\n",
                "6. 如果无法计算某个指标，请直接省略该指标，不要包含非数值的描述\n",
                "7. 所有金额使用千分位逗号，保留两位小数（如 `910,965,492.00元`）\n",
                "8. 百分比使用小数形式（如 0.3468 表示 34.68%）\n"
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
                    
                    if isinstance(key_metrics, list):
                        pass
                    elif isinstance(key_metrics, str):
                        key_metrics = [key_metrics] if key_metrics.strip() else []
                    elif isinstance(key_metrics, dict):
                        key_metrics = [str(v) for v in key_metrics.values()] if key_metrics else []
                    else:
                        key_metrics = []
                    
                    if "risk_factors" in parsed_data:
                        risk_factors = parsed_data["risk_factors"]
                    elif "风险因素" in parsed_data:
                        risk_factors = parsed_data["风险因素"]
                    elif "risks" in parsed_data:
                        risk_factors = parsed_data["risks"]
                    
                    if isinstance(risk_factors, list):
                        pass
                    elif isinstance(risk_factors, str):
                        risk_factors = [risk_factors] if risk_factors.strip() else []
                    elif isinstance(risk_factors, dict):
                        risk_factors = [str(v) for v in risk_factors.values()] if risk_factors else []
                    else:
                        risk_factors = []
                    
                    if "recommendations" in parsed_data:
                        recommendations = parsed_data["recommendations"]
                    elif "建议" in parsed_data:
                        recommendations = parsed_data["建议"]
                    elif "recommend" in parsed_data:
                        recommendations = parsed_data["recommend"]
                    
                    if isinstance(recommendations, list):
                        pass
                    elif isinstance(recommendations, str):
                        recommendations = [recommendations] if recommendations.strip() else []
                    elif isinstance(recommendations, dict):
                        recommendations = [str(v) for v in recommendations.values()] if recommendations else []
                    else:
                        recommendations = []
                    
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
                
                # 检查是否是"无法计算"或类似的描述性字符串
                if any(phrase in value for phrase in ["无法计算", "缺少", "未知", "未提供", "未找到", "无数据"]):
                    logger.debug(f"跳过非数值财务指标: {key} = '{value}'")
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
                        logger.debug(f"无法将百分比字符串转换为浮点数: {key} = '{value}'")
                        continue
                else:
                    # 尝试直接转换为浮点数
                    try:
                        cleaned[key] = float(value)
                    except ValueError:
                        logger.debug(f"无法将字符串转换为浮点数: {key} = '{value}'")
                        continue
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
                        for sub_sub_key, sub_sub_value in sub_value.items():
                            if isinstance(sub_sub_value, (int, float)):
                                cleaned[f"{key}_{sub_key}_{sub_sub_key}"] = float(sub_sub_value)
        
        return cleaned
    
    def _generate_analysis_report(
        self,
        user_input: str,
        domain: FinancialDomain,
        analysis: FinancialAnalysisResult,
        risk_assessment: Dict[str, Any],
        recommendations: List[str],
        data_summary: Optional[Dict[str, Any]] = None,
        has_financial_data: bool = False,
        data_error: Optional[str] = None,
        rag_enabled: bool = False,
    ) -> str:
        """Generate a public-facing Markdown report instead of exposing raw fields."""
        domain_names = {
            FinancialDomain.INVESTMENT: "投资分析",
            FinancialDomain.LOAN: "贷款融资",
            FinancialDomain.BUDGET: "预算管理",
            FinancialDomain.FINANCIAL_STATEMENT: "财务报表与风险分析",
            FinancialDomain.COST_CONTROL: "成本控制",
            FinancialDomain.CASH_FLOW: "现金流管理",
            FinancialDomain.TREASURY: "资金管理",
            FinancialDomain.OTHER: "综合财务分析",
        }
        domain_name = domain_names.get(domain, "综合财务分析")

        parts = [
            "# 企业财务风险分析报告",
            "",
            "## 分析概览",
            f"- **分析主题**：{domain_name}",
            f"- **置信度**：{analysis.confidence:.0%}",
        ]

        if has_financial_data and data_summary:
            revenue = data_summary.get("total_revenue")
            expenses = data_summary.get("total_expenses")
            profit = data_summary.get("total_profit")
            margin = data_summary.get("avg_profit_margin") or data_summary.get("profit_margin")
            parts.extend(["", "## 企业财务概览"])
            if revenue is not None:
                parts.append(f"- **营业收入**：{self._format_money(revenue)}")
            if expenses is not None:
                parts.append(f"- **总支出**：{self._format_money(expenses)}")
            if profit is not None:
                parts.append(f"- **营业利润**：{self._format_money(profit)}")
            if margin is not None:
                parts.append(f"- **利润率**：{self._format_percent(margin)}")
            fiscal_years = data_summary.get("fiscal_years") or []
            if fiscal_years:
                years_preview = ", ".join(str(y) for y in fiscal_years[:8])
                suffix = "..." if len(fiscal_years) > 8 else ""
                parts.append(f"- **覆盖年度**：{years_preview}{suffix}")
        else:
            parts.extend([
                "",
                "## 企业财务概览",
                "- **数据状态**：未获取到可用于量化分析的企业财务数据",
                f"- **说明**：{data_error or '当前只能提供通用财务风险分析框架'}",
            ])

        if analysis.financial_indicators:
            parts.extend(["", "## 核心指标", "| 指标 | 数值 | 解读 |", "|---|---:|---|"])
            for key, value in analysis.financial_indicators.items():
                parts.append(f"| {key} | {self._format_indicator_value(key, value)} | {self._indicator_interpretation(key, value)} |")
        elif has_financial_data and data_summary:
            fallback_metrics = self._derive_fallback_metrics(data_summary)
            if fallback_metrics:
                parts.extend(["", "## 核心指标", "| 指标 | 数值 | 解读 |", "|---|---:|---|"])
                for key, value in fallback_metrics.items():
                    parts.append(f"| {key} | {value} | {self._fallback_metric_interpretation(key, data_summary)} |")

        if analysis.key_metrics:
            parts.extend(["", "## 关键发现"])
            parts.extend(f"- {metric}" for metric in analysis.key_metrics[:6])

        risk_factors = risk_assessment.get("risk_factors") or analysis.risk_factors
        parts.extend(["", "## 风险判断"])
        if risk_factors:
            parts.extend(f"{idx}. {risk}" for idx, risk in enumerate(risk_factors[:6], 1))
        else:
            parts.append("- 暂未识别到明确高风险信号，但仍建议持续跟踪现金流、利润率和负债变化。")

        if recommendations:
            parts.extend(["", "## 改进建议"])
            parts.extend(f"{idx}. {rec}" for idx, rec in enumerate(recommendations[:7], 1))

        parts.extend(["", "## 数据来源与限制"])
        if has_financial_data:
            parts.append("- 本报告基于企业财务数据库中的汇总数据生成。")
            future_years = (data_summary or {}).get("future_fiscal_years") or []
            if future_years:
                parts.append(f"- 数据中包含未来或测试年度：{', '.join(str(y) for y in future_years)}，相关结论需结合数据口径复核。")
        elif rag_enabled:
            parts.append("- 本报告基于企业知识库文档和通用财务分析框架生成。")
        else:
            parts.append("- 当前缺少企业财务数据，无法进行精确量化判断。")

        return "\n".join(parts).strip()

    def _build_timeout_fallback_result(
        self,
        user_input: str,
        domain: FinancialDomain,
        entities: FinancialEntity,
        query_result: FinancialQueryResult,
        rag_enabled: bool = False,
        error_message: str = "LLM 调用超时，已改用企业数据生成兜底分析",
        error_type: str = "timeout",
    ) -> Dict[str, Any]:
        """Build a public, data-backed fallback when the LLM path fails."""
        data_summary = query_result.data_summary or {}
        has_financial_data = query_result.has_data and bool(data_summary)

        indicators: Dict[str, float] = {}
        if has_financial_data:
            revenue = data_summary.get("total_revenue") or 0
            expenses = data_summary.get("total_expenses") or 0
            profit = data_summary.get("total_profit") or 0
            if revenue:
                indicators["营业收入"] = float(revenue)
                indicators["利润率"] = float(profit) / float(revenue)
            if expenses:
                indicators["总支出"] = float(expenses)
            if profit:
                indicators["营业利润"] = float(profit)

        risk_factors: List[str] = []
        future_years = data_summary.get("future_fiscal_years") or []
        data_quality_notes = data_summary.get("data_quality_notes") or []
        if future_years:
            risk_factors.append("数据中包含未来或测试年度，结论需要结合数据口径复核")
        risk_factors.extend(str(note) for note in data_quality_notes[:3])
        if not has_financial_data:
            risk_factors.append("未获取到可用于量化分析的企业财务数据")

        confidence = 0.72 if has_financial_data else 0.35
        analysis = FinancialAnalysisResult(
            domain=domain,
            financial_indicators=indicators,
            key_metrics=[
                "企业数据库已返回财务概览，报告基于确定性规则兜底生成",
                "模型生成阶段超时，未进行扩展性自然语言推理",
            ],
            risk_factors=risk_factors,
            recommendations=[],
            confidence=confidence,
        )
        recommendations = self._generate_recommendations(analysis, domain)
        risk_assessment = self.assess_financial_risk(analysis, entities)
        report = self._generate_analysis_report(
            user_input=user_input,
            domain=domain,
            analysis=analysis,
            risk_assessment=risk_assessment,
            recommendations=recommendations,
            data_summary=data_summary,
            has_financial_data=has_financial_data,
            data_error=query_result.error_message,
            rag_enabled=rag_enabled,
        )
        report = (
            f"> 说明：{error_message}，以下结果基于已获取的企业财务数据和规则兜底生成。\n\n"
            f"{report}"
        )

        return self._serialize_result({
            "success": True,
            "degraded": True,
            "error_type": error_type,
            "error": error_message,
            "domain": domain,
            "analysis": analysis.dict(),
            "risk_assessment": risk_assessment,
            "entities": {
                "amount": entities.amount,
                "percentage": entities.percentage,
                "period": entities.period,
                "currency": entities.currency,
            },
            "financial_indicators": analysis.financial_indicators,
            "key_metrics": analysis.key_metrics,
            "risk_factors": analysis.risk_factors,
            "recommendations": recommendations,
            "confidence": analysis.confidence,
            "rag_enabled": rag_enabled,
            "has_financial_db_data": query_result.has_data,
            "financial_data_error": query_result.error_message,
            "analysis_report": report,
        })

    def _format_money(self, value: Any) -> str:
        try:
            return f"{float(value or 0):,.2f} 元"
        except (TypeError, ValueError):
            return "暂无数据"

    def _format_percent(self, value: Any) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "暂无数据"
        if abs(number) <= 1:
            number *= 100
        return f"{number:.2f}%"

    def _format_indicator_value(self, key: str, value: Any) -> str:
        key_text = str(key)
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        if any(token in key_text for token in ("率", "比率", "ROE", "ROA", "margin")):
            return self._format_percent(number)
        if any(token in key_text for token in ("收入", "成本", "利润", "金额", "费用", "支出")):
            return self._format_money(number)
        return f"{number:,.2f}"

    def _indicator_interpretation(self, key: str, value: Any) -> str:
        key_text = str(key)
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "需结合业务口径复核"
        if "利润率" in key_text or "净利率" in key_text:
            pct = number * 100 if abs(number) <= 1 else number
            if pct >= 20:
                return "盈利能力较强，但需关注可持续性和数据口径"
            if pct >= 5:
                return "盈利能力处于可接受区间"
            return "盈利能力偏弱，需要关注成本费用控制"
        if "负债" in key_text:
            pct = number * 100 if abs(number) <= 1 else number
            if pct >= 70:
                return "杠杆水平偏高，需关注偿债压力"
            if pct >= 50:
                return "杠杆水平中等，建议持续监控"
            return "杠杆水平相对稳健"
        return "用于辅助判断财务风险"

    def _derive_fallback_metrics(self, data_summary: Dict[str, Any]) -> Dict[str, str]:
        metrics = {}
        revenue = data_summary.get("total_revenue") or 0
        expenses = data_summary.get("total_expenses") or 0
        profit = data_summary.get("total_profit") or 0
        if revenue:
            metrics["收入规模"] = self._format_money(revenue)
            metrics["利润率"] = self._format_percent((profit / revenue) if revenue else 0)
        if expenses:
            metrics["支出规模"] = self._format_money(expenses)
        if profit:
            metrics["利润规模"] = self._format_money(profit)
        return metrics

    def _fallback_metric_interpretation(self, key: str, data_summary: Dict[str, Any]) -> str:
        if key == "利润率":
            revenue = data_summary.get("total_revenue") or 0
            profit = data_summary.get("total_profit") or 0
            return self._indicator_interpretation("利润率", (profit / revenue) if revenue else 0)
        if key == "收入规模":
            return "反映企业经营体量，是风险分析的基础口径"
        if key == "支出规模":
            return "用于观察成本费用压力"
        if key == "利润规模":
            return "用于判断盈利能力和安全垫"
        return "用于辅助判断财务风险"

    def _serialize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        序列化财务专家结果，清理无法 JSON 序列化的对象
        
        Args:
            result: 原始结果字典
            
        Returns:
            清理后的结果字典
        """
        serialized = {}
        
        for key, value in result.items():
            if value is None:
                serialized[key] = None
            elif isinstance(value, Enum):
                serialized[key] = value.value
            elif isinstance(value, (int, float, bool, str)):
                serialized[key] = value
            elif isinstance(value, list):
                serialized[key] = [
                    item.value if isinstance(item, Enum) else item
                    for item in value
                ]
            elif isinstance(value, dict):
                serialized[key] = self._serialize_dict(value)
            else:
                serialized[key] = str(value)
        
        return serialized
    
    def _serialize_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """递归序列化字典"""
        serialized = {}
        for k, v in d.items():
            if v is None:
                serialized[k] = None
            elif isinstance(v, Enum):
                serialized[k] = v.value
            elif isinstance(v, (int, float, bool, str)):
                serialized[k] = v
            elif isinstance(v, list):
                serialized[k] = [
                    item.value if isinstance(item, Enum) else str(item) if not isinstance(item, (int, float, str)) else item
                    for item in v
                ]
            elif isinstance(v, dict):
                serialized[k] = self._serialize_dict(v)
            else:
                serialized[k] = str(v)
        return serialized
    
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
