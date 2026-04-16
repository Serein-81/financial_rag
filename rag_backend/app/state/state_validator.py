"""
状态验证器

提供状态验证功能，确保状态符合规范

主要功能：
1. 必填字段验证
2. 类型验证
3. 值范围验证
4. 业务逻辑验证
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from app.state.unified_state import (
    UnifiedState,
    IntentCategory,
    SpecialistType,
    OrchestrationMode,
)

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """
    验证错误异常
    
    当状态验证失败时抛出此异常
    """
    
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"状态验证失败: {'; '.join(errors)}")


class ValidationResult:
    """
    验证结果
    
    存储验证结果，提供友好的接口
    """
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.is_valid: bool = True
    
    def add_error(self, message: str):
        """添加错误"""
        self.errors.append(message)
        self.is_valid = False
        logger.error(f"[ValidationResult] 验证错误: {message}")
    
    def add_warning(self, message: str):
        """添加警告"""
        self.warnings.append(message)
        logger.warning(f"[ValidationResult] 验证警告: {message}")
    
    def merge(self, other: "ValidationResult"):
        """合并另一个验证结果"""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.is_valid:
            self.is_valid = False
    
    def __bool__(self) -> bool:
        return self.is_valid
    
    def __repr__(self) -> str:
        return (
            f"ValidationResult(is_valid={self.is_valid}, "
            f"errors={len(self.errors)}, warnings={len(self.warnings)})"
        )


class StateValidator:
    """
    状态验证器
    
    提供全面的状态验证功能，确保状态符合系统规范。
    
    验证层次：
    1. 必填字段存在性
    2. 字段类型正确性
    3. 字段值范围合理性
    4. 业务逻辑一致性
    
    使用示例：
    ```python
    validator = StateValidator()
    
    # 完整验证
    result = validator.validate(state)
    if not result.is_valid:
        print(f"验证失败: {result.errors}")
    
    # 增量验证（只检查特定字段）
    result = validator.validate_field(state, "tenant_id")
    if not result.is_valid:
        print(f"tenant_id 验证失败")
    ```
    """
    
    # 必填字段列表
    REQUIRED_FIELDS = [
        "session_id",
        "tenant_id",
        "user_id",
        "request_id",
        "user_query",
        "query_timestamp",
    ]
    
    # 字段类型映射
    FIELD_TYPES = {
        "session_id": str,
        "tenant_id": str,
        "user_id": str,
        "request_id": str,
        "user_query": str,
        "query_timestamp": datetime,
        "intent": (type(None), IntentCategory),
        "intent_confidence": (int, float),
        "routing_strategy": (type(None), str),
        "target_specialists": list,
        "orchestration_mode": OrchestrationMode,
        "current_phase": str,
        "rag_context_ids": list,
        "rag_context_metadata": dict,
        "message_bus_summary": (type(None), str),
        "message_bus_disagreements": list,
        "message_bus_key_decisions": list,
        "specialist_result_ids": list,
        "specialist_results_metadata": list,
        "reflection_result_id": (type(None), str),
        "reflection_metadata": (type(None), dict),
        "aggregated_response": (type(None), str),
        "iteration": int,
        "max_iterations": int,
        "retry_count": int,
        "max_retries": int,
        "error": (type(None), str),
        "error_history": list,
        "warnings": list,
        "messages": list,
        "metadata": dict,
        "created_at": datetime,
        "updated_at": datetime,
        "trace_id": (type(None), str),
        "span_id": (type(None), str),
        "final_answer": (type(None), str),
        "needs_human_review": bool,
        "human_review_id": (type(None), str),
    }
    
    def __init__(self, strict: bool = True):
        """
        初始化验证器
        
        Args:
            strict: 是否使用严格模式。
                   严格模式下，所有警告都会被记录但不导致验证失败。
                   非严格模式下，部分非关键验证失败也会被接受。
        """
        self.strict = strict
    
    def validate(self, state: UnifiedState) -> ValidationResult:
        """
        完整验证状态
        
        执行所有验证检查：
        1. 必填字段存在性
        2. 字段类型正确性
        3. 字段值范围合理性
        4. 业务逻辑一致性
        
        Args:
            state: 要验证的状态
        
        Returns:
            ValidationResult: 验证结果
        
        Example:
            ```python
            validator = StateValidator()
            result = validator.validate(state)
            
            if not result:
                print("验证失败")
                for error in result.errors:
                    print(f"  - {error}")
            ```
        """
        result = ValidationResult()
        
        # 1. 必填字段验证
        self._validate_required_fields(state, result)
        
        # 2. 类型验证
        self._validate_field_types(state, result)
        
        # 3. 值范围验证
        self._validate_value_ranges(state, result)
        
        # 4. 业务逻辑验证
        self._validate_business_logic(state, result)
        
        if result.is_valid:
            logger.info(
                f"[StateValidator] 状态验证通过: "
                f"request_id={state.get('request_id', 'unknown')}"
            )
        else:
            logger.warning(
                f"[StateValidator] 状态验证失败: "
                f"request_id={state.get('request_id', 'unknown')}, "
                f"errors={result.errors}"
            )
        
        return result
    
    def validate_field(
        self,
        state: UnifiedState,
        field_name: str
    ) -> ValidationResult:
        """
        验证单个字段
        
        Args:
            state: 状态字典
            field_name: 字段名
        
        Returns:
            ValidationResult: 验证结果
        """
        result = ValidationResult()
        
        # 检查字段是否存在
        if field_name not in state:
            if field_name in self.REQUIRED_FIELDS:
                result.add_error(f"必填字段缺失: {field_name}")
            else:
                result.add_warning(f"字段不存在: {field_name}")
            return result
        
        # 类型检查
        expected_type = self.FIELD_TYPES.get(field_name)
        if expected_type:
            value = state[field_name]
            if not isinstance(value, expected_type):
                result.add_error(
                    f"字段类型错误: {field_name}, "
                    f"期望 {expected_type}, 实际 {type(value)}"
                )
        
        return result
    
    def _validate_required_fields(
        self,
        state: UnifiedState,
        result: ValidationResult
    ):
        """验证必填字段"""
        for field in self.REQUIRED_FIELDS:
            if field not in state:
                result.add_error(f"必填字段缺失: {field}")
            elif not state[field]:
                result.add_error(f"必填字段为空: {field}")
    
    def _validate_field_types(
        self,
        state: UnifiedState,
        result: ValidationResult
    ):
        """验证字段类型"""
        for field_name, expected_type in self.FIELD_TYPES.items():
            if field_name not in state:
                continue
            
            value = state[field_name]
            
            # 处理 None 值
            if value is None:
                # 如果期望 None 或 Optional 类型，允许 None
                if expected_type is type(None) or (
                    isinstance(expected_type, tuple) and type(None) in expected_type
                ):
                    continue
                else:
                    result.add_error(f"字段不能为 None: {field_name}")
                continue
            
            # 处理元组类型（如 Union）
            if isinstance(expected_type, tuple):
                if not isinstance(value, expected_type):
                    expected_str = " | ".join(t.__name__ for t in expected_type)
                    result.add_error(
                        f"字段类型错误: {field_name}, "
                        f"期望 {expected_str}, 实际 {type(value).__name__}"
                    )
            else:
                if not isinstance(value, expected_type):
                    result.add_error(
                        f"字段类型错误: {field_name}, "
                        f"期望 {expected_type.__name__}, 实际 {type(value).__name__}"
                    )
    
    def _validate_value_ranges(
        self,
        state: UnifiedState,
        result: ValidationResult
    ):
        """验证值范围"""
        # 置信度范围（先检查类型）
        if "intent_confidence" in state:
            confidence = state["intent_confidence"]
            # 只有在类型正确的情况下才验证范围
            if isinstance(confidence, (int, float)) and not (0.0 <= confidence <= 1.0):
                result.add_error(
                    f"置信度超出范围: {confidence}, 应在 [0.0, 1.0] 之间"
                )
        
        # 迭代次数非负（先检查类型）
        for field in ["iteration", "retry_count"]:
            if field in state and isinstance(state[field], (int, float)):
                if state[field] < 0:
                    result.add_error(f"{field} 不能为负数: {state[field]}")
        
        # 最大次数应大于 0
        for field in ["max_iterations", "max_retries"]:
            if field in state and isinstance(state[field], (int, float)) and state[field] <= 0:
                result.add_error(f"{field} 必须大于 0: {state[field]}")
        
        # 迭代次数不应超过最大次数
        if "iteration" in state and "max_iterations" in state:
            if state["iteration"] > state["max_iterations"]:
                result.add_warning(
                    f"当前迭代次数 ({state['iteration']}) "
                    f"超过最大次数 ({state['max_iterations']})"
                )
        
        # 重试次数不应超过最大次数
        if "retry_count" in state and "max_retries" in state:
            if state["retry_count"] > state["max_retries"]:
                result.add_warning(
                    f"当前重试次数 ({state['retry_count']}) "
                    f"超过最大次数 ({state['max_retries']})"
                )
    
    def _validate_business_logic(
        self,
        state: UnifiedState,
        result: ValidationResult
    ):
        """验证业务逻辑一致性"""
        # 意图识别时，target_specialists 不应为空
        if state.get("intent") in [
            IntentCategory.SINGLE_SPECIALIST,
            IntentCategory.MULTI_SPECIALIST,
            IntentCategory.EXPERT_CONSULTATION,
        ]:
            if not state.get("target_specialists"):
                result.add_error(
                    "意图为专家查询时，target_specialists 不能为空"
                )
        
        # 有意图时，置信度应该较高
        if state.get("intent") and state.get("intent") != IntentCategory.UNKNOWN:
            confidence = state.get("intent_confidence", 0.0)
            if confidence < 0.5:
                result.add_warning(
                    f"意图置信度较低 ({confidence})，建议重新识别"
                )
        
        # 有错误时，不应该有 final_answer
        if state.get("error") and state.get("final_answer"):
            result.add_warning(
                "状态同时包含错误和最终答案，可能存在逻辑不一致"
            )
        
        # 需要人工审核时，应该有审核 ID 或 final_answer
        if state.get("needs_human_review"):
            if not state.get("human_review_id") and not state.get("final_answer"):
                result.add_warning(
                    "需要人工审核但未提供审核 ID 或初步答案"
                )
        
        # 时间戳逻辑检查
        if state.get("created_at") and state.get("updated_at"):
            if state["updated_at"] < state["created_at"]:
                result.add_error(
                    "更新时间早于创建时间，时间逻辑错误"
                )
        
        if state.get("query_timestamp"):
            if state["query_timestamp"] > datetime.now():
                result.add_warning(
                    "查询时间戳晚于当前时间，可能存在时钟不同步问题"
                )
    
    def validate_transition(
        self,
        from_state: UnifiedState,
        to_state: UnifiedState
    ) -> ValidationResult:
        """
        验证状态转换的有效性
        
        Args:
            from_state: 源状态
            to_state: 目标状态
        
        Returns:
            ValidationResult: 验证结果
        """
        result = ValidationResult()
        
        # 基本的必填字段验证
        self._validate_required_fields(to_state, result)
        
        # 检查关键标识符是否一致
        for field in ["session_id", "tenant_id", "user_id", "request_id"]:
            if field in from_state and field in to_state:
                if from_state[field] != to_state[field]:
                    result.add_error(
                        f"状态转换时 {field} 发生变化: "
                        f"{from_state[field]} -> {to_state[field]}"
                    )
        
        # 检查 iteration 是否合理增加
        if to_state.get("iteration", 0) < from_state.get("iteration", 0):
            result.add_error(
                f"迭代次数不应减少: "
                f"{from_state.get('iteration')} -> {to_state.get('iteration')}"
            )
        
        # 检查 retry_count 是否合理增加
        if to_state.get("retry_count", 0) < from_state.get("retry_count", 0):
            result.add_error(
                f"重试次数不应减少: "
                f"{from_state.get('retry_count')} -> {to_state.get('retry_count')}"
            )
        
        return result
