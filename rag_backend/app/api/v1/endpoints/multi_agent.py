"""
多智能体系统 API 端点
提供多智能体协作、意图分析、专家查询等核心功能
"""

import uuid
import time
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

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
    ErrorResponse,
    SpecialistType,
    SpecialistResult,
    IntentAnalysisResult,
    ReflectionResult
)
from app.api import deps
from app.models.user import User
from app.multi_agent_system import AgentOrchestrator, OrchestrationContext
from app.multi_agent_system.agents import (
    FinanceSpecialist,
    TaxSpecialist,
    LegalSpecialist,
    ReflectionSpecialist,
    ReportGenerator
)
from app.agent_framework.llm.base_adapter import BaseLLMAdapter

logger = logging.getLogger(__name__)
router = APIRouter()

orchestrator: Optional[AgentOrchestrator] = None
finance_specialist: Optional[FinanceSpecialist] = None
tax_specialist: Optional[TaxSpecialist] = None
legal_specialist: Optional[LegalSpecialist] = None
reflection_specialist: Optional[ReflectionSpecialist] = None


def get_orchestrator():
    """获取或创建编排器实例"""
    global orchestrator
    if orchestrator is None:
        orchestrator = AgentOrchestrator()
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


def get_reflection_specialist():
    """获取或创建反思专家实例"""
    global reflection_specialist
    if reflection_specialist is None:
        reflection_specialist = ReflectionSpecialist()
    return reflection_specialist


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
    start_time = time.time()
    request_id = str(uuid.uuid4())
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        logger.info(f"处理多智能体查询 - 请求ID: {request_id}, 会话ID: {session_id}")
        logger.info(f"用户查询: {request.query}")
        
        orch = get_orchestrator()
        
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
        
        result = await orch.process(context)
        
        processing_time = time.time() - start_time
        
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
        
    except Exception as e:
        logger.error(f"处理多智能体查询失败 - 请求ID: {request_id}, 错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理查询失败: {str(e)}")


@router.post("/specialist/query", response_model=SpecialistQueryResponse)
async def query_specialist(
    request: SpecialistQueryRequest,
    current_user: User = Depends(deps.get_current_user)
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
        elif specialist_type == SpecialistType.REFLECTION:
            specialist = get_reflection_specialist()
            result = await specialist.run(
                query=request.query,
                context=request.context,
                **request.parameters
            )
        else:
            raise HTTPException(status_code=400, detail=f"不支持的专家类型: {specialist_type}")
        
        processing_time = time.time() - start_time
        
        return SpecialistQueryResponse(
            specialist_type=specialist_type,
            success=True,
            result=result,
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
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
    except Exception as e:
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.LEGAL,
            is_available=False,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message=f"异常: {str(e)}"
        ))
        overall_healthy = False
    
    try:
        reflection = get_reflection_specialist()
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.REFLECTION,
            is_available=True,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message="正常运行"
        ))
    except Exception as e:
        agents_status.append(AgentHealthStatus(
            agent_type=SpecialistType.REFLECTION,
            is_available=False,
            response_time=None,
            last_heartbeat=datetime.now(),
            status_message=f"异常: {str(e)}"
        ))
        overall_healthy = False
    
    orchestrator_healthy = get_orchestrator() is not None
    
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
    current_user: User = Depends(deps.get_current_user)
):
    """
    生成多智能体分析报告
    
    基于历史会话生成结构化报告
    """
    try:
        from datetime import datetime
        import json
        
        report_id = str(uuid.uuid4())
        
        orch = get_orchestrator()
        
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
        
    except Exception as e:
        logger.error(f"生成报告失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")
