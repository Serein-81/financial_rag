"""
工具调用追踪 Repository

提供工具调用追踪的数据库操作接口，自动处理租户隔离

使用方式：
    from app.repositories.tool_trace import ToolCallTraceRepository
    
    async def get_calls(db: AsyncSession, trace_id: str, tenant_id: str):
        repo = ToolCallTraceRepository(db)
        return await repo.get_by_trace(trace_id, tenant_id=tenant_id)
"""

from typing import Optional, List, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.tool_trace import ToolCallTrace
import logging

logger = logging.getLogger(__name__)


class ToolCallTraceRepository(BaseRepository[ToolCallTrace]):
    """
    工具调用追踪 Repository
    
    提供工具调用追踪的 CRUD 操作，自动处理租户隔离
    """
    
    def __init__(self, session: AsyncSession):
        """初始化 ToolCallTrace Repository"""
        super().__init__(session, ToolCallTrace)
    
    async def create_call(
        self,
        tool_name: str,
        tool_type: str,
        trace_id: Optional[str] = None,
        parent_call_id: Optional[str] = None,
        input_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ToolCallTrace:
        """
        创建工具调用记录
        
        Args:
            tool_name: 工具名称
            tool_type: 工具类型
            trace_id: Agent 追踪 ID
            parent_call_id: 父调用 ID
            input_params: 输入参数
            **kwargs: 其他字段
            
        Returns:
            创建的 ToolCallTrace
        """
        data = {
            'tool_name': tool_name,
            'tool_type': tool_type,
            'trace_id': trace_id,
            'parent_call_id': parent_call_id,
            'input_params': input_params,
            'status': 'running',
            **kwargs
        }
        
        return await self.create(**data)
    
    async def update_call_result(
        self,
        call_id: str,
        output_result: Optional[str] = None,
        duration: Optional[float] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ToolCallTrace]:
        """
        更新工具调用结果
        
        Args:
            call_id: 调用 ID
            output_result: 输出结果
            duration: 执行时间（毫秒）
            status: 状态
            error_message: 错误信息
            metadata: 元数据
            
        Returns:
            更新后的 ToolCallTrace
        """
        data = {
            'output_result': output_result,
            'duration': duration,
            'status': status,
            'error_message': error_message,
            'extra_metadata': metadata
        }
        
        return await self.update(call_id, **data)
    
    async def get_by_trace(
        self,
        trace_id: str,
        tenant_id: Optional[str] = None
    ) -> List[ToolCallTrace]:
        """
        根据追踪 ID 获取工具调用列表
        
        Args:
            trace_id: Agent 追踪 ID
            tenant_id: 租户 ID
            
        Returns:
            ToolCallTrace 列表
        """
        return await self.list(
            tenant_id=tenant_id,
            trace_id=trace_id,
            order_by='start_time',
            order_desc=False
        )
    
    async def get_call_chain(
        self,
        trace_id: str,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        构建工具调用链（树状结构）
        
        Args:
            trace_id: Agent 追踪 ID
            tenant_id: 租户 ID
            
        Returns:
            调用链数据
        """
        calls = await self.get_by_trace(trace_id, tenant_id)
        
        call_dict = {str(c.id): c for c in calls}
        root_calls = [c for c in calls if not c.parent_call_id]
        
        def build_tree(call: ToolCallTrace) -> Dict[str, Any]:
            children = [c for c in calls if c.parent_call_id == str(call.id)]
            return {
                "call_id": str(call.id),
                "tool_name": call.tool_name,
                "tool_type": call.tool_type,
                "input_params": call.input_params,
                "output_result": call.output_result[:200] if call.output_result else None,
                "duration": call.duration,
                "status": call.status,
                "error_message": call.error_message,
                "start_time": call.start_time,
                "children": [build_tree(child) for child in children]
            }
        
        return {
            "trace_id": trace_id,
            "total_calls": len(calls),
            "root_calls": [build_tree(root) for root in root_calls]
        }
    
    async def get_statistics(
        self,
        tenant_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取工具调用统计
        
        Args:
            tenant_id: 租户 ID
            trace_id: 追踪 ID
            
        Returns:
            统计数据
        """
        filters = {}
        if tenant_id:
            filters['tenant_id'] = tenant_id
        if trace_id:
            filters['trace_id'] = trace_id
        
        total = await self.count(**filters)
        
        success_count = await self.count(status='success', **filters)
        failed_count = await self.count(status='failed', **filters)
        running_count = await self.count(status='running', **filters)
        
        return {
            'total': total,
            'success': success_count,
            'failed': failed_count,
            'running': running_count
        }
