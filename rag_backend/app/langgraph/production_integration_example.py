"""
LangGraph 工作流熔断器集成示例

这是一个完整的示例，展示如何在生产环境中将熔断器集成到 LangGraph 工作流
"""

import asyncio
import logging
from typing import Literal
from app.langgraph.state import AgentState
from app.langgraph.circuit_breaker_integration import (
    get_circuit_breaker_manager,
    CircuitBreakerConfig
)
from app.multi_agent_system.async_task_scheduler import TaskState

logger = logging.getLogger(__name__)


class ProtectedLangGraphWorkflow:
    """
    受保护的 LangGraph 工作流
    
    集成熔断器保护，防止外部服务故障影响工作流
    """
    
    def __init__(self):
        self.circuit_breaker_manager = get_circuit_breaker_manager()
        self._initialized = False
    
    async def initialize(self):
        """初始化熔断器配置"""
        if self._initialized:
            return
        
        await self.circuit_breaker_manager.initialize()
        
        self.circuit_breaker_manager.register_breaker("finance_agent", CircuitBreakerConfig(
            failure_threshold=3,
            timeout=30.0,
            success_threshold=2
        ))
        
        self.circuit_breaker_manager.register_breaker("tax_agent", CircuitBreakerConfig(
            failure_threshold=3,
            timeout=30.0,
            success_threshold=2
        ))
        
        self.circuit_breaker_manager.register_breaker("erp_service", CircuitBreakerConfig(
            failure_threshold=5,
            timeout=60.0,
            success_threshold=2
        ))
        
        self._initialized = True
        logger.info("✅ ProtectedWorkflow 初始化完成")
    
    async def finance_analysis_node(self, state: AgentState) -> AgentState:
        """
        财务分析节点 - 带熔断保护
        
        Args:
            state: LangGraph 状态
            
        Returns:
            AgentState: 更新后的状态
        """
        query = state.get("query", "")
        
        async def finance_analysis():
            """实际的财务分析逻辑"""
            logger.info(f"🔍 执行财务分析: {query}")
            
            await asyncio.sleep(0.5)
            
            if "error" in query.lower():
                raise Exception("财务服务暂时不可用")
            
            return {
                "analysis": f"财务分析结果 for: {query}",
                "confidence": 0.85
            }
        
        result = await self.circuit_breaker_manager.execute_with_protection(
            "finance_agent",
            finance_analysis
        )
        
        if result.state == TaskState.COMPLETED:
            logger.info("✅ 财务分析节点执行成功")
            return {
                **state,
                "finance_result": result.result,
                "finance_confidence": result.result.get("confidence", 0.0)
            }
        else:
            logger.error(f"❌ 财务分析节点执行失败: {result.error}")
            return {
                **state,
                "finance_error": result.error,
                "finance_fallback_triggered": True
            }
    
    async def tax_analysis_node(self, state: AgentState) -> AgentState:
        """
        税务分析节点 - 带熔断保护
        
        Args:
            state: LangGraph 状态
            
        Returns:
            AgentState: 更新后的状态
        """
        query = state.get("query", "")
        
        async def tax_analysis():
            """实际的税务分析逻辑"""
            logger.info(f"🔍 执行税务分析: {query}")
            
            await asyncio.sleep(0.5)
            
            if "fail" in query.lower():
                raise Exception("税务API调用失败")
            
            return {
                "tax_report": f"税务报告 for: {query}",
                "tax_amount": 10000.0
            }
        
        result = await self.circuit_breaker_manager.execute_with_protection(
            "tax_agent",
            tax_analysis
        )
        
        if result.state == TaskState.COMPLETED:
            logger.info("✅ 税务分析节点执行成功")
            return {
                **state,
                "tax_result": result.result
            }
        else:
            logger.error(f"❌ 税务分析节点执行失败: {result.error}")
            return {
                **state,
                "tax_error": result.error,
                "tax_fallback_triggered": True
            }
    
    async def erp_integration_node(self, state: AgentState) -> AgentState:
        """
        ERP集成节点 - 带熔断保护
        
        Args:
            state: LangGraph 状态
            
        Returns:
            AgentState: 更新后的状态
        """
        async def erp_call():
            """ERP API调用"""
            logger.info("🔗 调用ERP系统")
            
            await asyncio.sleep(0.3)
            
            return {
                "erp_status": "connected",
                "data": {"revenue": 50000}
            }
        
        result = await self.circuit_breaker_manager.execute_with_protection(
            "erp_service",
            erp_call
        )
        
        if result.state == TaskState.COMPLETED:
            logger.info("✅ ERP集成节点执行成功")
            return {
                **state,
                "erp_data": result.result
            }
        else:
            logger.error(f"❌ ERP集成节点执行失败: {result.error}")
            return {
                **state,
                "erp_error": result.error
            }
    
    async def route_to_agents(self, state: AgentState) -> Literal["finance", "tax", "done"]:
        """
        路由函数 - 根据状态决定下一步
        
        Args:
            state: LangGraph 状态
            
        Returns:
            str: 下一个节点名称
        """
        if state.get("finance_fallback_triggered") or state.get("tax_fallback_triggered"):
            logger.warning("⚠️ 检测到降级触发，跳转到人工审核")
            return "human_review"
        
        if not state.get("finance_result"):
            return "finance"
        
        if not state.get("tax_result"):
            return "tax"
        
        return "done"
    
    async def aggregate_results(self, state: AgentState) -> AgentState:
        """
        聚合结果节点
        
        Args:
            state: LangGraph 状态
            
        Returns:
            AgentState: 最终状态
        """
        logger.info("📊 聚合工作流结果")
        
        final_result = {
            "finance_analysis": state.get("finance_result"),
            "tax_report": state.get("tax_result"),
            "erp_data": state.get("erp_data"),
            "has_errors": any([
                state.get("finance_error"),
                state.get("tax_error"),
                state.get("erp_error")
            ]),
            "partial_failure": any([
                state.get("finance_fallback_triggered"),
                state.get("tax_fallback_triggered")
            ])
        }
        
        return {
            **state,
            "final_result": final_result,
            "status": "completed"
        }
    
    async def human_review_node(self, state: AgentState) -> AgentState:
        """
        人工审核节点 - 当熔断触发时降级到这里
        
        Args:
            state: LangGraph 状态
            
        Returns:
            AgentState: 需要人工介入的状态
        """
        logger.warning("👤 工作流需要人工审核")
        
        return {
            **state,
            "needs_human_review": True,
            "review_reason": "熔断器触发，服务降级",
            "status": "pending_review"
        }


async def example_production_usage():
    """
    生产环境使用示例
    
    展示完整的工作流执行流程
    """
    print("\n" + "=" * 70)
    print("🚀 LangGraph 熔断器生产环境示例")
    print("=" * 70)
    
    workflow = ProtectedLangGraphWorkflow()
    await workflow.initialize()
    
    test_queries = [
        "分析第一季度财务状况",     # 正常查询
        "error query",            # 会触发财务分析失败
        "fail query",             # 会触发税务分析失败
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*70}")
        print(f"测试场景 {i}: {query}")
        print(f"{'='*70}")
        
        state = {
            "query": query,
            "messages": [],
            "iteration": 0
        }
        
        try:
            if not state.get("finance_result"):
                state = await workflow.finance_analysis_node(state)
            
            if not state.get("tax_result"):
                state = await workflow.tax_analysis_node(state)
            
            if not state.get("erp_data"):
                state = await workflow.erp_integration_node(state)
            
            if state.get("needs_human_review"):
                state = await workflow.human_review_node(state)
            else:
                state = await workflow.aggregate_results(state)
            
            print("\n✅ 工作流完成")
            print(f"   财务结果: {state.get('finance_result')}")
            print(f"   税务结果: {state.get('tax_result')}")
            print(f"   ERP数据: {state.get('erp_data')}")
            
            if state.get("has_errors"):
                print("   ⚠️ 存在错误")
            
        except Exception as e:
            print(f"❌ 工作流执行异常: {e}")
        
        stats = workflow.circuit_breaker_manager.get_all_stats()
        print("\n📊 当前熔断器状态:")
        for name, breaker_stat in stats.items():
            print(f"   {name}: {breaker_stat['state']} "
                  f"(失败: {breaker_stat['failure_count']}, "
                  f"成功: {breaker_stat['success_count']})")
    
    print("\n" + "=" * 70)
    print("✅ 所有测试场景执行完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(example_production_usage())
