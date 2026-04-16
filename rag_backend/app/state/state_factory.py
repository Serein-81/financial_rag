"""
状态工厂

提供统一的状态创建和管理功能

主要功能：
1. 创建初始状态
2. 从现有状态复制
3. 创建状态快照
4. 状态验证
"""

import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from copy import deepcopy

from app.state.unified_state import (
    UnifiedState,
    IntentCategory,
    OrchestrationMode,
)

logger = logging.getLogger(__name__)


class StateFactory:
    """
    状态工厂
    
    提供标准化的状态创建方法，确保所有状态都符合统一的结构规范。
    
    使用示例：
    ```python
    factory = StateFactory()
    
    # 创建初始状态
    initial_state = factory.create_initial_state(
        session_id="session-123",
        tenant_id="tenant-456",
        user_id="user-789",
        user_query="分析公司财务状况"
    )
    
    # 复制状态
    state_copy = factory.copy_state(initial_state)
    
    # 创建快照
    snapshot = factory.create_snapshot(initial_state)
    ```
    """
    
    DEFAULT_MAX_ITERATIONS = 10
    DEFAULT_MAX_RETRIES = 3
    
    @classmethod
    def create_initial_state(
        cls,
        session_id: str,
        tenant_id: str,
        user_id: str,
        user_query: str,
        request_id: Optional[str] = None,
        intent: Optional[IntentCategory] = None,
        orchestration_mode: OrchestrationMode = OrchestrationMode.LANGGRAPH,
        max_iterations: Optional[int] = None,
        max_retries: Optional[int] = None,
        trace_id: Optional[str] = None,
        **metadata: Any
    ) -> UnifiedState:
        """
        创建初始状态
        
        这是创建新状态的推荐方法，确保所有必填字段都被正确初始化。
        
        Args:
            session_id: 会话 ID
            tenant_id: 租户 ID
            user_id: 用户 ID
            user_query: 用户查询
            request_id: 请求 ID（可选，默认自动生成）
            intent: 意图类型（可选）
            orchestration_mode: 编排模式（默认 LANGGRAPH）
            max_iterations: 最大迭代次数（可选）
            max_retries: 最大重试次数（可选）
            trace_id: 追踪 ID（可选）
            **metadata: 其他元数据
        
        Returns:
            UnifiedState: 初始化的状态字典
        
        Raises:
            ValueError: 如果必填参数缺失或无效
        
        Example:
            ```python
            state = StateFactory.create_initial_state(
                session_id="sess-001",
                tenant_id="tenant-001",
                user_id="user-001",
                user_query="分析税务问题",
                intent=IntentCategory.MULTI_SPECIALIST
            )
            ```
        """
        # 参数验证
        if not session_id:
            raise ValueError("session_id 不能为空")
        if not tenant_id:
            raise ValueError("tenant_id 不能为空")
        if not user_id:
            raise ValueError("user_id 不能为空")
        if not user_query:
            raise ValueError("user_query 不能为空")
        
        # 生成请求 ID
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # 使用默认值
        if max_iterations is None:
            max_iterations = cls.DEFAULT_MAX_ITERATIONS
        if max_retries is None:
            max_retries = cls.DEFAULT_MAX_RETRIES
        
        now = datetime.now()
        
        # 创建状态
        state: UnifiedState = {
            # 核心会话信息
            "session_id": session_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "request_id": request_id,
            
            # 用户输入
            "user_query": user_query,
            "query_timestamp": now,
            
            # 意图识别
            "intent": intent,
            "intent_confidence": 0.0,
            "routing_strategy": None,
            "target_specialists": [],
            
            # 编排模式
            "orchestration_mode": orchestration_mode,
            "current_phase": "init",
            
            # RAG 检索
            "rag_context_ids": [],
            "rag_context_metadata": {},
            
            # Message Bus 上下文
            "message_bus_summary": None,
            "message_bus_disagreements": [],
            "message_bus_key_decisions": [],
            
            # 专家结果
            "specialist_result_ids": [],
            "specialist_results_metadata": [],
            
            # 反思结果
            "reflection_result_id": None,
            "reflection_metadata": None,
            
            # 聚合响应
            "aggregated_response": None,
            
            # 迭代控制
            "iteration": 0,
            "max_iterations": max_iterations,
            "retry_count": 0,
            "max_retries": max_retries,
            
            # 错误跟踪
            "error": None,
            "error_history": [],
            "warnings": [],
            
            # 消息历史
            "messages": [],
            
            # 元数据
            "metadata": metadata,
            "created_at": now,
            "updated_at": now,
            
            # 追踪信息
            "trace_id": trace_id,
            "span_id": None,
            
            # 最终结果
            "final_answer": None,
            "needs_human_review": False,
            "human_review_id": None,
        }
        
        logger.info(
            f"[StateFactory] 创建初始状态: session_id={session_id}, "
            f"request_id={request_id}, tenant_id={tenant_id}"
        )
        
        return state
    
    @classmethod
    def copy_state(cls, state: UnifiedState) -> UnifiedState:
        """
        深拷贝状态
        
        创建一个状态的深拷贝，所有可变对象都会被复制。
        这在需要保留状态历史或进行分支操作时很有用。
        
        Args:
            state: 要复制的状态
        
        Returns:
            UnifiedState: 新的状态副本
        
        Example:
            ```python
            original_state = StateFactory.create_initial_state(...)
            backup_state = StateFactory.copy_state(original_state)
            # 修改 backup_state 不会影响 original_state
            ```
        """
        copied_state = deepcopy(state)
        
        # 更新复制后的时间戳
        now = datetime.now()
        copied_state["created_at"] = now
        copied_state["updated_at"] = now
        
        # 生成新的请求 ID
        copied_state["request_id"] = str(uuid.uuid4())
        
        logger.debug(
            f"[StateFactory] 复制状态: original_request_id={state['request_id']}, "
            f"new_request_id={copied_state['request_id']}"
        )
        
        return copied_state
    
    @classmethod
    def create_snapshot(cls, state: UnifiedState) -> Dict[str, Any]:
        """
        创建状态快照
        
        创建一个只读的状态快照，包含当前状态的所有信息。
        快照可用于审计、回滚或调试。
        
        Args:
            state: 要快照的状态
        
        Returns:
            Dict[str, Any]: 状态快照字典，包含元数据
        
        Example:
            ```python
            snapshot = StateFactory.create_snapshot(current_state)
            # 保存到数据库或文件系统
            ```
        """
        snapshot = {
            "snapshot_id": str(uuid.uuid4()),
            "snapshot_type": "state_snapshot",
            "created_at": datetime.now().isoformat(),
            "request_id": state.get("request_id"),
            "session_id": state.get("session_id"),
            "current_phase": state.get("current_phase"),
            "iteration": state.get("iteration"),
            "state_data": deepcopy(state),
        }
        
        logger.info(
            f"[StateFactory] 创建快照: snapshot_id={snapshot['snapshot_id']}, "
            f"request_id={state.get('request_id')}"
        )
        
        return snapshot
    
    @classmethod
    def restore_from_snapshot(cls, snapshot: Dict[str, Any]) -> UnifiedState:
        """
        从快照恢复状态
        
        Args:
            snapshot: 状态快照
        
        Returns:
            UnifiedState: 恢复的状态
        
        Raises:
            ValueError: 如果快照格式无效
        """
        if not isinstance(snapshot, dict):
            raise ValueError("快照格式无效")
        
        if "state_data" not in snapshot:
            raise ValueError("快照缺少 state_data 字段")
        
        state = snapshot["state_data"]
        
        logger.info(
            f"[StateFactory] 从快照恢复: snapshot_id={snapshot.get('snapshot_id')}, "
            f"request_id={state.get('request_id')}"
        )
        
        return state
    
    @classmethod
    def create_error_state(
        cls,
        original_state: UnifiedState,
        error_message: str,
        error_type: Optional[str] = None
    ) -> UnifiedState:
        """
        创建错误状态
        
        从原始状态创建一个包含错误信息的新状态。
        保留原始状态的所有上下文信息，只更新错误相关字段。
        
        Args:
            original_state: 原始状态
            error_message: 错误消息
            error_type: 错误类型（可选）
        
        Returns:
            UnifiedState: 包含错误信息的状态
        """
        error_state = cls.copy_state(original_state)
        
        # 更新错误信息
        error_state["error"] = error_message
        error_state["current_phase"] = "error"
        error_state["updated_at"] = datetime.now()
        
        # 添加到错误历史
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "error": error_message,
            "error_type": error_type,
            "phase": original_state.get("current_phase"),
            "iteration": original_state.get("iteration"),
        }
        error_state["error_history"].append(error_entry)
        
        # 如果重试次数未超限，设置编排模式为重试
        if error_state["retry_count"] < error_state["max_retries"]:
            error_state["orchestration_mode"] = OrchestrationMode.HYBRID
            logger.info(
                f"[StateFactory] 状态进入重试模式: retry_count={error_state['retry_count']}, "
                f"max_retries={error_state['max_retries']}"
            )
        
        logger.warning(
            f"[StateFactory] 创建错误状态: request_id={original_state['request_id']}, "
            f"error={error_message}"
        )
        
        return error_state
    
    @classmethod
    def reset_for_retry(cls, state: UnifiedState) -> UnifiedState:
        """
        重置状态以进行重试
        
        在执行重试之前调用此方法，重置迭代计数器并增加重试计数。
        
        Args:
            state: 要重置的状态
        
        Returns:
            UnifiedState: 重置后的状态
        
        Example:
            ```python
            if state["retry_count"] < state["max_retries"]:
                state = StateFactory.reset_for_retry(state)
                # 执行重试逻辑
            ```
        """
        state = cls.copy_state(state)
        
        # 增加重试计数
        state["retry_count"] += 1
        
        # 重置迭代计数
        state["iteration"] = 0
        
        # 清除错误
        state["error"] = None
        
        # 重置阶段
        state["current_phase"] = "init"
        
        state["updated_at"] = datetime.now()
        
        logger.info(
            f"[StateFactory] 重置状态进行重试: request_id={state['request_id']}, "
            f"retry_count={state['retry_count']}"
        )
        
        return state
