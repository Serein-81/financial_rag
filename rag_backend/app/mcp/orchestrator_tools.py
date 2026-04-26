"""
Orchestrator Agent 专用工具

核心职责：
1. breakdown_task_to_blackboard: 将用户宏大目标拆解为 DAG 顺序的子任务，写入黑板
2. summarize_final_report: 收集黑板结论，生成最终交付报告

这是 Orchestrator Agent（协调者/主路由智能体）的专用工具箱
"""

import logging
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.mcp.decorators import local_tool

logger = logging.getLogger(__name__)


@local_tool(
    description="""将用户的宏大目标拆解为 DAG（有向无环图）顺序的子任务，写入黑板。

    功能：
    1. 分析用户目标，识别关键子任务
    2. 确定任务间的依赖关系，构建 DAG
    3. 设置任务优先级和执行顺序
    4. 将所有任务写入 TaskBlackboard

    返回：
    - task_graph: DAG 结构描述
    - created_tasks: 创建的任务列表
    - execution_order: 建议的执行顺序

    使用场景：
    - 用户提出复杂、多步骤的企业分析需求
    - 需要多个专家协作的综合性任务
    - 需要明确执行顺序的依赖任务
    """,
    name="breakdown_task_to_blackboard",
    tags=["orchestrator", "task-decomposition", "dag", "blackboard"],
    timeout=60
)
async def breakdown_task_to_blackboard(
    user_goal: str,
    session_id: str,
    tenant_id: str,
    required_expertise: Optional[List[str]] = None,
    priority_tasks: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    将用户宏大目标拆解为 DAG 任务并写入黑板

    Args:
        user_goal: 用户的宏大目标描述
        session_id: 会话ID
        tenant_id: 租户ID
        required_expertise: 需要哪些专业领域的专家（如 ["finance", "tax", "legal"]）
        priority_tasks: 高优先级任务标识列表
        context: 额外上下文信息

    Returns:
        包含 DAG 结构、创建的任务、执行顺序的字典
    """
    try:
        from app.multi_agent_system.task_blackboard import TaskBlackboard, TaskPriority, TaskStatus

        blackboard = TaskBlackboard(session_id=session_id)

        expertise_to_task_type = {
            "finance": "finance_analysis",
            "tax": "tax_calculation",
            "legal": "legal_review",
            "report": "report_generation",
            "data": "data_gathering"
        }

        task_templates = {
            "finance_analysis": {
                "task_type": "finance_analysis",
                "description": "执行财务数据分析",
                "priority": TaskPriority.HIGH if "finance" in (required_expertise or []) else TaskPriority.NORMAL,
                "tags": {"finance", "analysis"}
            },
            "tax_calculation": {
                "task_type": "tax_calculation",
                "description": "执行税务计算和分析",
                "priority": TaskPriority.HIGH if "tax" in (required_expertise or []) else TaskPriority.NORMAL,
                "tags": {"tax", "calculation"}
            },
            "legal_review": {
                "task_type": "legal_review",
                "description": "执行法律合规审查",
                "priority": TaskPriority.HIGH if "legal" in (required_expertise or []) else TaskPriority.NORMAL,
                "tags": {"legal", "compliance"}
            },
            "report_generation": {
                "task_type": "report_generation",
                "description": "生成综合分析报告",
                "priority": TaskPriority.NORMAL,
                "tags": {"report", "summary"}
            },
            "data_gathering": {
                "task_type": "data_gathering",
                "description": "收集和整理数据",
                "priority": TaskPriority.NORMAL,
                "tags": {"data", "collection"}
            }
        }

        if required_expertise:
            needed_tasks = [
                task_templates.get(expertise_to_task_type.get(exp, "data_gathering"), task_templates["data_gathering"])
                for exp in required_expertise
            ]
        else:
            needed_tasks = [
                task_templates["finance_analysis"],
                task_templates["tax_calculation"],
                task_templates["report_generation"]
            ]

        dag_structure = {
            "parallel_groups": [],
            "sequential_order": [],
            "dependencies": {}
        }

        if len(needed_tasks) > 1:
            for i, task in enumerate(needed_tasks[:-1]):
                dag_structure["dependencies"][i] = [i + 1]
            dag_structure["sequential_order"] = list(range(len(needed_tasks)))
        else:
            dag_structure["parallel_groups"] = [0]

        created_tasks = []
        for i, task_spec in enumerate(needed_tasks):
            is_priority = task_spec["task_type"] in (priority_tasks or [])
            task = await blackboard.create_task(
                task_type=task_spec["task_type"],
                description=f"[{session_id}] {user_goal[:50]}... -> {task_spec['description']}",
                priority=TaskPriority.CRITICAL if is_priority else task_spec["priority"],
                created_by="orchestrator_agent",
                input_data={
                    "user_goal": user_goal,
                    "parent_goal": user_goal,
                    "task_index": i,
                    "total_tasks": len(needed_tasks)
                },
                dependencies=[created_tasks[j].task_id for j in dag_structure.get("dependencies", {}).get(i, []) if j < len(created_tasks)],
                metadata={
                    "expertise_required": [t for t, v in expertise_to_task_type.items() if v == task_spec["task_type"]],
                    "dag_position": i,
                    "is_final_task": i == len(needed_tasks) - 1
                },
                tags=task_spec["tags"]
            )
            created_tasks.append(task)

        await blackboard.write_shared_data(
            key="dag_root_goal",
            value=user_goal
        )
        await blackboard.write_shared_data(
            key="task_count",
            value=len(created_tasks)
        )

        result = {
            "status": "success",
            "task_graph": {
                "nodes": [{"id": t.task_id, "type": t.task_type, "label": t.description[:50]} for t in created_tasks],
                "edges": [{"from": created_tasks[j].task_id, "to": t.task_id} for i, deps in dag_structure.get("dependencies", {}).items() for j in deps for t in created_tasks[i + 1:i + 2] if i < len(created_tasks) - 1]
            },
            "created_tasks": [
                {
                    "task_id": t.task_id,
                    "task_type": t.task_type,
                    "priority": t.priority.value if hasattr(t.priority, 'value') else str(t.priority),
                    "dependencies": t.dependencies,
                    "status": t.status.value if hasattr(t.status, 'value') else str(t.status)
                }
                for t in created_tasks
            ],
            "execution_order": dag_structure["sequential_order"] or dag_structure["parallel_groups"],
            "summary": {
                "total_tasks": len(created_tasks),
                "parallel_execution_possible": len(dag_structure.get("parallel_groups", [])) > 0,
                "estimated_stages": len(dag_structure["sequential_order"]) if dag_structure["sequential_order"] else 1
            }
        }

        logger.info(f"[breakdown_task_to_blackboard] 成功拆解目标，创建 {len(created_tasks)} 个任务")
        return result

    except Exception as e:
        logger.error(f"[breakdown_task_to_blackboard] 拆解失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"任务拆解失败: {str(e)}"
        }


@local_tool(
    description="""收集黑板上的所有结论，写成最终的交付报告。

    功能：
    1. 从 TaskBlackboard 读取所有已完成任务的结论
    2. 整合各专家的分析结果
    3. 生成结构化的最终交付报告
    4. 包含执行摘要、详细分析、建议和后续步骤

    使用场景：
    - 所有子任务完成后，需要汇总成最终报告
    - 用户请求生成综合交付物
    - 需要清晰、结构化的最终输出
    """,
    name="summarize_final_report",
    tags=["orchestrator", "report-generation", "summarization", "blackboard"],
    timeout=120
)
async def summarize_final_report(
    session_id: str,
    tenant_id: str,
    user_query: str,
    report_title: Optional[str] = None,
    include_executive_summary: bool = True,
    include_recommendations: bool = True,
    format: str = "markdown"
) -> Dict[str, Any]:
    """
    收集黑板结论，生成最终交付报告

    Args:
        session_id: 会话ID
        tenant_id: 租户ID
        user_query: 用户原始查询（用于报告上下文）
        report_title: 报告标题（可选）
        include_executive_summary: 是否包含执行摘要
        include_recommendations: 是否包含建议
        format: 报告格式（markdown/html/json）

    Returns:
        包含报告内容的字典
    """
    try:
        from app.multi_agent_system.task_blackboard import TaskBlackboard, TaskStatus

        blackboard = TaskBlackboard(session_id=session_id)

        completed_tasks = await blackboard.get_tasks_by_status(TaskStatus.COMPLETED)
        
        if not completed_tasks:
            return {
                "status": "warning",
                "message": "没有找到已完成的任务，无法生成报告",
                "report": None
            }

        shared_data = await blackboard.get_all_shared_data()
        root_goal = shared_data.get("dag_root_goal", user_query)

        section_content = []
        finance_results = []
        tax_results = []
        legal_results = []

        for task in completed_tasks:
            if task.output_data:
                task_type = task.task_type
                content = task.output_data.get("content", "") or task.output_data.get("response", "")

                if task_type == "finance_analysis":
                    finance_results.append({"task_id": task.task_id, "content": content, "metadata": task.metadata})
                elif task_type == "tax_calculation":
                    tax_results.append({"task_id": task.task_id, "content": content, "metadata": task.metadata})
                elif task_type == "legal_review":
                    legal_results.append({"task_id": task.task_id, "content": content, "metadata": task.metadata})
                elif task_type == "report_generation":
                    section_content.append({"section": "final_report", "content": content})

        report_sections = []

        if include_executive_summary:
            report_sections.append({
                "section": "executive_summary",
                "title": "📊 执行摘要",
                "content": f"根据您的查询「{user_query[:100]}...」，我们完成了以下分析：\n\n" +
                          f"- 完成财务分析 {len(finance_results)} 项\n" +
                          f"- 完成税务计算 {len(tax_results)} 项\n" +
                          f"- 完成法律审查 {len(legal_results)} 项\n" +
                          f"- 总任务数: {len(completed_tasks)}"
            })

        if finance_results:
            report_sections.append({
                "section": "finance_analysis",
                "title": "💰 财务分析结果",
                "content": "\n\n".join([r["content"] for r in finance_results if r["content"]])
            })

        if tax_results:
            report_sections.append({
                "section": "tax_calculation",
                "title": "📋 税务分析结果",
                "content": "\n\n".join([r["content"] for r in tax_results if r["content"]])
            })

        if legal_results:
            report_sections.append({
                "section": "legal_review",
                "title": "⚖️ 法律合规审查",
                "content": "\n\n".join([r["content"] for r in legal_results if r["content"]])
            })

        if include_recommendations:
            recommendations = []
            if finance_results:
                recommendations.append("财务建议：根据分析结果，建议关注现金流管理和资产结构优化")
            if tax_results:
                recommendations.append("税务建议：考虑合法合规的税务筹划方案，降低税负")
            if legal_results:
                recommendations.append("法务建议：确保合同条款符合最新法规要求")

            report_sections.append({
                "section": "recommendations",
                "title": "💡 建议与后续步骤",
                "content": "\n".join([f"{i+1}. {rec}" for i, rec in enumerate(recommendations)]) if recommendations else "暂无具体建议"
            })

        report_sections.extend(section_content)

        final_report = {
            "metadata": {
                "title": report_title or f"关于「{user_query[:30]}...」的综合分析报告",
                "generated_at": datetime.now().isoformat(),
                "session_id": session_id,
                "tenant_id": tenant_id,
                "total_tasks": len(completed_tasks),
                "format": format
            },
            "sections": report_sections,
            "raw_results": {
                "finance": finance_results,
                "tax": tax_results,
                "legal": legal_results
            }
        }

        if format == "markdown":
            report_text = f"# {final_report['metadata']['title']}\n\n"
            report_text += f"**生成时间**: {final_report['metadata']['generated_at']}\n\n"
            report_text += "---\n\n"

            for section in report_sections:
                report_text += f"## {section['title']}\n\n{section['content']}\n\n---\n\n"

            final_report["report_text"] = report_text
            final_report["report_content"] = report_text

        elif format == "html":
            html_parts = [f"<h1>{final_report['metadata']['title']}</h1>"]
            html_parts.append(f"<p><em>生成时间: {final_report['metadata']['generated_at']}</em></p>")

            for section in report_sections:
                html_parts.append(f"<h2>{section['title']}</h2>")
                html_parts.append(f"<p>{section['content'].replace(chr(10), '<br>')}</p>")

            final_report["report_text"] = "\n".join(html_parts)
            final_report["report_content"] = "\n".join(html_parts)

        else:
            final_report["report_text"] = str(final_report)
            final_report["report_content"] = str(final_report)

        await blackboard.write_shared_data(
            key="final_report_generated",
            value=True
        )

        logger.info(f"[summarize_final_report] 成功生成报告，包含 {len(report_sections)} 个章节")
        return final_report

    except Exception as e:
        logger.error(f"[summarize_final_report] 生成报告失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"报告生成失败: {str(e)}",
            "report": None
        }


def create_orchestrator_tools() -> List:
    """创建 Orchestrator Agent 专用工具列表"""
    return [
        breakdown_task_to_blackboard,
        summarize_final_report
    ]
