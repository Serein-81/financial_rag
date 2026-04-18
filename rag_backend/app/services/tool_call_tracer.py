# app/services/tool_call_tracer.py

"""
工具调用追踪服务

提供工具调用链的追踪和分析功能
"""

import time
from typing import Dict, Any, List
from sqlalchemy import select, func
from app.db.session import AsyncSessionLocal
from app.models.tool_trace import ToolCallTrace


class ToolCallTracer:
    """
    工具调用追踪服务
    
    负责记录和查询工具调用链路
    """
    
    async def start_call(
        self,
        tool_name: str,
        tool_type: str = "function",
        input_params: Dict = None,
        trace_id: str = None,
        parent_call_id: str = None
    ) -> str:
        """
        开始工具调用追踪
        
        Args:
            tool_name: 工具名称
            tool_type: 工具类型
            input_params: 输入参数
            trace_id: Agent 追踪 ID
            parent_call_id: 父调用 ID（用于嵌套调用）
            
        Returns:
            call_id: 调用 ID
        """
        async with AsyncSessionLocal() as db:
            call_trace = ToolCallTrace(
                tool_name=tool_name,
                tool_type=tool_type,
                input_params=input_params,
                trace_id=trace_id,
                parent_call_id=parent_call_id,
                start_time=time.time(),
                status="running"
            )
            
            db.add(call_trace)
            await db.commit()
            await db.refresh(call_trace)
            
            print(f"🔧 开始工具调用: {tool_name} (ID: {call_trace.id})")
            
            return str(call_trace.id)
    
    async def end_call(
        self,
        call_id: str,
        output_result: str = None,
        duration: float = None,
        status: str = "success",
        error_message: str = None,
        metadata: Dict = None
    ):
        """
        结束工具调用追踪
        
        Args:
            call_id: 调用 ID
            output_result: 输出结果
            duration: 执行时间（毫秒）
            status: 状态
            error_message: 错误信息
            metadata: 元数据
        """
        async with AsyncSessionLocal() as db:
            call_trace = await db.get(ToolCallTrace, call_id)
            if not call_trace:
                print(f"⚠️ 工具调用记录不存在: {call_id}")
                return
            
            call_trace.output_result = output_result
            call_trace.duration = duration
            call_trace.end_time = time.time()
            call_trace.status = status
            call_trace.error_message = error_message
            call_trace.extra_metadata = metadata  # 映射到数据库的 metadata 列
            
            await db.commit()
            
            # 打印日志
            status_icon = "✅" if status == "success" else "❌"
            print(f"{status_icon} 工具调用完成: {call_trace.tool_name} ({duration:.0f}ms)")
    
    async def get_trace_calls(self, trace_id: str) -> List[Dict[str, Any]]:
        """
        获取某次追踪的所有工具调用
        
        Args:
            trace_id: Agent 追踪 ID
            
        Returns:
            工具调用列表
        """
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ToolCallTrace)
                .where(ToolCallTrace.trace_id == trace_id)
                .order_by(ToolCallTrace.start_time.asc())
            )
            calls = result.scalars().all()
            
            return [
                {
                    "call_id": str(c.id),
                    "tool_name": c.tool_name,
                    "tool_type": c.tool_type,
                    "input_params": c.input_params,
                    "output_result": c.output_result[:200] if c.output_result else None,
                    "duration": c.duration,
                    "status": c.status,
                    "error_message": c.error_message,
                    "start_time": c.start_time
                }
                for c in calls
            ]
    
    async def build_call_chain(self, trace_id: str) -> Dict[str, Any]:
        """
        构建工具调用链（树状结构）
        
        Args:
            trace_id: Agent 追踪 ID
            
        Returns:
            调用链数据
        """
        async with AsyncSessionLocal() as db:
            # 查询所有调用
            result = await db.execute(
                select(ToolCallTrace)
                .where(ToolCallTrace.trace_id == trace_id)
                .order_by(ToolCallTrace.start_time.asc())
            )
            calls = result.scalars().all()
            
            if not calls:
                return {"call_tree": [], "statistics": {}}
            
            # 构建调用树
            call_map = {str(c.id): c for c in calls}
            roots = [c for c in calls if c.parent_call_id is None]
            
            def build_node(call: ToolCallTrace) -> Dict:
                node = {
                    "id": str(call.id),
                    "tool_name": call.tool_name,
                    "tool_type": call.tool_type,
                    "duration": call.duration,
                    "status": call.status,
                    "input": call.input_params,
                    "output": call.output_result[:100] if call.output_result else None,
                    "children": []
                }
                
                # 递归构建子节点
                children = [c for c in calls if c.parent_call_id == call.id]
                node["children"] = [build_node(child) for child in children]
                
                return node
            
            call_tree = [build_node(root) for root in roots]
            
            # 统计信息
            total_calls = len(calls)
            total_duration = sum(c.duration for c in calls if c.duration)
            success_count = len([c for c in calls if c.status == "success"])
            success_rate = success_count / total_calls if total_calls > 0 else 0
            
            return {
                "trace_id": trace_id,
                "call_tree": call_tree,
                "statistics": {
                    "total_calls": total_calls,
                    "total_duration": round(total_duration, 2),
                    "success_rate": round(success_rate * 100, 2),
                    "success_count": success_count,
                    "error_count": total_calls - success_count
                }
            }
    
    async def get_tool_statistics(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        获取工具使用统计
        
        Args:
            days: 统计最近多少天
            
        Returns:
            工具统计列表
        """
        from datetime import datetime, timedelta
        
        async with AsyncSessionLocal() as db:
            start_date = datetime.now() - timedelta(days=days)
            
            result = await db.execute(
                select(
                    ToolCallTrace.tool_name,
                    func.count(ToolCallTrace.id).label("call_count"),
                    func.avg(ToolCallTrace.duration).label("avg_duration"),
                    func.sum(
                        func.case((ToolCallTrace.status == "success", 1), else_=0)
                    ).label("success_count")
                )
                .where(ToolCallTrace.created_at >= start_date)
                .group_by(ToolCallTrace.tool_name)
            )
            
            stats = result.all()
            
            return [
                {
                    "tool_name": s.tool_name,
                    "call_count": s.call_count,
                    "avg_duration": round(s.avg_duration, 2) if s.avg_duration else 0,
                    "success_rate": round(s.success_count / s.call_count * 100, 2) if s.call_count > 0 else 0
                }
                for s in stats
            ]


# 创建全局实例
tool_call_tracer = ToolCallTracer()
