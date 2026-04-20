"""
工作流监控 API 端点

提供工作流追踪、统计等API接口
"""

import logging
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.db.session import SessionLocal
from app.api.deps import get_current_user, CurrentUser
from app.workflow.workflow_monitor import WorkflowMonitor

router = APIRouter(prefix="/workflow", tags=["Workflow Monitor"])
logger = logging.getLogger(__name__)


def get_workflow_monitor() -> WorkflowMonitor:
    """
    获取工作流监控器实例
    
    注意：此函数创建同步会话以兼容 WorkflowMonitor 的同步 API
    """
    sync_db = SessionLocal()
    return WorkflowMonitor(sync_db)


@router.get("/traces")
async def get_traces(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    workflow_type: Optional[str] = Query(None, description="工作流类型"),
    status: Optional[str] = Query(None, description="状态过滤"),
    tenant_id: Optional[str] = Query(None, description="租户ID"),
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取工作流追踪列表
    
    支持分页和各种过滤条件
    """
    logger.info(f"获取工作流追踪列表: page={page}, page_size={page_size}")
    
    result = monitor.get_traces(
        page=page,
        page_size=page_size,
        workflow_type=workflow_type,
        status=status,
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date
    )
    
    return result


@router.get("/traces/{trace_id}")
async def get_trace(
    trace_id: UUID,
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取单个工作流追踪详情
    """
    logger.info(f"获取工作流追踪详情: trace_id={trace_id}")
    
    trace = monitor.get_workflow_trace(trace_id)
    
    if not trace:
        return {"error": "工作流追踪不存在"}
    
    return trace


@router.get("/traces/{trace_id}/nodes")
async def get_trace_nodes(
    trace_id: UUID,
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取工作流节点的执行历史
    """
    logger.info(f"获取工作流节点执行历史: trace_id={trace_id}")
    
    nodes = monitor.get_node_executions(trace_id)
    
    return nodes


@router.get("/statistics")
async def get_statistics(
    workflow_type: Optional[str] = Query(None, description="工作流类型"),
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取工作流统计数据
    
    返回总工作流数、运行中、完成、失败的数量等统计信息
    """
    logger.info(f"获取工作流统计数据: workflow_type={workflow_type}")
    
    stats = monitor.get_statistics(
        workflow_type=workflow_type,
        start_date=start_date,
        end_date=end_date
    )
    
    return stats


@router.get("/running")
async def get_running_workflows(
    tenant_id: Optional[str] = Query(None, description="租户ID"),
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取正在运行的工作流
    """
    logger.info(f"获取正在运行的工作流: tenant_id={tenant_id}")
    
    workflows = monitor.get_running_workflows(tenant_id=tenant_id)
    
    return workflows


@router.get("/node-stats")
async def get_node_type_stats(
    workflow_type: Optional[str] = Query(None, description="工作流类型"),
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取节点类型统计
    """
    logger.info(f"获取节点类型统计: workflow_type={workflow_type}")
    
    try:
        from app.models.workflow_trace import WorkflowNodeExecution, WorkflowTrace
        from sqlalchemy import and_, func
        
        query = monitor.db.query(WorkflowNodeExecution)
        
        filters = []
        if workflow_type:
            filters.append(WorkflowNodeExecution.workflow_trace_id.in_(
                monitor.db.query(WorkflowTrace.id).filter(WorkflowTrace.workflow_type == workflow_type)
            ))
        if start_date:
            filters.append(WorkflowNodeExecution.created_at >= start_date)
        if end_date:
            filters.append(WorkflowNodeExecution.created_at <= end_date)
        
        if filters:
            query = query.filter(and_(*filters))
        
        stats = query.with_entities(
            WorkflowNodeExecution.node_type,
            func.count(WorkflowNodeExecution.id),
            func.avg(WorkflowNodeExecution.execution_time_ms),
            func.sum(
                func.case(
                    (WorkflowNodeExecution.status == 'completed', 1),
                    else_=0
                )
            )
        ).group_by(WorkflowNodeExecution.node_type).all()
        
        return [
            {
                "node_type": stat[0] or "unknown",
                "count": stat[1],
                "average_duration": stat[2] / 1000.0 if stat[2] else 0.0,
                "success_rate": (stat[3] / stat[1] * 100) if stat[1] > 0 else 0.0
            }
            for stat in stats
        ]
        
    except Exception as e:
        logger.error(f"获取节点类型统计失败: {e}", exc_info=True)
        return []


@router.post("/traces/{trace_id}/cancel")
async def cancel_workflow(
    trace_id: UUID,
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    取消工作流
    """
    logger.info(f"取消工作流: trace_id={trace_id}")
    
    try:
        from app.models.workflow_trace import WorkflowTrace, WorkflowStatus
        
        workflow_trace = monitor.db.query(WorkflowTrace).filter(
            WorkflowTrace.id == trace_id
        ).first()
        
        if not workflow_trace:
            return {"error": "工作流不存在"}
        
        if workflow_trace.status not in ["running", "waiting_human_review"]:
            return {"error": f"无法取消状态为 {workflow_trace.status} 的工作流"}
        
        workflow_trace.status = WorkflowStatus.CANCELLED.value
        workflow_trace.completed_at = datetime.utcnow()
        monitor.db.flush()
        
        return {"message": "工作流已取消", "trace_id": str(trace_id)}
        
    except Exception as e:
        logger.error(f"取消工作流失败: {e}", exc_info=True)
        return {"error": str(e)}


@router.post("/traces/{trace_id}/retry")
async def retry_workflow(
    trace_id: UUID,
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    重试失败的工作流
    """
    logger.info(f"重试工作流: trace_id={trace_id}")
    
    try:
        from app.models.workflow_trace import WorkflowTrace, WorkflowStatus
        
        workflow_trace = monitor.db.query(WorkflowTrace).filter(
            WorkflowTrace.id == trace_id
        ).first()
        
        if not workflow_trace:
            return {"error": "工作流不存在"}
        
        if workflow_trace.status not in ["failed", "cancelled"]:
            return {"error": f"只能重试失败或已取消的工作流，当前状态: {workflow_trace.status}"}
        
        workflow_trace.status = WorkflowStatus.RUNNING.value
        workflow_trace.completed_at = None
        workflow_trace.error_message = None
        workflow_trace.completed_nodes = 0
        workflow_trace.current_node = None
        monitor.db.flush()
        
        return {
            "message": "工作流已重置为运行状态",
            "trace_id": str(trace_id),
            "status": workflow_trace.status
        }
        
    except Exception as e:
        logger.error(f"重试工作流失败: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/tax")
async def get_tax_workflows(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    tax_type: Optional[str] = Query(None, description="税务类型"),
    status: Optional[str] = Query(None, description="状态过滤"),
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取税务工作流列表
    
    支持分页和各种过滤条件
    """
    logger.info(f"获取税务工作流列表: page={page}, page_size={page_size}, tax_type={tax_type}")
    
    result = monitor.get_traces(
        page=page,
        page_size=page_size,
        workflow_type="tax",
        status=status
    )
    
    return result


@router.get("/tax/statistics")
async def get_tax_statistics(
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取税务工作流统计数据
    
    返回税务工作流的统计数据
    """
    logger.info("获取税务工作流统计数据")
    
    stats = monitor.get_statistics(
        workflow_type="tax",
        start_date=start_date,
        end_date=end_date
    )
    
    return stats


@router.get("/tax/{trace_id}")
async def get_tax_workflow(
    trace_id: UUID,
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取税务工作流详情
    """
    logger.info(f"获取税务工作流详情: trace_id={trace_id}")
    
    trace = monitor.get_workflow_trace(trace_id)
    
    if not trace:
        return {"error": "税务工作流不存在"}
    
    return trace


@router.post("/tax/monitor")
async def create_tax_monitoring_session(
    data: dict,
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    创建税务工作流监控会话
    """
    logger.info(f"创建税务工作流监控会话: {data}")
    
    try:
        workflow_trace_id = data.get("workflow_trace_id")
        tax_type = data.get("tax_type")
        tax_period = data.get("tax_period")
        
        if not all([workflow_trace_id, tax_type, tax_period]):
            return {"error": "缺少必要的参数"}
        
        session_id = str(uuid.uuid4())
        
        return {"session_id": session_id}
        
    except Exception as e:
        logger.error(f"创建税务工作流监控会话失败: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/policy")
async def get_policy_workflows(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态过滤"),
    policy_id: Optional[str] = Query(None, description="政策ID"),
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取政策推送工作流列表
    
    支持分页和各种过滤条件
    """
    logger.info(f"获取政策推送工作流列表: page={page}, page_size={page_size}")
    
    result = monitor.get_traces(
        page=page,
        page_size=page_size,
        workflow_type="policy",
        status=status
    )
    
    return result


@router.get("/policy/statistics")
async def get_policy_statistics(
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取政策推送工作流统计数据
    
    返回政策推送工作流的统计数据
    """
    logger.info("获取政策推送工作流统计数据")
    
    stats = monitor.get_statistics(
        workflow_type="policy",
        start_date=start_date,
        end_date=end_date
    )
    
    return stats


@router.get("/policy/{trace_id}")
async def get_policy_workflow(
    trace_id: UUID,
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取政策推送工作流详情
    """
    logger.info(f"获取政策推送工作流详情: trace_id={trace_id}")
    
    trace = monitor.get_workflow_trace(trace_id)
    
    if not trace:
        return {"error": "政策推送工作流不存在"}
    
    return trace


@router.get("/policy/{trace_id}/matches")
async def get_policy_matches(
    trace_id: UUID,
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取政策匹配结果
    """
    logger.info(f"获取政策匹配结果: trace_id={trace_id}")
    
    try:
        nodes = monitor.get_node_executions(trace_id)
        
        matches = [
            node for node in nodes
            if node.get("node_type") == "policy_match"
        ]
        
        return matches
        
    except Exception as e:
        logger.error(f"获取政策匹配结果失败: {e}", exc_info=True)
        return []


@router.get("/policy/{trace_id}/notifications")
async def get_notification_records(
    trace_id: UUID,
    monitor: WorkflowMonitor = Depends(get_workflow_monitor),
    user: CurrentUser = Depends(get_current_user)
):
    """
    获取通知发送记录
    """
    logger.info(f"获取通知发送记录: trace_id={trace_id}")
    
    try:
        nodes = monitor.get_node_executions(trace_id)
        
        notifications = [
            node for node in nodes
            if node.get("node_type") == "notification"
        ]
        
        return notifications
        
    except Exception as e:
        logger.error(f"获取通知发送记录失败: {e}", exc_info=True)
        return []

