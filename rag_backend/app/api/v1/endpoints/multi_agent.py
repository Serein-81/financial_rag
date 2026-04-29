"""
多智能体系统 API 端点
提供多智能体协作、意图分析、专家查询等核心功能
"""

import uuid
import time
import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.schemas.multi_agent import (
    MultiAgentRequest,
    MultiAgentResponse,
    SpecialistQueryRequest,
    SpecialistQueryResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionStatus,
    SystemHealthResponse,
    AgentHealthStatus,
    ReportGenerationRequest,
    ReportGenerationResponse,
    SpecialistType,
    SpecialistResult,
    IntentAnalysisResult,
    ReflectionResult,
    MonitorSystemHealth,
    MonitorComponentStatus,
    AgentMetric,
    TaskPipeline,
    StreamingTask,
    IntentClassificationResult,
    UserRole,
    RBACPolicy,
    HITLApproval,
    HITLApprovalCreate,
    HITLApprovalReview,
    PermissionLevel,
    ApprovalStatus,
    SecurityEvent,
    SecurityStats,
    SecurityEventType,
    SecurityEventSeverity,
    SessionContext
)
from app.api import deps
from app.models.user import User
from app.services.redis_service import redis_service
from app.multi_agent_system import AgentOrchestrator, OrchestrationContext
from app.multi_agent_system.agents import (
    FinanceSpecialist,
    TaxSpecialist,
    LegalSpecialist
)

logger = logging.getLogger(__name__)
router = APIRouter()

orchestrator: Optional[AgentOrchestrator] = None
finance_specialist: Optional[FinanceSpecialist] = None
tax_specialist: Optional[TaxSpecialist] = None
legal_specialist: Optional[LegalSpecialist] = None


def get_orchestrator(tenant_id: str = None, user_id: str = None):
    """获取或创建编排器实例
    
    Args:
        tenant_id: 租户ID（可选，不传则使用已有实例或创建通用实例）
        user_id: 用户ID（可选）
    
    Returns:
        编排器实例
    """
    global orchestrator
    if orchestrator is None:
        orchestrator = AgentOrchestrator(
            tenant_id=tenant_id or "default",
            user_id=user_id or "default"
        )
    else:
        # 如果已有实例，更新租户ID（确保使用当前请求的租户）
        if tenant_id:
            orchestrator.tenant_id = tenant_id
            orchestrator.user_id = user_id or orchestrator.user_id
            logger.debug(f"[编排器] 更新租户ID: {tenant_id}")
    return orchestrator


def get_finance_specialist():
    """获取或创建金融专家实例"""
    global finance_specialist
    if finance_specialist is None:
        finance_specialist = FinanceSpecialist()
    return finance_specialist


def get_tax_specialist():
    """获取或创建税务专家实例"""
    global tax_specialist
    if tax_specialist is None:
        tax_specialist = TaxSpecialist()
    return tax_specialist


def get_legal_specialist():
    """获取或创建法律专家实例"""
    global legal_specialist
    if legal_specialist is None:
        legal_specialist = LegalSpecialist()
    return legal_specialist


@router.post("/query", response_model=MultiAgentResponse)
async def process_multi_agent_query(
    request: MultiAgentRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    处理多智能体查询请求
    
    主要流程：
    1. 意图分析 - 确定用户意图和路由策略
    2. 专家协作 - 根据意图调用相应专家智能体
    3. 结果整合 - 合并多个专家的分析结果
    4. 反思审查 - 质量检查和置信度评估
    """
    from app.services.monitor_service import monitor_service
    
    start_time = time.time()
    request_id = str(uuid.uuid4())
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        logger.info(f"处理多智能体查询 - 请求ID: {request_id}, 会话ID: {session_id}")
        logger.info(f"用户查询: {request.query}")
        logger.info(f"租户ID: {tenant_context['tenant_id']}")
        
        orch = get_orchestrator(tenant_id=tenant_context['tenant_id'], user_id=str(current_user.id))
        
        context = OrchestrationContext(
            session_id=session_id,
            tenant_id=tenant_context['tenant_id'],
            user_id=str(current_user.id),
            user_query=request.query,
            context=request.context or {},
            enable_reflection=request.enable_reflection,
            confidence_threshold=request.confidence_threshold,
            max_specialists=request.max_specialists
        )
        
        async with monitor_service.trace_agent(
            user_id=str(current_user.id),
            query=request.query,
            kb_id=request.context.get("kb_id") if request.context else None,
            session_id=session_id
        ) as trace:
            result = await orch.process(context)
            trace.set_result(str(result)[:500])
        
        processing_time = time.time() - start_time

        from app.services.operation_log_service import log_user_query
        log_user_query(
            user_id=str(current_user.id),
            query=request.query,
            tenant_id=tenant_context['tenant_id'],
            session_id=session_id,
            response_time_ms=processing_time * 1000,
            result_count=len(result.specialist_results) if result.specialist_results else 0
        )

        specialist_results = []
        for specialist_result in result.specialist_results:
            specialist_results.append(SpecialistResult(
                specialist_type=SpecialistType(specialist_result.get('specialist_type', 'unknown')),
                specialist_name=specialist_result.get('specialist_name', 'Unknown'),
                success=specialist_result.get('success', False),
                confidence=specialist_result.get('confidence', 0.0),
                analysis=specialist_result.get('analysis', {}),
                entities=specialist_result.get('entities', []),
                recommendations=specialist_result.get('recommendations', []),
                risks=specialist_result.get('risks', []),
                metadata=specialist_result.get('metadata', {}),
                processing_time=specialist_result.get('processing_time', 0.0),
                error_message=specialist_result.get('error_message')
            ))
        
        intent_result = result.intent_result
        intent_analysis = IntentAnalysisResult(
            primary_intent=intent_result.primary_intent,
            secondary_intents=intent_result.secondary_intents,
            complexity=intent_result.complexity,
            routing_strategy=intent_result.routing_strategy,
            confidence=intent_result.confidence,
            required_specialists=[SpecialistType(s) for s in intent_result.required_specialists],
            suggested_questions=intent_result.suggested_questions,
            metadata=intent_result.metadata
        )
        
        reflection_result = None
        if result.reflection_result:
            reflection_result = ReflectionResult(
                quality_score=result.reflection_result.quality_score,
                quality_level=result.reflection_result.quality_level,
                issues=result.reflection_result.issues,
                suggestions=result.reflection_result.suggestions,
                needs_revision=result.reflection_result.needs_revision,
                revision_required=result.reflection_result.revision_required
            )
        
        response = MultiAgentResponse(
            session_id=session_id,
            request_id=request_id,
            user_query=request.query,
            intent_analysis=intent_analysis,
            specialist_results=specialist_results,
            reflection_result=reflection_result,
            final_response=result.final_response,
            needs_human_review=result.needs_human_review,
            confidence=result.confidence,
            processing_time=processing_time,
            metadata=result.metadata or {}
        )
        
        logger.info(f"查询处理完成 - 请求ID: {request_id}, 耗时: {processing_time:.2f}秒")
        
        return response
        
    except (ValueError, KeyError) as e:
        logger.error(f"处理多智能体查询数据错误 - 请求ID: {request_id}, 错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"处理查询数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"处理多智能体查询IO错误 - 请求ID: {request_id}, 错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理查询IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"处理多智能体查询失败 - 请求ID: {request_id}, 错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理查询失败: {str(e)}")


@router.post("/query-async")
async def process_multi_agent_query_async(
    request: MultiAgentRequest,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    异步处理多智能体查询请求（推荐使用）
    
    与 /query 的区别：
    1. 立即返回 task_id 和 thread_id（不阻塞）
    2. 任务在后台通过 ARQ Worker 执行
    3. 前端通过 GET /api/v1/agent-task/status/{thread_id} 查询进度
    4. 切换页面后通过 GET /api/v1/agent-task/hydrate/{thread_id} 恢复状态
    
    使用流程：
    1. POST /query-async -> 获得 task_id, thread_id
    2. GET /agent-task/status/{thread_id} -> 轮询获取进度
    3. 页面切换后 GET /agent-task/hydrate/{thread_id} -> 恢复状态
    """
    import uuid as uuid_module
    from app.models.agent_task import AgentTaskStatus, TaskStatus, TaskPriority
    from app.db.session import AsyncSessionLocal
    
    task_id = f"lgwf_{uuid_module.uuid4().hex[:16]}"
    thread_id = request.session_id or f"thread_{uuid_module.uuid4().hex[:16]}"
    
    try:
        task_record = AgentTaskStatus(
            task_id=task_id,
            thread_id=thread_id,
            tenant_id=tenant_context['tenant_id'],
            user_id=current_user.id,
            task_type="langgraph_workflow",
            task_name="多智能体工作流",
            status=TaskStatus.PENDING,
            priority=TaskPriority.NORMAL,
            user_query=request.query,
            extra_metadata={
                "enable_reflection": request.enable_reflection,
                "confidence_threshold": request.confidence_threshold,
                "max_specialists": request.max_specialists,
                "context": request.context or {}
            }
        )
        
        db.add(task_record)
        await db.commit()
        
        try:
            from app.tasks.arq_tasks import ARQ_AVAILABLE
            if ARQ_AVAILABLE:
                from app.services.redis_service import get_redis_service
                import json
                
                redis_service = await get_redis_service()
                await redis_service.enqueue_task(
                    "run_langgraph_workflow",
                    {
                        "task_id": task_id,
                        "thread_id": thread_id,
                        "tenant_id": tenant_context['tenant_id'],
                        "user_id": str(current_user.id),
                        "user_query": request.query,
                        "enable_reflection": request.enable_reflection,
                        "confidence_threshold": request.confidence_threshold,
                        "max_specialists": request.max_specialists,
                        "context": request.context or {}
                    }
                )
                logger.info(f"[AsyncQuery] 任务已入队 ARQ: task_id={task_id}")
            else:
                import asyncio
                asyncio.create_task(
                    execute_workflow_background(
                        task_id=task_id,
                        thread_id=thread_id,
                        tenant_id=tenant_context['tenant_id'],
                        user_id=str(current_user.id),
                        user_query=request.query,
                        enable_reflection=request.enable_reflection
                    )
                )
                logger.info(f"[AsyncQuery] 任务已在后台执行: task_id={task_id}")
                
        except Exception as queue_error:
            logger.warning(f"[AsyncQuery] ARQ 入队失败，使用后台任务: {queue_error}")
            import asyncio
            asyncio.create_task(
                execute_workflow_background(
                    task_id=task_id,
                    thread_id=thread_id,
                    tenant_id=tenant_context['tenant_id'],
                    user_id=str(current_user.id),
                    user_query=request.query,
                    enable_reflection=request.enable_reflection
                )
            )
        
        logger.info(
            f"[AsyncQuery] 提交异步任务: task_id={task_id}, "
            f"thread_id={thread_id[:8]}..., user={current_user.id}"
        )
        
        return {
            "task_id": task_id,
            "thread_id": thread_id,
            "status": "submitted",
            "message": "任务已提交到后台，请使用 GET /api/v1/agent-task/status/" + thread_id + " 查询进度",
            "poll_url": f"/api/v1/agent-task/status/{thread_id}",
            "hydrate_url": f"/api/v1/agent-task/hydrate/{thread_id}"
        }
        
    except Exception as e:
        logger.error(f"[AsyncQuery] 提交任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"任务提交失败: {str(e)}")


async def execute_workflow_background(
    task_id: str,
    thread_id: str,
    tenant_id: str,
    user_id: str,
    user_query: str,
    enable_reflection: bool = True,
    confidence_threshold: float = 0.7,
    max_specialists: int = 3,
    context: dict = None
):
    """后台执行工作流任务"""
    from app.models.agent_task import AgentTaskStatus, TaskStatus
    from app.db.session import AsyncSessionLocal
    from datetime import datetime
    import traceback
    
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(AgentTaskStatus)
                .where(AgentTaskStatus.task_id == task_id)
                .values(status=TaskStatus.RUNNING, started_at=datetime.now())
            )
            await db.commit()
        
        logger.info(f"[Background] 开始执行工作流: task_id={task_id}")
        
        from app.multi_agent_system import AgentOrchestrator
        from app.multi_agent_system.orchestrator import OrchestrationContext
        
        orch = AgentOrchestrator(tenant_id=tenant_id, user_id=user_id)
        await orch.initialize()
        
        orchestration_context = OrchestrationContext(
            session_id=thread_id,
            tenant_id=tenant_id,
            user_id=user_id,
            user_query=user_query,
            context=context or {},
            enable_reflection=enable_reflection,
            confidence_threshold=confidence_threshold,
            max_specialists=max_specialists
        )
        
        result = await orch.process(orchestration_context)
        
        final_response = result.final_response or "处理完成"
        
        await db.execute(
            update(AgentTaskStatus)
            .where(AgentTaskStatus.task_id == task_id)
            .values(
                status=TaskStatus.COMPLETED,
                final_response=final_response,
                completed_at=datetime.now(),
                progress_percent=100,
                progress_message="任务完成"
            )
        )
        await db.commit()
        
        logger.info(f"[Background] 工作流执行完成: task_id={task_id}")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Background] 工作流执行失败: task_id={task_id}, error={error_msg}")
        logger.error(traceback.format_exc())


@router.post("/specialist/query", response_model=SpecialistQueryResponse)
async def query_specialist(
    request: SpecialistQueryRequest,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    单独查询专家智能体
    
    直接调用指定的专家智能体进行专业分析
    """
    start_time = time.time()
    
    try:
        specialist_type = request.specialist_type
        
        if specialist_type == SpecialistType.FINANCE:
            specialist = get_finance_specialist()
            result = await specialist.run(
                query=request.query,
                context=request.context,
                **request.parameters
            )
        elif specialist_type == SpecialistType.TAX:
            specialist = get_tax_specialist()
            result = await specialist.run(
                query=request.query,
                context=request.context,
                **request.parameters
            )
        elif specialist_type == SpecialistType.LEGAL:
            specialist = get_legal_specialist()
            result = await specialist.run(
                query=request.query,
                context=request.context,
                **request.parameters
            )
        else:
            raise HTTPException(status_code=400, detail=f"不支持的专家类型: {specialist_type}")
        
        processing_time = time.time() - start_time

        from app.services.operation_log_service import log_specialist_query
        log_specialist_query(
            user_id=str(current_user.id),
            specialist_type=request.specialist_type.value,
            query=request.query,
            tenant_id=tenant_context['tenant_id'],
            execution_time_ms=processing_time * 1000
        )

        return SpecialistQueryResponse(
            specialist_type=specialist_type,
            success=True,
            result=result,
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"查询专家智能体数据错误: {str(e)}", exc_info=True)
        return SpecialistQueryResponse(
            specialist_type=request.specialist_type,
            query=request.query,
            response="查询参数数据错误，请检查输入",
            success=False,
            confidence=0.0,
            error_message=str(e)
        )
    except (OSError, IOError) as e:
        logger.error(f"查询专家智能体IO错误: {str(e)}", exc_info=True)
        return SpecialistQueryResponse(
            specialist_type=request.specialist_type,
            query=request.query,
            response="系统IO错误，请稍后重试",
            success=False,
            confidence=0.0,
            error_message=str(e)
        )
    except Exception as e:
        logger.error(f"查询专家智能体失败: {str(e)}", exc_info=True)
        return SpecialistQueryResponse(
            specialist_type=request.specialist_type,
            success=False,
            result={},
            processing_time=time.time() - start_time,
            error_message=str(e)
        )


@router.get("/sessions/{session_id}", response_model=SessionStatus)
async def get_session_status(
    session_id: str,
    db_session: AsyncSession = Depends(deps.get_db)
):
    """
    获取会话状态
    
    查询指定会话的当前状态和基本信息
    """
    from app.models.chat import ChatSession
    from sqlalchemy import select, func
    
    try:
        result = await db_session.execute(
            select(
                ChatSession,
                func.count(ChatSession.id).label('message_count')
            )
            .where(ChatSession.id == session_id)
        )
        session_data = result.first()
        
        if not session_data:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session_obj, message_count = session_data
        
        return SessionStatus(
            session_id=str(session_obj.id),
            user_id=str(session_obj.user_id),
            tenant_id=getattr(session_obj, 'tenant_id', None),
            message_count=message_count,
            last_activity=session_obj.updated_at,
            created_at=session_obj.created_at,
            status="active"
        )
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"获取会话状态数据错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"获取会话状态数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"获取会话状态IO错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取会话状态IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"获取会话状态失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取会话状态失败: {str(e)}")


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(
    request: SessionCreateRequest,
    db_session: AsyncSession = Depends(deps.get_db)
):
    """
    创建新的多智能体会话
    
    初始化一个新的会话上下文
    """
    try:
        from app.models.chat import ChatSession
        
        session_id = str(uuid.uuid4())
        
        new_session = ChatSession(
            id=session_id,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
            title="新多智能体会话"
        )
        
        db_session.add(new_session)
        await db_session.commit()
        
        return SessionCreateResponse(
            session_id=session_id,
            created_at=new_session.created_at,
            metadata=request.metadata or {}
        )
        
    except (ValueError, KeyError) as e:
        logger.error(f"创建会话数据错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"创建会话数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"创建会话IO错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建会话IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"创建会话失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@router.get("/health", response_model=SystemHealthResponse)
async def check_system_health():
    """
    系统健康检查
    
    检查所有专家智能体和编排器的状态
    """
    from datetime import datetime
    
    agents_status = []
    overall_healthy = True
    
    try:
        finance = get_finance_specialist()
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.FINANCE,
            is_available=True,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message="正常运行"
        ))
    except (ValueError, KeyError) as e:
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.FINANCE,
            is_available=False,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message=f"数据错误: {str(e)}"
        ))
        overall_healthy = False
    except (OSError, IOError) as e:
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.FINANCE,
            is_available=False,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message=f"IO错误: {str(e)}"
        ))
        overall_healthy = False
    except Exception as e:
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.FINANCE,
            is_available=False,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message=f"异常: {str(e)}"
        ))
        overall_healthy = False
    
    try:
        tax = get_tax_specialist()
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.TAX,
            is_available=True,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message="正常运行"
        ))
    except (ValueError, KeyError) as e:
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.TAX,
            is_available=False,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message=f"数据错误: {str(e)}"
        ))
        overall_healthy = False
    except (OSError, IOError) as e:
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.TAX,
            is_available=False,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message=f"IO错误: {str(e)}"
        ))
        overall_healthy = False
    except Exception as e:
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.TAX,
            is_available=False,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message=f"异常: {str(e)}"
        ))
        overall_healthy = False
    
    try:
        legal = get_legal_specialist()
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.LEGAL,
            is_available=True,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message="正常运行"
        ))
    except (ValueError, KeyError) as e:
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.LEGAL,
            is_available=False,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message=f"数据错误: {str(e)}"
        ))
        overall_healthy = False
    except (OSError, IOError) as e:
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.LEGAL,
            is_available=False,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message=f"IO错误: {str(e)}"
        ))
        overall_healthy = False
    except Exception as e:
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.LEGAL,
            is_available=False,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message=f"异常: {str(e)}"
        ))
        overall_healthy = False
    
    orchestrator_healthy = orchestrator is not None
    
    return SystemHealthResponse(
        overall_status="healthy" if overall_healthy and orchestrator_healthy else "degraded",
        agents=agents_status,
        orchestrator_status="healthy" if orchestrator_healthy else "unavailable",
        database_status="connected",
        timestamp=datetime.now()
    )


@router.post("/report/generate", response_model=ReportGenerationResponse)
async def generate_report(
    request: ReportGenerationRequest,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    生成多智能体分析报告
    
    基于历史会话生成结构化报告
    """
    try:
        from datetime import datetime
        
        report_id = str(uuid.uuid4())
        
        orch = get_orchestrator(
            tenant_id=tenant_context['tenant_id'],
            user_id=str(current_user.id)
        )
        
        report_content = await orch.generate_report(
            session_id=request.session_id,
            report_type=request.report_type,
            format=request.format,
            include_sections=request.include_sections
        )
        
        return ReportGenerationResponse(
            report_id=report_id,
            session_id=request.session_id,
            report_type=request.report_type,
            format=request.format,
            content=report_content,
            generated_at=datetime.now(),
            metadata=request.metadata or {}
        )
        
    except (ValueError, KeyError) as e:
        logger.error(f"生成报告数据错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"生成报告数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"生成报告IO错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成报告IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"生成报告失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")


# ==========================================
# 监控 API 端点（前端监控页面使用）
# 复用 MonitorService 和现有组件
# ==========================================

@router.get("/monitor/health", response_model=MonitorSystemHealth)
async def get_monitor_health():
    """
    获取系统健康状态（前端监控页面使用）

    复用 MonitorService 和系统组件状态
    从 A2A Registry 获取实时 Agent 注册状态
    """
    from app.services.monitor_service import monitor_service
    from app.a2a_protocol import agent_registry

    stats = monitor_service.get_statistics()
    uptime_seconds = int(stats.get("avg_duration", 0) * stats.get("total_events", 0))

    active_sessions = 0
    try:
        if stats.get("total_events", 0) > 0:
            active_sessions = stats.get("total_events", 0)
    except (ValueError, KeyError) as e:
        logger.warning(f"获取active_sessions数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.warning(f"获取active_sessions IO错误: {str(e)}")
    except Exception as e:
        logger.warning(f"获取active_sessions失败: {str(e)}")

    agent_stats = agent_registry.get_agent_stats()
    registered_agents = agent_stats.get("total_agents", 0)

    healthy_agents = sum(
        1 for agent_info in agent_stats.get("agents", {}).values()
        if agent_info.get("healthy", False)
    )

    system_status = "healthy"
    if registered_agents == 0:
        system_status = "down"
    elif healthy_agents < registered_agents:
        system_status = "degraded"

    return MonitorSystemHealth(
        status=system_status,
        components=MonitorComponentStatus(
            rbac_service=True,
            task_scheduler=True,
            session_blackboard=True,
            hitl_manager=True,
            intent_classifier=True
        ),
        uptime=uptime_seconds,
        active_sessions=active_sessions,
        pending_approvals=0
    )


@router.get("/metrics", response_model=List[AgentMetric])
async def get_agent_metrics():
    """
    获取 Agent 指标列表（前端监控页面使用）

    从 A2A Registry 获取实时 Agent 注册状态
    从 MonitorService 获取历史调用统计
    """
    from app.services.monitor_service import monitor_service
    from app.a2a_protocol import agent_registry

    stats = monitor_service.get_statistics()
    agent_stats = agent_registry.get_agent_stats()

    registered_agents = agent_stats.get("agents", {})

    specialist_types = [
        ("finance_specialist", "金融专家"),
        ("tax_specialist", "税务专家"),
        ("legal_specialist", "法律专家"),
    ]

    agent_metrics = []
    for agent_id, agent_name in specialist_types:
        total_requests = 0
        success_rate = 0.0
        avg_latency = 0.0
        is_registered = False

        agent_info = registered_agents.get(agent_id)
        if agent_info:
            is_registered = agent_info.get("healthy", False)
            total_requests = stats.get("total_events", 0) if is_registered else 0
            success_count = stats.get("success_count", 0)
            if total_requests > 0:
                success_rate = success_count / total_requests
            avg_latency = stats.get("avg_duration", 0.0)

        agent_metrics.append(AgentMetric(
            agent_id=agent_id,
            agent_name=agent_name,
            total_requests=total_requests,
            success_rate=round(success_rate, 2),
            avg_latency=round(avg_latency, 3),
            last_execution=None
        ))

    return agent_metrics


@router.get("/pipelines/active", response_model=List[TaskPipeline])
async def get_active_pipelines():
    """
    获取活跃的任务管道列表（前端监控页面使用）

    复用 MonitorService 的活跃追踪
    """
    from app.services.monitor_service import monitor_service

    active_traces = monitor_service.active_traces

    pipelines = []
    for trace_id, event in list(active_traces.items())[:10]:
        metadata = event.metadata
        query = metadata.get("query", "")
        user_id = metadata.get("user_id", "unknown")
        session_id = metadata.get("session_id", "unknown")

        task = StreamingTask(
            task_id=trace_id,
            agent_id="orchestrator",
            agent_name="编排器",
            status="running",
            progress=0.5
        )

        intent = IntentClassificationResult(
            stage="keyword",
            intent="general",
            confidence=0.8,
            is_expense_related=False,
            should_process=True
        )

        pipeline = TaskPipeline(
            pipeline_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            query=query[:100] if query else "处理中...",
            tasks=[task],
            state="processing",
            intent_classification=intent,
            created_at=datetime.fromtimestamp(event.start_time).isoformat() if hasattr(event, 'start_time') else datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        pipelines.append(pipeline)

    return pipelines


# ==========================================
# RBAC (Role-Based Access Control) 端点
# ==========================================

@router.get("/rbac/roles", response_model=List[UserRole])
async def get_user_roles(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取用户角色列表

    返回当前用户的所有角色及其权限信息
    """
    try:
        roles = [
            UserRole(
                role_id="admin",
                role_name="管理员",
                permissions=[
                    PermissionLevel.PUBLIC,
                    PermissionLevel.SENSITIVE,
                    PermissionLevel.DANGEROUS,
                    PermissionLevel.CRITICAL
                ]
            ),
            UserRole(
                role_id="user",
                role_name="普通用户",
                permissions=[
                    PermissionLevel.PUBLIC,
                    PermissionLevel.SENSITIVE
                ]
            )
        ]

        return roles

    except (ValueError, KeyError) as e:
        logger.error(f"获取用户角色数据错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"获取用户角色数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"获取用户角色IO错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取用户角色IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"获取用户角色失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取用户角色失败: {str(e)}")


@router.get("/rbac/policies", response_model=List[RBACPolicy])
async def get_rbac_policies(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取RBAC策略列表

    返回所有定义的访问控制策略
    """
    try:
        policies = [
            RBACPolicy(
                policy_id="policy-001",
                role="admin",
                allowed_operations=["*"],
                denied_operations=[],
                created_at=datetime.now()
            ),
            RBACPolicy(
                policy_id="policy-002",
                role="user",
                allowed_operations=[
                    "view:public_data",
                    "request:approval"
                ],
                denied_operations=[
                    "approve:any",
                    "view:sensitive_data"
                ],
                created_at=datetime.now()
            )
        ]

        return policies

    except (ValueError, KeyError) as e:
        logger.error(f"获取RBAC策略数据错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"获取RBAC策略数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"获取RBAC策略IO错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取RBAC策略IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"获取RBAC策略失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取RBAC策略失败: {str(e)}")


# ==========================================
# HITL (Human-In-The-Loop) 端点
# ==========================================

hitl_approvals_storage = {}


@router.get("/hitl/pending", response_model=List[HITLApproval])
async def get_pending_approvals(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取待审批的HITL请求列表

    返回所有等待审批的操作请求
    """
    try:
        pending_approvals = []

        for approval in hitl_approvals_storage.values():
            if approval.status == ApprovalStatus.PENDING:
                if approval.expires_at > datetime.now():
                    pending_approvals.append(approval)

        return pending_approvals

    except (ValueError, KeyError) as e:
        logger.error(f"获取待审批请求数据错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"获取待审批请求数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"获取待审批请求IO错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取待审批请求IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"获取待审批请求失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取待审批请求失败: {str(e)}")


@router.get("/hitl/history", response_model=List[HITLApproval])
async def get_approval_history(
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context),
    db: AsyncSession = Depends(deps.get_db),
    status: Optional[ApprovalStatus] = Query(None, description="按状态筛选"),
    limit: int = Query(50, ge=1, le=100, description="返回数量限制")
):
    """
    获取审批历史记录

    返回已处理的审批请求历史，并从数据库获取最新操作记录
    """
    try:
        from sqlalchemy import select, text
        from app.models.review_request import ReviewRequest
        import json
        
        logger.info(f"[HITL] get_approval_history called, status={status}, limit={limit}, storage_size={len(hitl_approvals_storage)}")
        
        history = []
        seen_approval_ids = set()

        def parse_json_field(value):
            if isinstance(value, str):
                try:
                    return json.loads(value) if value else {}
                except json.JSONDecodeError:
                    logger.warning(f"[HITL] 无法解析 JSON 字段: {value}")
                    return {}
            return value or {}

        def map_review_status(review_status: str) -> ApprovalStatus:
            if review_status == "completed":
                return ApprovalStatus.APPROVED
            if review_status == "rejected":
                return ApprovalStatus.REJECTED
            if review_status == "timeout":
                return ApprovalStatus.TIMEOUT
            return ApprovalStatus.PENDING

        async def get_user_display_name(user_id: str) -> str:
            if not user_id:
                return ""
            if str(current_user.id) == str(user_id):
                return current_user.full_name or current_user.nickname or current_user.username or current_user.email or str(user_id)
            try:
                user_uuid = uuid.UUID(str(user_id))
            except (ValueError, TypeError):
                logger.warning(f"[HITL] 无法解析用户ID: {user_id}")
                return str(user_id)

            user_result = await db.execute(select(User).where(User.id == user_uuid))
            user = user_result.scalar_one_or_none()
            if not user:
                return str(user_id)
            return user.full_name or user.nickname or user.username or user.email or str(user_id)

        for approval in hitl_approvals_storage.values():
            if status and approval.status != status:
                continue
            history.append(approval)
            seen_approval_ids.add(approval.approval_id)

        logger.info(f"[HITL] filtered history from storage count: {len(history)}")
        
        history.sort(key=lambda x: x.created_at, reverse=True)

        logger.info(f"[HITL] trying to get reviews from database")
        db_statuses = ["completed", "rejected"]
        if status == ApprovalStatus.APPROVED:
            db_statuses = ["completed"]
        elif status == ApprovalStatus.REJECTED:
            db_statuses = ["rejected"]
        elif status in (ApprovalStatus.PENDING, ApprovalStatus.TIMEOUT):
            db_statuses = []

        db_reviews = []
        if db_statuses:
            review_result = await db.execute(
                select(ReviewRequest)
                .where(ReviewRequest.status.in_(db_statuses))
                .order_by(ReviewRequest.updated_at.desc())
                .limit(limit)
            )
            db_reviews = review_result.scalars().all()
        logger.info(f"[HITL] found {len(db_reviews)} reviews from database")

        for review in db_reviews:
            review_id = str(review.id)
            if review_id in seen_approval_ids:
                continue

            actions_result = await db.execute(
                text("SELECT * FROM review_request_actions WHERE review_request_id = :review_id ORDER BY created_at DESC LIMIT 1"),
                {"review_id": review_id}
            )
            latest_action = actions_result.fetchone()
            latest_action_dict = {}
            if latest_action:
                latest_action_dict = dict(latest_action._mapping) if hasattr(latest_action, '_mapping') else {c: getattr(latest_action, c) for c in latest_action._fields}
                logger.info(f"[HITL] action record: id={latest_action_dict.get('id')}, action={latest_action_dict.get('action')}")

            action_details = parse_json_field(latest_action_dict.get("action_details"))
            new_value = parse_json_field(latest_action_dict.get("new_value"))
            applicant_user_id = str(review.user_id)
            operator_user_id = str(latest_action_dict.get("user_id") or review.reviewed_by or current_user.id)
            applicant_name = await get_user_display_name(applicant_user_id)
            operator_name = await get_user_display_name(operator_user_id)
            reviewer_notes = (
                action_details.get("comment")
                or action_details.get("description")
                or new_value.get("review_comments")
                or review.review_comments
                or latest_action_dict.get("action")
            )

            operation = (
                latest_action_dict.get("action")
                or review.trigger_reason
                or review.review_type
                or "review"
            )

            approval_dict = {
                "approval_id": review_id,
                "task_id": str(review.task_id),
                "user_id": applicant_user_id,
                "user_name": applicant_name,
                "applicant_user_id": applicant_user_id,
                "applicant_name": applicant_name,
                "operator_user_id": operator_user_id,
                "operator_name": operator_name,
                "operation": operation,
                "details": {
                    "title": review.title,
                    "description": review.description,
                    "trigger_reason": review.trigger_reason,
                    "trigger_details": review.trigger_details or {},
                    "content": review.content or {},
                    "action_details": action_details,
                },
                "risk_level": PermissionLevel.SENSITIVE,
                "status": map_review_status(review.status),
                "created_at": review.created_at,
                "expires_at": review.sla_deadline or review.updated_at or review.created_at,
                "reviewed_at": review.reviewed_at or latest_action_dict.get("created_at") or review.updated_at,
                "reviewer_notes": reviewer_notes
            }

            history.append(HITLApproval(**approval_dict))
            seen_approval_ids.add(review_id)
            logger.info(f"[HITL] added review to history: review_id={review_id}, operation={operation}, reviewer_notes={reviewer_notes}")

        history.sort(key=lambda x: x.reviewed_at or x.created_at, reverse=True)
        
        result_approvals = []
        for approval in history[:limit]:
            try:
                if hasattr(approval, 'model_dump'):
                    approval_dict = approval.model_dump()
                elif hasattr(approval, '__dict__'):
                    approval_dict = vars(approval)
                else:
                    logger.warning(f"[HITL] 跳过无效 approval 对象: {type(approval)}")
                    continue
                
                task_id = approval_dict.get("task_id")
                approval_id = approval_dict.get("approval_id")
                user_id = approval_dict.get("user_id")
                
                if not task_id or not approval_id:
                    logger.warning(f"[HITL] 跳过无效 approval: approval_id={approval_id}, task_id={task_id}")
                    continue

                if not approval_dict.get("user_name") and user_id:
                    approval_dict["user_name"] = await get_user_display_name(str(user_id))

                if not approval_dict.get("applicant_user_id"):
                    approval_dict["applicant_user_id"] = user_id
                if not approval_dict.get("applicant_name") and approval_dict.get("applicant_user_id"):
                    approval_dict["applicant_name"] = await get_user_display_name(str(approval_dict["applicant_user_id"]))
                if not approval_dict.get("operator_user_id"):
                    approval_dict["operator_user_id"] = user_id
                if not approval_dict.get("operator_name") and approval_dict.get("operator_user_id"):
                    approval_dict["operator_name"] = await get_user_display_name(str(approval_dict["operator_user_id"]))
                
                logger.info(f"[HITL] 处理 approval: approval_id={approval_id}, task_id={task_id}")
                
                if task_id:
                    try:
                        result = await db.execute(
                            text("""
                                SELECT * FROM review_request_actions 
                                WHERE review_request_id = :task_id 
                                ORDER BY created_at DESC 
                                LIMIT 1
                            """),
                            {"task_id": task_id}
                        )
                        latest_action = result.fetchone()
                        
                        if not latest_action:
                            review_result = await db.execute(
                                text("SELECT id FROM review_requests WHERE task_id = :task_id LIMIT 1"),
                                {"task_id": task_id}
                            )
                            review_row = review_result.fetchone()
                            if review_row:
                                result = await db.execute(
                                    text("""
                                        SELECT * FROM review_request_actions 
                                        WHERE review_request_id = :review_id 
                                        ORDER BY created_at DESC 
                                        LIMIT 1
                                    """),
                                    {"review_id": str(review_row.id)}
                                )
                                latest_action = result.fetchone()
                        
                        if latest_action:
                            latest_action_dict = dict(latest_action._mapping) if hasattr(latest_action, '_mapping') else {c: getattr(latest_action, c) for c in latest_action._fields}
                            
                            action_details = latest_action_dict.get("action_details")
                            action_details = parse_json_field(action_details)
                            
                            reviewer_notes = None
                            if action_details:
                                reviewer_notes = action_details.get("comment") or action_details.get("description")
                            
                            if not reviewer_notes:
                                new_value = latest_action_dict.get("new_value")
                                new_value = parse_json_field(new_value)
                                if new_value:
                                    reviewer_notes = new_value.get("review_comments")
                            
                            if not reviewer_notes:
                                reviewer_notes = latest_action_dict.get("action")
                            
                            approval_dict["reviewer_notes"] = reviewer_notes
                            approval_dict["operation"] = latest_action_dict.get("action")
                            
                            logger.info(f"[HITL] 获取到操作记录: approval_id={approval_id}, action={approval_dict['operation']}, notes={reviewer_notes}")
                        else:
                            logger.info(f"[HITL] 未找到操作记录: task_id={task_id}")
                    except Exception as e:
                        logger.warning(f"[HITL] 获取操作记录失败: {str(e)}")
                
                result_approvals.append(HITLApproval(**approval_dict))
                logger.info(f"[HITL] 成功添加 approval: approval_id={approval_id}")
            except Exception as e:
                logger.error(f"[HITL] 处理 approval 失败: {str(e)}")
        
        return result_approvals

    except (ValueError, KeyError) as e:
        logger.error(f"获取审批历史数据错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"获取审批历史数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"获取审批历史IO错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取审批历史IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"获取审批历史失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取审批历史失败: {str(e)}")


@router.post("/hitl/approve", response_model=HITLApproval)
async def create_approval(
    request: HITLApprovalCreate,
    current_user: User = Depends(deps.get_current_user)
):
    """
    创建HITL审批请求

    创建一个需要人工审批的操作请求
    """
    try:
        approval_id = str(uuid.uuid4())
        now = datetime.now()

        approval = HITLApproval(
            approval_id=approval_id,
            task_id=request.task_id,
            user_id=str(current_user.id),
            operation=request.operation,
            details=request.details,
            risk_level=request.risk_level,
            status=ApprovalStatus.PENDING,
            created_at=now,
            expires_at=now + timedelta(hours=24)
        )

        hitl_approvals_storage[approval_id] = approval

        logger.info(f"创建HITL审批请求成功 - approval_id: {approval_id}, task_id: {request.task_id}")

        return approval

    except (ValueError, KeyError) as e:
        logger.error(f"创建审批请求数据错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"创建审批请求数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"创建审批请求IO错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建审批请求IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"创建审批请求失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建审批请求失败: {str(e)}")


@router.post("/hitl/{approval_id}/review", response_model=HITLApproval)
async def review_approval(
    approval_id: str,
    request: HITLApprovalReview,
    current_user: User = Depends(deps.get_current_user)
):
    """
    审核HITL审批请求

    审批或拒绝指定的审批请求
    """
    try:
        if approval_id not in hitl_approvals_storage:
            raise HTTPException(status_code=404, detail="审批请求不存在")

        approval = hitl_approvals_storage[approval_id]

        if approval.status != ApprovalStatus.PENDING:
            raise HTTPException(status_code=400, detail="该审批请求已处理")

        if approval.expires_at < datetime.now():
            approval.status = ApprovalStatus.TIMEOUT
            raise HTTPException(status_code=400, detail="该审批请求已过期")

        if request.action == "approve":
            approval.status = ApprovalStatus.APPROVED
        else:
            approval.status = ApprovalStatus.REJECTED

        approval.reviewed_at = datetime.now()
        approval.reviewer_notes = request.notes
        approval.operator_user_id = str(current_user.id)
        approval.operator_name = current_user.full_name or current_user.nickname or current_user.username or current_user.email
        approval.applicant_user_id = approval.user_id
        approval.applicant_name = approval.user_name

        logger.info(f"HITL审批完成 - approval_id: {approval_id}, action: {request.action}, reviewer: {current_user.id}")

        try:
            if redis_service.client:
                result_text = "已通过" if approval.status == ApprovalStatus.APPROVED else "已驳回"
                now_iso = datetime.utcnow().isoformat()
                notification = {
                    "id": f"notif_{uuid.uuid4().hex}",
                    "user_id": approval.user_id,
                    "title": "人工审核处理结果",
                    "message": f"您的申请「{approval.operation}」{result_text}",
                    "notification_type": "success" if approval.status == ApprovalStatus.APPROVED else "warning",
                    "type": "success" if approval.status == ApprovalStatus.APPROVED else "warning",
                    "priority": "high",
                    "source": "hitl",
                    "metadata": {
                        "approval_id": approval.approval_id,
                        "task_id": approval.task_id,
                        "status": approval.status.value,
                        "operator_id": str(current_user.id),
                        "operator_name": approval.operator_name,
                        "reviewer_notes": approval.reviewer_notes,
                    },
                    "action_url": "/hitl-approval",
                    "created_at": now_iso,
                    "timestamp": now_iso,
                    "is_read": False,
                    "read": False,
                }
                key = f"notification:user:{approval.user_id}"
                redis_service.client.lpush(key, json.dumps(notification, ensure_ascii=False))
                redis_service.client.expire(key, 604800)
        except Exception as e:
            logger.warning(f"[HITL] 发送审批结果通知失败: {e}")

        return approval

    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"审核审批请求数据错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"审核审批请求数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"审核审批请求IO错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"审核审批请求IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"审核审批请求失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"审核审批请求失败: {str(e)}")


# ==========================================
# 会话管理端点
# ==========================================

session_context_storage: Dict[str, SessionContext] = {}


@router.get("/session/{session_id}", response_model=SessionContext)
async def get_session_context(
    session_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取会话上下文

    返回指定会话的完整上下文信息
    """
    if session_id not in session_context_storage:
        session_context = SessionContext(
            session_id=session_id,
            user_id=str(current_user.id),
            state="active",
            pending_questions=[],
            historical_results={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        session_context_storage[session_id] = session_context

    return session_context_storage[session_id]


@router.get("/pipelines/history", response_model=List[TaskPipeline])
async def get_pipeline_history(
    limit: int = Query(50, ge=1, le=100),
    session_id: Optional[str] = Query(None),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取任务管道历史

    返回历史任务管道列表
    """
    logger.info(f"获取任务管道历史 - user_id: {current_user.id}, limit: {limit}")

    return []


# ==========================================
# 意图分类端点
# ==========================================
import numpy as np

INTENT_KEYWORDS = {
    "tax": ["税务", "税收", "税", "纳税", "报税", "企业所得税", "增值税", "个人所得税"],
    "legal": ["法律", "合同", "法规", "条款", "权利", "义务", "违法", "合规"],
    "finance": ["财务", "会计", "报表", "资产", "负债", "利润", "成本", "预算"],
    "audit": ["审计", "检查", "核查", "盘点"],
    "expense": ["报销", "费用", "支出", "差旅"],
}

INTENT_EXAMPLES = {
    "greeting": [
        "你好",
        "您好",
        "早上好",
        "在吗",
        "hello",
    ],
    "chitchat": [
        "今天天气怎么样",
        "周末去哪里玩",
        "中午吃什么",
        "推荐一部电影",
        "最近有什么新闻",
    ],
    "tax": [
        "企业所得税怎么计算",
        "增值税发票如何抵扣",
        "个人所得税申报",
        "税务筹划方案",
        "企业税收优惠",
    ],
    "legal": [
        "合同审查注意事项",
        "劳动合同权利义务",
        "企业合规管理",
        "合同违约处理",
        "知识产权保护",
    ],
    "finance": [
        "财务报表分析",
        "利润表制作",
        "企业成本控制",
        "预算编制流程",
        "现金流量管理",
    ],
    "audit": [
        "年度审计报告",
        "内部审计流程",
        "审计资料准备",
        "库存盘点流程",
        "财务审计注意",
    ],
    "expense": [
        "报销流程说明",
        "差旅费报销标准",
        "员工报销单填写",
        "费用预算控制",
        "报销审核流程",
    ],
}

INTENT_HIGH_RISK_KEYWORDS = [
    "删除", "批量", "导出", "全部", "敏感", "配置", "权限", "税务申报",
    "合同生成", "审计请求", "外部共享", "清空", "修改系统"
]

_embedding_cache: Dict[str, List[float]] = {}
_embedding_adapter = None


def _get_embedding_adapter():
    """获取或创建 Embedding 适配器（单例模式）"""
    global _embedding_adapter
    if _embedding_adapter is None:
        try:
            from app.services.embedding_factory import EmbeddingAdapterFactory
            _embedding_adapter = EmbeddingAdapterFactory.create_adapter("zhipu")
            logger.info("✅ 意图分类 Embedding 适配器初始化成功")
        except (ValueError, KeyError) as e:
            logger.error(f"❌ Embedding 适配器初始化数据错误: {e}")
            return None
        except (OSError, IOError) as e:
            logger.error(f"❌ Embedding 适配器初始化IO错误: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Embedding 适配器初始化失败: {e}")
            return None
    return _embedding_adapter


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """计算两个向量的余弦相似度"""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot_product / (norm1 * norm2))


async def _get_embeddings_batch(texts: List[str]) -> Dict[str, Optional[List[float]]]:
    """批量获取文本的 embedding 向量"""
    adapter = _get_embedding_adapter()
    if adapter is None:
        return {t: None for t in texts}
    
    texts_to_fetch = [t for t in texts if t not in _embedding_cache]
    
    if texts_to_fetch:
        try:
            embeddings, _ = await adapter.encode(texts_to_fetch, task_type="query")
            for i, text in enumerate(texts_to_fetch):
                _embedding_cache[text] = embeddings[i]
            if len(_embedding_cache) > 1000:
                oldest_keys = list(_embedding_cache.keys())[:100]
                for k in oldest_keys:
                    del _embedding_cache[k]
        except (ValueError, KeyError) as e:
            logger.error(f"批量 Embedding 获取数据错误: {e}")
            return {t: None for t in texts}
        except (OSError, IOError) as e:
            logger.error(f"批量 Embedding 获取IO错误: {e}")
            return {t: None for t in texts}
        except Exception as e:
            logger.error(f"批量 Embedding 获取失败: {e}")
            return {t: None for t in texts}
    
    return {t: _embedding_cache.get(t) for t in texts}


async def _compute_embedding_similarity(message: str) -> Dict[str, float]:
    """计算消息与各类别的 embedding 相似度（优化版）"""
    all_texts = [message]
    for examples in INTENT_EXAMPLES.values():
        all_texts.extend(examples)
    
    embeddings = await _get_embeddings_batch(all_texts)
    message_vector = embeddings.get(message)
    
    if message_vector is None:
        return {}
    
    similarities = {}
    for intent, examples in INTENT_EXAMPLES.items():
        example_vectors = []
        for example in examples:
            vec = embeddings.get(example)
            if vec is not None:
                example_vectors.append(vec)
        
        if not example_vectors:
            similarities[intent] = 0.0
            continue
        
        sims = [cosine_similarity(message_vector, ev) for ev in example_vectors]
        similarities[intent] = max(sims) if sims else 0.0
    
    return similarities


async def classify_single_intent(message: str, use_advanced: bool = True) -> IntentClassificationResult:
    """单条意图分类（两阶段：关键词 + Embedding）"""
    matched_keywords = []
    detected_intents = []
    is_greeting = False

    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in message:
                matched_keywords.append(keyword)
                detected_intents.append(intent)
                break

    is_high_risk = any(kw in message for kw in INTENT_HIGH_RISK_KEYWORDS)
    is_expense_related = "expense" in detected_intents or any(
        kw in message for kw in ["报销", "费用", "支出"]
    )

    stage = "keyword"
    confidence = min(len(detected_intents) * 0.3 + 0.4, 0.95)
    embedding_score: Optional[float] = None

    if use_advanced and not detected_intents:
        stage = "embedding"
        similarities = await _compute_embedding_similarity(message)
        
        if similarities:
            sorted_sims = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
            best_intent = sorted_sims[0][0]
            best_score = sorted_sims[0][1]
            avg_score = sum(s for _, s in sorted_sims) / len(sorted_sims)
            embedding_score = best_score

            if best_intent in ["greeting", "chitchat"]:
                is_greeting = True
                detected_intents = [best_intent]
                confidence = 0.95
                reasoning = f"问候/闲聊类别: {best_intent} ({best_score:.2%})"
            elif best_score >= 0.55 and (best_score - avg_score) >= 0.15:
                detected_intents = [best_intent]
                confidence = min(best_score * 0.8 + 0.2, 0.95)
                reasoning = f"向量相似度最高: {best_intent} ({best_score:.2%})，差异显著"
            else:
                detected_intents = []
                reasoning = f"无明确业务意图 (最高: {best_intent} {best_score:.2%})"
        else:
            reasoning = "Embedding 计算失败，无法使用高级分类"
    else:
        reasoning = ""

    keyword_matched = ", ".join(set(matched_keywords)) if matched_keywords else "无"
    reasoning_parts = []
    if matched_keywords:
        reasoning_parts.append(f"关键词: {keyword_matched}")
    if stage == "embedding" and embedding_score is not None and not is_greeting:
        reasoning_parts.append(f"向量相似度: {embedding_score:.2%}")
    if is_high_risk:
        reasoning_parts.append("⚠️高风险关键词")
    if is_expense_related:
        reasoning_parts.append("💰费用相关")

    final_reasoning = " | ".join(reasoning_parts) if reasoning_parts else reasoning

    should_process = is_expense_related or is_high_risk or (len(detected_intents) > 0 and detected_intents[0] not in ["greeting", "chitchat"])

    return IntentClassificationResult(
        stage=stage,
        intent=", ".join(detected_intents) if detected_intents else "general",
        confidence=confidence,
        embedding_score=embedding_score,
        is_expense_related=is_expense_related,
        should_process=should_process,
        matched_keywords=list(set(matched_keywords)),
        reasoning=final_reasoning
    )


@router.post("/intent/classify", response_model=IntentClassificationResult)
async def classify_intent(
    request: dict,
    current_user: User = Depends(deps.get_current_user)
):
    """
    意图分类

    对用户消息进行意图分类
    """
    message = request.get("message", "")
    use_advanced = request.get("use_advanced", True)

    logger.info(f"意图分类 - user_id: {current_user.id}, message: {message[:50]}...")

    result = await classify_single_intent(message, use_advanced)

    logger.info(f"意图分类结果 - intent: {result.intent}, confidence: {result.confidence}")

    from app.services.operation_log_service import log_intent_classification
    log_intent_classification(
        user_id=str(current_user.id),
        message=message,
        intent=result.intent,
        confidence=result.confidence
    )

    return result


@router.post("/intent/test", response_model=List[IntentClassificationResult])
async def test_intent_classification(
    request: dict,
    current_user: User = Depends(deps.get_current_user)
):
    """
    批量意图分类测试

    对多条消息进行意图分类测试
    """
    messages = request.get("messages", [])

    if not messages:
        raise HTTPException(status_code=400, detail="消息列表不能为空")

    logger.info(f"批量意图分类测试 - user_id: {current_user.id}, count: {len(messages)}")

    results = []
    for msg in messages:
        result = await classify_single_intent(msg)
        results.append(result)

    logger.info(f"批量意图分类完成 - 处理了 {len(results)} 条消息")

    return results


# ==========================================
# 安全审计端点
# ==========================================

security_events_storage: List[SecurityEvent] = []


def record_security_event(
    event_type: SecurityEventType,
    user_id: str,
    severity: SecurityEventSeverity,
    details: Dict[str, Any] = None,
    tenant_id: str = None,
    target_resource: str = None,
    ip_address: str = None,
    user_agent: str = None
) -> SecurityEvent:
    """记录安全事件"""
    event = SecurityEvent(
        event_id=f"sec_{uuid.uuid4().hex[:12]}",
        event_type=event_type,
        user_id=user_id,
        tenant_id=tenant_id,
        target_resource=target_resource,
        details=details or {},
        severity=severity,
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=datetime.now()
    )
    security_events_storage.append(event)

    if len(security_events_storage) > 1000:
        security_events_storage.pop(0)

    return event


@router.get("/security/events", response_model=List[SecurityEvent])
async def get_security_events(
    severity: Optional[str] = Query(None, description="按严重级别筛选"),
    event_type: Optional[str] = Query(None, description="按事件类型筛选"),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取安全事件列表

    返回最近的安全事件记录
    """
    logger.info(f"获取安全事件 - user_id: {current_user.id}, severity: {severity}, limit: {limit}")

    filtered_events = security_events_storage.copy()

    if severity:
        filtered_events = [e for e in filtered_events if e.severity.value == severity]

    if event_type:
        filtered_events = [e for e in filtered_events if e.event_type.value == event_type]

    filtered_events.sort(key=lambda x: x.created_at, reverse=True)

    return filtered_events[:limit]


@router.get("/security/stats", response_model=SecurityStats)
async def get_security_stats(
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取安全统计信息

    返回安全事件的统计摘要
    """
    logger.info(f"获取安全统计 - user_id: {current_user.id}")

    by_severity: Dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    by_type: Dict[str, int] = {}

    for event in security_events_storage:
        by_severity[event.severity.value] = by_severity.get(event.severity.value, 0) + 1
        event_type_value = event.event_type.value
        by_type[event_type_value] = by_type.get(event_type_value, 0) + 1

    recent_trends = []
    now = datetime.now()
    for i in range(7):
        date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        count = sum(1 for e in security_events_storage
                   if e.created_at.strftime("%Y-%m-%d") == date)
        recent_trends.append({"date": date, "count": count})

    return SecurityStats(
        total_events=len(security_events_storage),
        by_severity=by_severity,
        by_type=by_type,
        recent_trends=recent_trends
    )


# ==========================================
# 全局操作日志记录
# ==========================================

def log_user_action(
    action: str,
    user_id: str,
    details: Dict[str, Any] = None,
    tenant_id: str = None
):
    """记录用户操作日志"""
    logger.info(f"[用户操作] {action} - user_id: {user_id}, tenant_id: {tenant_id}, details: {details}")

    record_security_event(
        event_type=SecurityEventType.HIGH_RISK_OPERATION,
        user_id=user_id,
        tenant_id=tenant_id,
        severity=SecurityEventSeverity.LOW,
        details={
            "action": action,
            "details": details or {}
        }
    )


@router.get("/operations/logs")
async def get_operation_logs(
    limit: int = Query(100, ge=1, le=500),
    operation_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    获取操作日志

    返回用户的操作日志记录
    """
    from app.services.operation_log_service import operation_logger

    logger.info(f"获取操作日志 - user_id: {current_user.id}, limit: {limit}")

    logs = operation_logger.get_tenant_operations(
        tenant_id=tenant_context['tenant_id'],
        limit=limit,
        operation_type=operation_type,
        risk_level=risk_level
    )

    return {
        "total": len(logs),
        "logs": logs
    }


@router.get("/operations/stats")
async def get_operation_stats(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    获取操作统计

    返回操作统计信息
    """
    from app.services.operation_log_service import operation_logger

    logger.info(f"获取操作统计 - user_id: {current_user.id}, days: {days}")

    stats = operation_logger.get_statistics(
        tenant_id=tenant_context['tenant_id'],
        days=days
    )

    return stats
