"""
Agent Wrapper

将现有 Agent 包装为 A2A 兼容的 Agent
支持现有 BaseAgent 和专业 Agent 的透明转换
"""

import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass

from .agent_card import AgentCard, AgentCardBuilder, AgentSkill
from .server import A2AServer
from .models import Task, Message, TextPart
from .registry import AgentRegistry

logger = logging.getLogger(__name__)


@dataclass
class AgentWrapperConfig:
    """Agent 包装配置"""
    name: str
    description: str
    url: str
    skills: List[Dict[str, str]]
    version: str = "1.0.0"
    streaming: bool = False
    tags: List[str] = None


class AgentWrapper:
    """
    Agent 包装器
    
    将现有 Agent 转换为 A2A 兼容格式
    支持两种调用方式：
    1. run() - 同步返回结果
    2. run_async() - 异步处理任务
    """
    
    def __init__(
        self,
        agent_instance: Any,
        config: AgentWrapperConfig,
        registry: AgentRegistry = None
    ):
        self.agent = agent_instance
        self.config = config
        self.registry = registry or AgentRegistry.get_instance()
        
        if hasattr(self.agent, "llm") and not hasattr(self.agent, "llm_adapter"):
            self.agent.llm_adapter = self.agent.llm
            logger.info(f"🔧 设置 llm_adapter 别名: {config.name}")
        
        self.agent_card = self._build_agent_card()
        self.a2a_server = A2AServer(self.agent_card)
        
        self.a2a_server.set_task_handler(self._create_task_handler())
        
        logger.info(f"🔧 Agent 包装完成: {config.name}")
    
    def _build_agent_card(self) -> AgentCard:
        """构建 Agent Card"""
        builder = AgentCardBuilder(
            name=self.config.name,
            description=self.config.description,
            url=self.config.url
        )
        
        builder.with_version(self.config.version)
        
        builder.with_capabilities(
            streaming=self.config.streaming,
            state_transition_reports=True,
            artifact_updates=True
        )
        
        for skill_config in self.config.skills:
            builder.with_skill(
                skill_id=skill_config["id"],
                name=skill_config["name"],
                description=skill_config["description"]
            )
        
        if self.config.tags:
            builder.with_tags(self.config.tags)
        
        return builder.build()
    
    def _create_task_handler(self) -> Callable:
        """创建任务处理器"""
        async def handle_task(task: Task) -> Task:
            user_message = self._extract_user_message(task)
            
            if hasattr(self.agent, "run"):
                result = await self._call_agent(user_message, task)
            elif hasattr(self.agent, "process"):
                result = await self.agent.process(user_message)
            else:
                result = f"Agent {self.config.name} 不支持标准调用方法"
            
            task.add_message(role="agent", content=str(result))
            task.metadata["result"] = result
            
            return task
        
        return handle_task
    
    async def _call_agent(
        self,
        message: str,
        task: Task
    ) -> str:
        """调用 Agent"""
        try:
            logger.info(f"🔍 [AgentWrapper] 收到消息: '{message}', 类型: {type(message)}")
            
            if hasattr(self.agent, "llm") and not hasattr(self.agent, "llm_adapter"):
                self.agent.llm_adapter = self.agent.llm
            
            metadata = {
                "task_id": task.id,
                "session_id": task.sessionId,
                "tenant_id": task.metadata.get("tenant_id")
            }
            
            logger.info(f"🔍 [AgentWrapper] 元数据: {metadata}")
            
            if hasattr(self.agent, "run"):
                if hasattr(self.agent, "run_async"):
                    result = await self.agent.run_async(message, **metadata)
                else:
                    result = await self.agent.run(message, metadata=metadata)
            elif hasattr(self.agent, "process"):
                result = await self.agent.process(message)
            else:
                result = await self.agent(message)
            
            return result
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ Agent 调用数据失败: {self.config.name} - {e}")
            return f"处理失败: {str(e)}"
        except (OSError, IOError) as e:
            logger.error(f"❌ Agent 调用IO失败: {self.config.name} - {e}")
            return f"处理失败: {str(e)}"
        except Exception as e:
            logger.error(f"❌ Agent 调用失败: {self.config.name} - {e}")
            return f"处理失败: {str(e)}"
    
    def _extract_user_message(self, task: Task) -> str:
        """从任务中提取用户消息"""
        messages = [m for m in task.messages if m.role == "user"]
        if messages:
            message = messages[0]
            parts_text = []
            for part in message.parts:
                if isinstance(part, TextPart):
                    parts_text.append(part.text)
            return "\n".join(parts_text) if parts_text else ""
        return ""
    
    def get_a2a_server(self) -> A2AServer:
        """获取 A2A Server"""
        return self.a2a_server
    
    def get_agent_card(self) -> AgentCard:
        """获取 Agent Card"""
        return self.agent_card
    
    async def register(self) -> None:
        """向注册中心注册"""
        if self.registry:
            await self.registry.register_local_agent(
                name=self.config.name,
                card=self.agent_card,
                instance=self.agent
            )
            logger.info(f"✅ Agent 已注册: {self.config.name}")
    
    async def unregister(self) -> None:
        """从注册中心注销"""
        if self.registry:
            agent = self.registry.get_agent(self.config.name)
            if agent:
                logger.info(f"🗑️ Agent 已注销: {self.config.name}")


def wrap_tax_specialist(
    agent_instance: Any,
    base_url: str = "http://localhost:8000"
) -> AgentWrapper:
    """包装税务专家 Agent"""
    config = AgentWrapperConfig(
        name="tax_specialist",
        description="专业税务分析智能体，支持税务计算、合规审查、政策解读",
        url=f"{base_url}/a2a/tax_specialist",
        skills=[
            {"id": "tax_calculation", "name": "税务计算", "description": "计算各类税费"},
            {"id": "tax_compliance", "name": "税务合规", "description": "税务合规性审查"},
            {"id": "tax_policy", "name": "税务政策", "description": "税收优惠政策解读"}
        ],
        tags=["税务", "财务", "合规"]
    )
    return AgentWrapper(agent_instance, config)


def wrap_finance_specialist(
    agent_instance: Any,
    base_url: str = "http://localhost:8000"
) -> AgentWrapper:
    """包装财务专家 Agent"""
    config = AgentWrapperConfig(
        name="finance_specialist",
        description="专业财务分析智能体，支持财务报表分析、财务指标计算",
        url=f"{base_url}/a2a/finance_specialist",
        skills=[
            {"id": "financial_analysis", "name": "财务分析", "description": "财务报表和指标分析"},
            {"id": "ratio_calculation", "name": "比率计算", "description": "财务比率计算"}
        ],
        tags=["财务", "分析"]
    )
    return AgentWrapper(agent_instance, config)


def wrap_legal_specialist(
    agent_instance: Any,
    base_url: str = "http://localhost:8000"
) -> AgentWrapper:
    """包装法律专家 Agent"""
    config = AgentWrapperConfig(
        name="legal_specialist",
        description="专业法律合规智能体，支持合同审查、法规咨询",
        url=f"{base_url}/a2a/legal_specialist",
        skills=[
            {"id": "contract_review", "name": "合同审查", "description": "合同风险点识别"},
            {"id": "legal_advice", "name": "法律咨询", "description": "法规解读和建议"}
        ],
        tags=["法律", "合规", "合同"]
    )
    return AgentWrapper(agent_instance, config)


def wrap_react_agent(
    agent_instance: Any,
    base_url: str = "http://localhost:8000"
) -> AgentWrapper:
    """包装 ReAct 通用 Agent"""
    config = AgentWrapperConfig(
        name="react_agent",
        description="通用问答智能体，基于 ReAct 模式支持多轮对话和工具调用",
        url=f"{base_url}/a2a/react_agent",
        skills=[
            {"id": "general_qa", "name": "通用问答", "description": "通用问题回答"},
            {"id": "tool_execution", "name": "工具执行", "description": "调用各类工具完成任务"}
        ],
        streaming=True,
        tags=["通用", "问答", "工具"]
    )
    return AgentWrapper(agent_instance, config)
