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
from .core.plan_agent import PlanAgent
from .core.reflect_agent import ReflectAgent
from .core.output_agent import OutputAgent, OutputReviewResult, OutputAgentPrompts, output_agent
from app.multi_agent_system.agents.report_generator import ReportGenerator
from .tools.tool_manager import ToolManager
from .llm.zhipu_adapter import ZhipuAdapter

try:
    from app.multi_agent_system.agents.report_generator import ReportGenerator as _ReportGenerator
    from app.agent_framework.tools.tool_manager import ToolManager
    from app.agent_framework.llm.zhipu_adapter import ZhipuAdapter
    from app.core.config import settings
    
    def _create_report_generator(llm_adapter=None, tool_manager=None):
        """创建报表生成器实例"""
        if llm_adapter is None:
            if settings.ZHIPU_API_KEY:
                llm_adapter = ZhipuAdapter(api_key=settings.ZHIPU_API_KEY, model_name=settings.ZHIPU_MODEL)
            else:
                llm_adapter = None
        if tool_manager is None:
            tool_manager = ToolManager()
        
        if llm_adapter is not None:
            return _ReportGenerator(llm_adapter=llm_adapter, tool_manager=tool_manager)
        else:
            return None
    
    report_generator = _create_report_generator()
    
except ImportError:
    _ReportGenerator = None
    report_generator = None

ReportAgent = _ReportGenerator
report_agent = report_generator

__version__ = "1.2.0"

__all__ = [
    # 核心
    "BaseAgent",
    "ReActAgent",
    "PlanAgent",
    "ReflectAgent",
    
    # 输出智能体
    "OutputAgent",
    "OutputReviewResult",
    "OutputAgentPrompts",
    "output_agent",
    
    # 报表智能体
    "ReportAgent",
    "report_agent",
    "ReportGenerator",
    "report_generator",
    
    # 工具
    "ToolManager",
    "ZhipuAdapter",
]
