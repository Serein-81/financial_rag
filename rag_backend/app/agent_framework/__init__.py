# app/agent_framework/__init__.py

"""
自定义 Agent 框架

一个简洁、易懂的 Agent 实现，支持多种推理模式：
- ReAct: Reasoning and Acting
- Plan-and-Solve: 规划执行模式
- Reflect: 反思改进模式
- Output Review: 输出质量审查
- Agent Orchestration: 多智能体调度

设计理念：
- 简单优于复杂
- 核心代码易于理解
- 支持多种专业智能体协作
- 统一的质量把控
"""

from .core.base_agent import BaseAgent
from .core.react_agent import ReActAgent
from .core.output_agent import OutputAgent, OutputReviewResult, OutputAgentPrompts, output_agent
from .core.reviewed_agent import ReviewedReActAgent, create_reviewed_agent
from .core.report_agent import ReportAgent, report_agent
from .core.agent_orchestrator import (
    AgentOrchestrator,
    orchestrator,
    create_orchestrated_agent,
    TaskType,
    AgentCapability,
    TaskContext
)
from .tools.tool_manager import ToolManager
from .llm.zhipu_adapter import ZhipuAdapter

__version__ = "1.2.0"

__all__ = [
    # 核心
    "BaseAgent",
    "ReActAgent",
    
    # 输出智能体
    "OutputAgent",
    "OutputReviewResult",
    "OutputAgentPrompts",
    "output_agent",
    
    # 带审查的智能体
    "ReviewedReActAgent",
    "create_reviewed_agent",
    
    # 报表智能体
    "ReportAgent",
    "report_agent",
    
    # 智能体调度器
    "AgentOrchestrator",
    "orchestrator",
    "create_orchestrated_agent",
    "TaskType",
    "AgentCapability",
    "TaskContext",
    
    # 工具
    "ToolManager",
    "ZhipuAdapter",
]
