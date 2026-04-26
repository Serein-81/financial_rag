"""
Orchestrator Agent 集成测试

测试完整的任务拆解 → 专家执行 → 报告生成工作流
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

logging.basicConfig(level=logging.INFO)


async def test_complete_orchestrator_workflow():
    """测试完整的 Orchestrator 工作流"""
    print("\n=== 测试完整的 Orchestrator 工作流 ===")

    # 导入需要的模块
    from app.multi_agent_system.agents import get_orchestrator_agent
    from app.multi_agent_system.task_blackboard import TaskBlackboard, TaskStatus
    from app.mcp.orchestrator_tools import breakdown_task_to_blackboard, summarize_final_report

    # 1. 获取 Orchestrator Agent
    orchestrator = get_orchestrator_agent()
    print("✅ Orchestrator Agent 初始化完成")

    # 2. 使用真实黑板的模拟版本
    session_id = "integration_test_session"

    with patch('app.mcp.orchestrator_tools.TaskBlackboard') as MockBlackboard:
        # 创建模拟的 TaskBlackboard
        mock_blackboard = AsyncMock()
        MockBlackboard.return_value = mock_blackboard

        # 模拟任务创建
        mock_task_finance = MagicMock()
        mock_task_finance.task_id = "finance-task-001"
        mock_task_finance.task_type = "finance_analysis"
        mock_task_finance.priority = MagicMock(value=2)
        mock_task_finance.dependencies = []
        mock_task_finance.status = TaskStatus.COMPLETED
        mock_task_finance.description = "财务分析任务"
        mock_task_finance.output_data = {
            "content": "财务分析结果：企业年度营收增长15%，净利润率8.5%，现金流稳定"
        }
        mock_task_finance.metadata = {"importance": "high"}

        mock_task_tax = MagicMock()
        mock_task_tax.task_id = "tax-task-002"
        mock_task_tax.task_type = "tax_calculation"
        mock_task_tax.priority = MagicMock(value=2)
        mock_task_tax.dependencies = []
        mock_task_tax.status = TaskStatus.COMPLETED
        mock_task_tax.description = "税务计算任务"
        mock_task_tax.output_data = {
            "content": "税务分析结果：年度应缴税款45.2万元，建议优化税务结构可节省10-15%"
        }
        mock_task_tax.metadata = {"complexity": "medium"}

        # 设置模拟返回值
        mock_blackboard.create_task = AsyncMock(side_effect=[mock_task_finance, mock_task_tax])
        mock_blackboard.write_shared_data = AsyncMock()
        mock_blackboard.get_tasks_by_status = AsyncMock(return_value=[mock_task_finance, mock_task_tax])
        mock_blackboard.get_all_shared_data = AsyncMock(return_value={
            "dag_root_goal": "分析企业年度财务和税务状况",
            "task_count": 2
        })

        # 3. 测试 breakdown_task_to_blackboard
        print("\n📋 测试任务拆解...")
        breakdown_result = await breakdown_task_to_blackboard(
            user_goal="分析企业2024年度财务状况和税务优化方案",
            session_id=session_id,
            tenant_id="test-tenant",
            required_expertise=["finance", "tax"]
        )

        assert breakdown_result["status"] == "success"
        assert "task_graph" in breakdown_result
        assert len(breakdown_result["created_tasks"]) >= 2
        print(f"✅ 成功拆解为 {len(breakdown_result['created_tasks'])} 个任务")

        # 4. 测试 summarize_final_report
        print("\n📝 测试报告生成...")
        report_result = await summarize_final_report(
            session_id=session_id,
            tenant_id="test-tenant",
            user_query="分析企业2024年度财务状况和税务优化方案",
            report_title="企业财务与税务分析报告",
            format="markdown"
        )

        print(f"Report status: {report_result['status']}")
        print(f"Report sections: {len(report_result.get('sections', []))}")
        print(f"Has report content: {'report_content' in report_result}")

        if report_result["status"] == "success":
            sections = report_result.get("sections", [])
            print(f"\n📊 生成的报告章节 ({len(sections)}):")
            for i, section in enumerate(sections):
                print(f"  {i+1}. {section.get('title', '未命名章节')}")

            if "report_content" in report_result:
                content = report_result["report_content"]
                print(f"\n📄 报告内容预览 (前500字符):")
                print(content[:500] + "..." if len(content) > 500 else content)

        print("\n✅ 集成测试完成")


async def test_orchestrator_agent_workflow():
    """测试 OrchestratorAgent 的完整工作流方法"""
    print("\n=== 测试 OrchestratorAgent.execute_orchestrator_workflow() ===")

    from app.multi_agent_system.agents import OrchestratorAgent

    # 创建模拟的 LLM 适配器和工具管理器
    mock_llm_adapter = MagicMock()
    mock_tool_manager = MagicMock()

    with patch.object(OrchestratorAgent, 'breakdown_task_to_blackboard') as mock_breakdown, \
         patch.object(OrchestratorAgent, 'summarize_final_report') as mock_summarize:

        orchestrator = OrchestratorAgent(
            llm_adapter=mock_llm_adapter,
            tool_manager=mock_tool_manager,
            tenant_id="workflow-test"
        )

        # 设置模拟返回值
        mock_breakdown.return_value = {
            "status": "success",
            "created_tasks": [
                {"task_id": "task-1", "task_type": "finance_analysis"},
                {"task_id": "task-2", "task_type": "tax_calculation"}
            ],
            "summary": {"total_tasks": 2}
        }

        mock_summarize.return_value = {
            "status": "success",
            "report_content": "# 企业财务与税务分析报告\n\n## 执行摘要\n...",
            "sections": [
                {"section": "executive_summary", "title": "📊 执行摘要", "content": "..."},
                {"section": "finance_analysis", "title": "💰 财务分析结果", "content": "..."}
            ]
        }

        # 测试工作流执行
        result = await orchestrator.execute_orchestrator_workflow(
            user_goal="分析企业财务和税务状况",
            generate_report=True
        )

        print(f"Workflow status: {result['status']}")
        print(f"Workflow phase: {result.get('workflow', 'N/A')}")
        print(f"Task count: {len(result.get('task_ids', []))}")
        print(f"Has report: {result['report_result'] is not None}")
        print(f"Message: {result.get('message', 'N/A')}")

        assert result["status"] == "success"
        assert result["workflow"] == "orchestrator"
        assert len(result["task_ids"]) == 2
        assert result["report_result"] is not None

        print("\n✅ 工作流测试完成")


def test_orchestrator_prompt_files():
    """测试 Orchestrator Agent 的提示词文件"""
    print("\n=== 测试 Orchestrator Agent 提示词文件 ===")

    import os

    # 检查提示词文件是否存在
    prompt_dir = "app/prompts/agents/orchestrator"
    system_file = f"{prompt_dir}/system.md"
    agent_yaml = f"{prompt_dir}/agent.yaml"

    print(f"检查提示词目录: {prompt_dir}")
    print(f"系统提示词文件: {system_file}")
    print(f"Agent 配置: {agent_yaml}")

    # 检查文件是否存在
    files_exist = all(os.path.exists(f) for f in [system_file, agent_yaml])
    
    if files_exist:
        print("✅ 所有提示词文件都存在")
        
        # 读取文件内容进行简单验证
        try:
            with open(system_file, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"系统提示词长度: {len(content)} 字符")
                print("包含关键词: ", end="")
                keywords = ["Orchestrator Agent", "协调者", "任务拆解", "DAG"]
                for kw in keywords:
                    if kw in content:
                        print(f"{kw} ✓ ", end="")
                print()
        except Exception as e:
            print(f"读取系统提示词失败: {e}")

        try:
            import yaml
            with open(agent_yaml, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                print(f"Agent 名称: {config.get('agent', {}).get('name', 'N/A')}")
                print(f"工具数量: {len(config.get('tools', []))}")
                print(f"提示词文件: {config.get('prompt', {}).get('system_file', 'N/A')}")
        except Exception as e:
            print(f"读取 YAML 配置失败: {e}")

    else:
        print("❌ 部分提示词文件缺失")

    print("\n✅ 提示词文件检查完成")


async def main():
    """运行所有测试"""
    print("🚀 开始 Orchestrator Agent 集成测试")

    try:
        await test_complete_orchestrator_workflow()
    except Exception as e:
        print(f"❌ 工作流测试失败: {e}")

    try:
        await test_orchestrator_agent_workflow()
    except Exception as e:
        print(f"❌ 工作流方法测试失败: {e}")

    try:
        test_orchestrator_prompt_files()
    except Exception as e:
        print(f"❌ 提示词文件测试失败: {e}")

    print("\n🎉 所有测试完成")


if __name__ == "__main__":
    asyncio.run(main())
