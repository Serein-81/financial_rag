"""
Hybrid Dispatcher

混合调度器
统一调度本地 Agent 和远程 A2A Agent
优先使用本地，透明降级到远程
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from datetime import datetime
from dataclasses import dataclass

from .agent_card import AgentCard
from .client import A2AClient
from .registry import AgentRegistry, AgentType
from .models import Task, TaskStatus, Message, TextPart, TaskSubmitParams

logger = logging.getLogger(__name__)


class DispatchStrategy(str, Enum):
    """调度策略"""
    LOCAL_FIRST = "local_first"
    REMOTE_ONLY = "remote_only"
    LOCAL_ONLY = "local_only"
    LOAD_BALANCE = "load_balance"


@dataclass
class DispatchResult:
    """调度结果"""
    success: bool
    result: Any
    source: str
    agent_name: str
    duration_ms: float
    error: Optional[str] = None


@dataclass
class MultiAgentResult:
    """多 Agent 协作结果"""
    results: List[DispatchResult]
    final_response: Optional[str] = None
    execution_time_ms: float = 0.0


class HybridDispatcher:
    """
    混合调度器
    
    核心功能：
    1. 本地/远程 Agent 统一调度
    2. 能力匹配路由
    3. 故障转移
    4. 多 Agent 并行协作
    """
    
    def __init__(
        self,
        registry: AgentRegistry = None,
        strategy: DispatchStrategy = DispatchStrategy.LOCAL_FIRST,
        remote_timeout: float = 30.0
    ):
        self.registry = registry or AgentRegistry.get_instance()
        self.strategy = strategy
        self.remote_timeout = remote_timeout
        
        self._local_clients: Dict[str, Any] = {}
        self._remote_clients: Dict[str, A2AClient] = {}
        
        self._task_handlers: Dict[str, Callable] = {}
        
        logger.info(f"🔀 HybridDispatcher 初始化: 策略={strategy.value}")
    
    def set_task_handler(self, agent_name: str, handler: Callable) -> None:
        """设置任务处理器"""
        self._task_handlers[agent_name] = handler
    
    async def dispatch(
        self,
        query: str,
        agent_name: str = None,
        required_skills: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> DispatchResult:
        """
        调度任务到合适的 Agent
        
        Args:
            query: 用户查询
            agent_name: 指定 Agent 名称（可选）
            required_skills: 必需技能列表
            metadata: 附加元数据
            
        Returns:
            调度结果
        """
        start_time = datetime.now()
        
        target_card = await self._find_target_agent(query, agent_name, required_skills)
        if not target_card:
            return DispatchResult(
                success=False,
                result=None,
                source="dispatcher",
                agent_name=agent_name or "unknown",
                duration_ms=0,
                error="未找到合适的 Agent"
            )
        
        try:
            reg = self.registry.get_agent(target_card.name)
            
            if reg.agent_type == AgentType.LOCAL:
                result = await self._dispatch_local(target_card.name, query, metadata)
            else:
                result = await self._dispatch_remote(target_card, query, metadata)
            
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            return DispatchResult(
                success=True,
                result=result,
                source=reg.agent_type.value,
                agent_name=target_card.name,
                duration_ms=duration
            )
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 调度数据失败: {target_card.name} - {e}")
            return DispatchResult(
                success=False,
                result=None,
                source="dispatcher",
                agent_name=target_card.name,
                duration_ms=0,
                error=f"数据错误: {str(e)}"
            )
        except (OSError, IOError) as e:
            logger.error(f"❌ 调度IO失败: {target_card.name} - {e}")
            return DispatchResult(
                success=False,
                result=None,
                source="dispatcher",
                agent_name=target_card.name,
                duration_ms=0,
                error=f"IO错误: {str(e)}"
            )
        except Exception as e:
            logger.error(f"❌ 调度失败: {target_card.name} - {e}")
            return DispatchResult(
                success=False,
                result=None,
                source="dispatcher",
                agent_name=target_card.name,
                duration_ms=0,
                error=str(e)
            )
    
    async def _find_target_agent(
        self,
        query: str,
        agent_name: str = None,
        required_skills: List[str] = None
    ) -> Optional[AgentCard]:
        """查找目标 Agent"""
        if agent_name:
            reg = self.registry.get_agent(agent_name)
            if reg:
                return reg.card
        
        if required_skills:
            for skill_id in required_skills:
                agents = self.registry.find_agents_by_skill(skill_id)
                if agents:
                    if self.strategy == DispatchStrategy.LOCAL_FIRST:
                        for agent in agents:
                            reg = self.registry.get_agent(agent.name)
                            if reg and reg.agent_type == AgentType.LOCAL:
                                return agent
                    return agents[0]
        
        return self.registry.find_best_agent(query, required_skills)
    
    async def _dispatch_local(
        self,
        agent_name: str,
        query: str,
        metadata: Dict[str, Any] = None
    ) -> Any:
        """调度到本地 Agent"""
        handler = self._task_handlers.get(agent_name)
        if handler:
            return await handler(query, metadata)
        
        agent_instance = self.registry.get_agent_instance(agent_name)
        
        if not agent_instance:
            raise ValueError(f"本地 Agent 实例不存在: {agent_name}")
        
        if hasattr(agent_instance, "run"):
            if asyncio.iscoroutinefunction(agent_instance.run):
                result = await agent_instance.run(query, **(metadata or {}))
                return result
            return agent_instance.run(query, **(metadata or {}))
        
        if asyncio.iscoroutinefunction(agent_instance):
            return await agent_instance(query)
        
        return agent_instance(query)
    
    async def _dispatch_remote(
        self,
        agent_card: AgentCard,
        query: str,
        metadata: Dict[str, Any] = None
    ) -> Any:
        """调度到远程 Agent"""
        client = self._get_remote_client(agent_card)
        
        message = Message(
            role="user",
            parts=[TextPart(text=query)],
            metadata=metadata
        )
        
        params = TaskSubmitParams(
            message=message,
            acceptedOutputModes=["text"]
        )
        
        response = await asyncio.wait_for(
            client.submit_task(params),
            timeout=self.remote_timeout
        )
        
        return response
    
    def _get_remote_client(self, agent_card: AgentCard) -> A2AClient:
        """获取远程客户端（带缓存）"""
        if agent_card.name not in self._remote_clients:
            self._remote_clients[agent_card.name] = A2AClient(agent_card)
        return self._remote_clients[agent_card.name]
    
    async def dispatch_multi(
        self,
        query: str,
        agent_names: List[str],
        parallel: bool = True,
        metadata: Dict[str, Any] = None
    ) -> MultiAgentResult:
        """
        多 Agent 调度
        
        Args:
            query: 用户查询
            agent_names: Agent 名称列表
            parallel: 是否并行执行
            metadata: 附加元数据
            
        Returns:
            多 Agent 结果
        """
        start_time = datetime.now()
        results: List[DispatchResult] = []
        
        if parallel:
            tasks = [
                self.dispatch(query, name, metadata=metadata)
                for name in agent_names
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            results = [
                r if isinstance(r, DispatchResult) else DispatchResult(
                    success=False, result=None, source="dispatcher",
                    agent_name="unknown", duration_ms=0, error=str(r)
                )
                for r in results
            ]
        else:
            for name in agent_names:
                result = await self.dispatch(query, name, metadata=metadata)
                results.append(result)
        
        final_response = self._merge_results(results)
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return MultiAgentResult(
            results=results,
            final_response=final_response,
            execution_time_ms=execution_time
        )
    
    def _merge_results(self, results: List[DispatchResult]) -> str:
        """合并多 Agent 结果"""
        successful = [r for r in results if r.success and r.result]
        
        if not successful:
            return "所有 Agent 处理均失败"
        
        if len(successful) == 1:
            return str(successful[0].result)
        
        merged_parts = []
        for r in successful:
            merged_parts.append(f"[{r.agent_name}]: {r.result}")
        
        return "\n\n".join(merged_parts)
    
    async def fallback_dispatch(
        self,
        query: str,
        primary_agent: str,
        fallback_agents: List[str],
        metadata: Dict[str, Any] = None
    ) -> DispatchResult:
        """
        带故障转移的调度
        
        尝试 primary_agent，失败后依次尝试 fallback_agents
        """
        result = await self.dispatch(query, primary_agent, metadata=metadata)
        
        if result.success:
            return result
        
        logger.warning(f"⚠️ 主 Agent 失败，尝试备用: {primary_agent}")
        
        for fallback in fallback_agents:
            result = await self.dispatch(query, fallback, metadata=metadata)
            if result.success:
                logger.info(f"✅ 备用 Agent 成功: {fallback}")
                return result
        
        return DispatchResult(
            success=False,
            result=None,
            source="fallback",
            agent_name=primary_agent,
            duration_ms=0,
            error="所有 Agent 均失败"
        )
