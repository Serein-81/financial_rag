# app/api/v1/endpoints/prompt_optimization.py

"""
Prompt 优化 API 端点

提供 Prompt 模板管理、性能分析和 A/B 测试的 API 接口
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.services.prompt_optimizer import get_prompt_optimizer
from app.services.prompt_ab_test import get_ab_test_manager


router = APIRouter()


# ==========================================
# Pydantic 模型
# ==========================================

class TemplateCreate(BaseModel):
    """创建模板请求"""
    name: str
    version: str
    template_text: str
    agent_type: str
    use_case: str = "general"
    variables: Optional[dict] = None
    description: Optional[str] = None
    is_baseline: bool = False


class TemplateResponse(BaseModel):
    """模板响应"""
    id: str
    name: str
    version: str
    agent_type: str
    use_case: str
    is_active: bool
    is_baseline: bool
    description: Optional[str]
    created_at: str


class ExecutionRecord(BaseModel):
    """执行记录请求"""
    template_id: UUID
    user_query: str
    trace_id: Optional[UUID] = None
    final_answer: Optional[str] = None
    execution_time: Optional[float] = None
    iterations_count: Optional[int] = None
    tool_calls_count: Optional[int] = None
    success: bool = True
    user_feedback: Optional[int] = Field(None, ge=1, le=5)
    auto_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class ABTestCreate(BaseModel):
    """创建 A/B 测试请求"""
    test_name: str
    template_a_id: UUID
    template_b_id: UUID
    traffic_split: float = Field(0.5, ge=0.0, le=1.0)
    description: Optional[str] = None


class ABTestResponse(BaseModel):
    """A/B 测试响应"""
    id: str
    test_name: str
    status: str
    template_a_id: str
    template_b_id: str
    traffic_split: float
    total_executions: int
    winner_template_id: Optional[str]


# ==========================================
# 模板管理端点
# ==========================================

@router.post("/templates", response_model=TemplateResponse)
async def create_template(
    template: TemplateCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新的 Prompt 模板"""
    optimizer = get_prompt_optimizer(db)
    
    result = await optimizer.create_template(
        name=template.name,
        version=template.version,
        template_text=template.template_text,
        agent_type=template.agent_type,
        use_case=template.use_case,
        variables=template.variables,
        description=template.description,
        is_baseline=template.is_baseline
    )
    
    return TemplateResponse(
        id=str(result.id),
        name=result.name,
        version=result.version,
        agent_type=result.agent_type,
        use_case=result.use_case,
        is_active=result.is_active,
        is_baseline=result.is_baseline,
        description=result.description,
        created_at=result.created_at.isoformat()
    )


@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates(
    agent_type: Optional[str] = None,
    use_case: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """列出 Prompt 模板"""
    optimizer = get_prompt_optimizer(db)
    
    templates = await optimizer.list_templates(
        agent_type=agent_type,
        use_case=use_case,
        is_active=is_active
    )
    
    return [
        TemplateResponse(
            id=str(t.id),
            name=t.name,
            version=t.version,
            agent_type=t.agent_type,
            use_case=t.use_case,
            is_active=t.is_active,
            is_baseline=t.is_baseline,
            description=t.description,
            created_at=t.created_at.isoformat()
        )
        for t in templates
    ]


@router.get("/templates/{template_id}")
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取模板详情"""
    optimizer = get_prompt_optimizer(db)
    
    template = await optimizer.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {
        "id": str(template.id),
        "name": template.name,
        "version": template.version,
        "template_text": template.template_text,
        "agent_type": template.agent_type,
        "use_case": template.use_case,
        "is_active": template.is_active,
        "is_baseline": template.is_baseline,
        "variables": template.variables,
        "description": template.description,
        "created_at": template.created_at.isoformat()
    }


@router.patch("/templates/{template_id}/status")
async def update_template_status(
    template_id: UUID,
    is_active: bool,
    db: AsyncSession = Depends(get_db)
):
    """更新模板状态"""
    optimizer = get_prompt_optimizer(db)
    
    template = await optimizer.update_template_status(template_id, is_active)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"message": "Template status updated", "is_active": template.is_active}


# ==========================================
# 执行记录端点
# ==========================================

@router.post("/executions")
async def record_execution(
    execution: ExecutionRecord,
    db: AsyncSession = Depends(get_db)
):
    """记录 Prompt 执行结果"""
    optimizer = get_prompt_optimizer(db)
    
    result = await optimizer.record_execution(
        template_id=execution.template_id,
        user_query=execution.user_query,
        trace_id=execution.trace_id,
        final_answer=execution.final_answer,
        execution_time=execution.execution_time,
        iterations_count=execution.iterations_count,
        tool_calls_count=execution.tool_calls_count,
        success=execution.success,
        user_feedback=execution.user_feedback,
        auto_score=execution.auto_score,
        error_type=execution.error_type,
        error_message=execution.error_message
    )
    
    return {
        "message": "Execution recorded",
        "execution_id": str(result.id)
    }


@router.get("/templates/{template_id}/executions")
async def get_template_executions(
    template_id: UUID,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """获取模板的执行记录"""
    optimizer = get_prompt_optimizer(db)
    
    executions = await optimizer.get_template_executions(template_id, limit)
    
    return {
        "template_id": str(template_id),
        "total": len(executions),
        "executions": [
            {
                "id": str(e.id),
                "user_query": e.user_query,
                "success": e.success,
                "execution_time": e.execution_time,
                "iterations_count": e.iterations_count,
                "auto_score": e.auto_score,
                "created_at": e.created_at.isoformat()
            }
            for e in executions
        ]
    }


# ==========================================
# 性能分析端点
# ==========================================

@router.get("/templates/{template_id}/performance")
async def analyze_template_performance(
    template_id: UUID,
    days: int = 7,
    db: AsyncSession = Depends(get_db)
):
    """分析模板性能"""
    optimizer = get_prompt_optimizer(db)
    
    performance = await optimizer.analyze_template_performance(template_id, days)
    
    return performance


@router.get("/templates/compare")
async def compare_templates(
    template_a_id: UUID,
    template_b_id: UUID,
    days: int = 7,
    db: AsyncSession = Depends(get_db)
):
    """比较两个模板的性能"""
    optimizer = get_prompt_optimizer(db)
    
    comparison = await optimizer.compare_templates(template_a_id, template_b_id, days)
    
    return comparison


@router.get("/templates/{template_id}/suggestions")
async def get_optimization_suggestions(
    template_id: UUID,
    days: int = 7,
    db: AsyncSession = Depends(get_db)
):
    """获取优化建议"""
    optimizer = get_prompt_optimizer(db)
    
    suggestions = await optimizer.get_optimization_suggestions(template_id, days)
    
    return {
        "template_id": str(template_id),
        "suggestions": suggestions
    }


# ==========================================
# A/B 测试端点
# ==========================================

@router.post("/ab-tests", response_model=ABTestResponse)
async def create_ab_test(
    test: ABTestCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建 A/B 测试"""
    manager = get_ab_test_manager(db)
    
    result = await manager.create_test(
        test_name=test.test_name,
        template_a_id=test.template_a_id,
        template_b_id=test.template_b_id,
        traffic_split=test.traffic_split,
        description=test.description
    )
    
    return ABTestResponse(
        id=str(result.id),
        test_name=result.test_name,
        status=result.status,
        template_a_id=str(result.template_a_id),
        template_b_id=str(result.template_b_id),
        traffic_split=result.traffic_split,
        total_executions=result.total_executions,
        winner_template_id=str(result.winner_template_id) if result.winner_template_id else None
    )


@router.get("/ab-tests", response_model=List[ABTestResponse])
async def list_ab_tests(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """列出 A/B 测试"""
    manager = get_ab_test_manager(db)
    
    tests = await manager.list_tests(status=status)
    
    return [
        ABTestResponse(
            id=str(t.id),
            test_name=t.test_name,
            status=t.status,
            template_a_id=str(t.template_a_id),
            template_b_id=str(t.template_b_id),
            traffic_split=t.traffic_split,
            total_executions=t.total_executions,
            winner_template_id=str(t.winner_template_id) if t.winner_template_id else None
        )
        for t in tests
    ]


@router.get("/ab-tests/{test_id}/results")
async def get_ab_test_results(
    test_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取 A/B 测试结果"""
    manager = get_ab_test_manager(db)
    
    results = await manager.analyze_test_results(test_id)
    
    return results


@router.post("/ab-tests/{test_id}/complete")
async def complete_ab_test(
    test_id: UUID,
    winner: str,  # "template_a" or "template_b"
    db: AsyncSession = Depends(get_db)
):
    """手动完成 A/B 测试"""
    manager = get_ab_test_manager(db)
    
    # 获取测试
    test = await manager.get_test(test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # 确定获胜者 ID
    winner_id = test.template_a_id if winner == "template_a" else test.template_b_id
    
    # 更新状态
    await manager.update_test_status(test_id, "completed", winner_id)
    
    return {"message": "Test completed", "winner": winner}


@router.get("/ab-tests/{test_name}/select-template")
async def select_template_for_test(
    test_name: str,
    db: AsyncSession = Depends(get_db)
):
    """根据 A/B 测试选择模板"""
    manager = get_ab_test_manager(db)
    
    template_id = await manager.select_template(test_name)
    
    if not template_id:
        raise HTTPException(status_code=404, detail="Test not found or not running")
    
    return {"template_id": str(template_id)}
