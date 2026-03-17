"""
审查相关的 API 端点 - 支持租户隔离
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.db.session import AsyncSessionLocal
from app.api import deps
from app.models.user import User
from app.schemas.audit import (
    AuditTaskCreate,
    AuditTaskResponse,
    AuditResultResponse,
    AgentCollaborationResponse,
    TaskDecompositionResponse
)
from app.models.audit_task import AuditTask
from app.models.audit_result import AuditResult
from app.models.agent_collaboration import AgentCollaboration
from app.multi_agent_system import (
    AgentCoordinator,
    TaskDecomposer
)

router = APIRouter()

# 全局组件实例
coordinator = AgentCoordinator()
task_decomposer = TaskDecomposer()


@router.post("/tasks", response_model=AuditTaskResponse)
async def create_audit_task(
    task_data: AuditTaskCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db_session = Depends(deps.get_tenant_db)
):
    """
    创建审查任务 - 支持租户隔离
    
    创建新的审查任务并在后台执行
    """
    try:
        # 生成任务 ID
        task_id = str(uuid.uuid4())
        
        # 转换文档数据
        documents = [doc.dict() for doc in task_data.documents]
        
        # 创建数据库记录 - 包含租户信息
        db_task = AuditTask(
            id=task_id,
            user_id=str(current_user.id),
            tenant_id=tenant_context['tenant_id'],  # 🔒 租户隔离
            audit_type=task_data.audit_type.value,
            status="pending",
            documents=documents
        )
        
        db_session.add(db_task)
        await db_session.commit()
        await db_session.refresh(db_task)
        
        # 在后台执行审查任务
        background_tasks.add_task(
            execute_audit_task,
            task_id,
            tenant_context['tenant_id'],
            str(current_user.id),
            task_data.audit_type.value,
            documents
        )
        
        return AuditTaskResponse(
            id=str(db_task.id),
            tenant_id=db_task.tenant_id,
            user_id=str(db_task.user_id),
            audit_type=db_task.audit_type,
            status=db_task.status,
            documents=db_task.documents,
            created_at=db_task.created_at,
            completed_at=db_task.completed_at,
            error_message=None
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建审查任务失败: {str(e)}")


@router.get("/tasks/{task_id}", response_model=AuditTaskResponse)
async def get_audit_task(
    task_id: str,
    db: AsyncSession = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant)
):
    """
    获取审查任务信息
    """
    try:
        # 查询任务（带租户隔离）
        result = await db.execute(
            "SELECT * FROM audit_tasks WHERE id = :task_id AND tenant_id = :tenant_id",
            {"task_id": task_id, "tenant_id": tenant_id}
        )
        task = result.fetchone()
        
        if not task:
            raise HTTPException(status_code=404, detail="审查任务不存在")
        
        return AuditTaskResponse(
            id=str(task.id),
            tenant_id=task.tenant_id,
            user_id=str(task.user_id),
            audit_type=task.audit_type,
            status=task.status,
            documents=task.documents,
            created_at=task.created_at,
            completed_at=task.completed_at,
            error_message=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务信息失败: {str(e)}")


@router.get("/tasks/{task_id}/results", response_model=AuditResultResponse)
async def get_audit_results(
    task_id: str,
    db: AsyncSession = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant)
):
    """
    获取审查结果
    """
    try:
        # 检查任务是否存在且属于当前租户
        task_result = await db.execute(
            "SELECT * FROM audit_tasks WHERE id = :task_id AND tenant_id = :tenant_id",
            {"task_id": task_id, "tenant_id": tenant_id}
        )
        task = task_result.fetchone()
        
        if not task:
            raise HTTPException(status_code=404, detail="审查任务不存在")
        
        if task.status != "completed":
            raise HTTPException(status_code=400, detail=f"任务尚未完成，当前状态: {task.status}")
        
        # 查询审查结果
        results_query = await db.execute(
            "SELECT * FROM audit_results WHERE task_id = :task_id AND tenant_id = :tenant_id",
            {"task_id": task_id, "tenant_id": tenant_id}
        )
        results = results_query.fetchall()
        
        if not results:
            raise HTTPException(status_code=404, detail="审查结果不存在")
        
        # 构建响应（这里需要根据实际的结果格式调整）
        # TODO: 从协调器的状态中获取完整的结果
        
        return AuditResultResponse(
            task_id=task_id,
            tenant_id=tenant_id,
            audit_type=task.audit_type,
            findings=[],  # TODO: 转换实际的发现数据
            conflicts=[],  # TODO: 转换实际的冲突数据
            overall_risk_score=0.0,  # TODO: 计算实际的风险分数
            summary="审查完成",  # TODO: 生成实际的摘要
            recommendations=[],  # TODO: 提取实际的建议
            statistics={
                "total_findings": len(results),
                "total_conflicts": 0,
                "risk_level_distribution": {},
                "agent_contribution": {},
                "category_distribution": {},
                "average_confidence": 0.0,
                "average_risk_score": 0.0
            },
            created_at=task.completed_at or task.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取审查结果失败: {str(e)}")


@router.get("/tasks/{task_id}/collaborations", response_model=List[AgentCollaborationResponse])
async def get_agent_collaborations(
    task_id: str,
    db: AsyncSession = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant)
):
    """
    获取 Agent 协作记录
    """
    try:
        # 检查任务是否存在且属于当前租户
        task_result = await db.execute(
            "SELECT id FROM audit_tasks WHERE id = :task_id AND tenant_id = :tenant_id",
            {"task_id": task_id, "tenant_id": tenant_id}
        )
        task = task_result.fetchone()
        
        if not task:
            raise HTTPException(status_code=404, detail="审查任务不存在")
        
        # 查询协作记录
        collab_result = await db.execute(
            """
            SELECT * FROM agent_collaborations 
            WHERE task_id = :task_id AND tenant_id = :tenant_id 
            ORDER BY timestamp DESC
            """,
            {"task_id": task_id, "tenant_id": tenant_id}
        )
        collaborations = collab_result.fetchall()
        
        return [
            AgentCollaborationResponse(
                id=str(collab.id),
                task_id=str(collab.task_id),
                from_agent=collab.from_agent,
                to_agent=collab.to_agent,
                message_type=collab.message_type,
                message_content=collab.message_content,
                timestamp=collab.timestamp
            )
            for collab in collaborations
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取协作记录失败: {str(e)}")


@router.post("/tasks/decompose", response_model=TaskDecompositionResponse)
async def decompose_task(
    task_data: AuditTaskCreate,
    tenant_id: str = Depends(deps.get_current_tenant)
):
    """
    任务分解预览
    
    在实际创建任务前，预览任务分解结果
    """
    try:
        # 转换文档数据
        documents = [doc.dict() for doc in task_data.documents]
        
        # 执行任务分解
        decomposition_result = task_decomposer.decompose(
            documents=documents,
            requested_audit_type=task_data.audit_type.value
        )
        
        return TaskDecompositionResponse(**decomposition_result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"任务分解失败: {str(e)}")


@router.get("/tasks", response_model=List[AuditTaskResponse])
async def list_audit_tasks(
    skip: int = 0,
    limit: int = 20,
    status: str = None,
    audit_type: str = None,
    db: AsyncSession = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant),
    user_id: str = Depends(deps.get_current_user_id_from_context)
):
    """
    获取审查任务列表
    """
    try:
        # 构建查询条件
        where_conditions = ["tenant_id = :tenant_id", "user_id = :user_id"]
        params = {"tenant_id": tenant_id, "user_id": user_id}
        
        if status:
            where_conditions.append("status = :status")
            params["status"] = status
        
        if audit_type:
            where_conditions.append("audit_type = :audit_type")
            params["audit_type"] = audit_type
        
        # 执行查询
        query = f"""
            SELECT * FROM audit_tasks 
            WHERE {' AND '.join(where_conditions)}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :skip
        """
        params.update({"limit": limit, "skip": skip})
        
        result = await db.execute(query, params)
        tasks = result.fetchall()
        
        return [
            AuditTaskResponse(
                id=str(task.id),
                tenant_id=task.tenant_id,
                user_id=str(task.user_id),
                audit_type=task.audit_type,
                status=task.status,
                documents=task.documents,
                created_at=task.created_at,
                completed_at=task.completed_at,
                error_message=None
            )
            for task in tasks
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")


async def execute_audit_task(
    task_id: str,
    tenant_id: str,
    user_id: str,
    audit_type: str,
    documents: List[dict]
):
    """
    后台执行审查任务
    """
    try:
        print(f"🚀 [API] 开始执行后台审查任务: {task_id}")
        
        # 更新任务状态为处理中
        async with AsyncSessionLocal() as db:
            await db.execute(
                "UPDATE audit_tasks SET status = 'processing' WHERE id = :task_id",
                {"task_id": task_id}
            )
            await db.commit()
        
        # 执行审查
        result = await coordinator.audit(
            task_id=task_id,
            tenant_id=tenant_id,
            user_id=user_id,
            audit_type=audit_type,
            documents=documents
        )
        
        # 更新任务状态为完成
        async with AsyncSessionLocal() as db:
            await db.execute(
                "UPDATE audit_tasks SET status = 'completed', completed_at = NOW() WHERE id = :task_id",
                {"task_id": task_id}
            )
            await db.commit()
        
        print(f"✅ [API] 后台审查任务完成: {task_id}")
        
    except Exception as e:
        print(f"❌ [API] 后台审查任务失败: {task_id}, 错误: {e}")
        
        # 更新任务状态为失败
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    "UPDATE audit_tasks SET status = 'failed' WHERE id = :task_id",
                    {"task_id": task_id}
                )
                await db.commit()
        except Exception as update_error:
            print(f"❌ [API] 更新任务状态失败: {update_error}")