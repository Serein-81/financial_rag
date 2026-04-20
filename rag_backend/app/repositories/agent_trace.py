"""
Agent 追踪 Repository

提供 Agent 追踪的数据库操作接口，自动处理租户隔离

使用方式：
    from app.repositories.agent_trace import AgentTraceRepository, AgentStepRepository
    
    async def get_trace(db: AsyncSession, trace_id: str, tenant_id: str):
        repo = AgentTraceRepository(db)
        return await repo.get(trace_id, tenant_id=tenant_id)
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.agent_trace import AgentTrace, AgentStep
import logging

logger = logging.getLogger(__name__)


class AgentTraceRepository(BaseRepository[AgentTrace]):
    """
    Agent 追踪 Repository
    
    提供 Agent 追踪的 CRUD 操作，自动处理租户隔离
    """
    
    def __init__(self, session: AsyncSession):
        """初始化 AgentTrace Repository"""
        super().__init__(session, AgentTrace)
    
    async def create_trace(
        self,
        agent_type: str,
        user_query: str,
        session_id: Optional[str] = None,
        message_id: Optional[str] = None,
        langsmith_run_id: Optional[str] = None,
        **kwargs
    ) -> AgentTrace:
        """
        创建追踪记录
        
        Args:
            agent_type: Agent 类型
            user_query: 用户查询
            session_id: 会话 ID
            message_id: 消息 ID
            langsmith_run_id: LangSmith Run ID
            **kwargs: 其他字段
            
        Returns:
            创建的 AgentTrace
        """
        data = {
            'agent_type': agent_type,
            'user_query': user_query,
            'session_id': session_id,
            'message_id': message_id,
            'langsmith_run_id': langsmith_run_id,
            'status': 'running',
            **kwargs
        }
        
        return await self.create(**data)
    
    async def get_by_session(
        self,
        session_id: str,
        tenant_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AgentTrace]:
        """
        根据会话 ID 获取追踪列表
        
        Args:
            session_id: 会话 ID
            tenant_id: 租户 ID
            limit: 返回记录数限制
            
        Returns:
            AgentTrace 列表
        """
        return await self.list(
            tenant_id=tenant_id,
            session_id=session_id,
            limit=limit,
            order_by='created_at',
            order_desc=True
        )
    
    async def get_recent_traces(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AgentTrace]:
        """
        获取最近的追踪记录
        
        Args:
            tenant_id: 租户 ID
            limit: 返回记录数限制
            
        Returns:
            AgentTrace 列表
        """
        return await self.list(
            tenant_id=tenant_id,
            limit=limit,
            order_by='created_at',
            order_desc=True
        )


class AgentStepRepository(BaseRepository[AgentStep]):
    """
    Agent 步骤 Repository
    
    提供 Agent 步骤的 CRUD 操作，自动处理租户隔离
    """
    
    def __init__(self, session: AsyncSession):
        """初始化 AgentStep Repository"""
        super().__init__(session, AgentStep)
    
    async def create_step(
        self,
        trace_id: str,
        step_type: str,
        step_data: Dict[str, Any],
        **kwargs
    ) -> AgentStep:
        """
        创建步骤记录
        
        Args:
            trace_id: 追踪 ID
            step_type: 步骤类型
            step_data: 步骤数据
            **kwargs: 其他字段
            
        Returns:
            创建的 AgentStep
        """
        data = {
            'trace_id': trace_id,
            'step_type': step_type,
            'step_data': step_data,
            **kwargs
        }
        
        return await self.create(**data)
    
    async def bulk_create_steps(
        self,
        steps_data: List[Dict[str, Any]]
    ) -> List[AgentStep]:
        """
        批量创建步骤
        
        Args:
            steps_data: 步骤数据列表
            
        Returns:
            创建的 AgentStep 列表
        """
        return await self.bulk_create(steps_data)
    
    async def get_by_trace(
        self,
        trace_id: str,
        tenant_id: Optional[str] = None
    ) -> List[AgentStep]:
        """
        根据追踪 ID 获取步骤列表
        
        Args:
            trace_id: 追踪 ID
            tenant_id: 租户 ID
            
        Returns:
            AgentStep 列表
        """
        return await self.list(
            tenant_id=tenant_id,
            trace_id=trace_id,
            order_by='created_at',
            order_desc=False
        )
