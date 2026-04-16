"""
统一状态管理模块

提供整个多智能体系统的统一状态定义和管理。

主要组件：
- UnifiedState: 统一状态 TypedDict 定义
- StateFactory: 状态工厂，用于创建和初始化状态
- StateValidator: 状态验证器，用于验证状态的有效性
- StateManager: 状态管理器，用于管理状态的生命周期

使用示例：
```python
from app.state import StateFactory, UnifiedState

# 创建初始状态
state = StateFactory.create_initial_state(
    session_id="session-123",
    tenant_id="tenant-456",
    user_id="user-789",
    user_query="分析公司财务状况"
)

# 验证状态
validator = StateValidator()
if validator.validate(state):
    print("状态有效")
```

作者：Senior Python Backend Architect
版本：1.0.0
"""

from app.state.unified_state import (
    IntentCategory,
    SpecialistType,
    QualityLevel,
    OrchestrationMode,
    UnifiedState,
    AgentMessage,
    SpecialistResult,
    ReflectionResult,
)
from app.state.state_factory import StateFactory
from app.state.state_validator import StateValidator
from app.state.state_manager import StateManager

__all__ = [
    # 枚举类型
    "IntentCategory",
    "SpecialistType",
    "QualityLevel",
    "OrchestrationMode",
    # 核心类
    "UnifiedState",
    "AgentMessage",
    "SpecialistResult",
    "ReflectionResult",
    # 工具类
    "StateFactory",
    "StateValidator",
    "StateManager",
]
