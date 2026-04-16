"""
混合编排模块

提供 LangGraph + Message Bus 的混合编排模式实现。

主要组件：
- ExpertConsultationNode: 专家会诊节点
- SummarizerNode: 上下文压缩节点
- BlackboardManager: 黑板模式管理器
- HybridGraphBuilder: 混合图构建器

混合编排模式：
1. 顶层使用 LangGraph 进行流程控制
2. 复杂协作场景使用 Message Bus 黑板模式
3. 通过 Summarizer Node 压缩上下文

使用示例：
```python
from app.langgraph.hybrid import (
    ExpertConsultationNode,
    SummarizerNode,
    BlackboardManager,
    HybridGraphBuilder
)

# 创建混合图
builder = HybridGraphBuilder(agents_registry)
hybrid_graph = builder.build()

# 执行工作流
result = await hybrid_graph.ainvoke(initial_state)
```

作者：Senior Python Backend Architect
版本：1.0.0
"""

from app.langgraph.hybrid.expert_consultation_node import (
    ExpertConsultationNode,
    ExpertConsultationState,
)
from app.langgraph.hybrid.summarizer_node import (
    SummarizerNode,
    SummarizerState,
)
from app.langgraph.hybrid.blackboard_manager import (
    BlackboardManager,
    BlackboardEntry,
)
from app.langgraph.hybrid.hybrid_graph import (
    HybridGraphBuilder,
)

__all__ = [
    # 专家会诊
    "ExpertConsultationNode",
    "ExpertConsultationState",
    # 上下文压缩
    "SummarizerNode",
    "SummarizerState",
    # 黑板模式
    "BlackboardManager",
    "BlackboardEntry",
    # 图构建器
    "HybridGraphBuilder",
]
