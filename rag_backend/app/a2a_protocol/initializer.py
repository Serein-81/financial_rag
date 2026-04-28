"""
A2A 协议初始化模块

将现有 Agent 集成到 A2A 协议
"""

import logging
from typing import Optional, List

from .registry import AgentRegistry, agent_registry
from .wrapper import (
    AgentWrapper,
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
        from app.agent_framework.tools.tool_router import TOOL_ROUTING_CONFIG, ToolCategory

        tools = []
        for tool_name, tool in tool_manager.tools.items():
            config = TOOL_ROUTING_CONFIG.get(tool_name, {})
            
            description = config.get('description', '') or getattr(tool, 'description', '') or getattr(tool, '__doc__', '') or ''
            category = config.get('category', ToolCategory.LOCAL)

            if category == ToolCategory.LOCAL:
                location = ToolLocation.LOCAL
            elif category == ToolCategory.MCP:
                location = ToolLocation.MCP
            else:
                location = ToolLocation.MCP

            tool_category = self._infer_tool_category(tool_name, description, specialty)

            tools.append(ToolInfo(
                name=tool_name,
                description=description[:200] if description else '',
                location=location,
                parameters={},
                tags=[specialty.lower()],
                category=tool_category,
                is_async=True,
                enabled=True
            ))

        return tools

    def _infer_tool_category(self, tool_name: str, description: str, specialty: str) -> str:
        """从工具名称和描述推断工具类别"""
        tool_name_lower = tool_name.lower()
        desc_lower = description.lower()
        
        if 'search_web' in tool_name_lower or '网络搜索' in desc_lower or 'web' in tool_name_lower and 'search' in tool_name_lower:
            return '搜索'
        elif ('enterprise' in tool_name_lower or '企业信息' in desc_lower or '企业' in desc_lower) and ('assess' in tool_name_lower or 'risk' in tool_name_lower or '风险' in desc_lower):
            return '企业信息'
        elif 'calculate_tax' in tool_name_lower or '税务' in desc_lower or '增值税' in desc_lower or '所得税' in desc_lower or 'tax' in tool_name_lower:
            return '税务'
        elif 'finance' in tool_name_lower or '财务' in desc_lower or 'asset' in tool_name_lower or 'liability' in tool_name_lower or 'profit' in tool_name_lower or 'revenue' in tool_name_lower:
            return '财务'
        elif 'legal' in tool_name_lower or '法律' in desc_lower or 'contract' in tool_name_lower or 'provision' in desc_lower or '条款' in desc_lower:
            return '法律'
        elif 'knowledge' in tool_name_lower or '知识' in desc_lower or 'document' in tool_name_lower or '文档' in desc_lower:
            return '知识库'
        elif 'weather' in tool_name_lower or '天气' in desc_lower or 'location' in tool_name_lower or '位置' in desc_lower:
            return '生活服务'
        else:
            return specialty.lower()

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
        from app.agent_framework.tools.agent_tool_registry import get_specialist_tools_config

        specialist_config = get_specialist_tools_config(specialty.lower())
        allowed_mcp_tools = set(specialist_config.get("mcp_tools", []))
        allowed_local_tools = set(specialist_config.get("local_tools", []))
        allow_all_mcp_tools = "*" in allowed_mcp_tools
        allow_all_local_tools = "*" in allowed_local_tools

        logger.debug(f"   [DEBUG] {agent_name} allowed MCP tools: {allowed_mcp_tools}")
        logger.debug(f"   [DEBUG] {agent_name} allowed local tools: {allowed_local_tools}")

        all_tools = self._convert_tool_manager_tools(tool_manager, specialty)
        logger.debug(f"   [DEBUG] {agent_name} total tools: {len(all_tools)}")

        tools = []
        for tool in all_tools:
            if tool.location in (ToolLocation.CLOUD, ToolLocation.MCP):
                if allow_all_mcp_tools or tool.name in allowed_mcp_tools:
                    tools.append(tool)
                    logger.debug(f"   [ADD] {tool.location.value.upper()} tool: {tool.name}")
                else:
                    logger.debug(f"   [SKIP] {tool.location.value.upper()} tool (not in config): {tool.name}")
            elif tool.location == ToolLocation.LOCAL:
                if allow_all_local_tools or tool.name in allowed_local_tools or tool.name in allowed_mcp_tools:
                    tools.append(tool)
                    logger.debug(f"   [ADD] local tool: {tool.name}")
                else:
                    logger.debug(f"   [SKIP] local tool (not in config): {tool.name}")

        logger.info(f"   [INFO] {agent_name} assigned {len(tools)} tools (MCP: {len([t for t in tools if t.location == ToolLocation.MCP])}, CLOUD: {len([t for t in tools if t.location == ToolLocation.CLOUD])}, local: {len([t for t in tools if t.location == ToolLocation.LOCAL])})")

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

    async def _register_wrapper_safely(self, wrapper: AgentWrapper, agent_id: str) -> None:
        """Register an A2A wrapper without letting console encoding errors skip discovery."""
        try:
            await wrapper.register()
        except UnicodeEncodeError as e:
            logger.warning(
                "[WARN] A2A wrapper registered with logging encoding issue: %s - %s",
                agent_id,
                e,
            )
        except Exception as e:
            logger.warning(
                "[WARN] A2A wrapper registration skipped for discovery continuity: %s - %s: %s",
                agent_id,
                type(e).__name__,
                e,
            )
    
    async def initialize(self) -> None:
        """初始化所有 Agent"""
        logger.info("[INIT] Starting A2A protocol initialization")
        
        await self._register_tax_specialist()
        await self._register_finance_specialist()
        await self._register_legal_specialist()
        await self._register_react_agent()
        
        self.dispatcher = HybridDispatcher(
            registry=self.registry,
            strategy=DispatchStrategy.LOCAL_FIRST
        )
        
        logger.info(f"[OK] A2A initialized: {list(self.wrappers.keys())}")
    
    async def _register_tax_specialist(self) -> None:
        """注册税务专家"""
        logger.info("[START] _register_tax_specialist")
        try:
            logger.info("[STEP1] Creating LLM adapter")
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
            from app.agent_framework.tools.agent_tool_registry import initialize_tool_manager
            from app.agent_framework.llm.factory import LLMAdapterFactory
            from app.core.config import settings

            llm = LLMAdapterFactory.create_adapter(settings.LLM_PROVIDER)
            tool_manager = ToolManager()
            
            tool_reg_result = await initialize_tool_manager(tool_manager)
            logger.info(f"   [TOOL] tax_specialist registered {tool_reg_result['total_count']} tools")
            
            agent = TaxSpecialist(llm_adapter=llm, tool_manager=tool_manager)

            wrapper = wrap_tax_specialist(agent, self.base_url)
            await self._register_wrapper_safely(wrapper, "tax_specialist")
            self.wrappers["tax_specialist"] = wrapper

            self._register_to_discovery(
                agent_id="tax_specialist",
                agent_name="税务专家",
                agent_type=AgentType.SPECIALIST,
                specialty="税务",
                description="专业处理税务相关问题的智能体",
                tool_manager=tool_manager
            )

            logger.info("   [OK] tax_specialist registered")
        except (ValueError, KeyError, UnicodeEncodeError) as e:
             logger.warning(f"   [WARN] tax_specialist step1 failed: {type(e).__name__}: {e}")
        except (OSError, IOError) as e:
             logger.warning(f"   [WARN] tax_specialist step2 failed: {type(e).__name__}: {e}")
        except Exception as e:
             logger.warning(f"   [WARN] tax_specialist step3 failed: {type(e).__name__}: {e}")
    
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
            from app.agent_framework.tools.agent_tool_registry import initialize_tool_manager
            from app.agent_framework.llm.factory import LLMAdapterFactory
            from app.core.config import settings

            llm = LLMAdapterFactory.create_adapter(settings.LLM_PROVIDER)
            tool_manager = ToolManager()
            
            tool_reg_result = await initialize_tool_manager(tool_manager)
            logger.info(f"   [TOOL] finance_specialist registered {tool_reg_result['total_count']} tools")
            
            agent = FinanceSpecialist(llm_adapter=llm, tool_manager=tool_manager)

            wrapper = wrap_finance_specialist(agent, self.base_url)
            await self._register_wrapper_safely(wrapper, "finance_specialist")
            self.wrappers["finance_specialist"] = wrapper

            self._register_to_discovery(
                agent_id="finance_specialist",
                agent_name="财务专家",
                agent_type=AgentType.SPECIALIST,
                specialty="财务",
                description="专业处理财务相关问题的智能体",
                tool_manager=tool_manager
            )

            logger.info("   [OK] finance_specialist registered")
        except (ValueError, KeyError, UnicodeEncodeError) as e:
            logger.warning(f"   [WARN] finance_specialist skipped due to encoding/data error: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"   [WARN] finance_specialist skipped due to IO error: {e}")
        except Exception as e:
            logger.warning(f"   [WARN] finance_specialist skipped: {e}")
    
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
            from app.agent_framework.tools.agent_tool_registry import initialize_tool_manager
            from app.agent_framework.llm.factory import LLMAdapterFactory
            from app.core.config import settings

            llm = LLMAdapterFactory.create_adapter(settings.LLM_PROVIDER)
            tool_manager = ToolManager()
            
            tool_reg_result = await initialize_tool_manager(tool_manager)
            logger.info(f"   [TOOL] legal_specialist registered {tool_reg_result['total_count']} tools")
            
            agent = LegalSpecialist(llm_adapter=llm, tool_manager=tool_manager)

            wrapper = wrap_legal_specialist(agent, self.base_url)
            await self._register_wrapper_safely(wrapper, "legal_specialist")
            self.wrappers["legal_specialist"] = wrapper

            self._register_to_discovery(
                agent_id="legal_specialist",
                agent_name="法律专家",
                agent_type=AgentType.SPECIALIST,
                specialty="法律",
                description="专业处理法律相关问题的智能体",
                tool_manager=tool_manager
            )

            logger.info("   [OK] legal_specialist registered")
        except (ValueError, KeyError, UnicodeEncodeError) as e:
            logger.warning(f"   [WARN] legal_specialist skipped due to encoding/data error: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"   [WARN] legal_specialist skipped due to IO error: {e}")
        except Exception as e:
            logger.warning(f"   [WARN] legal_specialist skipped: {e}")
    
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
            from app.agent_framework.tools.agent_tool_registry import initialize_tool_manager
            from app.agent_framework.llm.factory import LLMAdapterFactory
            from app.core.config import settings

            llm_adapter = LLMAdapterFactory.create_adapter(settings.LLM_PROVIDER)
            tool_manager = ToolManager()
            
            tool_reg_result = await initialize_tool_manager(tool_manager)
            logger.info(f"   [TOOL] react_agent registered {tool_reg_result['total_count']} tools")
            
            agent = ReActAgent(llm_adapter=llm_adapter, tool_manager=tool_manager)

            wrapper = wrap_react_agent(agent, self.base_url)
            await self._register_wrapper_safely(wrapper, "react_agent")
            self.wrappers["react_agent"] = wrapper

            self._register_to_discovery(
                agent_id="react_agent",
                agent_name="ReAct 通用智能体",
                agent_type=AgentType.GENERAL,
                specialty="通用",
                description="基于 ReAct 推理模式的通用智能体",
                tool_manager=tool_manager
            )

            logger.info("   [OK] react_agent registered")
        except (ValueError, KeyError) as e:
            logger.warning(f"   [WARN] react_agent skipped due to data error: {e}")
        except (OSError, IOError) as e:
            logger.warning(f"   [WARN] react_agent skipped due to IO error: {e}")
        except Exception as e:
            logger.warning(f"   [WARN] react_agent skipped: {e}")
    
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
