"""
LangGraph 熔断器使用示例

展示如何在工作流中集成熔断保护和中断恢复机制
"""

import asyncio
import logging
from typing import Dict, Any, List
from app.langgraph.circuit_breaker_integration import (
    LangGraphCircuitBreakerManager,
    CircuitBreakerNode,
    WorkflowRecoveryManager,
    CircuitBreakerMiddleware,
    get_circuit_breaker_manager,
    initialize_circuit_breaker_manager,
    CircuitBreakerConfig
)
from app.multi_agent_system.async_task_scheduler import TaskState

logger = logging.getLogger(__name__)


async def example_1_basic_usage():
    """
    示例1: 基础熔断器使用
    
    场景：保护 LLM 服务调用
    """
    print("\n" + "=" * 60)
    print("示例1: 基础熔断器使用")
    print("=" * 60)
    
    manager = LangGraphCircuitBreakerManager()
    await manager.initialize()
    
    manager.register_breaker("llm_service", CircuitBreakerConfig(
        failure_threshold=3,
        timeout=10.0,
        success_threshold=2
    ))
    
    async def call_llm(query: str) -> str:
        """模拟 LLM 调用"""
        await asyncio.sleep(0.1)
        if hash(query) % 5 == 0:
            raise Exception("LLM 服务暂时不可用")
        return f"LLM 响应: {query}"
    
    for i in range(10):
        result = await manager.execute_with_protection(
            "llm_service",
            call_llm,
            f"查询 {i}"
        )
        
        status = "✅" if result.state == TaskState.COMPLETED else "❌"
        print(f"{status} 第{i+1}次调用: {result.state.value}")
        
        if result.state != TaskState.COMPLETED:
            print(f"   错误: {result.error}")
    
    stats = manager.get_breaker_stats("llm_service")
    print(f"\n熔断器状态: {stats}")


async def example_2_with_langgraph_node():
    """
    示例2: 在 LangGraph 节点中使用熔断器
    
    场景：财务专家节点保护
    """
    print("\n" + "=" * 60)
    print("示例2: LangGraph 节点熔断保护")
    print("=" * 60)
    
    manager = get_circuit_breaker_manager()
    await manager.initialize()
    
    manager.register_breaker("finance_specialist")
    
    async def finance_analysis(state: Dict[str, Any]) -> Dict[str, Any]:
        """财务分析节点"""
        query = state.get("query", "")
        
        async def analyze():
            await asyncio.sleep(0.2)
            if "error" in query.lower():
                raise Exception("财务数据服务异常")
            return f"财务分析完成: {query}"
        
        result = await manager.execute_with_protection(
            "finance_specialist",
            analyze
        )
        
        if result.state == TaskState.COMPLETED:
            return {
                **state,
                "finance_result": result.result,
                "analysis_successful": True
            }
        else:
            return {
                **state,
                "finance_error": result.error,
                "analysis_successful": False,
                "needs_human_review": True
            }
    
    state1 = {"query": "分析第一季度收入"}
    result1 = await finance_analysis(state1)
    print(f"✅ 正常查询结果: {result1.get('finance_result')}")
    
    state2 = {"query": "分析错误数据"}
    result2 = await finance_analysis(state2)
    print(f"❌ 错误查询处理: needs_human_review={result2.get('needs_human_review')}")


async def example_3_workflow_recovery():
    """
    示例3: 工作流中断恢复
    
    场景：任务执行中断后的恢复
    """
    print("\n" + "=" * 60)
    print("示例3: 工作流中断恢复机制")
    print("=" * 60)
    
    class MockCheckpointer:
        async def get(self, thread_id: str):
            return None
    
    recovery_manager = WorkflowRecoveryManager(MockCheckpointer())
    
    async def simulate_workflow(thread_id: str, initial_state: Dict[str, Any] = None):
        """模拟工作流执行"""
        state = initial_state or {"step": 0, "data": []}
        
        for step in range(state["step"], 5):
            if step == 2 and state.get("simulate_error"):
                raise Exception("模拟的网络中断")
            
            state["step"] = step + 1
            state["data"].append(f"步骤{step+1}完成")
            await asyncio.sleep(0.1)
        
        return {"status": "completed", "final_state": state}
    
    thread_id = "workflow_001"
    
    try:
        result = await simulate_workflow(thread_id, {"simulate_error": True})
        
    except Exception as e:
        print(f"⚠️ 工作流中断: {e}")
        
        current_state = {"step": 2, "data": ["步骤1完成", "步骤2完成"], "simulate_error": True}
        await recovery_manager.save_interrupted_state(
            thread_id,
            current_state,
            "step_2_node",
            str(e)
        )
        
        interrupted = await recovery_manager.get_interrupted_workflow(thread_id)
        print(f"📋 已保存中断状态: 步骤{interrupted['state']['step']}")
        
        retry_result = await recovery_manager.retry_interrupted_workflow(
            thread_id,
            simulate_workflow,
            initial_state={"step": 2, "data": ["步骤1完成", "步骤2完成"], "simulate_error": False}
        )
        print(f"✅ 工作流恢复成功: {retry_result['status']}")


async def example_4_circuit_breaker_middleware():
    """
    示例4: 使用中间件包装外部调用
    
    场景：自动保护多个外部服务
    """
    print("\n" + "=" * 60)
    print("示例4: 熔断器中间件")
    print("=" * 60)
    
    manager = get_circuit_breaker_manager()
    await manager.initialize()
    
    middleware = CircuitBreakerMiddleware(manager)
    
    manager.register_breaker("erp_service")
    manager.register_breaker("crm_service")
    
    async def erp_api_call(endpoint: str):
        """ERP API 调用"""
        await asyncio.sleep(0.1)
        if "fail" in endpoint:
            raise Exception("ERP 服务不可用")
        return {"status": "success", "data": f"ERP: {endpoint}"}
    
    async def crm_api_call(endpoint: str):
        """CRM API 调用"""
        await asyncio.sleep(0.1)
        if "fail" in endpoint:
            raise Exception("CRM 服务不可用")
        return {"status": "success", "data": f"CRM: {endpoint}"}
    
    protected_erp = middleware.wrap_external_call("erp_service", erp_api_call)
    protected_crm = middleware.wrap_external_call("crm_service", crm_api_call)
    
    result1 = await protected_erp("customer/list")
    print(f"✅ ERP 调用成功: {result1}")
    
    result2 = await protected_crm("fail/endpoint")
    print(f"❌ CRM 调用失败: {result2}")
    
    stats = middleware.get_protected_calls_stats()
    print(f"\n📊 调用统计: {stats}")
    
    all_breakers = manager.get_all_stats()
    print(f"🔧 熔断器状态:")
    for name, breaker_stat in all_breakers.items():
        print(f"   {name}: {breaker_stat['state']}")


async def main():
    """主函数"""
    print("\n🚀 LangGraph 熔断器使用示例")
    print("=" * 60)
    
    await example_1_basic_usage()
    await example_2_with_langgraph_node()
    await example_3_workflow_recovery()
    await example_4_circuit_breaker_middleware()
    
    print("\n" + "=" * 60)
    print("✅ 所有示例执行完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
