"""
Agent Registry

Agent 注册中心
负责 Agent Card 的注册、发现和管理
支持本地 Agent 和远程 Agent 的统一管理
"""

import httpx
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio

from .agent_card import AgentCard, AgentSkill
from .models import Task, TaskStatus, TaskSubmitParams, Message

logger = logging.getLogger(__name__)


class AgentType(str, Enum):
    """Agent 类型"""
    LOCAL = "local"
    REMOTE = "remote"


@dataclass
class AgentRegistration:
    """Agent 注册信息"""
    card: AgentCard
    agent_type: AgentType
    instance: Any = None
    registered_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    health_status: str = "healthy"


class AgentRegistry:
    """
    Agent 注册中心
    
    功能：
    1. 本地 Agent 注册
    2. 远程 Agent 发现
    3. 能力匹配查询
    4. Agent 健康检查
    """
    
    _instance: Optional["AgentRegistry"] = None
    
    @classmethod
    def get_instance(cls) -> "AgentRegistry":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = AgentRegistry()
        return cls._instance
    
    def __init__(self):
        self._agents: Dict[str, AgentRegistration] = {}
        self._skill_index: Dict[str, List[str]] = {}
        self._remote_discovery_urls: List[str] = []
        self._lock = asyncio.Lock()
        logger.info("📋 Agent Registry 初始化完成")
    
    async def register_local_agent(
        self,
        name: str,
        card: AgentCard,
        instance: Any
    ) -> None:
        """
        注册本地 Agent
        
        Args:
            name: Agent 名称
            card: Agent Card
            instance: Agent 实例
        """
        async with self._lock:
            registration = AgentRegistration(
                card=card,
                agent_type=AgentType.LOCAL,
                instance=instance
            )
            self._agents[name] = registration
            
            for skill in card.skills:
                if skill.id not in self._skill_index:
                    self._skill_index[skill.id] = []
                self._skill_index[skill.id].append(name)
            
            logger.info(f"✅ 本地 Agent 注册: {name}")
    
    async def register_remote_agent(self, card: AgentCard) -> None:
        """
        注册远程 Agent
        
        Args:
            card: 远程 Agent Card
        """
        async with self._lock:
            registration = AgentRegistration(
                card=card,
                agent_type=AgentType.REMOTE
            )
            self._agents[card.name] = registration
            
            for skill in card.skills:
                if skill.id not in self._skill_index:
                    self._skill_index[skill.id] = []
                self._skill_index[skill.id].append(card.name)
            
            logger.info(f"🌐 远程 Agent 注册: {card.name}")
    
    async def discover_remote_agents(self, discovery_url: str) -> int:
        """
        从远程端点发现 Agent
        
        Args:
            discovery_url: Agent Card 发现端点
            
        Returns:
            发现的 Agent 数量
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{discovery_url}/.well-known/agent.json")
                if response.status_code == 200:
                    card = AgentCard(**response.json())
                    await self.register_remote_agent(card)
                    return 1
        except (ValueError, KeyError) as e:
            logger.warning(f"⚠️ 发现远程 Agent 数据失败: {discovery_url} - {e}")
        except (OSError, IOError) as e:
            logger.warning(f"⚠️ 发现远程 Agent IO失败: {discovery_url} - {e}")
        except Exception as e:
            logger.warning(f"⚠️ 发现远程 Agent 失败: {discovery_url} - {e}")
        return 0
    
    def get_agent(self, name: str) -> Optional[AgentRegistration]:
        """获取 Agent 注册信息"""
        return self._agents.get(name)
    
    def get_agent_instance(self, name: str) -> Optional[Any]:
        """获取 Agent 实例（仅本地）"""
        reg = self._agents.get(name)
        if reg and reg.agent_type == AgentType.LOCAL:
            return reg.instance
        return None
    
    def find_agents_by_skill(self, skill_id: str) -> List[AgentCard]:
        """根据技能 ID 查找 Agent"""
        agent_names = self._skill_index.get(skill_id, [])
        return [
            self._agents[name].card 
            for name in agent_names 
            if name in self._agents
        ]
    
    def find_agents_by_query(self, query: str) -> List[tuple[AgentCard, float]]:
        """
        根据查询文本查找最匹配的 Agent
        
        Returns:
            (AgentCard, 匹配度) 列表，按匹配度降序
        """
        results = []
        for reg in self._agents.values():
            score = reg.card.matches_query(query)
            if score > 0:
                results.append((reg.card, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def find_best_agent(
        self, 
        query: str, 
        required_skills: List[str] = None
    ) -> Optional[AgentCard]:
        """
        查找最佳匹配的 Agent
        
        Args:
            query: 用户查询
            required_skills: 必需技能列表
            
        Returns:
            最佳匹配的 Agent Card
        """
        candidates = self.find_agents_by_query(query)
        
        if required_skills:
            filtered = []
            for card, score in candidates:
                if all(card.has_skill(skill_id) for skill_id in required_skills):
                    filtered.append((card, score))
            candidates = filtered
        
        if candidates:
            return candidates[0][0]
        return None
    
    def list_all_agents(self) -> List[AgentCard]:
        """列出所有注册的 Agent"""
        return [reg.card for reg in self._agents.values()]
    
    async def health_check(self, name: str) -> bool:
        """
        Agent 健康检查
        
        Args:
            name: Agent 名称
            
        Returns:
            是否健康
        """
        reg = self._agents.get(name)
        if not reg:
            return False
        
        if reg.agent_type == AgentType.REMOTE:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{reg.card.url}/health")
                    return response.status_code == 200
            except (ValueError, KeyError):
                return False
            except (OSError, IOError):
                return False
            except TimeoutError:
                return False
            except Exception:
                return False
        
        return True
    
    def get_agent_stats(self) -> Dict[str, Any]:
        """获取注册统计信息"""
        local_count = sum(1 for r in self._agents.values() if r.agent_type == AgentType.LOCAL)
        remote_count = sum(1 for r in self._agents.values() if r.agent_type == AgentType.REMOTE)
        
        return {
            "total_agents": len(self._agents),
            "local_agents": local_count,
            "remote_agents": remote_count,
            "total_skills": len(self._skill_index),
            "agents": {
                name: {
                    "type": reg.agent_type.value,
                    "skills": [s.id for s in reg.card.skills],
                    "healthy": reg.health_status == "healthy"
                }
                for name, reg in self._agents.items()
            }
        }


agent_registry = AgentRegistry.get_instance()
