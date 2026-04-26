# app/workflow/agent_integration.py

"""
Agent与工作流集成模块

提供AgentTracer与WorkflowMonitor的集成功能：
- Agent执行时自动关联工作流追踪
- 支持在Agent执行过程中传递工作流上下文
- 提供统一的追踪上下文管理器
"""

import uuid
import logging
from typing import Optional, Dict, Any
from contextvars import ContextVar
from dataclasses import dataclass

logger = logging.getLogger(__name__)

workflow_context_var: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "workflow_context",
    default=None
)


@dataclass
class WorkflowContext:
    """工作流执行上下文"""
    workflow_trace_id: uuid.UUID
    node_execution_id: uuid.UUID
    node_name: str
    workflow_type: str
    execution_order: int = 0


class WorkflowContextManager:
    """
    工作流上下文管理器
    
    提供线程/协程安全的上下文管理，确保Agent执行时能够访问工作流信息
    """
    
    @staticmethod
    def set_context(context: Optional[WorkflowContext]) -> None:
        """
        设置工作流上下文
        
        Args:
            context: 工作流上下文
        """
        if context:
            workflow_context_var.set({
                "workflow_trace_id": str(context.workflow_trace_id),
                "node_execution_id": str(context.node_execution_id),
                "node_name": context.node_name,
                "workflow_type": context.workflow_type,
                "execution_order": context.execution_order
            })
            logger.debug(f"工作流上下文已设置: workflow={context.workflow_trace_id}, node={context.node_name}")
        else:
            workflow_context_var.set(None)
            logger.debug("工作流上下文已清除")
    
    @staticmethod
    def get_context() -> Optional[Dict[str, Any]]:
        """
        获取当前工作流上下文
        
        Returns:
            工作流上下文字典
        """
        return workflow_context_var.get()
    
    @staticmethod
    def get_workflow_trace_id() -> Optional[uuid.UUID]:
        """
        获取当前工作流追踪ID
        
        Returns:
            工作流追踪ID
        """
        context = workflow_context_var.get()
        if context:
            return uuid.UUID(context["workflow_trace_id"])
        return None
    
    @staticmethod
    def get_node_execution_id() -> Optional[uuid.UUID]:
        """
        获取当前节点执行ID
        
        Returns:
            节点执行ID
        """
        context = workflow_context_var.get()
        if context:
            return uuid.UUID(context["node_execution_id"])
        return None
    
    @staticmethod
    def is_in_workflow() -> bool:
        """
        检查当前是否在某个工作流中执行
        
        Returns:
            是否在工作流中
        """
        return workflow_context_var.get() is not None


class AgentWorkflowIntegrator:
    """
    Agent与工作流集成器
    
    提供AgentTracer与WorkflowMonitor的集成接口
    """
    
    def __init__(self, db_session):
        """
        初始化集成器
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session
        self.workflow_monitor = None
        self._init_workflow_monitor()
    
    def _init_workflow_monitor(self):
        """初始化工作流监控器"""
        try:
            from app.workflow.workflow_monitor import WorkflowMonitor
            self.workflow_monitor = WorkflowMonitor(self.db)
        except ImportError as e:
            logger.warning(f"无法导入WorkflowMonitor: {e}")
            self.workflow_monitor = None
    
    async def execute_agent_with_workflow(
        self,
        agent_func,
        workflow_trace_id: uuid.UUID,
        node_name: str,
        node_type: str = "agent",
        execution_order: int = 0,
        input_data: Optional[Dict[str, Any]] = None,
        agent_type: str = "react",
        user_query: str = "",
        user_id: str = "",
        tenant_id: str = "",
        **agent_kwargs
    ) -> tuple[Any, uuid.UUID, uuid.UUID]:
        """
        在工作流上下文中执行Agent
        
        Args:
            agent_func: Agent执行函数
            workflow_trace_id: 工作流追踪ID
            node_name: 节点名称
            node_type: 节点类型
            execution_order: 执行顺序
            input_data: 节点输入数据
            agent_type: Agent类型
            user_query: 用户查询
            user_id: 用户ID
            tenant_id: 租户ID
            **agent_kwargs: 传递给agent_func的其他参数
            
        Returns:
            (agent_result, node_execution_id, agent_trace_id): 执行结果和追踪ID
        """
        if not self.workflow_monitor:
            result = await agent_func(**agent_kwargs)
            return result, None, None
        
        node_execution_id = self.workflow_monitor.start_node(
            workflow_trace_id=workflow_trace_id,
            node_name=node_name,
            node_type=node_type,
            execution_order=execution_order,
            input_data=input_data
        )
        
        context = WorkflowContext(
            workflow_trace_id=workflow_trace_id,
            node_execution_id=node_execution_id,
            node_name=node_name,
            workflow_type="",
            execution_order=execution_order
        )
        WorkflowContextManager.set_context(context)
        
        agent_trace_id = None
        try:
            from app.services.agent_tracer import AgentTracer
            tracer = AgentTracer()
            
            agent_trace_id = await tracer.start_trace(
                agent_type=agent_type,
                user_query=user_query,
                user_id=user_id,
                tenant_id=tenant_id,
                session_id=agent_kwargs.get("session_id"),
                message_id=agent_kwargs.get("message_id")
            )
            
            agent_kwargs.pop("session_id", None)
            agent_kwargs.pop("message_id", None)
            
            result = await agent_func(**agent_kwargs)
            
            await tracer.end_trace(
                trace_id=agent_trace_id,
                final_answer=str(result)[:500] if result else "",
                success=True
            )
            
            self.workflow_monitor.complete_node(
                node_execution_id=node_execution_id,
                output_data={"result": str(result)[:500] if result else ""},
                status="completed"
            )
            
            return result, node_execution_id, uuid.UUID(agent_trace_id)
            
        except Exception as e:
            logger.error(f"Agent执行失败: {e}", exc_info=True)
            
            if agent_trace_id:
                try:
                    from app.services.agent_tracer import AgentTracer
                    tracer = AgentTracer()
                    await tracer.end_trace(
                        trace_id=agent_trace_id,
                        final_answer="",
                        success=False,
                        error_message=str(e)
                    )
                except Exception:
                    pass
            
            if self.workflow_monitor:
                self.workflow_monitor.complete_node(
                    node_execution_id=node_execution_id,
                    status="failed",
                    error_message=str(e)
                )
            
            raise
        
        finally:
            WorkflowContextManager.set_context(None)
    
    def link_agent_trace_to_node(
        self,
        agent_trace_id: uuid.UUID,
        node_execution_id: uuid.UUID
    ) -> None:
        """
        手动关联Agent追踪到节点执行
        
        这个方法允许在Agent执行后手动建立关联关系
        
        Args:
            agent_trace_id: Agent追踪ID
            node_execution_id: 节点执行ID
        """
        if not self.workflow_monitor:
            return
        
        try:
            from app.models.workflow_trace import WorkflowNodeExecution
            
            node_execution = self.db.query(WorkflowNodeExecution).filter(
                WorkflowNodeExecution.id == node_execution_id
            ).first()
            
            if node_execution:
                node_execution.agent_trace_id = agent_trace_id
                self.db.flush()
                logger.info(f"Agent追踪已关联到节点: agent={agent_trace_id}, node={node_execution_id}")
            else:
                logger.warning(f"节点执行不存在: {node_execution_id}")
                
        except Exception as e:
            logger.error(f"关联Agent追踪失败: {e}", exc_info=True)


def get_workflow_context() -> Optional[Dict[str, Any]]:
    """
    获取当前工作流上下文的便捷函数
    
    Returns:
        工作流上下文
    """
    return WorkflowContextManager.get_context()


def is_agent_in_workflow() -> bool:
    """
    检查当前Agent是否在工作流中执行
    
    Returns:
        是否在工作流中
    """
    return WorkflowContextManager.is_in_workflow()
