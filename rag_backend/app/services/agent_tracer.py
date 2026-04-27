# app/services/agent_tracer.py

"""
Agent 追踪服务

提供 Agent 执行追踪的核心功能
支持双写：本地数据库 + LangSmith
"""

import time
import logging
import asyncio
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func
from app.db.session import AsyncSessionLocal
from app.models.agent_trace import AgentTrace, AgentStep
from app.langsmith_integration import get_tracer, get_langsmith_config

logger = logging.getLogger(__name__)


class AgentTracerSession:
    """Agent追踪会话上下文管理器
    
    为每个trace维护独立的数据库会话，
    减少事务数量并确保数据完整性
    """
    
    def __init__(self, tracer: 'AgentTracer', trace_id: str, user_id: str, tenant_id: str):
        self.tracer = tracer
        self.trace_id = trace_id
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.db = None
        self.pending_steps: List[AgentStep] = []
        self._closed = False
    
    async def __aenter__(self):
        self.db = AsyncSessionLocal()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._closed:
            return
        
        try:
            if self.pending_steps:
                self.db.add_all(self.pending_steps)
                await self.db.commit()
        except Exception as e:
            logger.error(f"AgentTracerSession commit失败: {e}")
            await self.db.rollback()
        finally:
            await self.db.close()
            self._closed = True
    
    async def add_step(self, step_data: Dict[str, Any]) -> None:
        """添加步骤到缓冲"""
        step = AgentStep(
            trace_id=self.trace_id,
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            **step_data
        )
        self.pending_steps.append(step)
    
    async def flush_steps(self) -> None:
        """手动刷新缓冲（可选调用）"""
        if self.pending_steps:
            self.db.add_all(self.pending_steps)
            await self.db.flush()
            self.pending_steps = []


class AgentTracer:
    """
    Agent 追踪服务
    
    负责记录和查询 Agent 的执行过程
    支持双写模式：本地数据库（业务必需）+ LangSmith（LLM 调试）
    
    优化：使用缓冲机制减少事务数量
    """
    
    def __init__(self):
        self.langsmith_tracer = None
        self.langsmith_enabled = False
        self._init_langsmith()
        self._current_trace_id: Optional[str] = None
        self._current_user_id: Optional[str] = None
        self._current_tenant_id: Optional[str] = None
        self._pending_steps: List[AgentStep] = []
        self._lock = asyncio.Lock()
    
    def _init_langsmith(self):
        """初始化 LangSmith 追踪器"""
        config = get_langsmith_config()
        if config.get("enabled"):
            try:
                self.langsmith_tracer = get_tracer()
                self.langsmith_enabled = True
                logger.info(f"[AgentTracer] LangSmith 集成已启用 | 项目: {config.get('project')}")
            except Exception as e:
                logger.warning(f"[AgentTracer] LangSmith 初始化失败: {e}")
                self.langsmith_enabled = False
        else:
            logger.info("[AgentTracer] LangSmith 未启用，仅使用本地数据库追踪")
    
    async def start_trace(
        self,
        agent_type: str,
        user_query: str,
        user_id: str,
        tenant_id: str,
        session_id: str = None,
        message_id: str = None
    ) -> str:
        """
        开始一次新的追踪
        
        Args:
            agent_type: Agent 类型（react/plan/reflect）
            user_query: 用户查询
            user_id: 用户 ID
            tenant_id: 租户 ID
            session_id: 会话 ID（可选）
            message_id: 消息 ID（可选）
            
        Returns:
            trace_id: 追踪 ID
        """
        langsmith_run_id = None
        if self.langsmith_enabled and self.langsmith_tracer:
            try:
                with self.langsmith_tracer.trace_agent_run(
                    agent_name=agent_type,
                    agent_type=agent_type,
                    user_query=user_query,
                    session_id=session_id,
                    metadata={"message_id": message_id} if message_id else None
                ) as run_id:
                    langsmith_run_id = run_id
            except Exception as e:
                logger.warning(f"[AgentTracer] LangSmith start_trace 失败: {e}")
        
        async with AsyncSessionLocal() as db:
            trace = AgentTrace(
                agent_type=agent_type,
                user_query=user_query,
                user_id=user_id,
                tenant_id=tenant_id,
                session_id=session_id,
                message_id=message_id,
                status="running"
            )
            
            db.add(trace)
            await db.commit()
            await db.refresh(trace)
            
            async with self._lock:
                self._current_trace_id = str(trace.id)
                self._current_user_id = user_id
                self._current_tenant_id = tenant_id
                self._pending_steps = []
            
            logger.info(f"🎬 开始追踪: {trace.id} | Agent: {agent_type} | User: {user_id}")
            if langsmith_run_id:
                logger.debug(f"[AgentTracer] LangSmith Run ID: {langsmith_run_id}")
            
            return str(trace.id)
    
    async def add_step(
        self,
        trace_id: str,
        step_number: int,
        step_type: str,
        content: str,
        tool_name: str = None,
        tool_input: Dict = None,
        tool_output: str = None,
        tool_duration: float = None,
        confidence: float = None,
        metadata: Dict = None
    ):
        """
        添加执行步骤
        
        Args:
            trace_id: 追踪 ID
            step_number: 步骤编号
            step_type: 步骤类型（thought/action/observation/final_answer）
            content: 步骤内容
            tool_name: 工具名称（可选）
            tool_input: 工具输入（可选）
            tool_output: 工具输出（可选）
            tool_duration: 工具执行时间（可选）
            confidence: 置信度（可选）
            metadata: 元数据（可选）
        
        优化：使用缓冲机制，将多个step缓存在内存中，
        减少事务提交次数。只在end_trace时统一提交。
        """
        async with self._lock:
            step = AgentStep(
                trace_id=trace_id,
                user_id=self._current_user_id,
                tenant_id=self._current_tenant_id,
                step_number=step_number,
                step_type=step_type,
                content=content,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
                tool_duration=tool_duration,
                confidence=confidence,
                extra_metadata=metadata,
                timestamp=time.time()
            )
            
            if self._current_trace_id == trace_id:
                self._pending_steps.append(step)
            else:
                async with AsyncSessionLocal() as db:
                    db.add(step)
                    await db.commit()
            
            icon = self._get_step_icon(step_type)
            logger.debug(f"{icon} Step {step_number} ({step_type}): {content[:50]}...")
        
        if self.langsmith_enabled and self.langsmith_tracer:
            try:
                self.langsmith_tracer.add_agent_step(
                    parent_run_id=trace_id,
                    step_type=step_type,
                    content=content,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    tool_output=tool_output,
                    duration_ms=tool_duration
                )
            except Exception as e:
                logger.warning(f"[AgentTracer] LangSmith add_step 失败: {e}")
    
    async def end_trace(
        self,
        trace_id: str,
        final_answer: str,
        success: bool = True,
        error_message: str = None
    ):
        """
        结束追踪
        
        Args:
            trace_id: 追踪 ID
            final_answer: 最终答案
            success: 是否成功
            error_message: 错误信息（如果失败）
        
        优化：提交所有pending的steps，减少事务数量
        """
        try:
            # 确保 final_answer 是字符串
            if not isinstance(final_answer, str):
                final_answer = str(final_answer) if final_answer else ""
            
            async with AsyncSessionLocal() as db:
                pending_steps_to_commit = []
                async with self._lock:
                    if self._current_trace_id == trace_id and self._pending_steps:
                        pending_steps_to_commit = self._pending_steps
                        self._pending_steps = []
                        self._current_trace_id = None
                        self._current_user_id = None
                        self._current_tenant_id = None
                
                if pending_steps_to_commit:
                    db.add_all(pending_steps_to_commit)
                    await db.flush()
                
                trace = await db.get(AgentTrace, trace_id)
                if not trace:
                    logger.warning(f"⚠️ 追踪记录不存在: {trace_id}")
                    return
                
                all_steps = pending_steps_to_commit.copy()
                result = await db.execute(
                    select(AgentStep)
                    .where(AgentStep.trace_id == trace_id)
                    .order_by(AgentStep.step_number.asc())
                )
                existing_steps = result.scalars().all()
                all_steps.extend(existing_steps)
                
                total_duration_ms = None
                if all_steps:
                    total_duration_ms = (all_steps[-1].timestamp - all_steps[0].timestamp) * 1000
                
                trace.final_answer = final_answer
                trace.total_iterations = len(all_steps)
                trace.tool_calls_count = len([s for s in all_steps if s.step_type == "action"])
                trace.status = "completed" if success else "failed"
                trace.error_message = error_message
                trace.completed_at = func.now()
                
                if all_steps:
                    trace.total_time = all_steps[-1].timestamp - all_steps[0].timestamp
                
                await db.commit()
                
                logger.info(f"🏁 追踪结束: {trace_id}")
                logger.info(f"   状态: {trace.status}")
                logger.info(f"   总步骤: {trace.total_iterations}")
                logger.info(f"   工具调用: {trace.tool_calls_count}")
                logger.info(f"   总耗时: {trace.total_time:.2f}s" if trace.total_time else "   总耗时: 0.00s")
                
                if self.langsmith_enabled and self.langsmith_tracer:
                    try:
                        final_answer_preview = final_answer[:500] if final_answer else ""
                        self.langsmith_tracer.end_agent_run(
                            run_id=str(trace_id),
                            final_answer=final_answer_preview,
                            success=success,
                            error_message=error_message,
                            total_steps=len(all_steps),
                            total_duration_ms=total_duration_ms
                        )
                    except Exception as e:
                        logger.warning(f"[AgentTracer] LangSmith end_trace 失败: {e}")
                        
        except Exception as e:
            logger.error(f"[AgentTracer] end_trace 发生错误: {e}", exc_info=True)
    
    async def get_trace_with_steps(
        self,
        trace_id: str,
        user_id: str = None,
        tenant_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取完整的追踪信息（包括所有步骤）
        
        Args:
            trace_id: 追踪 ID
            user_id: 用户 ID（用于权限验证）
            tenant_id: 租户 ID（用于权限验证）
            
        Returns:
            包含追踪和步骤的完整信息
            
        Raises:
            PermissionError: 如果用户无权访问该追踪记录
        """
        async with AsyncSessionLocal() as db:
            trace = await db.get(AgentTrace, trace_id)
            if not trace:
                return None
            
            if user_id and str(trace.user_id) != str(user_id):
                logger.warning(f"⚠️ 用户 {user_id} 无权访问追踪记录 {trace_id}")
                return None
            if tenant_id and trace.tenant_id != tenant_id:
                logger.warning(f"⚠️ 租户 {tenant_id} 无权访问追踪记录 {trace_id}")
                return None
            
            result = await db.execute(
                select(AgentStep)
                .where(AgentStep.trace_id == trace_id)
                .order_by(AgentStep.step_number.asc())
            )
            steps = result.scalars().all()
            
            return {
                "trace_id": str(trace.id),
                "session_id": str(trace.session_id) if trace.session_id else None,
                "message_id": str(trace.message_id) if trace.message_id else None,
                "agent_type": trace.agent_type,
                "user_query": trace.user_query,
                "final_answer": trace.final_answer,
                "status": trace.status,
                "total_iterations": trace.total_iterations,
                "total_time": trace.total_time,
                "tool_calls_count": trace.tool_calls_count,
                "created_at": trace.created_at.isoformat() if trace.created_at else None,
                "steps": [
                    {
                        "step_number": s.step_number,
                        "step_type": s.step_type,
                        "content": s.content,
                        "tool_name": s.tool_name,
                        "tool_input": s.tool_input,
                        "tool_output": s.tool_output,
                        "tool_duration": s.tool_duration,
                        "confidence": s.confidence,
                        "timestamp": s.timestamp
                    }
                    for s in steps
                ]
            }
    
    async def get_session_traces(
        self,
        session_id: str,
        user_id: str = None,
        tenant_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        获取某个会话的追踪记录（带用户过滤）
        
        Args:
            session_id: 会话 ID
            user_id: 用户 ID（可选，用于权限验证）
            tenant_id: 租户 ID（可选）
            
        Returns:
            追踪记录列表
        """
        async with AsyncSessionLocal() as db:
            query = select(AgentTrace).where(AgentTrace.session_id == session_id)
            if user_id:
                query = query.where(AgentTrace.user_id == user_id)
            if tenant_id:
                query = query.where(AgentTrace.tenant_id == tenant_id)
            
            query = query.order_by(AgentTrace.created_at.desc())
            result = await db.execute(query)
            traces = result.scalars().all()
            
            return [
                {
                    "trace_id": str(t.id),
                    "session_id": str(t.session_id) if t.session_id else None,
                    "message_id": str(t.message_id) if t.message_id else None,
                    "agent_type": t.agent_type,
                    "user_query": t.user_query,
                    "status": t.status,
                    "total_iterations": t.total_iterations,
                    "total_time": t.total_time,
                    "tool_calls_count": t.tool_calls_count,
                    "created_at": t.created_at.isoformat() if t.created_at else None
                }
                for t in traces
            ]
    
    async def get_recent_traces(
        self,
        user_id: str,
        tenant_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取当前用户/租户的追踪记录
        
        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            limit: 返回的记录数量限制
            
        Returns:
            追踪记录列表
        """
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AgentTrace)
                .where(
                    AgentTrace.user_id == user_id,
                    AgentTrace.tenant_id == tenant_id
                )
                .order_by(AgentTrace.created_at.desc())
                .limit(limit)
            )
            traces = result.scalars().all()
            
            return [
                {
                    "trace_id": str(t.id),
                    "session_id": str(t.session_id) if t.session_id else None,
                    "message_id": str(t.message_id) if t.message_id else None,
                    "agent_type": t.agent_type,
                    "user_query": t.user_query,
                    "status": t.status,
                    "total_iterations": t.total_iterations,
                    "total_time": t.total_time,
                    "tool_calls_count": t.tool_calls_count,
                    "created_at": t.created_at.isoformat() if t.created_at else None
                }
                for t in traces
            ]
    
    def _get_step_icon(self, step_type: str) -> str:
        """获取步骤类型对应的图标"""
        icons = {
            "thought": "💭",
            "action": "🔧",
            "observation": "👁️",
            "final_answer": "✅"
        }
        return icons.get(step_type, "📝")


# 创建全局实例
agent_tracer = AgentTracer()
