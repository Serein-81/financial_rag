"""
多智能体系统模块

导出核心类和组件
"""

from .state import (
    AuditState,
    AuditType,
    RiskLevel,
    Finding,
    Conflict,
    Report,
    create_initial_state
)

from .coordinator import AgentCoordinator
# 为了向后兼容，添加别名
MultiAgentCoordinator = AgentCoordinator
from .message_bus import MessageBus, MessageType, AgentMessage
from .task_decomposer import TaskDecomposer, DocumentType, AuditPriority
from .result_merger import ResultMerger

# Agent 相关
from .agents.base_specialist import BaseSpecialistAgent

__all__ = [
    # 状态管理
    "AuditState",
    "AuditType", 
    "RiskLevel",
    "Finding",
    "Conflict",
    "Report",
    "create_initial_state",
    
    # 核心组件
    "AgentCoordinator",
    "MultiAgentCoordinator",  # 别名
    "MessageBus",
    "MessageType",
    "AgentMessage",
    "TaskDecomposer",
    "DocumentType",
    "AuditPriority",
    "ResultMerger",
    
    # Agent 基类
    "BaseSpecialistAgent"
]