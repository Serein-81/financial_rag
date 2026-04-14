"""
税务工作流监控集成模块

将税务提交工作流与第一阶段创建的WorkflowMonitor集成：
1. 自动追踪工作流执行
2. 节点级别执行追踪
3. Agent执行关联
4. 人工审核追踪
5. 错误追踪和告警
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import uuid4
from datetime import datetime

from app.workflow import (
    WorkflowMonitor,
    WorkflowConfig,
    NodeType,
    WorkflowContextManager,
    WorkflowContext,
    HumanReviewTracker,
    ReviewAction,
    ReviewPriority
)
from app.langgraph.tax_workflow.state import (
    TaxSubmissionState,
    SubmissionStatus,
    ValidationResult,
    FinancialData,
    TaxCalculationItem,
    RiskItem
)

logger = logging.getLogger(__name__)


class TaxWorkflowMonitor:
    """
    税务工作流监控器
    
    为税务提交流程提供完整的监控、追踪和可观测性能力
    """
    
    def __init__(
        self,
        db_session,
        workflow_monitor: Optional[WorkflowMonitor] = None,
        human_review_tracker: Optional[HumanReviewTracker] = None
    ):
        """
        初始化税务工作流监控器
        
        Args:
            db_session: 数据库会话（必需）
            workflow_monitor: 工作流监控器实例（可选）
            human_review_tracker: 人工审核追踪器实例（可选）
        """
        self.db = db_session
        self._workflow_monitor = workflow_monitor
        self._human_review_tracker = human_review_tracker
        
        self._current_workflow_trace_id: Optional[str] = None
        self._current_node_execution_id: Optional[str] = None
        
        logger.info("✅ 税务工作流监控器初始化完成")
    
    @property
    def workflow_monitor(self) -> WorkflowMonitor:
        """获取工作流监控器"""
        if self._workflow_monitor is None:
            self._workflow_monitor = WorkflowMonitor(self.db)
        return self._workflow_monitor
    
    @property
    def human_review_tracker(self) -> HumanReviewTracker:
        """获取人工审核追踪器"""
        if self._human_review_tracker is None:
            self._human_review_tracker = HumanReviewTracker(self.db)
        return self._human_review_tracker
    
    def start_workflow(
        self,
        state: TaxSubmissionState,
        total_nodes: int = 8
    ) -> str:
        """
        启动工作流追踪
        
        Args:
            state: 税务提交状态
            total_nodes: 总节点数
        
        Returns:
            str: 工作流追踪ID
        """
        try:
            config = WorkflowConfig(
                workflow_type="tax_submission",
                workflow_version="1.0",
                session_id=state.get("session_id", uuid4()),
                tenant_id=state.get("tenant_id"),
                user_id=state.get("user_id"),
                metadata={
                    "fiscal_year": state.get("fiscal_year"),
                    "tax_types": state.get("tax_types", []),
                    "validation_level": state.get("validation_level"),
                    "initial_status": state.get("status")
                }
            )
            
            workflow_trace_id = self.workflow_monitor.start_workflow(config, total_nodes)
            self._current_workflow_trace_id = workflow_trace_id
            
            logger.info(f"🚀 税务工作流追踪启动: {workflow_trace_id}")
            logger.info(f"   - tenant_id: {state.get('tenant_id')}")
            logger.info(f"   - fiscal_year: {state.get('fiscal_year')}")
            logger.info(f"   - tax_types: {state.get('tax_types')}")
            
            return workflow_trace_id
            
        except Exception as e:
            logger.error(f"❌ 启动工作流追踪失败: {e}", exc_info=True)
            raise
    
    def start_node(
        self,
        node_name: str,
        node_type: NodeType,
        input_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        启动节点执行追踪
        
        Args:
            node_name: 节点名称
            node_type: 节点类型
            input_data: 输入数据
        
        Returns:
            str: 节点执行ID
        """
        if not self._current_workflow_trace_id:
            logger.warning("⚠️ 未找到工作流追踪ID，跳过节点追踪")
            return None
        
        try:
            node_execution_id = self.workflow_monitor.start_node(
                workflow_trace_id=self._current_workflow_trace_id,
                node_name=node_name,
                node_type=node_type,
                input_data=input_data
            )
            
            self._current_node_execution_id = node_execution_id
            
            WorkflowContextManager.set_context(WorkflowContext(
                workflow_trace_id=uuid4(),
                node_execution_id=uuid4(),
                node_name=node_name,
                workflow_type="tax_submission",
                execution_order=self._get_execution_order(node_name)
            ))
            
            logger.info(f"🔄 节点执行开始: {node_name} (ID: {node_execution_id})")
            
            return node_execution_id
            
        except Exception as e:
            logger.error(f"❌ 启动节点追踪失败: {e}", exc_info=True)
            return None
    
    def complete_node(
        self,
        node_name: str,
        output_data: Optional[Dict[str, Any]] = None,
        agent_trace_id: Optional[str] = None,
        token_usage: Optional[Dict[str, Any]] = None,
        execution_time_ms: Optional[float] = None
    ) -> None:
        """
        完成节点执行追踪
        
        Args:
            node_name: 节点名称
            output_data: 输出数据
            agent_trace_id: Agent追踪ID
            token_usage: Token使用统计
            execution_time_ms: 执行时间（毫秒）
        """
        if not self._current_workflow_trace_id or not self._current_node_execution_id:
            logger.warning("⚠️ 未找到工作流/节点追踪ID，跳过节点完成记录")
            return
        
        try:
            self.workflow_monitor.complete_node(
                workflow_trace_id=self._current_workflow_trace_id,
                node_execution_id=self._current_node_execution_id,
                output_data=output_data,
                agent_trace_id=agent_trace_id,
                token_usage=token_usage,
                execution_time_ms=execution_time_ms
            )
            
            WorkflowContextManager.set_context(None)
            self._current_node_execution_id = None
            
            logger.info(f"✅ 节点执行完成: {node_name}")
            
        except Exception as e:
            logger.error(f"❌ 完成节点追踪失败: {e}", exc_info=True)
    
    def record_validation(
        self,
        validation_result: ValidationResult
    ) -> None:
        """
        记录验证结果
        
        Args:
            validation_result: 验证结果
        """
        if not validation_result.is_valid:
            logger.warning(f"⚠️ 验证失败: {validation_result.errors}")
    
    def record_financial_data(
        self,
        financial_data: FinancialData
    ) -> None:
        """
        记录财务数据获取
        
        Args:
            financial_data: 财务数据
        """
        if financial_data.data_status != "complete":
            logger.warning(f"⚠️ 财务数据不完整: {financial_data.data_status}")
    
    def record_tax_calculation(
        self,
        tax_items: List[TaxCalculationItem]
    ) -> None:
        """
        记录税务计算
        
        Args:
            tax_items: 税务计算项列表
        """
        total_tax = sum(item.calculated_tax for item in tax_items)
        logger.info(f"💰 税务计算完成: {len(tax_items)} 项, 总税额: {total_tax:,.2f}")
    
    def record_risk_assessment(
        self,
        risk_items: List[RiskItem],
        high_risk_threshold: float = 0.7
    ) -> None:
        """
        记录风险评估
        
        Args:
            risk_items: 风险项列表
            high_risk_threshold: 高风险阈值
        """
        high_risk = [r for r in risk_items if r.severity == "high"]
        medium_risk = [r for r in risk_items if r.severity == "medium"]
        low_risk = [r for r in risk_items if r.severity == "low"]
        
        logger.info(f"🔍 风险评估完成: 高风险 {len(high_risk)} 项, 中风险 {len(medium_risk)} 项, 低风险 {len(low_risk)} 项")
        
        if high_risk:
            logger.warning(f"⚠️ 发现 {len(high_risk)} 项高风险")
    
    async def start_human_review(
        self,
        state: TaxSubmissionState,
        risk_items: List[RiskItem],
        priority: ReviewPriority = ReviewPriority.HIGH
    ) -> str:
        """
        启动人工审核追踪
        
        Args:
            state: 税务提交状态
            risk_items: 风险项列表
            priority: 审核优先级
        
        Returns:
            str: 审核追踪ID
        """
        if not self._current_workflow_trace_id:
            logger.warning("⚠️ 未找到工作流追踪ID，跳过人工审核追踪")
            return None
        
        try:
            high_risk_items = [
                {
                    "risk_id": r.risk_id,
                    "risk_type": r.risk_type,
                    "severity": r.severity,
                    "description": r.description
                }
                for r in risk_items
                if r.severity == "high"
            ]
            
            tracking_id = await self.human_review_tracker.create_review_tracking(
                workflow_trace_id=self._current_workflow_trace_id,
                node_execution_id=self._current_node_execution_id,
                review_reason=f"税务提交发现 {len(high_risk_items)} 项高风险项需要人工审核",
                review_type="tax_submission",
                requester_id=str(state.get("user_id")),
                tenant_id=state.get("tenant_id"),
                priority=priority,
                metadata={
                    "fiscal_year": state.get("fiscal_year"),
                    "tax_types": state.get("tax_types"),
                    "risk_items": high_risk_items
                }
            )
            
            logger.info(f"👤 人工审核追踪创建: {tracking_id}, 优先级: {priority.value}")
            
            return tracking_id
            
        except Exception as e:
            logger.error(f"❌ 启动人工审核追踪失败: {e}", exc_info=True)
            return None
    
    async def record_review_action(
        self,
        tracking_id: str,
        action: ReviewAction,
        reviewer_id: str,
        comments: Optional[str] = None
    ) -> None:
        """
        记录审核动作
        
        Args:
            tracking_id: 审核追踪ID
            action: 审核动作
            reviewer_id: 审核人ID
            comments: 审核意见
        """
        try:
            await self.human_review_tracker.record_action(
                tracking_id=tracking_id,
                action=action,
                reviewer_id=reviewer_id,
                comments=comments
            )
            
            logger.info(f"📝 审核动作记录: {action.value} by {reviewer_id}")
            
        except Exception as e:
            logger.error(f"❌ 记录审核动作失败: {e}", exc_info=True)
    
    def complete_workflow(
        self,
        status: str = "completed",
        output_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        完成工作流追踪
        
        Args:
            status: 完成状态
            output_data: 输出数据
            error_message: 错误信息
        """
        if not self._current_workflow_trace_id:
            logger.warning("⚠️ 未找到工作流追踪ID，跳过工作流完成记录")
            return
        
        try:
            self.workflow_monitor.complete_workflow(
                workflow_trace_id=self._current_workflow_trace_id,
                status=status,
                output_data=output_data,
                error_message=error_message
            )
            
            logger.info(f"🏁 税务工作流追踪完成: {self._current_workflow_trace_id}, status={status}")
            
            self._current_workflow_trace_id = None
            
        except Exception as e:
            logger.error(f"❌ 完成工作流追踪失败: {e}", exc_info=True)
    
    def record_error(
        self,
        node_name: str,
        error: Exception,
        error_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        记录错误
        
        Args:
            node_name: 节点名称
            error: 异常对象
            error_context: 错误上下文
        """
        try:
            error_message = str(error)
            error_type = type(error).__name__
            
            logger.error(f"❌ 节点 {node_name} 执行错误: {error_type}: {error_message}")
            
            if self._current_node_execution_id:
                self.workflow_monitor.record_node_error(
                    workflow_trace_id=self._current_workflow_trace_id,
                    node_execution_id=self._current_node_execution_id,
                    error_message=f"{error_type}: {error_message}",
                    error_context=error_context
                )
            
        except Exception as e:
            logger.error(f"❌ 记录错误失败: {e}", exc_info=True)
    
    def get_workflow_trace_id(self) -> Optional[str]:
        """获取当前工作流追踪ID"""
        return self._current_workflow_trace_id
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        获取执行摘要
        
        Returns:
            Dict: 执行摘要信息
        """
        if not self._current_workflow_trace_id:
            return {}
        
        try:
            trace = self.workflow_monitor.get_workflow_trace(self._current_workflow_trace_id)
            
            if trace:
                return {
                    "workflow_trace_id": str(trace.id),
                    "workflow_type": trace.workflow_type,
                    "status": trace.status,
                    "current_node": trace.current_node,
                    "total_nodes": trace.total_nodes,
                    "completed_nodes": trace.completed_nodes,
                    "execution_time_ms": trace.execution_time_ms,
                    "created_at": trace.created_at.isoformat() if trace.created_at else None,
                    "updated_at": trace.updated_at.isoformat() if trace.updated_at else None
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"❌ 获取执行摘要失败: {e}", exc_info=True)
            return {}
    
    def _get_execution_order(self, node_name: str) -> int:
        """获取节点执行顺序"""
        node_order_map = {
            "validate_submission": 1,
            "fetch_financial_data": 2,
            "calculate_taxes": 3,
            "assess_risk": 4,
            "request_human_review": 5,
            "handle_human_review": 6,
            "save_submission": 7,
            "handle_error": 8
        }
        return node_order_map.get(node_name, 0)


def create_tax_workflow_monitor(db_session) -> TaxWorkflowMonitor:
    """
    创建税务工作流监控器实例
    
    由于监控器需要数据库会话，不提供全局单例。
    使用此工厂函数为每个请求创建新的实例。
    
    Args:
        db_session: 数据库会话
    
    Returns:
        TaxWorkflowMonitor: 新的监控器实例
    """
    return TaxWorkflowMonitor(db_session)
