# app/agent_framework/core/agent_factory.py

"""
Agent 工厂

根据配置创建不同模式的 Agent
"""

import logging
from typing import Optional

from app.core.config import settings
from ..llm.factory import create_llm_adapter
from ..llm.base_adapter import BaseLLMAdapter
from ..llm.agent_llm_config import AgentLLMConfig, AgentType, TenantLLMConfig
from ..llm.agent_adapter_factory import AgentLLMAdapterFactory
from ..tools.tool_manager import ToolManager
from .base_agent import BaseAgent
from .react_agent import ReActAgent
from .plan_agent import PlanAgent
from .reflect_agent import ReflectAgent

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Agent 工厂
    
    根据配置自动创建对应模式的 Agent
    支持的模式：react, plan, reflect
    """
    
    @staticmethod
    def create_agent(
        mode: Optional[str] = None,
        llm_adapter: Optional[BaseLLMAdapter] = None,
        tool_manager: Optional[ToolManager] = None,
        **kwargs
    ) -> BaseAgent:
        """
        创建 Agent
        
        Args:
            mode: Agent 模式（react, plan, reflect）
                 如果为 None，则使用配置文件中的 AGENT_MODE
            llm_adapter: LLM 适配器，如果为 None 则自动创建
            tool_manager: 工具管理器，如果为 None 则自动创建
            **kwargs: 其他参数
        
        Returns:
            对应模式的 Agent 实例
            
        Raises:
            ValueError: 不支持的 Agent 模式
        
        Examples:
            # 使用默认配置
            agent = AgentFactory.create_agent()
            
            # 指定模式
            agent = AgentFactory.create_agent("plan")
            
            # 自定义适配器
            adapter = ZhipuAdapter(...)
            agent = AgentFactory.create_agent("react", llm_adapter=adapter)
        """
        # 使用指定的模式或配置文件中的默认值
        mode = mode or getattr(settings, 'AGENT_MODE', 'react')
        mode = mode.lower().strip()
        
        logger.info(f"🏭 [Agent工厂] 创建 Agent: {mode}")
        
        # 创建 LLM 适配器（如果未提供）
        if llm_adapter is None:
            llm_adapter = create_llm_adapter()
            logger.info(f"   - LLM: {settings.LLM_PROVIDER}")
        
        # 创建工具管理器（如果未提供）
        if tool_manager is None:
            tool_manager = ToolManager()
            logger.info(f"   - 工具数: {len(tool_manager.get_all_tools())}")
        
        # 根据模式创建 Agent
        if mode == "react":
            logger.info("   - 模式: ReAct（推理-行动）")
            return ReActAgent(
                llm_adapter=llm_adapter,
                tool_manager=tool_manager,
                **kwargs
            )
        
        elif mode == "plan":
            logger.info("   - 模式: Plan（计划-执行）")
            return PlanAgent(
                llm_adapter=llm_adapter,
                tool_manager=tool_manager,
                **kwargs
            )
        
        elif mode == "reflect":
            logger.info("   - 模式: Reflect（反思-改进）")
            return ReflectAgent(
                llm_adapter=llm_adapter,
                tool_manager=tool_manager,
                **kwargs
            )
        
        else:
            raise ValueError(
                f"不支持的 Agent 模式: {mode}\n"
                f"支持的模式: react, plan, reflect\n"
                f"请在 .env 中设置 AGENT_MODE"
            )
    
    @staticmethod
    def get_supported_modes() -> list:
        """
        获取支持的 Agent 模式列表
        
        Returns:
            支持的模式名称列表
        """
        return ["react", "plan", "reflect"]
    
    @staticmethod
    def get_current_mode() -> str:
        """
        获取当前配置的 Agent 模式
        
        Returns:
            当前模式名称
        """
        return getattr(settings, 'AGENT_MODE', 'react')
    
    @staticmethod
    def get_mode_description(mode: str) -> str:
        """
        获取模式描述
        
        Args:
            mode: 模式名称
            
        Returns:
            模式描述
        """
        descriptions = {
            "react": "ReAct 模式 - 推理与行动交替，适合简单快速的任务",
            "plan": "Plan 模式 - 先规划后执行，适合复杂的多步骤任务",
            "reflect": "Reflect 模式 - 执行后反思改进，适合高质量要求的任务"
        }
        return descriptions.get(mode, "未知模式")
    
    @staticmethod
    def create_agent_with_config(
        mode: Optional[str] = None,
        llm_config: Optional[AgentLLMConfig] = None,
        tool_manager: Optional[ToolManager] = None,
        **kwargs
    ) -> BaseAgent:
        """
        根据智能体配置创建 Agent（支持每个智能体使用不同的LLM）
        
        Args:
            mode: Agent 模式（react, plan, reflect）
            llm_config: 智能体LLM配置，如果为 None 则使用全局默认
            tool_manager: 工具管理器
            **kwargs: 其他参数
        
        Returns:
            对应模式的 Agent 实例
        """
        from app.core.config import settings
        
        mode = mode or getattr(settings, 'AGENT_MODE', 'react')
        mode = mode.lower().strip()
        
        logger.info(f"🏭 [Agent工厂] 创建 Agent (智能体配置): {mode}")
        
        if llm_config:
            llm_adapter = AgentLLMAdapterFactory.create_adapter(llm_config)
            logger.info(f"   - 使用自定义 LLM: {llm_config.provider}/{llm_config.model or 'default'}")
        else:
            llm_adapter = create_llm_adapter()
            logger.info(f"   - 使用默认 LLM: {settings.LLM_PROVIDER}")
        
        if tool_manager is None:
            tool_manager = ToolManager()
            logger.info(f"   - 工具数: {len(tool_manager.get_all_tools())}")
        
        if mode == "react":
            return ReActAgent(llm_adapter=llm_adapter, tool_manager=tool_manager, **kwargs)
        elif mode == "plan":
            return PlanAgent(llm_adapter=llm_adapter, tool_manager=tool_manager, **kwargs)
        elif mode == "reflect":
            return ReflectAgent(llm_adapter=llm_adapter, tool_manager=tool_manager, **kwargs)
        else:
            raise ValueError(f"不支持的 Agent 模式: {mode}")


# 便捷函数
def create_agent(
    mode: Optional[str] = None,
    llm_adapter: Optional[BaseLLMAdapter] = None,
    tool_manager: Optional[ToolManager] = None,
    **kwargs
) -> BaseAgent:
    """
    创建 Agent 的便捷函数
    
    Args:
        mode: Agent 模式，如果为 None 则使用配置文件中的默认值
        llm_adapter: LLM 适配器
        tool_manager: 工具管理器
        **kwargs: 其他参数
    
    Returns:
        对应模式的 Agent 实例
    """
    return AgentFactory.create_agent(mode, llm_adapter, tool_manager, **kwargs)
