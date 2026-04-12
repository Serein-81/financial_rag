"""
税务提交工作流图组装

使用 LangGraph 构建税务提交工作流
"""

import logging
from typing import Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import TaxSubmissionState, create_initial_submission_state
from .nodes import (
    validate_submission_node,
    fetch_financial_data_node,
    calculate_taxes_node,
    assess_risk_node,
    request_human_review_node,
    handle_human_review_node,
    save_submission_node,
    handle_error_node
)
from .conditional import (
    route_after_validation,
    route_after_financial_data,
    route_after_risk_assessment,
    route_after_human_review,
    check_continue_workflow
)

logger = logging.getLogger(__name__)


class TaxSubmissionWorkflow:
    """
    税务提交工作流
    
    使用 LangGraph 实现税务提交流程的状态机
    """
    
    def __init__(self, checkpointer: Optional[MemorySaver] = None):
        """
        初始化工作流
        
        Args:
            checkpointer: 状态持久化检查点（用于中断恢复）
        """
        self.checkpointer = checkpointer or MemorySaver()
        self.graph = None
        self.compiled_graph = None
        
        self._build_graph()
        
        logger.info("✅ 税务提交工作流初始化完成")
    
    def _build_graph(self):
        """构建工作流图"""
        workflow = StateGraph(TaxSubmissionState)
        
        workflow.add_node("validate_submission", validate_submission_node)
        workflow.add_node("fetch_financial_data", fetch_financial_data_node)
        workflow.add_node("calculate_taxes", calculate_taxes_node)
        workflow.add_node("assess_risk", assess_risk_node)
        workflow.add_node("request_human_review", request_human_review_node)
        workflow.add_node("handle_human_review", handle_human_review_node)
        workflow.add_node("save_submission", save_submission_node)
        workflow.add_node("handle_error", handle_error_node)
        
        workflow.set_entry_point("validate_submission")
        
        workflow.add_conditional_edges(
            "validate_submission",
            route_after_validation,
            {
                "fetch_financial_data": "fetch_financial_data",
                "handle_error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "fetch_financial_data",
            route_after_financial_data,
            {
                "calculate_taxes": "calculate_taxes",
                "handle_error": "handle_error"
            }
        )
        
        workflow.add_edge("calculate_taxes", "assess_risk")
        
        workflow.add_conditional_edges(
            "assess_risk",
            route_after_risk_assessment,
            {
                "request_human_review": "request_human_review",
                "save_submission": "save_submission"
            }
        )
        
        workflow.add_edge("request_human_review", "handle_human_review")
        
        workflow.add_conditional_edges(
            "handle_human_review",
            route_after_human_review,
            {
                "save_submission": "save_submission",
                "handle_error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "save_submission",
            check_continue_workflow,
            {
                True: END,
                False: "handle_error"
            }
        )
        
        workflow.add_edge("handle_error", END)
        
        self.graph = workflow
    
    def compile(self):
        """编译工作流图"""
        if not self.compiled_graph:
            self.compiled_graph = self.graph.compile(
                checkpointer=self.checkpointer
            )
            logger.info("✅ 工作流图编译完成")
        return self.compiled_graph
    
    async def execute(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
        fiscal_year: int,
        fiscal_period: Optional[str] = None,
        tax_types: list = None,
        include_policy_benefits: bool = True,
        include_risk_assessment: bool = True,
        config: Optional[dict] = None
    ) -> TaxSubmissionState:
        """
        执行税务提交工作流
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID
            user_id: 用户ID
            fiscal_year: 财政年度
            fiscal_period: 财政期间
            tax_types: 税种列表
            include_policy_benefits: 是否包含政策优惠
            include_risk_assessment: 是否包含风险评估
            config: LangGraph 配置（包含 thread_id 等）
        
        Returns:
            TaxSubmissionState: 最终状态
        """
        if tax_types is None:
            tax_types = ["vat", "income_tax"]
        
        if config is None:
            config = {"configurable": {"thread_id": session_id}}
        
        initial_state = create_initial_submission_state(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            tax_types=tax_types,
            include_policy_benefits=include_policy_benefits,
            include_risk_assessment=include_risk_assessment
        )
        
        logger.info(f"🚀 开始执行税务提交工作流: {session_id}")
        
        compiled = self.compile()
        
        final_state = None
        async for state in compiled.astream(initial_state, config=config):
            final_state = state
            current_step = state.get("current_step", 0)
            current_status = state.get("current_status", "unknown")
            logger.debug(f"📍 步骤 {current_step}: {current_status}")
        
        logger.info(f"✅ 税务提交工作流完成: {session_id}")
        
        return final_state
    
    def get_graph_visualization(self) -> dict:
        """
        获取工作流图的可视化数据
        
        Returns:
            dict: 包含节点和边的数据
        """
        if not self.compiled_graph:
            self.compile()
        
        nodes = [
            {"id": "validate_submission", "label": "验证提交"},
            {"id": "fetch_financial_data", "label": "获取财务数据"},
            {"id": "calculate_taxes", "label": "计算税务"},
            {"id": "assess_risk", "label": "风险评估"},
            {"id": "request_human_review", "label": "请求人工审核"},
            {"id": "handle_human_review", "label": "处理审核结果"},
            {"id": "save_submission", "label": "保存提交"},
            {"id": "handle_error", "label": "错误处理"}
        ]
        
        edges = [
            {"from": "validate_submission", "to": "fetch_financial_data", "condition": "验证通过"},
            {"from": "validate_submission", "to": "handle_error", "condition": "验证失败"},
            {"from": "fetch_financial_data", "to": "calculate_taxes", "condition": "数据获取成功"},
            {"from": "fetch_financial_data", "to": "handle_error", "condition": "数据获取失败"},
            {"from": "calculate_taxes", "to": "assess_risk"},
            {"from": "assess_risk", "to": "request_human_review", "condition": "有高风险"},
            {"from": "assess_risk", "to": "save_submission", "condition": "无高风险"},
            {"from": "request_human_review", "to": "handle_human_review"},
            {"from": "handle_human_review", "to": "save_submission", "condition": "审核通过"},
            {"from": "handle_human_review", "to": "handle_error", "condition": "审核拒绝"},
            {"from": "save_submission", "to": "END", "condition": "成功"},
            {"from": "save_submission", "to": "handle_error", "condition": "失败"},
            {"from": "handle_error", "to": "END"}
        ]
        
        return {
            "nodes": nodes,
            "edges": edges
        }


tax_submission_workflow = TaxSubmissionWorkflow()
