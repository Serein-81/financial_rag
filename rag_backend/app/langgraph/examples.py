"""
LangGraph 使用示例

展示如何将 LangGraph 与现有 Agent 集成
"""

import asyncio
import uuid
from typing import Dict, Any

from app.agent_framework.llm.openai_adapter import OpenAIAdapter
from app.agent_framework.llm.zhipu_adapter import ZhipuAIAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from app.agent_framework.core.react_agent import ReActAgent
from app.agent_framework.core.reflect_agent import ReflectAgent
from app.multi_agent_system.agents.finance_specialist import FinanceSpecialist
from app.multi_agent_system.agents.tax_specialist import TaxSpecialist
from app.multi_agent_system.agents.legal_specialist import LegalSpecialist
from app.multi_agent_system.agents.reflection_specialist import ReflectionSpecialist
from app.multi_agent_system.agents.intent_router_agent import IntentRouterAgent

from app.langgraph import (
    MultiAgentWorkflowBuilder,
    SimpleAgentWorkflow,
    AgentState
)


def create_agents_registry(
    llm_adapter: Any,
    tool_manager: ToolManager,
    enable_rag: bool = True
) -> Dict[str, Any]:
    """
    创建 Agent 注册表
    
    Args:
        llm_adapter: LLM 适配器
        tool_manager: 工具管理器
        enable_rag: 是否启用 RAG
        
    Returns:
        Agent 注册表
    """
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
            enable_rag=enable_rag
        ),
        "tax": TaxSpecialist(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            enable_rag=enable_rag
        ),
        "legal": LegalSpecialist(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            enable_rag=enable_rag
        ),
        "reflection": ReflectionSpecialist(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            confidence_threshold=0.7
        ),
        "rag_retriever": None,  # 稍后配置
        "aggregator": None,  # 稍后配置
        "direct_answer": None  # 稍后配置
    }
    
    return registry


async def example_simple_workflow():
    """
    示例 1: 简单的单 Agent 工作流
    """
    print("\n" + "=" * 60)
    print("示例 1: 简单工作流")
    print("=" * 60)
    
    llm_adapter = OpenAIAdapter(api_key="your-api-key")
    tool_manager = ToolManager()
    
    agent = ReActAgent(
        llm_adapter=llm_adapter,
        tool_manager=tool_manager,
        system_prompt="你是一个有用的助手"
    )
    
    workflow = SimpleAgentWorkflow(agent=agent, name="helper")
    
    result = await workflow.invoke(
        session_id=str(uuid.uuid4()),
        tenant_id="default",
        user_id="user1",
        user_query="你好，请介绍一下你自己",
        iteration=0,
        max_iterations=10,
        retry_count=0,
        max_retries=3,
        error=None,
        error_history=[],
        messages=[],
        metadata={},
        intent=None,
        intent_confidence=0.0,
        routing_strategy=None,
        target_specialists=[],
        rag_context=None,
        specialist_results=[],
        reflection_result=None,
        aggregated_response=None,
        final_answer=None,
        needs_human_review=False
    )
    
    print(f"\n最终答案: {result.get('final_answer')}")
    print("=" * 60)


async def example_multi_agent_workflow():
    """
    示例 2: 多智能体工作流
    """
    print("\n" + "=" * 60)
    print("示例 2: 多智能体工作流")
    print("=" * 60)
    
    llm_adapter = OpenAIAdapter(api_key="your-api-key")
    tool_manager = ToolManager()
    
    registry = create_agents_registry(llm_adapter, tool_manager)
    
    builder = MultiAgentWorkflowBuilder(
        agents_registry=registry,
        enable_checkpointer=True,
        enable_reflection=True,
        max_iterations=10,
        max_retries=3
    )
    
    builder.compile()
    
    result = await builder.invoke(
        session_id=str(uuid.uuid4()),
        tenant_id="enterprise_001",
        user_id="user_001",
        user_query="我想了解企业税收优惠政策有哪些？",
        confidence_threshold=0.7
    )
    
    print(f"\n最终答案: {result.get('final_answer')}")
    print(f"意图分类: {result.get('intent')}")
    print(f"目标专家: {result.get('target_specialists')}")
    print(f"质量评分: {result.get('reflection_result', {}).get('overall_score', 'N/A')}")
    print(f"需要人工审核: {result.get('needs_human_review')}")
    print("=" * 60)


async def example_streaming_workflow():
    """
    示例 3: 流式执行工作流
    """
    print("\n" + "=" * 60)
    print("示例 3: 流式执行工作流")
    print("=" * 60)
    
    llm_adapter = OpenAIAdapter(api_key="your-api-key")
    tool_manager = ToolManager()
    
    registry = create_agents_registry(llm_adapter, tool_manager)
    
    builder = MultiAgentWorkflowBuilder(
        agents_registry=registry,
        enable_reflection=True
    )
    builder.compile()
    
    print("\n流式输出:")
    print("-" * 40)
    
    async for state in builder.stream(
        session_id=str(uuid.uuid4()),
        tenant_id="enterprise_001",
        user_id="user_001",
        user_query="解释一下增值税的计算方法"
    ):
        if state.get("specialist_results"):
            print(f"\n[节点] 专家完成: {len(state['specialist_results'])} 个")
        if state.get("reflection_result"):
            print(f"[节点] 反思完成: 质量={state['reflection_result'].get('quality_level')}")
        if state.get("final_answer"):
            print(f"\n[完成] 最终答案已生成")
    
    print("-" * 40)
    print("=" * 60)


async def example_with_checkpointer():
    """
    示例 4: 带状态持久化的工作流
    """
    print("\n" + "=" * 60)
    print("示例 4: 状态持久化")
    print("=" * 60)
    
    from langgraph.checkpoint.memory import MemorySaver
    
    llm_adapter = OpenAIAdapter(api_key="your-api-key")
    tool_manager = ToolManager()
    
    registry = create_agents_registry(llm_adapter, tool_manager)
    
    builder = MultiAgentWorkflowBuilder(
        agents_registry=registry,
        enable_checkpointer=True,
        enable_reflection=True
    )
    
    checkpointer = MemorySaver()
    builder.compile()
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    result = await builder.invoke(
        session_id=thread_id,
        tenant_id="enterprise_001",
        user_id="user_001",
        user_query="企业年报应该包含哪些内容？",
        config=config
    )
    
    print(f"首次执行完成，thread_id: {thread_id}")
    print(f"最终答案: {result.get('final_answer')[:100]}...")
    
    print("\n检查点已保存，可以稍后恢复执行")
    print("=" * 60)


async def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("LangGraph 多智能体工作流示例")
    print("=" * 60)
    
    await example_simple_workflow()
    await example_multi_agent_workflow()
    await example_streaming_workflow()
    await example_with_checkpointer()
    
    print("\n所有示例执行完成!")


if __name__ == "__main__":
    asyncio.run(main())
