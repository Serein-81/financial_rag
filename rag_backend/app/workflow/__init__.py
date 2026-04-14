# app/workflow/__init__.py

"""
工作流模块

提供LangGraph工作流的统一管理，包括：
- 工作流监控和追踪
- 节点级别的执行追踪
- 与现有AgentTracer的集成
- 人工审核追踪
- 税务工作流监控
"""

from .workflow_monitor import (
    WorkflowMonitor,
    NodeType,
    WorkflowEvent,
    WorkflowConfig,
    NodeExecutionContext,
    workflow_context,
    node_context,
)

from .agent_integration import (
    WorkflowContextManager,
    WorkflowContext,
    AgentWorkflowIntegrator,
    get_workflow_context,
    is_agent_in_workflow,
)

from .human_review_tracker import (
    HumanReviewTracker,
    ReviewAction,
    ReviewPriority,
    ReviewTrackingRecord,
)

from .tax_workflow_monitor import (
    TaxWorkflowMonitor,
    create_tax_workflow_monitor,
)

from .policy_workflow_monitor import (
    PolicyWorkflowMonitor,
    PolicyMatchLevel,
    NotificationChannel,
    create_policy_workflow_monitor,
)

from .base_nodes import (
    NodeExecutionTracker,
    create_validation_node_tracker,
    create_financial_data_node_tracker,
    create_tax_calculation_node_tracker,
    create_risk_assessment_node_tracker,
    create_human_review_node_tracker,
    create_save_node_tracker,
    create_error_handler_tracker,
)

__all__ = [
    # 工作流监控
    "WorkflowMonitor",
    "NodeType",
    "WorkflowEvent",
    "WorkflowConfig",
    "NodeExecutionContext",
    "workflow_context",
    "node_context",
    
    # Agent集成
    "WorkflowContextManager",
    "WorkflowContext",
    "AgentWorkflowIntegrator",
    "get_workflow_context",
    "is_agent_in_workflow",
    
    # 人工审核追踪
    "HumanReviewTracker",
    "ReviewAction",
    "ReviewPriority",
    "ReviewTrackingRecord",
    
    # 税务工作流监控
    "TaxWorkflowMonitor",
    "create_tax_workflow_monitor",
    
    # 政策推送工作流监控
    "PolicyWorkflowMonitor",
    "PolicyMatchLevel",
    "NotificationChannel",
    "create_policy_workflow_monitor",
    
    # 节点追踪
    "NodeExecutionTracker",
    "create_validation_node_tracker",
    "create_financial_data_node_tracker",
    "create_tax_calculation_node_tracker",
    "create_risk_assessment_node_tracker",
    "create_human_review_node_tracker",
    "create_save_node_tracker",
    "create_error_handler_tracker",
]
