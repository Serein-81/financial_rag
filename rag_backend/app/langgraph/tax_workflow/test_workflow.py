"""
税务提交工作流测试
"""

import asyncio
import logging
from app.langgraph.tax_workflow import TaxSubmissionWorkflow, create_initial_submission_state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_tax_submission_workflow():
    """
    测试税务提交工作流
    """
    logger.info("🚀 开始测试税务提交工作流")
    
    workflow = TaxSubmissionWorkflow()
    
    initial_state = create_initial_submission_state(
        session_id="test_session_001",
        tenant_id="tenant_001",
        user_id="user_001",
        fiscal_year=2024,
        fiscal_period="Q4",
        tax_types=["vat", "income_tax"],
        include_policy_benefits=True,
        include_risk_assessment=True
    )
    
    logger.info(f"📋 初始状态: {initial_state['session_id']}")
    logger.info(f"   - 财政年度: {initial_state['fiscal_year']}")
    logger.info(f"   - 税种: {initial_state['tax_types']}")
    
    config = {"configurable": {"thread_id": "test_session_001"}}
    
    try:
        result = await workflow.execute(
            session_id=initial_state["session_id"],
            tenant_id=initial_state["tenant_id"],
            user_id=initial_state["user_id"],
            fiscal_year=initial_state["fiscal_year"],
            fiscal_period=initial_state["fiscal_period"],
            tax_types=initial_state["tax_types"],
            include_policy_benefits=initial_state["include_policy_benefits"],
            include_risk_assessment=initial_state["include_risk_assessment"],
            config=config
        )
        
        logger.info("✅ 工作流执行完成")
        logger.info(f"   - 最终状态: {result.get('current_status')}")
        logger.info(f"   - 完成步骤: {result.get('current_step')}/{result.get('total_steps')}")
        
        if result.get("tax_calculations"):
            logger.info(f"   - 税务计算项: {len(result['tax_calculations'])}")
            for calc in result["tax_calculations"]:
                logger.info(f"     * {calc.tax_type}: ¥{calc.calculated_tax:,.2f}")
        
        if result.get("risk_items"):
            logger.info(f"   - 风险项: {len(result['risk_items'])}")
            for risk in result["risk_items"]:
                logger.info(f"     * {risk.risk_type} ({risk.severity})")
        
        logger.info(f"   - 总税负: ¥{result.get('total_tax_burden', 0):,.2f}")
        logger.info(f"   - 风险评分: {result.get('overall_risk_score', 0):.2f}")
        
        if result.get("final_summary"):
            logger.info(f"   - 摘要: {result['final_summary']}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ 工作流执行失败: {e}", exc_info=True)
        raise


async def test_workflow_components():
    """
    测试工作流组件
    """
    logger.info("🧪 测试工作流组件")
    
    workflow = TaxSubmissionWorkflow()
    
    logger.info("✅ 工作流初始化成功")
    
    viz_data = workflow.get_graph_visualization()
    logger.info(f"📊 工作流图: {len(viz_data['nodes'])} 个节点, {len(viz_data['edges'])} 条边")
    
    for node in viz_data["nodes"]:
        logger.info(f"   - 节点: {node['label']}")
    
    logger.info("✅ 组件测试完成")


if __name__ == "__main__":
    asyncio.run(test_workflow_components())
    asyncio.run(test_tax_submission_workflow())
