"""
A2A 协议初始化模块

将现有 Agent 集成到 A2A 协议
"""

import logging
from typing import Optional, List

from .registry import AgentRegistry, agent_registry
from .wrapper import (
    AgentWrapper,
    AgentWrapperConfig,
    wrap_tax_specialist,
    wrap_finance_specialist,
    wrap_legal_specialist,
    wrap_react_agent
)
from .dispatcher import HybridDispatcher, DispatchStrategy
from app.services.agent_registry import (
    agent_discovery_registry,
    AgentInfo,
    ToolInfo,
    AgentType,
    ToolLocation
)

logger = logging.getLogger(__name__)


class A2AInitializer:
    """
    A2A 协议初始化器

    负责：
    1. 包装现有 Agent
    2. 注册到 Agent Registry
    3. 注册到 Agent Discovery Registry
    4. 配置调度策略
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.registry = agent_registry
        self.wrappers: dict[str, AgentWrapper] = {}
        self.dispatcher: Optional[HybridDispatcher] = None

    def _convert_tool_manager_tools(self, tool_manager, specialty: str) -> List[ToolInfo]:
        """将 ToolManager 的工具转换为 ToolInfo"""
        from app.mcp.mcp_factory import MCPClientFactory

        tools = []
        for tool_name, tool in tool_manager.tools.items():
            description = getattr(tool, 'description', '') or getattr(tool, '__doc__', '') or ''

            factory = MCPClientFactory()
            if factory.is_local():
                location = ToolLocation.LOCAL
            elif factory.is_cloud():
                location = ToolLocation.CLOUD
            else:
                location = ToolLocation.MCP

            tools.append(ToolInfo(
                name=tool_name,
                description=description[:200] if description else '',
                location=location,
                parameters={},
                tags=[specialty.lower()],
                category=specialty.lower(),
                is_async=True,
                enabled=True
            ))

        return tools

    def _register_to_discovery(
        self,
        agent_id: str,
        agent_name: str,
        agent_type: AgentType,
        specialty: str,
        description: str,
        tool_manager
    ) -> None:
        """注册 Agent 到发现注册中心"""
        tools = self._convert_tool_manager_tools(tool_manager, specialty)

        agent_info = AgentInfo(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_type=agent_type,
            description=description,
            specialty=specialty,
            tools=tools,
            capabilities=[specialty],
            enabled=True
        )

        agent_discovery_registry.register_agent(agent_info)
    
    async def initialize(self) -> None:
        """初始化所有 Agent"""
        logger.info("🚀 A2A 协议初始化")
        
        await self._register_tax_specialist()
        await self._register_finance_specialist()
        await self._register_legal_specialist()
        await self._register_react_agent()
        
        self.dispatcher = HybridDispatcher(
            registry=self.registry,
            strategy=DispatchStrategy.LOCAL_FIRST
        )
        
        logger.info(f"✅ A2A 初始化完成: {list(self.wrappers.keys())}")
    
    async def _register_tax_specialist(self) -> None:
        """注册税务专家"""
        try:
            import logging
            logging.getLogger('app.agent_framework.llm.factory').setLevel(logging.WARNING)
            logging.getLogger('app.agent_framework.tools.tool_manager').setLevel(logging.WARNING)
            logging.getLogger('app.multi_agent_system.agents.tax_specialist').setLevel(logging.WARNING)
            logging.getLogger('app.a2a_protocol.server').setLevel(logging.WARNING)
            logging.getLogger('app.a2a_protocol.wrapper').setLevel(logging.WARNING)
            logging.getLogger('app.a2a_protocol.registry').setLevel(logging.WARNING)
            logging.getLogger('app.services.agent_registry').setLevel(logging.WARNING)
            
            from app.multi_agent_system.agents import TaxSpecialist
            from app.agent_framework.tools.tool_manager import ToolManager
            from app.agent_framework.llm.factory import LLMAdapterFactory
            from app.core.config import settings

            llm = LLMAdapterFactory.create_adapter(settings.LLM_PROVIDER)
            tool_manager = ToolManager()
            agent = TaxSpecialist(llm_adapter=llm, tool_manager=tool_manager)

            wrapper = wrap_tax_specialist(agent, self.base_url)
            await wrapper.register()
            self.wrappers["tax_specialist"] = wrapper

            self._register_to_discovery(
                agent_id="tax_specialist",
                agent_name="税务专家",
                agent_type=AgentType.SPECIALIST,
                specialty="税务",
                description="专业处理税务相关问题的智能体",
                tool_manager=tool_manager
            )

            logger.info("   ✅ tax_specialist")
        except (ValueError, KeyError) as e:
            logger.warning(f"   ⚠️ tax_specialist 跳过数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"   ⚠️ tax_specialist 跳过IO错误: {e}")
        except Exception as e:
            logger.warning(f"   ⚠️ tax_specialist 跳过: {e}")
    
    async def _register_finance_specialist(self) -> None:
        """注册财务专家"""
        try:
            import logging
            logging.getLogger('app.agent_framework.llm.factory').setLevel(logging.WARNING)
            logging.getLogger('app.agent_framework.tools.tool_manager').setLevel(logging.WARNING)
            logging.getLogger('app.multi_agent_system.agents.finance_specialist').setLevel(logging.WARNING)
            logging.getLogger('app.a2a_protocol.server').setLevel(logging.WARNING)
            logging.getLogger('app.a2a_protocol.wrapper').setLevel(logging.WARNING)
            logging.getLogger('app.a2a_protocol.registry').setLevel(logging.WARNING)
            logging.getLogger('app.services.agent_registry').setLevel(logging.WARNING)
            
            from app.multi_agent_system.agents import FinanceSpecialist
            from app.agent_framework.tools.tool_manager import ToolManager
            from app.agent_framework.llm.factory import LLMAdapterFactory
            from app.core.config import settings

            llm = LLMAdapterFactory.create_adapter(settings.LLM_PROVIDER)
            tool_manager = ToolManager()
            agent = FinanceSpecialist(llm_adapter=llm, tool_manager=tool_manager)

            wrapper = wrap_finance_specialist(agent, self.base_url)
            await wrapper.register()
            self.wrappers["finance_specialist"] = wrapper

            self._register_to_discovery(
                agent_id="finance_specialist",
                agent_name="财务专家",
                agent_type=AgentType.SPECIALIST,
                specialty="财务",
                description="专业处理财务相关问题的智能体",
                tool_manager=tool_manager
            )

            logger.info("   ✅ finance_specialist")
        except (ValueError, KeyError) as e:
            logger.warning(f"   ⚠️ finance_specialist 跳过数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"   ⚠️ finance_specialist 跳过IO错误: {e}")
        except Exception as e:
            logger.warning(f"   ⚠️ finance_specialist 跳过: {e}")
    
    async def _register_legal_specialist(self) -> None:
        """注册法律专家"""
        try:
            import logging
            logging.getLogger('app.agent_framework.llm.factory').setLevel(logging.WARNING)
            logging.getLogger('app.agent_framework.tools.tool_manager').setLevel(logging.WARNING)
            logging.getLogger('app.multi_agent_system.agents.legal_specialist').setLevel(logging.WARNING)
            logging.getLogger('app.a2a_protocol.server').setLevel(logging.WARNING)
            logging.getLogger('app.a2a_protocol.wrapper').setLevel(logging.WARNING)
            logging.getLogger('app.a2a_protocol.registry').setLevel(logging.WARNING)
            logging.getLogger('app.services.agent_registry').setLevel(logging.WARNING)
            
            from app.multi_agent_system.agents import LegalSpecialist
            from app.agent_framework.tools.tool_manager import ToolManager
            from app.agent_framework.llm.factory import LLMAdapterFactory
            from app.core.config import settings

            llm = LLMAdapterFactory.create_adapter(settings.LLM_PROVIDER)
            tool_manager = ToolManager()
            agent = LegalSpecialist(llm_adapter=llm, tool_manager=tool_manager)

            wrapper = wrap_legal_specialist(agent, self.base_url)
            await wrapper.register()
            self.wrappers["legal_specialist"] = wrapper

            self._register_to_discovery(
                agent_id="legal_specialist",
                agent_name="法律专家",
                agent_type=AgentType.SPECIALIST,
                specialty="法律",
                description="专业处理法律相关问题的智能体",
                tool_manager=tool_manager
            )

            logger.info("   ✅ legal_specialist")
        except (ValueError, KeyError) as e:
            logger.warning(f"   ⚠️ legal_specialist 跳过数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"   ⚠️ legal_specialist 跳过IO错误: {e}")
        except Exception as e:
            logger.warning(f"   ⚠️ legal_specialist 跳过: {e}")
    
    async def _register_react_agent(self) -> None:
        """注册 ReAct 通用 Agent"""
        try:
            import logging
            logging.getLogger('app.agent_framework.llm.factory').setLevel(logging.WARNING)
            logging.getLogger('app.agent_framework.tools.tool_manager').setLevel(logging.WARNING)
            logging.getLogger('app.agent_framework.core.react_agent').setLevel(logging.WARNING)
            logging.getLogger('app.a2a_protocol.server').setLevel(logging.WARNING)
            logging.getLogger('app.a2a_protocol.wrapper').setLevel(logging.WARNING)
            logging.getLogger('app.a2a_protocol.registry').setLevel(logging.WARNING)
            logging.getLogger('app.services.agent_registry').setLevel(logging.WARNING)
            
            from app.agent_framework.core.react_agent import ReActAgent
            from app.agent_framework.tools.tool_manager import ToolManager
            from app.agent_framework.llm.factory import LLMAdapterFactory
            from app.core.config import settings

            llm_adapter = LLMAdapterFactory.create_adapter(settings.LLM_PROVIDER)
            tool_manager = ToolManager()
            agent = ReActAgent(llm_adapter=llm_adapter, tool_manager=tool_manager)

            wrapper = wrap_react_agent(agent, self.base_url)
            await wrapper.register()
            self.wrappers["react_agent"] = wrapper

            self._register_to_discovery(
                agent_id="react_agent",
                agent_name="ReAct 通用智能体",
                agent_type=AgentType.GENERAL,
                specialty="通用",
                description="基于 ReAct 推理模式的通用智能体",
                tool_manager=tool_manager
            )

            logger.info("   ✅ react_agent")
        except (ValueError, KeyError) as e:
            logger.warning(f"   ⚠️ react_agent 跳过数据错误: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"   ⚠️ react_agent 跳过IO错误: {e}")
        except Exception as e:
            logger.warning(f"   ⚠️ react_agent 跳过: {e}")
    
    def get_dispatcher(self) -> HybridDispatcher:
        """获取调度器"""
        if not self.dispatcher:
            self.dispatcher = HybridDispatcher(registry=self.registry)
        return self.dispatcher
    
    def get_registry(self) -> AgentRegistry:
        """获取注册中心"""
        return self.registry


a2a_initializer: Optional[A2AInitializer] = None


async def initialize_a2a_protocol(base_url: str = "http://localhost:8000") -> tuple[A2AInitializer, AgentRegistry]:
    """初始化 A2A 协议，返回初始化器和注册中心"""
    global a2a_initializer
    a2a_initializer = A2AInitializer(base_url)
    await a2a_initializer.initialize()
    return a2a_initializer, a2a_initializer.registry


def get_a2a_initializer() -> Optional[A2AInitializer]:
    """获取初始化器"""
    return a2a_initializer
