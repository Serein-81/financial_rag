"""
税务智能服务
整合财务数据查询、税务计算、政策检索、人工审核和报告生成
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.schemas.tax_intelligence import (
    TaxAnalysisRequest,
    TaxAnalysisResult,
    TaxAnalysisType,
    TaxIntelligenceStatus,
    TaxCalculationResult,
    PolicyBenefitItem,
    TaxRiskItem,
    TaxOptimizationSuggestion,
    PolicyMatchLevel,
    TaxCalculationRequest,
    PolicyQueryRequest,
    PolicySubscriptionRequest,
)
from app.agent_framework.tools.financial_data_tools import FinancialDataQueryTool, TaxCalculationTool
from app.services.policy_retrieval_service import PolicyRetrievalService
from app.multi_agent_system.human_review import HumanReviewQueue, ReviewTrigger, ReviewPriority
from app.multi_agent_system.report_generator import ReportGenerator
from app.services.agent_tracer import AgentTracer
from app.services.admin_notification_service import AdminNotificationService, RiskLevel, RiskCategory, HighRiskBehavior
from app.multi_agent_system.agents.tax_specialist import TaxSpecialist
from app.agent_framework.llm.factory import LLMAdapterFactory
from app.agent_framework.tools.tool_manager import ToolManager
from app.langgraph.tax_workflow import TaxSubmissionWorkflow

logger = logging.getLogger(__name__)


class TaxIntelligenceService:
    """
    税务智能服务
    
    功能：
    1. 税务分析工作流编排
    2. 财务数据查询与整合
    3. 税务计算与验证
    4. 优惠政策智能匹配
    5. 风险评估与预警
    6. 人工审核触发
    7. 分析报告生成
    """

    def __init__(self):
        self.financial_data_tool = FinancialDataQueryTool()
        self.tax_calculation_tool = TaxCalculationTool()
        self.policy_service = PolicyRetrievalService()
        self.human_review_queue = HumanReviewQueue()
        self.report_generator = ReportGenerator()
        self.agent_tracer = AgentTracer()
        self.notification_service = AdminNotificationService()
        
        self._initialize_llm_components()
        self._initialize_langgraph_workflow()
        
        logger.info("✅ 税务智能服务初始化完成")
    
    def _initialize_langgraph_workflow(self):
        """初始化 LangGraph 税务提交工作流"""
        try:
            self.tax_workflow = TaxSubmissionWorkflow()
            logger.info("✅ LangGraph 工作流初始化完成")
        except Exception as e:
            logger.warning(f"⚠️ LangGraph 工作流初始化失败: {e}")
            self.tax_workflow = None

    def _initialize_llm_components(self):
        """初始化LLM组件"""
        try:
            self.llm_adapter = LLMAdapterFactory.create_adapter("zhipu")
            self.tool_manager = ToolManager()
            self.tax_specialist = TaxSpecialist(
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager
            )
            logger.info("✅ LLM组件初始化完成")
        except (ValueError, KeyError) as e:
            logger.warning(f"⚠️ LLM组件初始化数据错误: {e}")
            self.tax_specialist = None
        except (OSError, IOError) as e:
            logger.warning(f"⚠️ LLM组件初始化IO错误: {e}")
            self.tax_specialist = None
        except Exception as e:
            logger.warning(f"⚠️ LLM组件初始化失败: {e}")
            self.tax_specialist = None

    async def create_analysis(
        self,
        request: TaxAnalysisRequest
    ) -> TaxIntelligenceStatus:
        """
        创建税务分析任务
        
        Args:
            request: 税务分析请求
            
        Returns:
            TaxIntelligenceStatus: 分析状态
        """
        analysis_id = str(uuid.uuid4())
        
        logger.info(f"🔍 创建税务分析任务: {analysis_id}")
        logger.info(f"   - 分析类型: {request.analysis_type}")
        logger.info(f"   - 财务年度: {request.fiscal_year}")
        logger.info(f"   - 租户ID: {request.tenant_id}")
        
        return TaxIntelligenceStatus.PENDING

    async def execute_analysis_workflow(
        self,
        request: TaxAnalysisRequest
    ) -> TaxAnalysisResult:
        """
        执行税务分析工作流
        
        优先使用 LangGraph 工作流，如果失败则回退到原有流程
        
        工作流程：
        1. 启动追踪
        2. 执行 LangGraph 工作流（如果可用）
        3. 或执行原有线性流程
        4. 匹配优惠政策
        5. 评估风险
        6. 生成优化建议
        7. 如有必要触发人工审核
        8. 生成分析报告
        9. 结束追踪
        
        Args:
            request: 税务分析请求
            
        Returns:
            TaxAnalysisResult: 分析结果
        """
        start_time = datetime.now()
        analysis_id = str(uuid.uuid4())
        
        logger.info(f"🚀 开始执行税务分析工作流: {analysis_id}")
        
        trace_id = None
        try:
            trace_id = await self.agent_tracer.start_trace(
                agent_type="tax_intelligence",
                user_query=f"税务分析 - {request.analysis_type.value}",
                message_id=analysis_id
            )
            
            await self.agent_tracer.add_step(
                trace_id=trace_id,
                step_number=1,
                step_type="thought",
                content="开始税务分析工作流"
            )
            
            if self.tax_workflow:
                result = await self._execute_langgraph_workflow(request, analysis_id, trace_id)
            else:
                result = await self._execute_legacy_workflow(request, analysis_id, trace_id)
            
            if request.include_policy_benefits:
                await self.agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=result.current_step + 1,
                    step_type="thought",
                    content="步骤: 匹配适用的税收优惠政策"
                )
                
                policy_benefits = await self._match_policy_benefits(
                    request,
                    result.tax_calculations
                )
                result.policy_benefits = policy_benefits
                result.total_potential_savings = sum(
                    p.potential_savings for p in policy_benefits
                )
            
            await self.agent_tracer.add_step(
                trace_id=trace_id,
                step_number=result.current_step + 1,
                step_type="thought",
                content="步骤: 生成优化建议"
            )
            
            optimization_suggestions = await self._generate_optimization_suggestions(
                request,
                result.tax_calculations,
                result.policy_benefits
            )
            result.optimization_suggestions = optimization_suggestions
            
            result.summary = self._generate_executive_summary(result)
            result.status = TaxIntelligenceStatus.COMPLETED
            result.completed_at = datetime.now()
            result.processing_time = (datetime.now() - start_time).total_seconds()
            
            await self.agent_tracer.add_step(
                trace_id=trace_id,
                step_number=result.current_step + 2,
                step_type="final_answer",
                content=f"税务分析完成，风险评分: {result.overall_risk_score}"
            )
            
            logger.info(f"✅ 税务分析工作流完成: {analysis_id}")
            logger.info(f"   - 总税负: ¥{result.total_tax_burden:,.2f}")
            logger.info(f"   - 税负率: {result.tax_burden_rate:.2f}%")
            logger.info(f"   - 风险评分: {result.overall_risk_score}")
            logger.info(f"   - 预估节省: ¥{result.total_potential_savings:,.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 税务分析工作流执行失败: {e}", exc_info=True)
            
            if trace_id:
                await self.agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=f"分析失败: {str(e)}",
                    success=False,
                    error_message=str(e)
                )
            
            return TaxAnalysisResult(
                analysis_id=analysis_id,
                analysis_type=request.analysis_type,
                fiscal_year=request.fiscal_year,
                fiscal_period=self._format_period(request),
                status=TaxIntelligenceStatus.FAILED,
                summary=f"分析失败: {str(e)}",
                created_at=start_time,
                completed_at=datetime.now(),
                processing_time=(datetime.now() - start_time).total_seconds()
            )
    
    async def _execute_langgraph_workflow(
        self,
        request: TaxAnalysisRequest,
        analysis_id: str,
        trace_id: str
    ) -> TaxAnalysisResult:
        """
        使用 LangGraph 工作流执行税务分析
        
        Args:
            request: 税务分析请求
            analysis_id: 分析ID
            trace_id: 追踪ID
        
        Returns:
            TaxAnalysisResult: 分析结果
        """
        logger.info(f"📊 使用 LangGraph 工作流执行: {analysis_id}")
        
        tax_types = [t.value if hasattr(t, 'value') else t for t in request.tax_types]
        
        workflow_state = await self.tax_workflow.execute(
            session_id=analysis_id,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            fiscal_year=request.fiscal_year,
            fiscal_period=self._format_period(request),
            tax_types=tax_types,
            include_policy_benefits=request.include_policy_benefits,
            include_risk_assessment=request.include_risk_assessment
        )
        
        formatted_period = self._format_period(request)
        
        result = TaxAnalysisResult(
            analysis_id=analysis_id,
            analysis_type=request.analysis_type or TaxAnalysisType.COMPREHENSIVE,
            fiscal_year=request.fiscal_year,
            fiscal_period=formatted_period,
            status=TaxIntelligenceStatus.COMPLETED,
            created_at=workflow_state.get("created_at", datetime.now())
        )
        
        if workflow_state.get("financial_data"):
            result.financial_summary = workflow_state["financial_data"].model_dump()
        
        result.tax_calculations = workflow_state.get("tax_calculations", [])
        result.total_tax_burden = workflow_state.get("total_tax_burden", 0.0)
        result.tax_burden_rate = workflow_state.get("tax_burden_rate", 0.0)
        
        result.risk_assessment = workflow_state.get("risk_items", [])
        result.overall_risk_score = workflow_state.get("overall_risk_score", 0.0)
        result.high_risk_count = workflow_state.get("high_risk_count", 0)
        
        result.summary = workflow_state.get("final_summary", "")
        
        logger.info(f"✅ LangGraph 工作流执行完成: {analysis_id}")
        
        return result
    
    async def _execute_legacy_workflow(
        self,
        request: TaxAnalysisRequest,
        analysis_id: str,
        trace_id: str
    ) -> TaxAnalysisResult:
        """
        使用原有线性流程执行税务分析（回退方案）
        
        Args:
            request: 税务分析请求
            analysis_id: 分析ID
            trace_id: 追踪ID
        
        Returns:
            TaxAnalysisResult: 分析结果
        """
        logger.info(f"📊 使用传统工作流执行: {analysis_id}")
        
        result = TaxAnalysisResult(
            analysis_id=analysis_id,
            analysis_type=request.analysis_type,
            fiscal_year=request.fiscal_year,
            fiscal_period=self._format_period(request),
            status=TaxIntelligenceStatus.ANALYZING,
            created_at=datetime.now()
        )
        
        await self.agent_tracer.add_step(
            trace_id=trace_id,
            step_number=2,
            step_type="thought",
            content=f"步骤1: 获取{request.fiscal_year}年度财务数据"
        )
        
        financial_data = await self._fetch_financial_data(request)
        result.financial_summary = financial_data
        
        await self.agent_tracer.add_step(
            trace_id=trace_id,
            step_number=3,
            step_type="thought",
            content=f"步骤2: 执行税务计算，税种: {request.tax_types}"
        )
        
        tax_calculations = await self._execute_tax_calculations(
            request,
            financial_data
        )
        result.tax_calculations = tax_calculations
        result.total_tax_burden = sum(c.calculated_tax for c in tax_calculations)
        result.tax_burden_rate = self._calculate_tax_burden_rate(
            tax_calculations,
            financial_data
        )
        
        if request.include_risk_assessment:
            await self.agent_tracer.add_step(
                trace_id=trace_id,
                step_number=4,
                step_type="thought",
                content="步骤3: 评估税务风险"
            )
            
            risk_assessment = await self._assess_tax_risks(
                request,
                tax_calculations,
                financial_data
            )
            result.risk_assessment = risk_assessment
            result.overall_risk_score = self._calculate_overall_risk_score(risk_assessment)
            result.high_risk_count = sum(1 for r in risk_assessment if r.severity == "high")
            
            if result.high_risk_count > 0:
                await self._trigger_human_review_if_needed(
                    request,
                    risk_assessment,
                    analysis_id
                )
        
        result.current_step = 5
        
        return result

    async def _fetch_financial_data(
        self,
        request: TaxAnalysisRequest
    ) -> Dict[str, Any]:
        """获取财务数据"""
        try:
            include_vat = "vat" in request.tax_types
            include_corporate_tax = "income_tax" in request.tax_types
            
            financial_data = await self.financial_data_tool.execute(
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                fiscal_year=request.fiscal_year,
                include_vat=include_vat,
                include_corporate_tax=include_corporate_tax
            )
            
            if financial_data.get("status") == "error":
                logger.warning(f"⚠️ 财务数据查询失败: {financial_data.get('message')}")
                return {
                    "total_revenue": 0.0,
                    "taxable_sales": 0.0,
                    "total_expenses": 0.0,
                    "data_status": "missing"
                }
            
            return financial_data.get("financial_data", {})
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 获取财务数据数据错误: {e}")
            return {}
        except (OSError, IOError) as e:
            logger.error(f"❌ 获取财务数据IO错误: {e}")
            return {}
        except Exception as e:
            logger.error(f"❌ 获取财务数据失败: {e}")
            return {}

    async def _execute_tax_calculations(
        self,
        request: TaxAnalysisRequest,
        financial_data: Dict[str, Any]
    ) -> List[TaxCalculationResult]:
        """执行税务计算"""
        calculations = []
        
        for tax_type in request.tax_types:
            try:
                if tax_type == "vat":
                    calculation = await self.tax_calculation_tool.execute(
                        tax_type="vat",
                        taxable_amount=financial_data.get("taxable_sales", 0.0),
                        tax_rate=financial_data.get("vat_rate", 0.13),
                        input_tax=financial_data.get("input_tax", 0.0)
                    )
                    
                    calculations.append(TaxCalculationResult(
                        tax_type="增值税",
                        taxable_amount=calculation.get("taxable_amount", 0.0),
                        tax_rate=calculation.get("tax_rate", 0.13),
                        calculated_tax=calculation.get("net_tax_payable", 0.0),
                        effective_rate=calculation.get("effective_rate", 0.0),
                        input_tax=calculation.get("input_tax", 0.0),
                        output_tax=calculation.get("output_tax", 0.0),
                        net_tax_payable=calculation.get("net_tax_payable", 0.0),
                        calculation_details=calculation
                    ))
                    
                elif tax_type == "income_tax":
                    calculation = await self.tax_calculation_tool.execute(
                        tax_type="corporate_income",
                        taxable_amount=financial_data.get("taxable_income", 0.0),
                        tax_rate=financial_data.get("corporate_tax_rate", 0.25),
                        is_small_enterprise=financial_data.get("is_small_enterprise", False)
                    )
                    
                    calculations.append(TaxCalculationResult(
                        tax_type="企业所得税",
                        taxable_amount=calculation.get("taxable_amount", 0.0),
                        tax_rate=calculation.get("tax_rate", 0.25),
                        calculated_tax=calculation.get("calculated_tax", 0.0),
                        effective_rate=calculation.get("effective_rate", 0.0),
                        calculation_details=calculation
                    ))
                    
            except (ValueError, KeyError) as e:
                logger.error(f"❌ 税务计算数据错误 ({tax_type}): {e}")
            except (OSError, IOError) as e:
                logger.error(f"❌ 税务计算IO错误 ({tax_type}): {e}")
            except Exception as e:
                logger.error(f"❌ 税务计算失败 ({tax_type}): {e}")
        
        return calculations

    async def _match_policy_benefits(
        self,
        request: TaxAnalysisRequest,
        tax_calculations: List[TaxCalculationResult]
    ) -> List[PolicyBenefitItem]:
        """匹配适用的税收优惠政策"""
        try:
            policy_results = await self.policy_service.semantic_search(
                query=f"{request.analysis_type.value} 优惠政策 {request.fiscal_year}",
                top_k=5,
                tenant_id=request.tenant_id
            )
            
            policy_benefits = []
            for policy in policy_results:
                policy_benefits.append(PolicyBenefitItem(
                    policy_id=policy.get("policy_id"),
                    policy_title=policy.get("title", ""),
                    policy_source=policy.get("source_name", ""),
                    match_level=PolicyMatchLevel.PARTIAL,
                    applicability=policy.get("score", 0.5),
                    potential_savings=0.0,
                    conditions=self._extract_policy_conditions(policy),
                    implementation_suggestions=["请咨询税务顾问获取详细指导"],
                    applicable_policies=[policy.get("title", "")]
                ))
            
            return policy_benefits
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 政策匹配数据错误: {e}")
            return []
        except (OSError, IOError) as e:
            logger.error(f"❌ 政策匹配IO错误: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ 政策匹配失败: {e}")
            return []

    def _extract_policy_conditions(self, policy: Dict[str, Any]) -> List[str]:
        """提取政策适用条件"""
        conditions = []
        if policy.get("industries"):
            conditions.append(f"适用行业: {', '.join(policy.get('industries', []))}")
        if policy.get("regions"):
            conditions.append(f"适用地区: {', '.join(policy.get('regions', []))}")
        if policy.get("tax_types"):
            conditions.append(f"适用税种: {', '.join(policy.get('tax_types', []))}")
        return conditions if conditions else ["请参阅政策原文获取详细条件"]

    async def _assess_tax_risks(
        self,
        request: TaxAnalysisRequest,
        tax_calculations: List[TaxCalculationResult],
        financial_data: Dict[str, Any]
    ) -> List[TaxRiskItem]:
        """评估税务风险"""
        risks = []
        
        for calc in tax_calculations:
            if calc.tax_type == "增值税":
                if calc.input_tax > calc.output_tax * 0.8:
                    risks.append(TaxRiskItem(
                        risk_id=str(uuid.uuid4()),
                        risk_type="进项税额异常",
                        severity="medium",
                        description="进项税额占比过高，可能存在异常",
                        legal_basis=["增值税暂行条例"],
                        potential_penalty="需补缴税款并加收滞纳金",
                        remediation_suggestions=["检查进项发票的真实性", "确保发票与业务相符"],
                        confidence=0.85
                    ))
                    
            elif calc.tax_type == "企业所得税":
                if calc.effective_rate < 0.15:
                    risks.append(TaxRiskItem(
                        risk_id=str(uuid.uuid4()),
                        risk_type="税负率异常偏低",
                        severity="high",
                        description="企业所得税实际税率明显偏低",
                        legal_basis=["企业所得税法"],
                        potential_penalty="可能被税务机关评估",
                        remediation_suggestions=["确保所有收入已申报", "检查成本费用扣除合规性"],
                        confidence=0.80
                    ))
        
        if financial_data.get("data_status") == "missing":
            risks.append(TaxRiskItem(
                risk_id=str(uuid.uuid4()),
                risk_type="财务数据缺失",
                severity="high",
                description="部分财务数据无法获取",
                legal_basis=["税务申报相关规定"],
                potential_penalty="申报不完整",
                remediation_suggestions=["完善财务数据记录", "确保历史数据可追溯"],
                confidence=0.95
            ))
        
        return risks

    async def _trigger_human_review_if_needed(
        self,
        request: TaxAnalysisRequest,
        risks: List[TaxRiskItem],
        analysis_id: str
    ):
        """必要时触发人工审核"""
        high_risk_count = sum(1 for r in risks if r.severity == "high")
        
        if high_risk_count > 0:
            logger.warning(f"⚠️ 检测到{high_risk_count}个高风险项，触发人工审核")
            
            await self.notification_service.detect_risk_level(
                user_query=f"税务分析 - {request.analysis_type.value}",
                context={"risk_count": high_risk_count}
            )
            
            review_request = self.human_review_queue.create_review_request(
                task_id=analysis_id,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                review_type="tax_analysis_review",
                trigger_reason=ReviewTrigger.ANOMALY_DETECTED,
                description=f"税务分析检测到{high_risk_count}个高风险项",
                content={"analysis_id": analysis_id, "risks": [r.model_dump() for r in risks]},
                priority=ReviewPriority.HIGH
            )
            
            logger.info(f"📋 人工审核请求已创建: {review_request.id}")

    async def _generate_optimization_suggestions(
        self,
        request: TaxAnalysisRequest,
        tax_calculations: List[TaxCalculationResult],
        policy_benefits: List[PolicyBenefitItem]
    ) -> List[TaxOptimizationSuggestion]:
        """生成税务优化建议"""
        suggestions = []
        
        for benefit in policy_benefits:
            if benefit.match_level == PolicyMatchLevel.FULL:
                suggestions.append(TaxOptimizationSuggestion(
                    category="优惠政策",
                    priority="high",
                    current_situation="尚未完全享受税收优惠",
                    optimization_approach=f"申请{benefit.policy_title}",
                    expected_benefits=f"预估节省税款 ¥{benefit.potential_savings:,.2f}",
                    implementation_steps=[
                        "评估适用条件",
                        "准备申请材料",
                        "提交税务机关审批",
                        "跟踪审批结果"
                    ],
                    applicable_policies=[benefit.policy_title]
                ))
        
        for calc in tax_calculations:
            if calc.tax_type == "增值税" and calc.net_tax_payable and calc.net_tax_payable > 0:
                suggestions.append(TaxOptimizationSuggestion(
                    category="进项管理",
                    priority="medium",
                    current_situation="存在增值税留抵",
                    optimization_approach="优化进项发票管理，确保应抵尽抵",
                    expected_benefits="提高资金使用效率",
                    implementation_steps=[
                        "梳理可抵扣进项",
                        "规范发票取得流程",
                        "关注发票时效性"
                    ]
                ))
        
        return suggestions

    def _calculate_tax_burden_rate(
        self,
        calculations: List[TaxCalculationResult],
        financial_data: Dict[str, Any]
    ) -> float:
        """计算税负率"""
        total_tax = sum(c.calculated_tax for c in calculations)
        total_revenue = financial_data.get("total_revenue", 0.0)
        
        if total_revenue > 0:
            return round((total_tax / total_revenue) * 100, 2)
        return 0.0

    def _calculate_overall_risk_score(self, risks: List[TaxRiskItem]) -> float:
        """计算综合风险评分"""
        if not risks:
            return 0.0
        
        weights = {"high": 10, "medium": 5, "low": 1}
        total_score = sum(weights.get(r.severity, 0) * r.confidence for r in risks)
        
        return min(round(total_score, 1), 100.0)

    def _generate_executive_summary(self, result: TaxAnalysisResult) -> str:
        """生成执行摘要"""
        summary_parts = []
        
        summary_parts.append(f"本次{result.analysis_type.value}税务分析已完成。")
        
        if result.total_tax_burden > 0:
            summary_parts.append(
                f"本期应缴税款合计¥{result.total_tax_burden:,.2f}，"
                f"税负率为{result.tax_burden_rate:.2f}%。"
            )
        
        if result.risk_assessment:
            high_risk = result.high_risk_count
            if high_risk > 0:
                summary_parts.append(
                    f"检测到{high_risk}个高风险项，需要重点关注。"
                )
            else:
                summary_parts.append("税务风险整体可控。")
        
        if result.total_potential_savings > 0:
            summary_parts.append(
                f"发现{len(result.policy_benefits)}项可适用的优惠政策，"
                f"预估可节省税款¥{result.total_potential_savings:,.2f}。"
            )
        
        return " ".join(summary_parts)

    def _format_period(self, request: TaxAnalysisRequest) -> str:
        """格式化财务期间"""
        if request.fiscal_quarter:
            return f"{request.fiscal_year}年第{request.fiscal_quarter}季度"
        elif request.fiscal_month:
            return f"{request.fiscal_year}年{request.fiscal_month}月"
        else:
            return f"{request.fiscal_year}年度"

    async def calculate_tax(
        self,
        request: TaxCalculationRequest
    ) -> Dict[str, Any]:
        """执行税务计算"""
        try:
            calculation = await self.tax_calculation_tool.execute(
                tax_type=request.tax_type,
                taxable_amount=request.taxable_amount,
                tax_rate=request.tax_rate,
                input_tax=request.input_tax,
                is_small_enterprise=request.is_small_enterprise
            )
            
            return {
                "calculation_id": str(uuid.uuid4()),
                "tax_type": request.tax_type,
                "taxable_amount": request.taxable_amount,
                "tax_rate": request.tax_rate,
                "calculated_tax": calculation.get("net_tax_payable", 0.0),
                "effective_rate": calculation.get("effective_rate", 0.0),
                "breakdown": calculation,
                "timestamp": datetime.now()
            }
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 税务计算数据错误: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except (OSError, IOError) as e:
            logger.error(f"❌ 税务计算IO错误: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.error(f"❌ 税务计算失败: {e}")
            raise

    async def query_policies(
        self,
        request: PolicyQueryRequest
    ) -> Dict[str, Any]:
        """查询适用的税收优惠政策"""
        try:
            filters = {}
            if request.tax_types:
                filters["tax_types"] = request.tax_types
            if request.industries:
                filters["industries"] = request.industries
            if request.regions:
                filters["regions"] = request.regions
            
            policy_results = await self.policy_service.semantic_search(
                query=request.query,
                top_k=request.top_k,
                filters=filters if filters else None,
                tenant_id=request.tenant_id
            )
            
            policies = []
            for policy in policy_results:
                policies.append(PolicyBenefitItem(
                    policy_id=policy.get("policy_id"),
                    policy_title=policy.get("title", ""),
                    policy_source=policy.get("source_name", ""),
                    match_level=PolicyMatchLevel.PARTIAL,
                    applicability=policy.get("score", 0.5),
                    conditions=self._extract_policy_conditions(policy)
                ))
            
            return {
                "query": request.query,
                "total_results": len(policies),
                "policies": policies,
                "timestamp": datetime.now()
            }
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 政策查询数据错误: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except (OSError, IOError) as e:
            logger.error(f"❌ 政策查询IO错误: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.error(f"❌ 政策查询失败: {e}")
            raise

    async def subscribe_policy_updates(
        self,
        request: PolicySubscriptionRequest
    ) -> Dict[str, Any]:
        """订阅政策更新"""
        subscription_id = str(uuid.uuid4())
        
        logger.info(f"📧 创建政策订阅: {subscription_id}")
        logger.info(f"   - 订阅类型: {request.subscription_type}")
        logger.info(f"   - 通知邮箱: {request.notification_email}")
        
        return {
            "subscription_id": subscription_id,
            "status": "active",
            "subscription_type": request.subscription_type,
            "created_at": datetime.now(),
            "next_notification_time": self._calculate_next_notification_time(
                request.subscription_type
            ),
            "message": "政策订阅创建成功"
        }

    def _calculate_next_notification_time(self, subscription_type: str) -> datetime:
        """计算下次通知时间"""
        from datetime import timedelta
        
        if subscription_type == "immediate":
            return datetime.now()
        elif subscription_type == "daily":
            return datetime.now() + timedelta(days=1)
        elif subscription_type == "weekly":
            return datetime.now() + timedelta(weeks=1)
        else:
            return datetime.now() + timedelta(weeks=1)

    async def get_report_by_id(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取税务分析报告
        
        Args:
            analysis_id: 分析ID
            
        Returns:
            分析报告数据字典，如果未找到则返回 None
        """
        try:
            logger.info(f"📋 获取税务分析报告: {analysis_id}")
            
            from app.db.session import AsyncSessionLocal
            from app.models.tax_report import TaxReport
            from sqlalchemy import select
            
            async with AsyncSessionLocal() as db:
                stmt = select(TaxReport).where(TaxReport.id == analysis_id)
                result = await db.execute(stmt)
                report = result.scalar_one_or_none()
                
                if not report:
                    logger.warning(f"⚠️ 未找到报告: {analysis_id}")
                    return None
                
                report_dict = {
                    "analysis_id": str(report.id),
                    "analysis_type": report.tax_type or "comprehensive",
                    "fiscal_year": report.tax_period_year or 2024,
                    "fiscal_period": f"{report.tax_period_year}年" if report.tax_period_year else "未知期间",
                    "status": report.status or "completed",
                    "financial_summary": {
                        "revenue": report.key_metrics.get("taxable_sales", 0) if report.key_metrics else 0,
                        "expenses": 0,
                        "profit": report.key_metrics.get("taxable_sales", 0) if report.key_metrics else 0,
                        "total_revenue": report.key_metrics.get("taxable_sales", 0) if report.key_metrics else 0
                    },
                    "tax_calculations": report.processing_result.get("tax_calculations", []) if report.processing_result else [],
                    "total_tax_burden": report.processing_result.get("total_tax", 0) if report.processing_result else 0,
                    "tax_burden_rate": report.processing_result.get("tax_rate", 0) if report.processing_result else 0,
                    "policy_benefits": [],
                    "total_potential_savings": 0.0,
                    "risk_assessment": [],
                    "overall_risk_score": report.risk_score or 0,
                    "high_risk_count": 0,
                    "optimization_suggestions": [],
                    "summary": f"税务报告分析完成，置信度: {report.confidence_score or 0:.2%}",
                    "created_at": report.created_at,
                    "completed_at": report.updated_at,
                    "processing_time": None
                }
                
                logger.info(f"✅ 报告获取成功: {analysis_id}")
                return report_dict
                
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 获取报告数据错误: {e}", exc_info=True)
            return None
        except (OSError, IOError) as e:
            logger.error(f"❌ 获取报告IO错误: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"❌ 获取报告失败: {e}", exc_info=True)
            return None

    async def get_analysis_history(
        self,
        user_id: str,
        tenant_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        获取税务分析历史记录

        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            page: 页码
            page_size: 每页数量

        Returns:
            包含历史记录列表和总数的字典
        """
        try:
            logger.info(f"📋 获取税务分析历史: user={user_id}, page={page}, page_size={page_size}")

            from app.db.session import AsyncSessionLocal
            from app.models.tax_report import TaxReport
            from sqlalchemy import select, func, desc

            async with AsyncSessionLocal() as db:
                offset = (page - 1) * page_size

                count_stmt = select(func.count(TaxReport.id)).where(
                    TaxReport.tenant_id == tenant_id
                )
                count_result = await db.execute(count_stmt)
                total = count_result.scalar() or 0

                stmt = (
                    select(TaxReport)
                    .where(TaxReport.tenant_id == tenant_id)
                    .order_by(desc(TaxReport.created_at))
                    .offset(offset)
                    .limit(page_size)
                )
                result = await db.execute(stmt)
                reports = result.scalars().all()

                items = []
                for report in reports:
                    processing_result = report.processing_result or {}
                    risk_score = report.risk_score or 0
                    
                    items.append({
                        "id": str(report.id),
                        "analysis_id": str(report.id),
                        "analysis_type": report.tax_type or "comprehensive",
                        "fiscal_year": report.tax_period_year or 2024,
                        "fiscal_period": f"{report.tax_period_year}年" if report.tax_period_year else "未知期间",
                        "overall_risk_score": risk_score,
                        "total_tax_burden": processing_result.get("total_tax", 0.0),
                        "tax_type": report.tax_type,
                        "status": report.status,
                        "confidence_score": float(report.confidence_score or 0),
                        "created_at": report.created_at.isoformat() if report.created_at else None
                    })

                return {
                    "analyses": items,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                }

        except Exception as e:
            logger.error(f"❌ 获取分析历史失败: {e}", exc_info=True)
            return {"analyses": [], "total": 0, "page": page, "page_size": page_size}
