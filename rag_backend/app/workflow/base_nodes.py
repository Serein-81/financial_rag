"""
工作流节点监控Mixin

为LangGraph工作流节点提供监控能力：
1. 自动追踪节点执行
2. 记录执行时间和Token使用
3. 关联Agent执行追踪
4. 错误捕获和记录
"""

import logging
import time
from typing import Dict, Any, Optional, Callable
from functools import wraps
from uuid import uuid4

from app.workflow import NodeType

logger = logging.getLogger(__name__)


class NodeExecutionTracker:
    """
    节点执行追踪器
    
    提供节点级别的执行追踪功能
    """
    
    def __init__(self, monitor):
        """
        初始化追踪器
        
        Args:
            monitor: TaxWorkflowMonitor实例
        """
        self.monitor = monitor
        self._node_start_times: Dict[str, float] = {}
    
    def track_node_execution(
        self,
        node_name: str,
        node_type: NodeType,
        input_transform: Optional[Callable] = None,
        output_transform: Optional[Callable] = None
    ):
        """
        节点执行追踪装饰器
        
        Args:
            node_name: 节点名称
            node_type: 节点类型
            input_transform: 输入转换函数
            output_transform: 输出转换函数
        
        Returns:
            装饰器函数
        """
        def decorator(func):
            @wraps(func)
            async def async_wrapper(state, *args, **kwargs):
                start_time = time.time()
                node_execution_id = None
                
                try:
                    input_data = input_transform(state) if input_transform else {"state_keys": list(state.keys())}
                    
                    node_execution_id = self.monitor.start_node(
                        node_name=node_name,
                        node_type=node_type,
                        input_data=input_data
                    )
                    
                    logger.info(f"🔄 [{node_name}] 开始执行")
                    
                    result = await func(state, *args, **kwargs)
                    
                    execution_time_ms = (time.time() - start_time) * 1000
                    
                    output_data = output_transform(result) if output_transform else {"status": result.get("status") if isinstance(result, dict) else None}
                    
                    self.monitor.complete_node(
                        node_name=node_name,
                        output_data=output_data,
                        execution_time_ms=execution_time_ms
                    )
                    
                    logger.info(f"✅ [{node_name}] 执行完成，耗时: {execution_time_ms:.2f}ms")
                    
                    return result
                    
                except Exception as e:
                    execution_time_ms = (time.time() - start_time) * 1000
                    
                    self.monitor.record_error(
                        node_name=node_name,
                        error=e,
                        error_context={
                            "node_execution_id": node_execution_id,
                            "execution_time_ms": execution_time_ms
                        }
                    )
                    
                    logger.error(f"❌ [{node_name}] 执行失败: {e}", exc_info=True)
                    raise
            
            @wraps(func)
            def sync_wrapper(state, *args, **kwargs):
                start_time = time.time()
                node_execution_id = None
                
                try:
                    input_data = input_transform(state) if input_transform else {"state_keys": list(state.keys())}
                    
                    node_execution_id = self.monitor.start_node(
                        node_name=node_name,
                        node_type=node_type,
                        input_data=input_data
                    )
                    
                    logger.info(f"🔄 [{node_name}] 开始执行")
                    
                    result = func(state, *args, **kwargs)
                    
                    execution_time_ms = (time.time() - start_time) * 1000
                    
                    output_data = output_transform(result) if output_transform else {"status": result.get("status") if isinstance(result, dict) else None}
                    
                    self.monitor.complete_node(
                        node_name=node_name,
                        output_data=output_data,
                        execution_time_ms=execution_time_ms
                    )
                    
                    logger.info(f"✅ [{node_name}] 执行完成，耗时: {execution_time_ms:.2f}ms")
                    
                    return result
                    
                except Exception as e:
                    execution_time_ms = (time.time() - start_time) * 1000
                    
                    self.monitor.record_error(
                        node_name=node_name,
                        error=e,
                        error_context={
                            "node_execution_id": node_execution_id,
                            "execution_time_ms": execution_time_ms
                        }
                    )
                    
                    logger.error(f"❌ [{node_name}] 执行失败: {e}", exc_info=True)
                    raise
            
            import asyncio
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    def track_agent_execution(
        self,
        node_name: str,
        agent_execution_func: Callable
    ):
        """
        Agent执行追踪
        
        Args:
            node_name: 节点名称
            agent_execution_func: Agent执行函数
        
        Returns:
            包装后的函数
        """
        @wraps(agent_execution_func)
        async def wrapper(*args, **kwargs):
            agent_trace_id = str(uuid4())
            
            try:
                logger.info(f"🤖 [{node_name}] Agent执行开始: {agent_trace_id}")
                
                result = await agent_execution_func(*args, **kwargs)
                
                logger.info(f"✅ [{node_name}] Agent执行完成: {agent_trace_id}")
                
                return result
                
            except Exception as e:
                logger.error(f"❌ [{node_name}] Agent执行失败: {agent_trace_id}, error={e}")
                raise
        
        return wrapper


def create_validation_node_tracker(monitor):
    """创建验证节点追踪器"""
    return NodeExecutionTracker(monitor)


def create_financial_data_node_tracker(monitor):
    """创建财务数据节点追踪器"""
    return NodeExecutionTracker(monitor)


def create_tax_calculation_node_tracker(monitor):
    """创建税务计算节点追踪器"""
    return NodeExecutionTracker(monitor)


def create_risk_assessment_node_tracker(monitor):
    """创建风险评估节点追踪器"""
    return NodeExecutionTracker(monitor)


def create_human_review_node_tracker(monitor):
    """创建人工审核节点追踪器"""
    return NodeExecutionTracker(monitor)


def create_save_node_tracker(monitor):
    """创建保存节点追踪器"""
    return NodeExecutionTracker(monitor)


def create_error_handler_tracker(monitor):
    """创建错误处理节点追踪器"""
    return NodeExecutionTracker(monitor)
