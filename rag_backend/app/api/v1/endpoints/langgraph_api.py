"""
LangGraph API 端点

基于 LangGraph 的多智能体工作流 API
提供持久化、流式输出、人工介入等功能
"""

import uuid
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api import deps
from app.models.user import User
from app.langgraph import (
    MultiAgentWorkflowBuilder
)
from app.langgraph.persistences import (
    get_checkpointer
)

logger = logging.getLogger(__name__)
router = APIRouter()


class LangGraphQueryRequest(BaseModel):
    """LangGraph 查询请求"""
    query: str = Field(..., description="用户查询")
    session_id: Optional[str] = Field(None, description="会话ID，不提供则自动生成")
    thread_id: Optional[str] = Field(None, description="LangGraph thread ID")
    enable_reflection: bool = Field(True, description="是否启用反思审核")
    enable_streaming: bool = Field(False, description="是否启用流式输出")
    enable_persistence: bool = Field(True, description="是否启用状态持久化")
    confidence_threshold: float = Field(0.7, ge=0.0, le=1.0, description="置信度阈值")
    max_iterations: int = Field(10, ge=1, le=50, description="最大迭代次数")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="额外元数据")


class LangGraphQueryResponse(BaseModel):
    """LangGraph 查询响应"""
    session_id: str
    thread_id: str
    final_answer: str
    intent: Optional[str] = None
    intent_confidence: float = 0.0
    target_specialists: List[str] = Field(default_factory=list)
    quality_score: Optional[float] = None
    quality_level: Optional[str] = None
    needs_human_review: bool = False
    processing_time_ms: float = 0.0
    nodes_executed: List[str] = Field(default_factory=list)
    iteration: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowStatusResponse(BaseModel):
    """工作流状态响应"""
    thread_id: str
    status: str
    current_node: Optional[str] = None
    checkpoint_available: bool
    last_updated: Optional[datetime] = None


_workflow_builders: Dict[str, MultiAgentWorkflowBuilder] = {}
_workflow_configs: Dict[str, Dict[str, Any]] = {}


def get_workflow_builder(
    tenant_id: str,
    enable_reflection: bool = True,
    enable_persistence: bool = True
) -> MultiAgentWorkflowBuilder:
    """获取或创建工作流构建器"""
    key = f"{tenant_id}_{enable_reflection}_{enable_persistence}"
    
    if key not in _workflow_builders:
        agents_registry = _create_agents_registry()
        
        builder = MultiAgentWorkflowBuilder(
            agents_registry=agents_registry,
            enable_checkpointer=enable_persistence,
            enable_reflection=enable_reflection,
            max_iterations=10,
            max_retries=3
        )
        
        builder.compile()
        _workflow_builders[key] = builder
        _workflow_configs[key] = {
            "tenant_id": tenant_id,
            "enable_reflection": enable_reflection,
            "enable_persistence": enable_persistence,
            "created_at": datetime.now()
        }
    
    return _workflow_builders[key]


def _create_agents_registry() -> Dict[str, Any]:
    """创建 Agent 注册表"""
    from app.agent_framework.llm.openai_adapter import OpenAIAdapter
    from app.agent_framework.tools.tool_manager import ToolManager
    from app.agent_framework.core.react_agent import ReActAgent
    from app.multi_agent_system.agents.intent_router_agent import IntentRouterAgent
    from app.multi_agent_system.agents.finance_specialist import FinanceSpecialist
    from app.multi_agent_system.agents.tax_specialist import TaxSpecialist
    from app.multi_agent_system.agents.legal_specialist import LegalSpecialist
    
    llm_adapter = OpenAIAdapter()
    tool_manager = ToolManager()
    
    registry = {
        "receptionist": ReActAgent(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt="你是一个友好的智能助手接待员..."
        ),
        "intent": IntentRouterAgent(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager
        ),
        "finance": FinanceSpecialist(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            enable_rag=True
        ),
        "tax": TaxSpecialist(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            enable_rag=True
        ),
        "legal": LegalSpecialist(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            enable_rag=True
        ),
        "reflection": None,  # 使用 review_quality 函数替代
        "rag_retriever": None,
        "aggregator": None,
        "direct_answer": None
    }
    
    return registry


@router.post("/query", response_model=LangGraphQueryResponse)
async def langgraph_query(
    request: LangGraphQueryRequest,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    LangGraph 多智能体查询
    
    特性：
    - 持久化执行：支持故障恢复
    - 条件路由：智能选择专家
    - 质量审核：反思机制
    - 可选流式输出
    """
    start_time = time.time()
    session_id = request.session_id or str(uuid.uuid4())
    thread_id = request.thread_id or str(uuid.uuid4())
    
    logger.info(f"[LangGraph API] 开始处理 | session={session_id[:8]} | query={request.query[:50]}...")
    
    try:
        builder = get_workflow_builder(
            tenant_id=tenant_context["tenant_id"],
            enable_reflection=request.enable_reflection,
            enable_persistence=request.enable_persistence
        )
        
        config = {"configurable": {"thread_id": thread_id}} if request.enable_persistence else {}
        
        result = await builder.invoke(
            session_id=session_id,
            tenant_id=tenant_context["tenant_id"],
            user_id=str(current_user.id),
            user_query=request.query,
            config=config,
            confidence_threshold=request.confidence_threshold,
            max_iterations=request.max_iterations,
            **request.metadata
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        quality_info = {}
        if result.get("reflection_result"):
            quality_info = {
                "quality_score": result["reflection_result"].overall_score,
                "quality_level": result["reflection_result"].quality_level.value
            }
        
        response = LangGraphQueryResponse(
            session_id=session_id,
            thread_id=thread_id,
            final_answer=result.get("final_answer", "无法处理您的请求"),
            intent=result.get("intent"),
            intent_confidence=result.get("intent_confidence", 0.0),
            target_specialists=[s.value for s in result.get("target_specialists", [])],
            needs_human_review=result.get("needs_human_review", False),
            processing_time_ms=processing_time,
            nodes_executed=result.get("metadata", {}).get("nodes_executed", []),
            iteration=result.get("iteration", 0),
            metadata={
                "specialist_count": len(result.get("specialist_results", [])),
                "retry_count": result.get("retry_count", 0),
                "error": result.get("error")
            },
            **quality_info
        )
        
        logger.info(f"[LangGraph API] 完成 | time={processing_time:.0f}ms | human_review={response.needs_human_review}")
        
        return response
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"[LangGraph API] 错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def langgraph_stream(
    request: LangGraphQueryRequest,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    LangGraph 流式查询
    
    SSE 流式输出，中间状态实时推送
    """
    session_id = request.session_id or str(uuid.uuid4())
    thread_id = request.thread_id or str(uuid.uuid4())
    
    logger.info(f"[LangGraph Stream] 开始 | session={session_id[:8]}...")
    
    async def event_generator():
        builder = get_workflow_builder(
            tenant_id=tenant_context["tenant_id"],
            enable_reflection=request.enable_reflection,
            enable_persistence=request.enable_persistence
        )
        
        config = {"configurable": {"thread_id": thread_id}} if request.enable_persistence else {}
        
        try:
            async for state in builder.stream(
                session_id=session_id,
                tenant_id=tenant_context["tenant_id"],
                user_id=str(current_user.id),
                user_query=request.query,
                config=config,
                confidence_threshold=request.confidence_threshold,
                **request.metadata
            ):
                node_name = state.get("metadata", {}).get("last_node", "unknown")
                
                event_data = {
                    "type": "state_update",
                    "session_id": session_id,
                    "thread_id": thread_id,
                    "node": node_name,
                    "iteration": state.get("iteration", 0),
                    "intent": state.get("intent"),
                    "specialist_count": len(state.get("specialist_results", [])),
                    "has_final_answer": state.get("final_answer") is not None
                }
                
                yield f"data: {event_data}\n\n"
                
                if state.get("final_answer"):
                    final_event = {
                        "type": "final",
                        "session_id": session_id,
                        "final_answer": state["final_answer"],
                        "needs_human_review": state.get("needs_human_review", False)
                    }
                    yield f"data: {final_event}\n\n"
                    break
                    
        except (ValueError, KeyError) as e:
            raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
        except (OSError, IOError) as e:
            raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
        except Exception as e:
            logger.error(f"[LangGraph Stream] 错误: {e}")
            error_event = {"type": "error", "error": str(e)}
            yield f"data: {error_event}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/status/{thread_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    thread_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    获取工作流状态
    
    用于检查持久化的工作流是否可以恢复
    """
    try:
        checkpointer = get_checkpointer()
        
        if checkpointer:
            checkpoint = await checkpointer.get(thread_id)
            if checkpoint:
                return WorkflowStatusResponse(
                    thread_id=thread_id,
                    status="paused",
                    current_node=checkpoint.get("current_node"),
                    checkpoint_available=True,
                    last_updated=checkpoint.get("timestamp")
                )
        
        return WorkflowStatusResponse(
            thread_id=thread_id,
            status="not_found",
            checkpoint_available=False
        )
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"[LangGraph Status] 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume/{thread_id}")
async def resume_workflow(
    thread_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    恢复暂停的工作流
    
    用于人工介入后的工作流恢复
    """
    try:
        builder = get_workflow_builder(
            tenant_id=tenant_context["tenant_id"],
            enable_reflection=True,
            enable_persistence=True
        )
        
        if not builder.compiled_graph:
            builder.compile()
        
        config = {"configurable": {"thread_id": thread_id}}
        
        result = await builder.compiled_graph.ainvoke(None, config=config)
        
        return {
            "status": "resumed",
            "thread_id": thread_id,
            "final_answer": result.get("final_answer"),
            "needs_human_review": result.get("needs_human_review", False)
        }
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"[LangGraph Resume] 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/workflow/{thread_id}")
async def delete_workflow(
    thread_id: str,
    current_user: User = Depends(deps.get_current_user),
    tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    删除工作流状态
    
    用于清理持久化的检查点
    """
    try:
        checkpointer = get_checkpointer()
        
        if checkpointer:
            await checkpointer.delete(thread_id)
        
        return {"status": "deleted", "thread_id": thread_id}
        
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"[LangGraph Delete] 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
