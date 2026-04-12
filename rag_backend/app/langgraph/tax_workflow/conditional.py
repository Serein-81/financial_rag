"""
税务提交工作流条件路由

定义工作流的条件分支逻辑
"""

from typing import Literal
from .state import TaxSubmissionState, SubmissionStatus


def route_after_validation(state: TaxSubmissionState) -> Literal["fetch_financial_data", "handle_error"]:
    """
    验证后的路由决策
    
    根据验证结果决定下一步：
    - 验证通过 -> 获取财务数据
    - 验证失败 -> 错误处理
    
    Args:
        state: 当前状态
    
    Returns:
        str: 下一个节点名称
    """
    validation_result = state.get("validation_result")
    
    if validation_result and validation_result.is_valid:
        return "fetch_financial_data"
    else:
        return "handle_error"


def route_after_financial_data(state: TaxSubmissionState) -> Literal["calculate_taxes", "handle_error"]:
    """
    财务数据获取后的路由决策
    
    根据财务数据状态决定下一步：
    - 数据获取成功 -> 执行税务计算
    - 数据获取失败 -> 错误处理
    
    Args:
        state: 当前状态
    
    Returns:
        str: 下一个节点名称
    """
    financial_data = state.get("financial_data")
    
    if financial_data:
        return "calculate_taxes"
    else:
        return "handle_error"


def route_after_risk_assessment(state: TaxSubmissionState) -> Literal["request_human_review", "save_submission"]:
    """
    风险评估后的路由决策
    
    根据风险评估结果决定下一步：
    - 有高风险项 -> 请求人工审核
    - 无高风险项 -> 保存提交结果
    
    Args:
        state: 当前状态
    
    Returns:
        str: 下一个节点名称
    """
    high_risk_count = state.get("high_risk_count", 0)
    
    if high_risk_count > 0:
        return "request_human_review"
    else:
        return "save_submission"


def route_after_human_review(state: TaxSubmissionState) -> Literal["save_submission", "handle_error"]:
    """
    人工审核后的路由决策
    
    根据审核结果决定下一步：
    - 审核通过 -> 保存提交结果
    - 审核拒绝 -> 错误处理
    
    Args:
        state: 当前状态
    
    Returns:
        str: 下一个节点名称
    """
    approved = state.get("approved", True)
    
    if approved:
        return "save_submission"
    else:
        return "handle_error"


def check_continue_workflow(state: TaxSubmissionState) -> bool:
    """
    检查是否继续工作流
    
    检查当前状态是否允许继续执行：
    - 无错误 -> 继续
    - 有错误 -> 停止
    
    Args:
        state: 当前状态
    
    Returns:
        bool: 是否继续
    """
    errors = state.get("errors", [])
    current_status = state.get("current_status")
    
    if current_status in [SubmissionStatus.FAILED, SubmissionStatus.VALIDATION_FAILED]:
        return False
    
    critical_errors = [e for e in errors if "失败" in e or "错误" in e]
    
    return len(critical_errors) < 3


def check_retry_needed(state: TaxSubmissionState) -> bool:
    """
    检查是否需要重试
    
    检查工作流步骤是否失败需要重试：
    - 失败步骤 < 3 -> 可以重试
    - 失败步骤 >= 3 -> 不重试
    
    Args:
        state: 当前状态
    
    Returns:
        bool: 是否需要重试
    """
    errors = state.get("errors", [])
    return len(errors) < 3


def get_routing_info(state: TaxSubmissionState) -> dict:
    """
    获取路由信息摘要
    
    提供当前状态的路由决策信息
    
    Args:
        state: 当前状态
    
    Returns:
        dict: 路由信息
    """
    return {
        "current_status": state.get("current_status"),
        "current_step": state.get("current_step"),
        "total_steps": state.get("total_steps"),
        "has_errors": len(state.get("errors", [])) > 0,
        "error_count": len(state.get("errors", [])),
        "has_warnings": len(state.get("warnings", [])) > 0,
        "warning_count": len(state.get("warnings", [])),
        "high_risk_count": state.get("high_risk_count", 0),
        "approved": state.get("approved", True)
    }
