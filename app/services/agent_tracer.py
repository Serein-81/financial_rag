# app/services/agent_tracer.py

"""
Agent 追踪服务

提供 Agent 执行追踪的核心功能
"""

import time
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.agent_trace import AgentTrace, AgentStep


class AgentTracer:
    """
    Agent 追踪服务
    
    负责记录和查询 Agent 的执行过程
    """
    
    async def start_trace(
        self,
        agent_type: str,
        user_query: str,
        session_id: str = None,
        message_id: str = None
    ) -> str:
        """
        开始一次新的追踪
        
        Args:
            agent_type: Agent 类型（react/plan/reflect）
            user_query: 用户查询
            session_id: 会话 ID（可选）
            message_id: 消息 ID（可选）
            
        Returns:
            trace_id: 追踪 ID
        """
        async with AsyncSessionLocal() as db:
            trace = AgentTrace(
                agent_type=agent_type,
                user_query=user_query,
                session_id=session_id,
                message_id=message_id,
                status="running"
            )
            
            db.add(trace)
            await db.commit()
            await db.refresh(trace)
            
            print(f"🎬 开始追踪: {trace.id} | Agent: {agent_type}")
            
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
        """
        async with AsyncSessionLocal() as db:
            step = AgentStep(
                trace_id=trace_id,
                step_number=step_number,
                step_type=step_type,
                content=content,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
                tool_duration=tool_duration,
                confidence=confidence,
                metadata=metadata,
                timestamp=time.time()
            )
            
            db.add(step)
            await db.commit()
            
            # 打印日志
            icon = self._get_step_icon(step_type)
            print(f"{icon} Step {step_number} ({step_type}): {content[:50]}...")
    
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
        """
        async with AsyncSessionLocal() as db:
            # 获取追踪记录
            trace = await db.get(AgentTrace, trace_id)
            if not trace:
                print(f"⚠️ 追踪记录不存在: {trace_id}")
                return
            
            # 查询所有步骤
            result = await db.execute(
                select(AgentStep)
                .where(AgentStep.trace_id == trace_id)
                .order_by(AgentStep.step_number.asc())
            )
            steps = result.scalars().all()
            
            # 更新统计信息
            trace.final_answer = final_answer
            trace.total_iterations = len(steps)
            trace.tool_calls_count = len([s for s in steps if s.step_type == "action"])
            trace.status = "completed" if success else "failed"
            trace.error_message = error_message
            trace.completed_at = func.now()
            
            # 计算总时间
            if steps:
                trace.total_time = steps[-1].timestamp - steps[0].timestamp
            
            await db.commit()
            
            # 打印摘要
            print(f"🏁 追踪结束: {trace_id}")
            print(f"   状态: {trace.status}")
            print(f"   总步骤: {trace.total_iterations}")
            print(f"   工具调用: {trace.tool_calls_count}")
            print(f"   总耗时: {trace.total_time:.2f}s")
    
    async def get_trace_with_steps(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        获取完整的追踪信息（包括所有步骤）
        
        Args:
            trace_id: 追踪 ID
            
        Returns:
            包含追踪和步骤的完整信息
        """
        async with AsyncSessionLocal() as db:
            # 获取追踪记录
            trace = await db.get(AgentTrace, trace_id)
            if not trace:
                return None
            
            # 获取所有步骤
            result = await db.execute(
                select(AgentStep)
                .where(AgentStep.trace_id == trace_id)
                .order_by(AgentStep.step_number.asc())
            )
            steps = result.scalars().all()
            
            return {
                "trace_id": str(trace.id),
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
    
    async def get_session_traces(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取某个会话的所有追踪记录
        
        Args:
            session_id: 会话 ID
            
        Returns:
            追踪记录列表
        """
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AgentTrace)
                .where(AgentTrace.session_id == session_id)
                .order_by(AgentTrace.created_at.desc())
            )
            traces = result.scalars().all()
            
            return [
                {
                    "trace_id": str(t.id),
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
