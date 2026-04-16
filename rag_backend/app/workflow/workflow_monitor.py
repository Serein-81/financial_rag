# app/workflow/workflow_monitor.py

"""
工作流监控组件

为LangGraph工作流提供完整的可观测性，支持：
- 工作流级别的追踪
- 节点级别的追踪
- 与现有AgentTracer的集成
- 与LangSmith的无缝对接
"""

import uuid
import logging
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class NodeType(str, Enum):
    """节点类型"""
    NORMAL = "normal"
    HUMAN_REVIEW = "human_review"
    CONDITIONAL = "conditional"
    AGENT = "agent"
    TOOL = "tool"


class WorkflowEvent(str, Enum):
    """工作流事件类型"""
    WORKFLOW_START = "workflow_start"
    NODE_START = "node_start"
    NODE_END = "node_end"
    WORKFLOW_END = "workflow_end"
    HUMAN_REVIEW_START = "human_review_start"
    HUMAN_REVIEW_END = "human_review_end"
    ERROR = "error"


@dataclass
class WorkflowConfig:
    """工作流配置"""
    workflow_type: str
    workflow_version: Optional[str] = None
    session_id: Optional[uuid.UUID] = None
    tenant_id: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class NodeExecutionContext:
    """节点执行上下文"""
    workflow_trace_id: uuid.UUID
    node_name: str
    node_type: NodeType = NodeType.NORMAL
    execution_order: int = 0
    input_data: Optional[Dict[str, Any]] = None
    agent_trace_id: Optional[uuid.UUID] = None


class WorkflowMonitor:
    """
    工作流监控器
    
    提供工作流级别的追踪和监控能力，与现有的AgentTracer形成双层追踪体系。
    
    使用示例:
    ```python
    # 创建监控器
    monitor = WorkflowMonitor(db_session)
    
    # 开始工作流
    with monitor.start_workflow(config) as workflow_id:
        # 执行节点
        with monitor.start_node(workflow_id, "validate_tax", node_type=NodeType.NORMAL) as node_execution_id:
            # 执行业务逻辑
            result = validate_tax(data)
            # 记录节点输出
            monitor.complete_node(node_execution_id, output_data=result)
    ```
    """
    
    def __init__(self, db_session: Session):
        """
        初始化工作流监控器
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session
    
    def start_workflow(
        self,
        config: WorkflowConfig,
        total_nodes: int = 0
    ) -> uuid.UUID:
        """
        开始工作流追踪
        
        Args:
            config: 工作流配置
            total_nodes: 总节点数
            
        Returns:
            workflow_trace_id: 工作流追踪ID
        """
        try:
            from app.models.workflow_trace import WorkflowTrace, WorkflowStatus
            
            workflow_trace = WorkflowTrace(
                id=uuid.uuid4(),
                workflow_type=config.workflow_type,
                workflow_version=config.workflow_version,
                session_id=config.session_id,
                tenant_id=config.tenant_id,
                user_id=config.user_id,
                input_data=config.metadata,
                status=WorkflowStatus.RUNNING.value,
                total_nodes=total_nodes,
                completed_nodes=0,
                workflow_metadata=config.metadata
            )
            
            self.db.add(workflow_trace)
            self.db.flush()
            
            logger.info(f"工作流追踪开始: {workflow_trace.id}, type={config.workflow_type}")
            
            return workflow_trace.id
            
        except Exception as e:
            logger.error(f"创建工作流追踪失败: {e}")
            raise
    
    def complete_workflow(
        self,
        workflow_trace_id: uuid.UUID,
        output_data: Optional[Dict[str, Any]] = None,
        status: str = "completed"
    ) -> None:
        """
        完成工作流追踪
        
        Args:
            workflow_trace_id: 工作流追踪ID
            output_data: 输出数据
            status: 完成状态
        """
        try:
            from app.models.workflow_trace import WorkflowTrace, WorkflowStatus
            
            workflow_trace = self.db.query(WorkflowTrace).filter(
                WorkflowTrace.id == workflow_trace_id
            ).first()
            
            if not workflow_trace:
                logger.warning(f"工作流追踪不存在: {workflow_trace_id}")
                return
            
            workflow_trace.status = status
            workflow_trace.output_data = output_data
            workflow_trace.completed_at = datetime.utcnow()
            
            if workflow_trace.created_at:
                duration_ms = (workflow_trace.completed_at - workflow_trace.created_at).total_seconds() * 1000
                workflow_trace.execution_time_ms = duration_ms
            
            if status == WorkflowStatus.WAITING_HUMAN_REVIEW.value:
                workflow_trace.status = WorkflowStatus.WAITING_HUMAN_REVIEW.value
            
            self.db.flush()
            
            logger.info(f"工作流追踪完成: {workflow_trace_id}, status={status}")
            
        except Exception as e:
            logger.error(f"完成工作流追踪失败: {e}", exc_info=True)
            raise
    
    def update_workflow_progress(
        self,
        workflow_trace_id: uuid.UUID,
        current_node: Optional[str] = None,
        completed_nodes: Optional[int] = None
    ) -> None:
        """
        更新工作流进度
        
        Args:
            workflow_trace_id: 工作流追踪ID
            current_node: 当前节点名称
            completed_nodes: 已完成节点数
        """
        try:
            from app.models.workflow_trace import WorkflowTrace
            
            workflow_trace = self.db.query(WorkflowTrace).filter(
                WorkflowTrace.id == workflow_trace_id
            ).first()
            
            if not workflow_trace:
                return
            
            if current_node is not None:
                workflow_trace.current_node = current_node
            
            if completed_nodes is not None:
                workflow_trace.completed_nodes = completed_nodes
            
            self.db.flush()
            
        except Exception as e:
            logger.error(f"更新工作流进度失败: {e}")
    
    def start_node(
        self,
        workflow_trace_id: uuid.UUID,
        node_name: str,
        node_type: NodeType = NodeType.NORMAL,
        execution_order: int = 0,
        input_data: Optional[Dict[str, Any]] = None,
        agent_trace_id: Optional[uuid.UUID] = None
    ) -> uuid.UUID:
        """
        开始节点追踪
        
        Args:
            workflow_trace_id: 工作流追踪ID
            node_name: 节点名称
            node_type: 节点类型
            execution_order: 执行顺序
            input_data: 节点输入
            agent_trace_id: 关联的Agent追踪ID
            
        Returns:
            node_execution_id: 节点执行ID
        """
        try:
            from app.models.workflow_trace import WorkflowNodeExecution
            
            node_type_str = node_type.value if hasattr(node_type, 'value') else str(node_type)
            
            node_execution = WorkflowNodeExecution(
                id=uuid.uuid4(),
                workflow_trace_id=workflow_trace_id,
                node_name=node_name,
                node_type=node_type_str,
                execution_order=execution_order,
                input_data=self._summarize_data(input_data),
                status="running",
                agent_trace_id=agent_trace_id,
                created_at=datetime.utcnow()
            )
            
            self.db.add(node_execution)
            self.db.flush()
            
            logger.debug(f"节点执行开始: {node_execution.id}, node={node_name}")
            
            self.update_workflow_progress(
                workflow_trace_id,
                current_node=node_name
            )
            
            return node_execution.id
            
        except Exception as e:
            logger.error(f"创建节点追踪失败: {e}", exc_info=True)
            raise
    
    def complete_node(
        self,
        node_execution_id: uuid.UUID,
        output_data: Optional[Dict[str, Any]] = None,
        status: str = "completed",
        error_message: Optional[str] = None,
        token_usage: Optional[Dict[str, int]] = None
    ) -> None:
        """
        完成节点追踪
        
        Args:
            node_execution_id: 节点执行ID
            output_data: 节点输出
            status: 完成状态
            error_message: 错误信息
            token_usage: Token使用量
        """
        try:
            from app.models.workflow_trace import WorkflowNodeExecution
            
            node_execution = self.db.query(WorkflowNodeExecution).filter(
                WorkflowNodeExecution.id == node_execution_id
            ).first()
            
            if not node_execution:
                logger.warning(f"节点执行不存在: {node_execution_id}")
                return
            
            node_execution.status = status
            node_execution.output_data = self._summarize_data(output_data)
            node_execution.completed_at = datetime.utcnow()
            node_execution.error_message = error_message
            
            if node_execution.created_at:
                duration_ms = (node_execution.completed_at - node_execution.created_at).total_seconds() * 1000
                node_execution.execution_time_ms = duration_ms
            
            if token_usage:
                node_execution.token_usage = token_usage
            
            self.db.flush()
            
            workflow_trace_id = node_execution.workflow_trace_id
            
            self.db.query(WorkflowNodeExecution).filter(
                WorkflowNodeExecution.workflow_trace_id == workflow_trace_id,
                WorkflowNodeExecution.status == "completed"
            ).update(
                {"status": "completed"}
            )
            
            from app.models.workflow_trace import WorkflowTrace
            
            workflow_trace = self.db.query(WorkflowTrace).filter(
                WorkflowTrace.id == workflow_trace_id
            ).first()
            
            if workflow_trace:
                workflow_trace.completed_nodes = self.db.query(WorkflowNodeExecution).filter(
                    WorkflowNodeExecution.workflow_trace_id == workflow_trace_id,
                    WorkflowNodeExecution.status == "completed"
                ).count()
                self.db.flush()
            
            logger.debug(f"节点执行完成: {node_execution_id}, status={status}")
            
        except Exception as e:
            logger.error(f"完成节点追踪失败: {e}", exc_info=True)
            raise
    
    def start_human_review_node(
        self,
        workflow_trace_id: uuid.UUID,
        node_name: str,
        execution_order: int,
        input_data: Optional[Dict[str, Any]] = None,
        review_request_id: Optional[uuid.UUID] = None
    ) -> uuid.UUID:
        """
        开始人工审核节点
        
        这个方法会创建节点追踪并将工作流状态设置为等待人工审核
        
        Args:
            workflow_trace_id: 工作流追踪ID
            node_name: 节点名称
            execution_order: 执行顺序
            input_data: 输入数据
            review_request_id: 审核请求ID
            
        Returns:
            node_execution_id: 节点执行ID
        """
        from app.models.workflow_trace import WorkflowTrace, WorkflowStatus
        
        node_execution_id = self.start_node(
            workflow_trace_id=workflow_trace_id,
            node_name=node_name,
            node_type=NodeType.HUMAN_REVIEW,
            execution_order=execution_order,
            input_data=input_data
        )
        
        workflow_trace = self.db.query(WorkflowTrace).filter(
            WorkflowTrace.id == workflow_trace_id
        ).first()
        
        if workflow_trace:
            workflow_trace.status = WorkflowStatus.WAITING_HUMAN_REVIEW.value
            if review_request_id:
                workflow_trace.human_review_id = review_request_id
            self.db.flush()
        
        logger.info(f"人工审核节点开始: {node_execution_id}, workflow={workflow_trace_id}")
        
        return node_execution_id
    
    def complete_human_review(
        self,
        node_execution_id: uuid.UUID,
        review_result: Dict[str, Any],
        workflow_trace_id: uuid.UUID
    ) -> None:
        """
        完成人工审核
        
        这个方法会完成节点追踪并恢复工作流执行
        
        Args:
            node_execution_id: 节点执行ID
            review_result: 审核结果
            workflow_trace_id: 工作流追踪ID
        """
        from app.models.workflow_trace import WorkflowTrace, WorkflowStatus
        
        self.complete_node(
            node_execution_id=node_execution_id,
            output_data=review_result,
            status="completed"
        )
        
        workflow_trace = self.db.query(WorkflowTrace).filter(
            WorkflowTrace.id == workflow_trace_id
        ).first()
        
        if workflow_trace:
            workflow_trace.status = WorkflowStatus.RUNNING.value
            self.db.flush()
        
        logger.info(f"人工审核完成: {node_execution_id}, result={review_result.get('action', 'unknown')}")
    
    def get_workflow_trace(self, workflow_trace_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        获取工作流追踪详情
        
        Args:
            workflow_trace_id: 工作流追踪ID
            
        Returns:
            工作流追踪信息
        """
        try:
            from app.models.workflow_trace import WorkflowTrace, WorkflowNodeExecution
            
            workflow_trace = self.db.query(WorkflowTrace).filter(
                WorkflowTrace.id == workflow_trace_id
            ).first()
            
            if not workflow_trace:
                return None
            
            node_executions = self.db.query(WorkflowNodeExecution).filter(
                WorkflowNodeExecution.workflow_trace_id == workflow_trace_id
            ).order_by(WorkflowNodeExecution.execution_order).all()
            
            return {
                "id": str(workflow_trace.id),
                "workflow_type": workflow_trace.workflow_type,
                "workflow_version": workflow_trace.workflow_version,
                "status": workflow_trace.status,
                "current_node": workflow_trace.current_node,
                "total_nodes": workflow_trace.total_nodes,
                "completed_nodes": workflow_trace.completed_nodes,
                "progress_percentage": workflow_trace.progress_percentage,
                "execution_time_ms": workflow_trace.execution_time_ms,
                "created_at": workflow_trace.created_at.isoformat() if workflow_trace.created_at else None,
                "completed_at": workflow_trace.completed_at.isoformat() if workflow_trace.completed_at else None,
                "nodes": [
                    {
                        "id": str(node.id),
                        "node_name": node.node_name,
                        "node_type": node.node_type,
                        "status": node.status,
                        "execution_time_ms": node.execution_time_ms,
                        "created_at": node.created_at.isoformat() if node.created_at else None,
                        "completed_at": node.completed_at.isoformat() if node.completed_at else None,
                    }
                    for node in node_executions
                ]
            }
            
        except Exception as e:
            logger.error(f"获取工作流追踪失败: {e}", exc_info=True)
            return None
    
    @staticmethod
    def _summarize_data(data: Optional[Dict[str, Any]], max_length: int = 1000) -> Optional[Dict[str, Any]]:
        """
        摘要数据，避免存储过大
        
        Args:
            data: 原始数据
            max_length: 单个字段最大长度
            
        Returns:
            摘要后的数据
        """
        if not data:
            return None
        
        summarized = {}
        for key, value in data.items():
            if isinstance(value, str) and len(value) > max_length:
                summarized[key] = f"{value[:max_length]}... [truncated]"
            elif isinstance(value, dict):
                summarized[key] = WorkflowMonitor._summarize_data(value, max_length)
            elif isinstance(value, list) and len(value) > 10:
                summarized[key] = f"[list with {len(value)} items]"
            else:
                summarized[key] = value
        
        return summarized
    
    def get_traces(
        self,
        page: int = 1,
        page_size: int = 10,
        workflow_type: Optional[str] = None,
        status: Optional[str] = None,
        tenant_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取工作流追踪列表
        
        Args:
            page: 页码
            page_size: 每页数量
            workflow_type: 工作流类型过滤
            status: 状态过滤
            tenant_id: 租户ID过滤
            start_date: 开始时间过滤
            end_date: 结束时间过滤
            
        Returns:
            分页的工作流追踪列表
        """
        try:
            from app.models.workflow_trace import WorkflowTrace
            from sqlalchemy import and_, desc
            
            query = self.db.query(WorkflowTrace)
            
            filters = []
            if workflow_type:
                filters.append(WorkflowTrace.workflow_type == workflow_type)
            if status:
                filters.append(WorkflowTrace.status == status)
            if tenant_id:
                filters.append(WorkflowTrace.tenant_id == tenant_id)
            if start_date:
                filters.append(WorkflowTrace.created_at >= start_date)
            if end_date:
                filters.append(WorkflowTrace.created_at <= end_date)
            
            if filters:
                query = query.filter(and_(*filters))
            
            total = query.count()
            
            traces = query.order_by(desc(WorkflowTrace.created_at)).offset((page - 1) * page_size).limit(page_size).all()
            
            return {
                "items": [
                    {
                        "id": str(trace.id),
                        "workflow_type": trace.workflow_type,
                        "workflow_version": trace.workflow_version,
                        "session_id": str(trace.session_id) if trace.session_id else None,
                        "tenant_id": trace.tenant_id,
                        "user_id": str(trace.user_id) if trace.user_id else None,
                        "status": trace.status,
                        "total_nodes": trace.total_nodes,
                        "completed_nodes": trace.completed_nodes,
                        "current_node": trace.current_node,
                        "metadata": trace.workflow_metadata,
                        "started_at": trace.created_at.isoformat() if trace.created_at else None,
                        "completed_at": trace.completed_at.isoformat() if trace.completed_at else None,
                        "duration": trace.execution_time_ms / 1000.0 if trace.execution_time_ms else None,
                        "error_message": trace.error_message
                    }
                    for trace in traces
                ],
                "total": total,
                "page": page,
                "page_size": page_size
            }
            
        except Exception as e:
            logger.error(f"获取工作流追踪列表失败: {e}", exc_info=True)
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
    
    def get_statistics(
        self,
        workflow_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取工作流统计数据
        
        Args:
            workflow_type: 工作流类型过滤
            start_date: 开始时间过滤
            end_date: 结束时间过滤
            
        Returns:
            工作流统计数据
        """
        try:
            from app.models.workflow_trace import WorkflowTrace
            from sqlalchemy import and_, func, desc
            
            query = self.db.query(WorkflowTrace)
            
            filters = []
            if workflow_type:
                filters.append(WorkflowTrace.workflow_type == workflow_type)
            if start_date:
                filters.append(WorkflowTrace.created_at >= start_date)
            if end_date:
                filters.append(WorkflowTrace.created_at <= end_date)
            
            if filters:
                query = query.filter(and_(*filters))
            
            total_workflows = query.count()
            
            running_workflows = query.filter(WorkflowTrace.status == "running").count()
            
            completed_workflows = query.filter(WorkflowTrace.status == "completed").count()
            
            failed_workflows = query.filter(WorkflowTrace.status == "failed").count()
            
            avg_duration_result = self.db.query(func.avg(WorkflowTrace.execution_time_ms)).filter(
                WorkflowTrace.execution_time_ms.isnot(None)
            ).scalar()
            average_duration = avg_duration_result / 1000.0 if avg_duration_result else 0.0
            
            success_rate = (completed_workflows / total_workflows * 100) if total_workflows > 0 else 0.0
            
            type_counts = self.db.query(
                WorkflowTrace.workflow_type,
                func.count(WorkflowTrace.id)
            ).group_by(WorkflowTrace.workflow_type).all()
            
            workflows_by_type = {wf_type: count for wf_type, count in type_counts}
            
            recent_traces = query.order_by(desc(WorkflowTrace.created_at)).limit(10).all()
            
            return {
                "total_workflows": total_workflows,
                "running_workflows": running_workflows,
                "completed_workflows": completed_workflows,
                "failed_workflows": failed_workflows,
                "average_duration": average_duration,
                "success_rate": success_rate,
                "workflows_by_type": workflows_by_type,
                "recent_traces": [
                    {
                        "id": str(trace.id),
                        "workflow_type": trace.workflow_type,
                        "status": trace.status,
                        "started_at": trace.created_at.isoformat() if trace.created_at else None,
                        "completed_at": trace.completed_at.isoformat() if trace.completed_at else None,
                        "duration": trace.execution_time_ms / 1000.0 if trace.execution_time_ms else None
                    }
                    for trace in recent_traces
                ]
            }
            
        except Exception as e:
            logger.error(f"获取工作流统计数据失败: {e}", exc_info=True)
            return {
                "total_workflows": 0,
                "running_workflows": 0,
                "completed_workflows": 0,
                "failed_workflows": 0,
                "average_duration": 0.0,
                "success_rate": 0.0,
                "workflows_by_type": {},
                "recent_traces": []
            }

    def get_running_workflows(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取正在运行的工作流
        
        Args:
            tenant_id: 租户ID过滤
            
        Returns:
            正在运行的工作流列表
        """
        try:
            from app.models.workflow_trace import WorkflowTrace
            from sqlalchemy import desc
            
            query = self.db.query(WorkflowTrace).filter(
                WorkflowTrace.status.in_(["running", "waiting_human_review"])
            )
            
            if tenant_id:
                query = query.filter(WorkflowTrace.tenant_id == tenant_id)
            
            workflows = query.order_by(desc(WorkflowTrace.created_at)).all()
            
            return [
                {
                    "id": str(wf.id),
                    "workflow_type": wf.workflow_type,
                    "workflow_version": wf.workflow_version,
                    "session_id": str(wf.session_id) if wf.session_id else None,
                    "tenant_id": wf.tenant_id,
                    "user_id": str(wf.user_id) if wf.user_id else None,
                    "status": wf.status,
                    "total_nodes": wf.total_nodes,
                    "completed_nodes": wf.completed_nodes,
                    "current_node": wf.current_node,
                    "metadata": wf.workflow_metadata,
                    "started_at": wf.created_at.isoformat() if wf.created_at else None,
                    "duration": wf.execution_time_ms / 1000.0 if wf.execution_time_ms else None,
                    "error_message": wf.error_message
                }
                for wf in workflows
            ]
            
        except Exception as e:
            logger.error(f"获取正在运行的工作流失败: {e}", exc_info=True)
            return []
    
    def get_node_executions(self, workflow_trace_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        获取节点的执行历史
        
        Args:
            workflow_trace_id: 工作流追踪ID
            
        Returns:
            节点执行列表
        """
        try:
            from app.models.workflow_trace import WorkflowNodeExecution
            
            node_executions = self.db.query(WorkflowNodeExecution).filter(
                WorkflowNodeExecution.workflow_trace_id == workflow_trace_id
            ).order_by(WorkflowNodeExecution.execution_order).all()
            
            return [
                {
                    "id": str(node.id),
                    "workflow_trace_id": str(node.workflow_trace_id),
                    "node_name": node.node_name,
                    "node_type": node.node_type,
                    "execution_order": node.execution_order,
                    "status": node.status,
                    "input_data": node.input_data,
                    "output_data": node.output_data,
                    "error_message": node.error_message,
                    "started_at": node.created_at.isoformat() if node.created_at else None,
                    "completed_at": node.completed_at.isoformat() if node.completed_at else None,
                    "duration": node.execution_time_ms / 1000.0 if node.execution_time_ms else None,
                    "token_usage": node.token_usage
                }
                for node in node_executions
            ]
            
        except Exception as e:
            logger.error(f"获取节点执行历史失败: {e}", exc_info=True)
            return []

@contextmanager
def workflow_context(
    monitor: WorkflowMonitor,
    config: WorkflowConfig,
    total_nodes: int = 0
):
    """
    工作流上下文管理器
    
    简化工作流的追踪管理，自动处理开始和结束
    
    Args:
        monitor: 工作流监控器
        config: 工作流配置
        total_nodes: 总节点数
        
    Yields:
        workflow_trace_id: 工作流追踪ID
    """
    workflow_trace_id = None
    try:
        workflow_trace_id = monitor.start_workflow(config, total_nodes)
        yield workflow_trace_id
        monitor.complete_workflow(workflow_trace_id, status="completed")
    except Exception as e:
        if workflow_trace_id:
            monitor.complete_workflow(workflow_trace_id, status="failed", output_data={"error": str(e)})
        raise


@contextmanager
def node_context(
    monitor: WorkflowMonitor,
    workflow_trace_id: uuid.UUID,
    node_name: str,
    node_type: NodeType = NodeType.NORMAL,
    execution_order: int = 0,
    input_data: Optional[Dict[str, Any]] = None
):
    """
    节点上下文管理器
    
    简化节点的追踪管理，自动处理开始和结束
    
    Args:
        monitor: 工作流监控器
        workflow_trace_id: 工作流追踪ID
        node_name: 节点名称
        node_type: 节点类型
        execution_order: 执行顺序
        input_data: 节点输入
        
    Yields:
        node_execution_id: 节点执行ID
    """
    node_execution_id = None
    try:
        node_execution_id = monitor.start_node(
            workflow_trace_id,
            node_name,
            node_type,
            execution_order,
            input_data
        )
        yield node_execution_id
        monitor.complete_node(node_execution_id, status="completed")
    except Exception as e:
        if node_execution_id:
            monitor.complete_node(
                node_execution_id,
                status="failed",
                error_message=str(e)
            )
        raise

    def get_running_workflows(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取正在运行的工作流

        Args:
            tenant_id: 租户ID过滤

        Returns:
            正在运行的工作流列表
        """
        try:
            from app.models.workflow_trace import WorkflowTrace
            from sqlalchemy import desc

            query = self.db.query(WorkflowTrace).filter(
                WorkflowTrace.status.in_(["running", "waiting_human_review"])
            )

            if tenant_id:
                query = query.filter(WorkflowTrace.tenant_id == tenant_id)

            workflows = query.order_by(desc(WorkflowTrace.created_at)).all()

            return [
                {
                    "id": str(wf.id),
                    "workflow_type": wf.workflow_type,
                    "workflow_version": wf.workflow_version,
                    "session_id": str(wf.session_id) if wf.session_id else None,
                    "tenant_id": wf.tenant_id,
                    "user_id": str(wf.user_id) if wf.user_id else None,
                    "status": wf.status,
                    "total_nodes": wf.total_nodes,
                    "completed_nodes": wf.completed_nodes,
                    "current_node": wf.current_node,
                    "metadata": wf.workflow_metadata,
                    "started_at": wf.created_at.isoformat() if wf.created_at else None,
                    "duration": wf.execution_time_ms / 1000.0 if wf.execution_time_ms else None,
                    "error_message": wf.error_message
                }
                for wf in workflows
            ]

        except Exception as e:
            logger.error(f"获取正在运行的工作流失败: {e}", exc_info=True)
            return []

    def get_node_executions(self, workflow_trace_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        获取节点的执行历史
        
        Args:
            workflow_trace_id: 工作流追踪ID
            
        Returns:
            节点执行列表
        """
        try:
            from app.models.workflow_trace import WorkflowNodeExecution
            
            node_executions = self.db.query(WorkflowNodeExecution).filter(
                WorkflowNodeExecution.workflow_trace_id == workflow_trace_id
            ).order_by(WorkflowNodeExecution.execution_order).all()
            
            return [
                {
                    "id": str(node.id),
                    "workflow_trace_id": str(node.workflow_trace_id),
                    "node_name": node.node_name,
                    "node_type": node.node_type,
                    "execution_order": node.execution_order,
                    "status": node.status,
                    "input_data": node.input_data,
                    "output_data": node.output_data,
                    "error_message": node.error_message,
                    "started_at": node.created_at.isoformat() if node.created_at else None,
                    "completed_at": node.completed_at.isoformat() if node.completed_at else None,
                    "duration": node.execution_time_ms / 1000.0 if node.execution_time_ms else None,
                    "token_usage": node.token_usage
                }
                for node in node_executions
            ]
            
        except Exception as e:
            logger.error(f"获取节点执行历史失败: {e}", exc_info=True)
            return []
