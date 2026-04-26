"""
税务提交工作流节点函数

定义税务提交流程中的各个处理节点
"""

import logging
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
        state = update_submission_status(state, SubmissionStatus.VALIDATING, step=1)
        logger.info(f"✅ [Node] 验证通过: {state['analysis_id']}")
    else:
        state = update_submission_status(state, SubmissionStatus.VALIDATION_FAILED, step=1)
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
        from app.services.tax_intelligence_service import TaxIntelligenceService
        
        tax_service = TaxIntelligenceService()
        tax_calculations = []
        total_tax = 0.0
        
        for tax_type in state.get("tax_types", []):
            try:
                user_input = f"""
请分析以下{state['fiscal_year']}年度税务数据：
- 营业收入: ¥{financial_data.total_revenue:,.2f}
- 应税销售额: ¥{financial_data.taxable_sales:,.2f}
- 可抵扣进项税额: ¥{financial_data.input_tax or 0:,.2f}
- 营业成本: ¥{financial_data.total_expenses:,.2f}
- 应税所得额: ¥{financial_data.taxable_income:,.2f}

请计算{_get_tax_type_name(tax_type)}应纳税额，并识别潜在风险点。
"""
                if tax_service.tax_specialist:
                    analysis_result = await tax_service.tax_specialist.run(
                        user_input=user_input,
                        history=[],
                        context={
                            "fiscal_year": state["fiscal_year"],
                            "financial_data": financial_data.model_dump() if hasattr(financial_data, 'model_dump') else financial_data,
                            "tax_type": tax_type
                        }
                    )
                    
                    if not isinstance(analysis_result, dict):
                        logger.warning(f"⚠️ TaxSpecialist 返回类型异常: {type(analysis_result)}")
                        if isinstance(analysis_result, str):
                            analysis_result = {"success": False, "error": analysis_result}
                        else:
                            analysis_result = {"success": False, "error": str(analysis_result)}
                    
                    if analysis_result.get("success"):
                        tax_amount = _extract_tax_amount_from_analysis(analysis_result, tax_type)
                        tax_rate = _extract_tax_rate_from_analysis(analysis_result, tax_type)
                        
                        tax_calculations.append(TaxCalculationItem(
                            tax_type=_get_tax_type_name(tax_type),
                            taxable_amount=financial_data.taxable_sales if tax_type == "vat" else financial_data.taxable_income,
                            tax_rate=tax_rate,
                            calculated_tax=tax_amount,
                            effective_rate=(tax_amount / financial_data.total_revenue) if financial_data.total_revenue > 0 else 0,
                            calculation_details={
                                "analysis_result": analysis_result,
                                "raw_amounts": financial_data.model_dump() if hasattr(financial_data, 'model_dump') else financial_data
                            }
                        ))
                        total_tax += tax_amount
                        
                        risk_assessment_data = analysis_result.get("risk_assessment")
                        if risk_assessment_data and isinstance(risk_assessment_data, dict):
                            for risk in risk_assessment_data.get("risk_items", []):
                                if isinstance(risk, dict):
                                    state["risk_items"].append(RiskItem(
                                        risk_id=str(uuid.uuid4()),
                                        risk_type=risk.get("risk_type", "unknown"),
                                        severity=risk.get("severity", "medium"),
                                        description=risk.get("description", ""),
                                        remediation_suggestions=risk.get("remediation", [])
                                    ))
                    else:
                        error_msg = analysis_result.get('error', '未知错误') if isinstance(analysis_result, dict) else str(analysis_result)
                        raise Exception(f"TaxSpecialist 分析失败: {error_msg}")
                else:
                    raise Exception("TaxSpecialist 未初始化")
                        
            except Exception as e:
                logger.error(f"❌ 税务计算失败 ({tax_type}): {e}")
                state["warnings"].append(f"{tax_type}计算异常: {str(e)}")
        
        state["tax_calculations"] = tax_calculations
        state["total_tax_burden"] = total_tax
        
        logger.info(f"📊 [Node DEBUG] tax_calculations 长度: {len(tax_calculations)}")
        for i, calc in enumerate(tax_calculations):
            logger.info(f"📊 [Node DEBUG] calc[{i}]: tax_type={calc.tax_type}, calculated_tax={calc.calculated_tax}")
        logger.info(f"📊 [Node DEBUG] total_tax_burden = {state['total_tax_burden']}")
        
        if financial_data.total_revenue > 0:
            state["tax_burden_rate"] = (state["total_tax_burden"] / financial_data.total_revenue) * 100
        else:
            state["tax_burden_rate"] = 0.0
        
        state = update_submission_status(state, SubmissionStatus.TAXES_CALCULATED, step=3)
        logger.info(f"✅ [Node] 税务计算完成: {state['analysis_id']}, 总税负: ¥{state['total_tax_burden']:,.2f}")
        
    except Exception as e:
        logger.error(f"❌ [Node] 税务计算失败: {e}", exc_info=True)
        state["errors"].append(f"税务计算失败: {str(e)}")
        state = update_submission_status(state, SubmissionStatus.FAILED, step=3)
    
    return state


def _get_tax_type_name(tax_type: str) -> str:
    """获取税种中文名称"""
    tax_type_map = {
        "vat": "增值税",
        "income_tax": "企业所得税",
        "personal_income_tax": "个人所得税",
        "consumption_tax": "消费税",
        "behavior_tax": "行为税"
    }
    return tax_type_map.get(tax_type, tax_type)


def _extract_tax_amount_from_analysis(analysis_result: any, tax_type: str) -> float:
    """从 TaxSpecialist 分析结果中提取税额"""
    try:
        if not isinstance(analysis_result, dict):
            logger.warning(f"⚠️ 提取税额: analysis_result 类型异常 {type(analysis_result)}")
            return 0.0
            
        analysis = analysis_result.get("analysis")
        if analysis and isinstance(analysis, dict):
            tax_amount = analysis.get("tax_amount")
            if tax_amount is not None:
                if isinstance(tax_amount, str):
                    import re
                    numbers = re.findall(r'[\d,]+\.?\d*', str(tax_amount).replace(',', ''))
                    if numbers:
                        return float(numbers[0].replace(',', ''))
                    return 0.0
                return float(tax_amount)
        
        entities = analysis_result.get("entities")
        if entities and isinstance(entities, dict):
            tax_amount = entities.get("tax_amount")
            if tax_amount is not None:
                if isinstance(tax_amount, str):
                    import re
                    numbers = re.findall(r'[\d,]+\.?\d*', str(tax_amount).replace(',', ''))
                    if numbers:
                        return float(numbers[0].replace(',', ''))
                    return 0.0
                return float(tax_amount)
        
        recommendations = analysis_result.get("recommendations")
        if recommendations and isinstance(recommendations, list):
            for rec in recommendations:
                if isinstance(rec, dict) and "tax" in str(rec).lower():
                    import re
                    numbers = re.findall(r'¥?([\d,]+\.?\d*)', str(rec))
                    if numbers:
                        return float(numbers[0].replace(',', ''))
        
        return 0.0
    except Exception as e:
        logger.warning(f"⚠️ 提取税额失败: {e}")
        return 0.0


def _extract_tax_rate_from_analysis(analysis_result: any, tax_type: str) -> float:
    """从 TaxSpecialist 分析结果中提取税率"""
    try:
        if not isinstance(analysis_result, dict):
            logger.warning(f"⚠️ 提取税率: analysis_result 类型异常 {type(analysis_result)}")
            return _get_default_tax_rate(tax_type)
            
        analysis = analysis_result.get("analysis")
        if analysis and isinstance(analysis, dict):
            tax_rate = analysis.get("tax_rate")
            if tax_rate is not None:
                if isinstance(tax_rate, str):
                    if "%" in tax_rate:
                        return float(tax_rate.replace("%", "").strip()) / 100
                    return float(tax_rate)
                return float(tax_rate)
        
        entities = analysis_result.get("entities")
        if entities and isinstance(entities, dict):
            tax_rate = entities.get("tax_rate")
            if tax_rate is not None:
                if isinstance(tax_rate, str):
                    if "%" in tax_rate:
                        return float(tax_rate.replace("%", "").strip()) / 100
                    return float(tax_rate)
                return float(tax_rate)
        
        return _get_default_tax_rate(tax_type)
    except Exception as e:
        logger.warning(f"⚠️ 提取税率失败: {e}")
        return _get_default_tax_rate(tax_type)


def _get_default_tax_rate(tax_type: str) -> float:
    """获取默认税率"""
    default_rates = {
        "vat": 0.13,
        "income_tax": 0.25,
        "personal_income_tax": 0.20,
        "consumption_tax": 0.10,
        "behavior_tax": 0.05
    }
    return default_rates.get(tax_type, 0.13)


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
        state["overall_risk_score"] = 0.0
        state["high_risk_count"] = 0
        return state
    
    financial_data = state.get("financial_data")
    tax_calculations = state.get("tax_calculations", [])
    
    try:
        risk_items_added = 0
        
        for calc in tax_calculations:
            calc_tax_type = calc.tax_type if hasattr(calc, 'tax_type') else str(calc.get('tax_type', ''))
            calc_effective_rate = calc.effective_rate if hasattr(calc, 'effective_rate') else float(calc.get('effective_rate', 0))
            calc_input_tax = calc.input_tax if hasattr(calc, 'input_tax') else float(calc.get('input_tax', 0))
            calc_output_tax = calc.output_tax if hasattr(calc, 'output_tax') else float(calc.get('output_tax', 0))
            calc_details = calc.calculation_details if hasattr(calc, 'calculation_details') else calc.get('calculation_details', {}) if isinstance(calc, dict) else {}
            
            logger.info(f"📊 [Node] 处理税种: {calc_tax_type}, 有效税率: {calc_effective_rate}")
            
            llm_analysis_result = None
            if calc_details and isinstance(calc_details, dict):
                analysis_result = calc_details.get('analysis_result')
                if analysis_result and isinstance(analysis_result, dict):
                    llm_analysis_result = analysis_result
                    logger.info(f"📊 [Node] 找到LLM分析结果: {analysis_result.get('success')}")
            
            if llm_analysis_result:
                llm_analysis = llm_analysis_result.get('analysis', {})
                if llm_analysis and isinstance(llm_analysis, dict):
                    compliance_status = llm_analysis.get('compliance_status', 'compliant')
                    risk_points = llm_analysis.get('risk_points', [])
                    tax_rate = llm_analysis.get('tax_rate')
                    
                    logger.info(f"📊 [Node] LLM合规状态: {compliance_status}")
                    logger.info(f"📊 [Node] LLM风险点: {risk_points}")
                    logger.info(f"📊 [Node] LLM税率: {tax_rate}")
                    
                    if compliance_status in ['review_required', 'non_compliant', 'needs_review']:
                        severity = 'high' if compliance_status == 'non_compliant' else 'medium'
                        risk = RiskItem(
                            risk_id=str(uuid.uuid4()),
                            risk_type=f"{calc_tax_type}合规性风险",
                            severity=severity,
                            description=f"LLM检测到合规性问题: {compliance_status}。{' '.join(risk_points) if risk_points else '建议进行合规性审查'}",
                            legal_basis=["税务申报相关规定"],
                            potential_penalty="可能被税务机关审查",
                            remediation_suggestions=[
                                "建议进行详细的合规性审查",
                                "确保所有收入已按规定申报",
                                "检查成本费用扣除的合规性"
                            ],
                            confidence=0.85
                        )
                        state = add_risk_item(state, risk)
                        risk_items_added += 1
                        logger.info(f"⚠️ [Node] 添加LLM检测的风险项: {risk.risk_type}, 严重程度: {risk.severity}")
                    
                    if tax_rate is None or tax_rate == 0:
                        risk = RiskItem(
                            risk_id=str(uuid.uuid4()),
                            risk_type=f"{calc_tax_type}税率缺失",
                            severity="medium",
                            description="LLM分析发现税率信息缺失",
                            legal_basis=["税收征收管理法"],
                            potential_penalty="需要补充税率信息",
                            remediation_suggestions=["确认适用的税率", "如有疑问咨询税务顾问"],
                            confidence=0.80
                        )
                        state = add_risk_item(state, risk)
                        risk_items_added += 1
                        logger.info(f"⚠️ [Node] 添加税率缺失风险项: {risk.risk_type}")
                
                llm_risk_assessment = llm_analysis_result.get('risk_assessment', {})
                if llm_risk_assessment and isinstance(llm_risk_assessment, dict):
                    risk_level = llm_risk_assessment.get('risk_level', 'low')
                    risk_factors = llm_risk_assessment.get('risk_factors', [])
                    
                    logger.info(f"📊 [Node] LLM风险级别: {risk_level}, 风险因素: {risk_factors}")
                    
                    if risk_level in ['high', 'critical'] and risk_factors:
                        risk = RiskItem(
                            risk_id=str(uuid.uuid4()),
                            risk_type=f"{calc_tax_type}税务风险",
                            severity=risk_level,
                            description=f"LLM评估的高风险因素: {'; '.join(risk_factors)}",
                            legal_basis=["相关税法规定"],
                            potential_penalty="可能被税务机关关注",
                            remediation_suggestions=llm_analysis_result.get('recommendations', ["建议咨询专业税务顾问"]),
                            confidence=llm_analysis_result.get('confidence', 0.8)
                        )
                        state = add_risk_item(state, risk)
                        risk_items_added += 1
                        logger.info(f"⚠️ [Node] 添加LLM评估的高风险项: {risk.risk_type}, 严重程度: {risk.severity}")
            
            if calc_tax_type == "增值税":
                if calc_input_tax > calc_output_tax * 0.8:
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
                    risk_items_added += 1
                    logger.info(f"⚠️ [Node] 添加风险项: {risk.risk_type}, 严重程度: {risk.severity}")
                    
            elif calc_tax_type == "企业所得税":
                logger.info(f"📊 [Node] 企业所得税有效税率: {calc_effective_rate}")
                if calc_effective_rate < 0.15:
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
                    risk_items_added += 1
                    logger.info(f"⚠️ [Node] 添加风险项: {risk.risk_type}, 严重程度: {risk.severity}")
        
        if financial_data:
            data_status = financial_data.data_status if hasattr(financial_data, 'data_status') else financial_data.get('data_status', 'complete')
            if data_status == "missing":
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
                risk_items_added += 1
                logger.info(f"⚠️ [Node] 添加风险项: {risk.risk_type}, 严重程度: {risk.severity}")
        
        state["overall_risk_score"] = float(state.get("overall_risk_score", 0.0))
        state["high_risk_count"] = int(state.get("high_risk_count", 0))
        
        logger.info(f"📊 [Node DEBUG] risk_items数量: {len(state['risk_items'])}")
        logger.info(f"📊 [Node DEBUG] overall_risk_score: {state['overall_risk_score']}, 类型: {type(state['overall_risk_score'])}")
        logger.info(f"📊 [Node DEBUG] high_risk_count: {state['high_risk_count']}, 类型: {type(state['high_risk_count'])}")
        
        state = update_submission_status(state, SubmissionStatus.RISK_ASSESSED, step=4)
        logger.info(f"✅ [Node] 风险评估完成: {state['analysis_id']}, 高风险项: {state['high_risk_count']}, 风险评分: {state['overall_risk_score']}")
        
    except Exception as e:
        logger.error(f"❌ [Node] 风险评估失败: {e}", exc_info=True)
        state["errors"].append(f"风险评估失败: {str(e)}")
        state["overall_risk_score"] = 0.0
        state["high_risk_count"] = 0
        state = update_submission_status(state, SubmissionStatus.RISK_ASSESSED, step=4)
    
    return state