# app/agent_framework/__init__.py

"""
自定义 Agent 框架

一个简洁、易懂的 Agent 实现，支持多种推理模式：
- ReAct: Reasoning and Acting
- Plan-and-Solve: 规划执行模式  
- Reflect: 反思改进模式

设计理念：
- 简单优于复杂
- 核心代码易于理解
- 支持 LangChain 工具兼容
- 保持高度可扩展性
"""

from .core.base_agent import BaseAgent
from .core.react_agent import ReActAgent
from .tools.tool_manager import ToolManager
from .llm.zhipu_adapter import ZhipuAdapter

__version__ = "1.0.0"

__all__ = [
    "BaseAgent",
    "ReActAgent", 
    "ToolManager",
    "ZhipuAdapter",
]