"""
税务提交工作流节点函数

定义税务提交流程中的各个处理节点
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
import uuid

from .state import (
    TaxSubmissionState,
    SubmissionStatus,
    ValidationResult,
    ValidationLevel,
    FinancialData,
    TaxCalculationItem,
    RiskItem,
    PolicyBenefit,
    HumanReviewRequest,
    update_submission_status,
    add_risk_item
)

logger = logging.getLogger(__name__)


async def validate_submission_node(state: TaxSubmissionState) -> TaxSubmissionState:
    """
    验证提交数据节点
    
    验证输入的税务提交数据完整性和合法性
    
    Args:
        state: 当前状态
    
    Returns:
        TaxSubmissionState: 更新后的状态
    """
    logger.info(f"🔍 [Node] 验证提交数据: {state['analysis_id']}")
    
    state = update_submission_status(state, SubmissionStatus.VALIDATING, step=1)
    
    errors = []
    warnings = []
    validated_fields = []
    
    if not state.get("tenant_id"):
        errors.append("租户ID不能为空")
    
    if not state.get("user_id"):
        errors.append("用户ID不能为空")
    
    if not state.get("fiscal_year"):
        errors.append("财政年度不能为空")
    elif state["fiscal_year"] < 2000 or state["fiscal_year"] > 2100:
        errors.append("财政年度超出有效范围")
    else:
        validated_fields.append("fiscal_year")
    
    if not state.get("tax_types"):
        errors.append("税种列表不能为空")
    else:
        valid_tax_types = {"vat", "income_tax", "personal_income", "consumption_tax"}
        for tax_type in state["tax_types"]:
            if tax_type not in valid_tax_types:
                warnings.append(f"未识别的税种: {tax_type}")
        validated_fields.append("tax_types")
    
    validation_level = state.get("validation_level", ValidationLevel.NORMAL)
    
    if validation_level == ValidationLevel.STRICT and warnings:
        errors.extend(warnings)
        warnings = []
    
    is_valid = len(errors) == 0
    
    state["validation_result"] = ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        validation_level=validation_level,
        validated_fields=validated_fields
    )
    
    if is_valid:
        state = update_submission_status(state, SubmissionStatus.VALIDATION_FAILED, step=1)
        logger.info(f"✅ [Node] 验证通过: {state['analysis_id']}")
    else:
        logger.warning(f"⚠️ [Node] 验证失败: {state['analysis_id']}, 错误: {errors}")
    
    return state


async def fetch_financial_data_node(state: TaxSubmissionState) -> TaxSubmissionState:
    """
    获取财务数据节点
    
    使用 LangChain 工具从本地数据库获取财务数据
    
    Args:
        state: 当前状态
    
    Returns:
        TaxSubmissionState: 更新后的状态
    """
    logger.info(f"💰 [Node] 获取财务数据: {state['analysis_id']}")
    
    state = update_submission_status(state, SubmissionStatus.FETCHING_FINANCIAL_DATA, step=2)
    
    try:
        from app.agent_framework.tools.financial_data_tools import FinancialDataQueryTool
        
        financial_tool = FinancialDataQueryTool()
        
        include_vat = "vat" in state.get("tax_types", [])
        include_corporate_tax = "income_tax" in state.get("tax_types", [])
        
        financial_result = await financial_tool.execute(
            user_id=state["user_id"],
            tenant_id=state["tenant_id"],
            fiscal_year=state["fiscal_year"],
            include_vat=include_vat,
            include_corporate_tax=include_corporate_tax
        )
        
        if financial_result.get("status") == "error":
            logger.warning(f"⚠️ 财务数据查询失败: {financial_result.get('message')}")
            state["financial_data"] = FinancialData(
                total_revenue=0.0,
                taxable_sales=0.0,
                total_expenses=0.0,
                data_status="missing"
            )
            state["warnings"].append("部分财务数据无法获取")
        else:
            financial_data = financial_result.get("financial_data", {})
            state["financial_data"] = FinancialData(
                total_revenue=financial_data.get("total_revenue", 0.0),
                taxable_sales=financial_data.get("taxable_sales", 0.0),
                total_expenses=financial_data.get("total_expenses", 0.0),
                input_tax=financial_data.get("input_tax", 0.0),
                output_tax=financial_data.get("output_tax", 0.0),
                taxable_income=financial_data.get("taxable_income", 0.0),
                data_status=financial_data.get("data_status", "complete")
            )
        
        state = update_submission_status(state, SubmissionStatus.FINANCIAL_DATA_FETCHED, step=2)
        logger.info(f"✅ [Node] 财务数据获取完成: {state['analysis_id']}")
        
    except (ValueError, KeyError) as e:
        logger.error(f"❌ [Node] 财务数据获取数据错误: {e}", exc_info=True)
        state["errors"].append(f"财务数据获取失败: {str(e)}")
        state = update_submission_status(state, SubmissionStatus.FAILED, step=2)
    except (OSError, IOError) as e:
        logger.error(f"❌ [Node] 财务数据获取IO错误: {e}", exc_info=True)
        state["errors"].append(f"财务数据获取失败: {str(e)}")
        state = update_submission_status(state, SubmissionStatus.FAILED, step=2)
    except Exception as e:
        logger.error(f"❌ [Node] 财务数据获取失败: {e}", exc_info=True)
        state["errors"].append(f"财务数据获取失败: {str(e)}")
        state = update_submission_status(state, SubmissionStatus.FAILED, step=2)
    
    return state


async def calculate_taxes_node(state: TaxSubmissionState) -> TaxSubmissionState:
    """
    计算税务节点
    
    使用 MCP 云端工具执行税务计算
    
    Args:
        state: 当前状态
    
    Returns:
        TaxSubmissionState: 更新后的状态
    """
    logger.info(f"🧮 [Node] 执行税务计算: {state['analysis_id']}")
    
    state = update_submission_status(state, SubmissionStatus.CALCULATING_TAXES, step=3)
    
    financial_data = state.get("financial_data")
    if not financial_data:
        state["errors"].append("缺少财务数据，无法执行税务计算")
        state = update_submission_status(state, SubmissionStatus.FAILED, step=3)
        return state
    
    try:
        from app.agent_framework.tools.tool_manager import ToolManager
        from app.agent_framework.tools.hybrid_manager import ExecutionMode
        
        tool_manager = ToolManager()
        
        tax_calculations = []
        
        for tax_type in state.get("tax_types", []):
            try:
                if tax_type == "vat":
                    mcp_tool = tool_manager.get_tool("vat_calculator")
                    if mcp_tool:
                        calc_result = await mcp_tool.execute(
                            taxable_amount=financial_data.taxable_sales,
                            tax_rate=0.13,
                            input_tax=financial_data.input_tax
                        )
                        
                        tax_calculations.append(TaxCalculationItem(
                            tax_type="增值税",
                            taxable_amount=calc_result.get("taxable_amount", financial_data.taxable_sales),
                            tax_rate=calc_result.get("tax_rate", 0.13),
                            calculated_tax=calc_result.get("net_tax_payable", 0.0),
                            effective_rate=calc_result.get("effective_rate", 0.0),
                            input_tax=calc_result.get("input_tax", 0.0),
                            output_tax=calc_result.get("output_tax", 0.0),
                            net_tax_payable=calc_result.get("net_tax_payable", 0.0),
                            calculation_details=calc_result
                        ))
                
                elif tax_type == "income_tax":
                    mcp_tool = tool_manager.get_tool("corporate_income_tax_calculator")
                    if mcp_tool:
                        calc_result = await mcp_tool.execute(
                            taxable_amount=financial_data.taxable_income,
                            tax_rate=0.25,
                            is_small_enterprise=False
                        )
                        
                        tax_calculations.append(TaxCalculationItem(
                            tax_type="企业所得税",
                            taxable_amount=calc_result.get("taxable_amount", financial_data.taxable_income),
                            tax_rate=calc_result.get("tax_rate", 0.25),
                            calculated_tax=calc_result.get("calculated_tax", 0.0),
                            effective_rate=calc_result.get("effective_rate", 0.0),
                            calculation_details=calc_result
                        ))
                        
            except Exception as e:
                logger.error(f"❌ 税务计算失败 ({tax_type}): {e}")
                state["warnings"].append(f"{tax_type}计算异常")
        
        state["tax_calculations"] = tax_calculations
        state["total_tax_burden"] = sum(c.calculated_tax for c in tax_calculations)
        
        if financial_data.total_revenue > 0:
            state["tax_burden_rate"] = (state["total_tax_burden"] / financial_data.total_revenue) * 100
        else:
            state["tax_burden_rate"] = 0.0
        
        state = update_submission_status(state, SubmissionStatus.TAXES_CALCULATED, step=3)
        logger.info(f"✅ [Node] 税务计算完成: {state['analysis_id']}, 总税负: ¥{state['total_tax_burden']:,.2f}")
        
    except Exception as e:
        logger.error(f"❌ [Node] 风险评估失败: {e}", exc_info=True)
        state["errors"].append(f"风险评估失败: {str(e)}")
        state = update_submission_status(state, SubmissionStatus.FAILED, step=4)
    
    return state


async def request_human_review_node(state: TaxSubmissionState) -> TaxSubmissionState:
    """
    请求人工审核节点
    
    当检测到高风险项时触发人工审核
    
    Args:
        state: 当前状态
    
    Returns:
        TaxSubmissionState: 更新后的状态
    """
    logger.info(f"👤 [Node] 请求人工审核: {state['analysis_id']}")
    
    state = update_submission_status(state, SubmissionStatus.REQUIRES_HUMAN_REVIEW, step=5)
    
    high_risk_count = state.get("high_risk_count", 0)
    
    if high_risk_count > 0:
        risk_types = [r.risk_type for r in state.get("risk_items", []) if r.severity == "high"]
        
        state["human_review_request"] = HumanReviewRequest(
            review_id=str(uuid.uuid4()),
            reason=f"检测到{high_risk_count}个高风险项: {', '.join(risk_types)}",
            requested_at=datetime.now(),
            requested_by=state["user_id"],
            status="pending"
        )
        
        logger.warning(f"⚠️ [Node] 人工审核已触发: {state['analysis_id']}, 风险项: {risk_types}")
        
        try:
            from app.multi_agent_system.human_review import HumanReviewQueue, ReviewTrigger, ReviewPriority
            
            review_queue = HumanReviewQueue()
            
            priority = ReviewPriority.HIGH if high_risk_count > 2 else ReviewPriority.MEDIUM
            
            await review_queue.add_review_request(
                trigger=ReviewTrigger.HIGH_RISK_DETECTED,
                analysis_id=state["analysis_id"],
                risk_items=state["risk_items"],
                priority=priority
            )
            
            logger.info(f"✅ [Node] 人工审核请求已添加队列: {state['human_review_request'].review_id}")
            
        except Exception as e:
            logger.error(f"❌ [Node] 添加审核队列失败: {e}")
            state["warnings"].append("人工审核队列添加失败")
    
    return state


async def handle_human_review_node(state: TaxSubmissionState) -> TaxSubmissionState:
    """
    处理人工审核结果节点
    
    根据人工审核结果更新状态
    
    Args:
        state: 当前状态
    
    Returns:
        TaxSubmissionState: 更新后的状态
    """
    logger.info(f"✅ [Node] 处理人工审核结果: {state['analysis_id']}")
    
    human_review = state.get("human_review_request")
    
    if not human_review:
        state = update_submission_status(state, SubmissionStatus.HUMAN_REVIEW_APPROVED, step=5)
        state["approved"] = True
        return state
    
    try:
        from app.multi_agent_system.human_review import HumanReviewQueue
        
        review_queue = HumanReviewQueue()
        
        review_result = await review_queue.get_review_result(human_review.review_id)
        
        if review_result:
            if review_result.get("approved", False):
                state = update_submission_status(state, SubmissionStatus.HUMAN_REVIEW_APPROVED, step=5)
                state["approved"] = True
                state["approval_comments"] = review_result.get("comments", "")
                logger.info(f"✅ [Node] 人工审核通过: {state['analysis_id']}")
            else:
                state = update_submission_status(state, SubmissionStatus.HUMAN_REVIEW_REJECTED, step=5)
                state["approved"] = False
                state["approval_comments"] = review_result.get("comments", "")
                state["errors"].append(f"人工审核拒绝: {review_result.get('comments', '')}")
                logger.warning(f"❌ [Node] 人工审核拒绝: {state['analysis_id']}")
        else:
            state = update_submission_status(state, SubmissionStatus.HUMAN_REVIEW_APPROVED, step=5)
            state["approved"] = True
            logger.info(f"⏭️ [Node] 人工审核结果未获取，默认通过: {state['analysis_id']}")
            
    except Exception as e:
        logger.error(f"❌ [Node] 处理审核结果失败: {e}")
        state["warnings"].append(f"审核结果处理失败: {str(e)}")
        state = update_submission_status(state, SubmissionStatus.HUMAN_REVIEW_APPROVED, step=5)
        state["approved"] = True
    
    return state


async def save_submission_node(state: TaxSubmissionState) -> TaxSubmissionState:
    """
    保存提交结果节点
    
    将税务分析结果保存到数据库
    
    Args:
        state: 当前状态
    
    Returns:
        TaxSubmissionState: 更新后的状态
    """
    logger.info(f"💾 [Node] 保存提交结果: {state['analysis_id']}")
    
    state = update_submission_status(state, SubmissionStatus.SAVING, step=6)
    
    if not state.get("approved", True):
        state = update_submission_status(state, SubmissionStatus.FAILED, step=6)
        state["final_summary"] = "提交被拒绝：人工审核未通过"
        return state
    
    try:
        state = update_submission_status(state, SubmissionStatus.SAVED, step=6)
        logger.info(f"✅ [Node] 提交结果已保存: {state['analysis_id']}")
        
        state["final_summary"] = generate_summary(state)
        state = update_submission_status(state, SubmissionStatus.COMPLETED, step=6)
        state["completed_at"] = datetime.now()
        
        logger.info(f"🎉 [Node] 税务提交工作流完成: {state['analysis_id']}")
        
    except Exception as e:
        logger.error(f"❌ [Node] 保存提交结果失败: {e}", exc_info=True)
        state["errors"].append(f"保存失败: {str(e)}")
        state = update_submission_status(state, SubmissionStatus.FAILED, step=6)
    
    return state


async def handle_error_node(state: TaxSubmissionState) -> TaxSubmissionState:
    """
    错误处理节点
    
    处理工作流中的错误
    
    Args:
        state: 当前状态
    
    Returns:
        TaxSubmissionState: 更新后的状态
    """
    logger.error(f"❌ [Node] 错误处理: {state['analysis_id']}")
    
    state["current_status"] = SubmissionStatus.FAILED
    state["final_summary"] = f"工作流执行失败: {', '.join(state.get('errors', []))}"
    state["completed_at"] = datetime.now()
    
    return state


def generate_summary(state: TaxSubmissionState) -> str:
    """
    生成税务分析摘要
    
    Args:
        state: 当前状态
    
    Returns:
        str: 摘要文本
    """
    summary_parts = []
    
    summary_parts.append(f"税务分析完成 ({state['fiscal_year']}年度)")
    
    if state.get("tax_calculations"):
        total = state["total_tax_burden"]
        summary_parts.append(f"总税负: ¥{total:,.2f}")
    
    if state.get("risk_items"):
        high_risk = state["high_risk_count"]
        if high_risk > 0:
            summary_parts.append(f"高风险项: {high_risk}项")
        else:
            summary_parts.append("风险评估: 低风险")
    
    if state.get("policy_benefits"):
        savings = state["total_potential_savings"]
        if savings > 0:
            summary_parts.append(f"预估节省: ¥{savings:,.2f}")
    
    if state.get("warnings"):
        summary_parts.append(f"警告: {len(state['warnings'])}项")
    
    return " | ".join(summary_parts)


async def assess_risk_node(state: TaxSubmissionState) -> TaxSubmissionState:
    """
    风险评估节点
    
    评估税务风险并生成风险项
    
    Args:
        state: 当前状态
    
    Returns:
        TaxSubmissionState: 更新后的状态
    """
    logger.info(f"⚠️ [Node] 风险评估: {state['analysis_id']}")
    
    state = update_submission_status(state, SubmissionStatus.ASSESSING_RISK, step=4)
    
    if not state.get("include_risk_assessment", True):
        logger.info(f"⏭️ [Node] 风险评估已跳过: {state['analysis_id']}")
        state = update_submission_status(state, SubmissionStatus.RISK_ASSESSED, step=4)
        return state
    
    financial_data = state.get("financial_data")
    tax_calculations = state.get("tax_calculations", [])
    
    try:
        for calc in tax_calculations:
            if calc.tax_type == "增值税":
                if calc.input_tax > calc.output_tax * 0.8:
                    risk = RiskItem(
                        risk_id=str(uuid.uuid4()),
                        risk_type="进项税额异常",
                        severity="medium",
                        description="进项税额占比过高，可能存在异常",
                        legal_basis=["增值税暂行条例"],
                        potential_penalty="需补缴税款并加收滞纳金",
                        remediation_suggestions=["检查进项发票的真实性", "确保发票与业务相符"],
                        confidence=0.85
                    )
                    state = add_risk_item(state, risk)
                    
            elif calc.tax_type == "企业所得税":
                if calc.effective_rate < 0.15:
                    risk = RiskItem(
                        risk_id=str(uuid.uuid4()),
                        risk_type="税负率异常偏低",
                        severity="high",
                        description="企业所得税实际税率明显偏低",
                        legal_basis=["企业所得税法"],
                        potential_penalty="可能被税务机关评估",
                        remediation_suggestions=["确保所有收入已申报", "检查成本费用扣除合规性"],
                        confidence=0.80
                    )
                    state = add_risk_item(state, risk)
        
        if financial_data and financial_data.data_status == "missing":
            risk = RiskItem(
                risk_id=str(uuid.uuid4()),
                risk_type="财务数据缺失",
                severity="high",
                description="部分财务数据无法获取",
                legal_basis=["税务申报相关规定"],
                potential_penalty="申报不完整",
                remediation_suggestions=["完善财务数据记录", "确保历史数据可追溯"],
                confidence=0.95
            )
            state = add_risk_item(state, risk)
        
        state = update_submission_status(state, SubmissionStatus.RISK_ASSESSED, step=4)
        logger.info(f"✅ [Node] 风险评估完成: {state['analysis_id']}, 高风险项: {state['high_risk_count']}")
        
    except Exception as e:
        logger.error(f"❌ [Node] 风险评估失败: {e}", exc_info=True)