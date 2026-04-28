"""
Agent 注册中心

集中管理所有 Agent 及其工具信息
支持追踪功能扩展
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ToolLocation(str, Enum):
    """工具位置类型"""
    LOCAL = "local"
    CLOUD = "cloud"
    MCP = "mcp"


class AgentType(str, Enum):
    """Agent 类型"""
    SPECIALIST = "specialist"
    GENERAL = "general"
    ROUTER = "router"
    UTILITY = "utility"


@dataclass
class ToolInfo:
    """工具信息"""
    name: str
    description: str
    location: ToolLocation
    parameters: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    category: str = "general"
    is_async: bool = True
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentInfo:
    """Agent 信息"""
    agent_id: str
    agent_name: str
    agent_type: AgentType
    description: str
    specialty: Optional[str] = None
    tools: List[ToolInfo] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_local_tools(self) -> List[ToolInfo]:
        """获取本地工具"""
        return [t for t in self.tools if t.location == ToolLocation.LOCAL]

    def get_cloud_tools(self) -> List[ToolInfo]:
        """获取云端工具"""
        return [t for t in self.tools if t.location == ToolLocation.CLOUD]

    def get_mcp_tools(self) -> List[ToolInfo]:
        """获取 MCP 工具"""
        return [t for t in self.tools if t.location == ToolLocation.MCP]

    def get_tool_count_summary(self) -> Dict[str, int]:
        """获取工具数量统计"""
        return {
            "total": len(self.tools),
            "local": len(self.get_local_tools()),
            "cloud": len(self.get_cloud_tools()),
            "mcp": len(self.get_mcp_tools())
        }


class AgentDiscoveryRegistry:
    """
    Agent 发现注册中心

    负责注册、发现和管理所有 Agent 及其工具
    与 A2A 协议的 AgentRegistry 不同，专注于 Agent 发现和工具分类
    """

    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}
        self._tool_index: Dict[str, str] = {}  # tool_name -> agent_id
        logger.info("📋 Agent Discovery 注册中心初始化完成")

    def register_agent(self, agent_info: AgentInfo) -> None:
        """
        注册 Agent

        Args:
            agent_info: Agent 信息
        """
        self._agents[agent_info.agent_id] = agent_info

        for tool in agent_info.tools:
            self._tool_index[tool.name] = agent_info.agent_id

        logger.info(f"✅ 注册 Agent: {agent_info.agent_name} ({agent_info.agent_id})")
        logger.info(f"   工具数量: {len(agent_info.tools)} (本地:{len(agent_info.get_local_tools())}, 云端:{len(agent_info.get_cloud_tools())}, MCP:{len(agent_info.get_mcp_tools())})")

    def unregister_agent(self, agent_id: str) -> bool:
        """
        注销 Agent

        Args:
            agent_id: Agent ID

        Returns:
            是否成功注销
        """
        if agent_id not in self._agents:
            return False

        agent_info = self._agents[agent_id]
        for tool in agent_info.tools:
            self._tool_index.pop(tool.name, None)

        del self._agents[agent_id]
        logger.info(f"🗑️ 注销 Agent: {agent_id}")
        return True

    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """
        获取 Agent 信息

        Args:
            agent_id: Agent ID

        Returns:
            Agent 信息，如果不存在返回 None
        """
        return self._agents.get(agent_id)

    def get_agent_by_tool(self, tool_name: str) -> Optional[AgentInfo]:
        """
        根据工具名称查找 Agent

        Args:
            tool_name: 工具名称

        Returns:
            Agent 信息
        """
        agent_id = self._tool_index.get(tool_name)
        if agent_id:
            return self._agents.get(agent_id)
        return None

    def list_agents(
        self,
        agent_type: Optional[AgentType] = None,
        enabled_only: bool = True
    ) -> List[AgentInfo]:
        """
        列出所有 Agent

        Args:
            agent_type: Agent 类型过滤
            enabled_only: 仅返回启用的 Agent

        Returns:
            Agent 信息列表
        """
        agents = list(self._agents.values())

        if agent_type:
            agents = [a for a in agents if a.agent_type == agent_type]

        if enabled_only:
            agents = [a for a in agents if a.enabled]

        return agents

    def list_all_tools(
        self,
        location: Optional[ToolLocation] = None,
        enabled_only: bool = True
    ) -> List[ToolInfo]:
        """
        列出所有工具

        Args:
            location: 工具位置过滤
            enabled_only: 仅返回启用的工具

        Returns:
            工具信息列表
        """
        tools = []
        for agent in self._agents.values():
            tools.extend(agent.tools)

        if location:
            tools = [t for t in tools if t.location == location]

        if enabled_only:
            tools = [t for t in tools if t.enabled]

        return tools

    def get_summary(self) -> Dict[str, Any]:
        """
        获取注册中心摘要

        Returns:
            摘要信息
        """
        total_agents = len(self._agents)
        enabled_agents = len([a for a in self._agents.values() if a.enabled])

        total_tools = sum(len(a.tools) for a in self._agents.values())
        local_tools = sum(len(a.get_local_tools()) for a in self._agents.values())
        cloud_tools = sum(len(a.get_cloud_tools()) for a in self._agents.values())
        mcp_tools = sum(len(a.get_mcp_tools()) for a in self._agents.values())

        return {
            "total_agents": total_agents,
            "enabled_agents": enabled_agents,
            "total_tools": total_tools,
            "tool_breakdown": {
                "local": local_tools,
                "cloud": cloud_tools,
                "mcp": mcp_tools
            },
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "agent_name": a.agent_name,
                    "agent_type": a.agent_type.value,
                    "specialty": a.specialty,
                    "tool_count": len(a.tools),
                    "tool_summary": a.get_tool_count_summary(),
                    "enabled": a.enabled
                }
                for a in self._agents.values()
            ]
        }

    def add_tool_to_agent(
        self,
        agent_id: str,
        tool_info: ToolInfo
    ) -> bool:
        """
        为 Agent 添加工具

        Args:
            agent_id: Agent ID
            tool_info: 工具信息

        Returns:
            是否成功添加
        """
        agent = self.get_agent(agent_id)
        if not agent:
            logger.warning(f"尝试为不存在的 Agent 添加工具: {agent_id}")
            return False

        agent.tools.append(tool_info)
        self._tool_index[tool_info.name] = agent_id
        agent.last_updated = datetime.now()
        return True

    def remove_tool_from_agent(
        self,
        agent_id: str,
        tool_name: str
    ) -> bool:
        """
        从 Agent 移除工具

        Args:
            agent_id: Agent ID
            tool_name: 工具名称

        Returns:
            是否成功移除
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return False

        tool = next((t for t in agent.tools if t.name == tool_name), None)
        if not tool:
            return False

        agent.tools.remove(tool)
        self._tool_index.pop(tool_name, None)
        agent.last_updated = datetime.now()
        return True

    def enable_agent(self, agent_id: str, enabled: bool = True) -> bool:
        """
        启用/禁用 Agent

        Args:
            agent_id: Agent ID
            enabled: 是否启用

        Returns:
            是否成功
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return False

        agent.enabled = enabled
        agent.last_updated = datetime.now()
        return True


agent_discovery_registry = AgentDiscoveryRegistry()
