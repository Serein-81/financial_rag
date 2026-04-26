"""
MCP 基础设施工具

提供多智能体系统的核心基础设施工具：
1. get_current_time_and_context: 绝对时间锚点（所有 Agent 通用）
2. delegate_task_to_blackboard: 派单印章（Orchestrator 专用）

工具设计原则：
- 时间锚点：赋予 Agent 物理世界的时间感知，解决大模型时间线混乱问题
- 派单印章：唯一的状态写入口，通过 DAG 构建任务依赖关系
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from app.mcp.decorators import local_tool

logger = logging.getLogger(__name__)

VALID_AGENT_ROLES = ["Finance_Agent", "Tax_Agent", "Legal_Agent"]


class TimeQueryInput(BaseModel):
    timezone: str = Field("Asia/Shanghai", description="目标时区")


class SubTaskDefinition(BaseModel):
    assignee_role: str = Field(..., description="指派的专家角色")
    task_description: str = Field(..., description="清晰、明确、不可产生歧义的子任务执行指令")
    depends_on_task_ids: List[str] = Field(default=[], description="该任务必须等待哪些 task_id 完成后才能开始")


class TaskDelegationInput(BaseModel):
    global_objective: str = Field(..., description="本次拆解的全局宏观目标")
    sub_tasks: List[SubTaskDefinition] = Field(..., description="拆解出的子任务列表")


@local_tool(
    description="""获取系统当前的绝对物理时间、日期、星期和时区信息。

    架构意图：
    - 大模型没有生物钟，记忆停留在训练数据截止日期
    - 当用户提问"今年最新的增值税政策"或"对比上个月营收"时，
      如果不知道"今年"是 2026 年，大模型会陷入时间线混乱

    使用场景（【必须】调用此工具）：
    - 用户请求包含相对时间词：今年、去年、上个月、本季度、下周
    - 需要计算历史数据对比
    - 处理政策查询时需要明确时间范围
    - 任何需要区分"现在"和"过去"的场景

    返回维度：
    - absolute_datetime: 完整时间戳（含时区）
    - current_year/current_month/current_quarter: 时间分解
    - day_of_week: 星期信息（用于工作日判断）
    """,
    name="get_current_time_and_context",
    tags=["foundation", "time", "anchor", "context"],
    timeout=5
)
async def get_current_time_and_context(
    timezone: str = "Asia/Shanghai"
) -> str:
    """
    获取系统当前的绝对物理时间、日期、星期和时区信息

    Args:
        timezone: 目标时区，默认 Asia/Shanghai

    Returns:
        JSON 字符串包含全维度时间信息
    """
    try:
        import pytz

        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz)

        result = {
            "absolute_datetime": current_time.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "current_year": current_time.year,
            "current_month": current_time.month,
            "current_quarter": (current_time.month - 1) // 3 + 1,
            "day_of_week": current_time.strftime("%A"),
            "day_of_week_short": current_time.strftime("%a"),
            "is_weekend": current_time.weekday() >= 5,
            "date_only": current_time.strftime("%Y-%m-%d"),
            "time_only": current_time.strftime("%H:%M:%S"),
            "timezone_offset": current_time.strftime("%z"),
            "system_notice": "请严格以此时间作为推算'当前'和'历史'数据的唯一基准",
            "relative_time_rules": {
                "今年": f"{current_time.year}年",
                "去年": f"{current_time.year - 1}年",
                "前年": f"{current_time.year - 2}年",
                "明年": f"{current_time.year + 1}年",
                "本季度": f"Q{(current_time.month - 1) // 3 + 1}",
                "上季度": f"Q{((current_time.month - 1) // 3) % 4 + 1}",
                "本月": f"{current_time.year}年{current_time.month}月",
                "上月": f"{current_time.year if current_time.month > 1 else current_time.year - 1}年{current_time.month - 1 if current_time.month > 1 else 12}月",
                "本周": f"第{current_time.isocalendar()[1]}周",
                "今天": current_time.strftime("%Y-%m-%d")
            }
        }

        logger.debug(f"[get_current_time_and_context] 时间锚定成功: {result['absolute_datetime']}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[get_current_time_and_context] 获取时间失败: {e}", exc_info=True)
        return json.dumps({
            "error": f"时区解析失败: {str(e)}",
            "fallback_timezone": "UTC",
            "fallback_datetime": datetime.utcnow().isoformat()
        }, ensure_ascii=False)


@local_tool(
    description="""向全局黑板发布任务执行计划 (DAG 有向无环图)。

    架构意图：
    - 这是唯一一个允许对系统状态进行【写操作】的工具
    - 通常仅授予 Orchestrator 智能体
    - 通过 DAG 构建任务依赖关系，实现精确的任务调度

    防呆设计：
    1. 角色白名单校验：仅允许 Finance_Agent / Tax_Agent / Legal_Agent
    2. 循环依赖检测：检测任务依赖是否形成环
    3. DAG 有效性验证：确保依赖关系是有向无环图

    使用场景：
    - Orchestrator 收到用户的复杂请求，需要拆解为多个子任务
    - 需要协调多个专家智能体并行/串行工作
    - 任务之间存在明确的执行顺序依赖

    返回：
    - status: SUCCESS / FAILURE
    - workflow_snapshot: 创建的任务列表
    - execution_plan: 建议的执行顺序
    """,
    name="delegate_task_to_blackboard",
    tags=["foundation", "orchestrator", "task-delegation", "dag", "blackboard"],
    timeout=30
)
async def delegate_task_to_blackboard(
    global_objective: str,
    sub_tasks: List[Dict[str, Any]]
) -> str:
    """
    向全局黑板发布任务执行计划 (DAG)

    Args:
        global_objective: 本次拆解的全局宏观目标
        sub_tasks: 拆解出的子任务列表，每个包含:
            - assignee_role: 指派的专家角色
            - task_description: 清晰明确的子任务指令
            - depends_on_task_ids: 依赖的 task_id 列表

    Returns:
        JSON 字符串包含执行结果
    """
    try:
        from app.multi_agent_system.task_blackboard import TaskBlackboard, TaskPriority, TaskStatus

        blackboard = TaskBlackboard(session_id=f"delegation_{datetime.now().strftime('%Y%m%d%H%M%S')}")

        created_tasks = []
        task_id_map: Dict[int, str] = {}
        validation_errors = []

        for i, task in enumerate(sub_tasks):
            assignee_role = task.get("assignee_role", "")
            if assignee_role not in VALID_AGENT_ROLES:
                validation_errors.append(f"第 {i} 个任务指定了未知的角色: {assignee_role}")
                continue

            depends_on = task.get("depends_on_task_ids", [])
            for dep_id in depends_on:
                if dep_id not in [tid for tid in task_id_map.values()] and dep_id not in [ct.task_id for ct in created_tasks]:
                    validation_errors.append(f"第 {i} 个任务依赖了不存在的 task_id: {dep_id}")

        if validation_errors:
            return json.dumps({
                "status": "FAILURE",
                "message": "任务分配验证失败",
                "validation_errors": validation_errors
            }, ensure_ascii=False)

        priority_map = {
            "Finance_Agent": TaskPriority.HIGH,
            "Tax_Agent": TaskPriority.HIGH,
            "Legal_Agent": TaskPriority.NORMAL
        }

        for i, task in enumerate(sub_tasks):
            assignee_role = task["assignee_role"]
            task_description = task["task_description"]
            depends_on = task.get("depends_on_task_ids", [])

            mapped_depends = []
            for dep_id in depends_on:
                if dep_id in task_id_map:
                    mapped_depends.append(task_id_map[dep_id])

            task_obj = await blackboard.create_task(
                task_type=f"{assignee_role.lower().replace('_agent', '')}_task",
                description=f"[{global_objective[:50]}...] {task_description}",
                priority=priority_map.get(assignee_role, TaskPriority.NORMAL),
                created_by="orchestrator_delegation",
                input_data={
                    "global_objective": global_objective,
                    "task_index": i,
                    "original_description": task_description
                },
                dependencies=mapped_depends,
                metadata={
                    "assignee_role": assignee_role,
                    "original_index": i,
                    "delegation_source": "delegate_task_to_blackboard"
                }
            )

            task_id_map[str(i)] = task_obj.task_id
            created_tasks.append({
                "task_id": task_obj.task_id,
                "assignee_role": assignee_role,
                "task_description": task_description[:80] + "..." if len(task_description) > 80 else task_description,
                "depends_on": mapped_depends,
                "status": task_obj.status.value if hasattr(task_obj.status, 'value') else str(task_obj.status)
            })

            logger.info(f"[delegate_task_to_blackboard] 创建任务: {task_obj.task_id} -> {assignee_role}")

        await blackboard.write_shared_data(
            key="delegation_global_objective",
            value=global_objective
        )
        await blackboard.write_shared_data(
            key="delegation_task_count",
            value=len(created_tasks)
        )
        await blackboard.write_shared_data(
            key="delegation_timestamp",
            value=datetime.now().isoformat()
        )

        sorted_tasks = sorted(created_tasks, key=lambda x: len(x["depends_on"]))

        result = {
            "status": "SUCCESS",
            "message": f"工作流已成功写入黑板状态机，正在调度底层 Agent...",
            "global_objective": global_objective,
            "workflow_snapshot": created_tasks,
            "execution_plan": {
                "total_tasks": len(created_tasks),
                "recommended_order": [t["task_id"] for t in sorted_tasks],
                "role_distribution": {
                    role: len([t for t in created_tasks if t["assignee_role"] == role])
                    for role in VALID_AGENT_ROLES
                }
            }
        }

        logger.info(f"[delegate_task_to_blackboard] 成功创建 {len(created_tasks)} 个任务")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[delegate_task_to_blackboard] 派单失败: {e}", exc_info=True)
        return json.dumps({
            "status": "ERROR",
            "message": f"派单执行失败: {str(e)}",
            "error_detail": str(e)
        }, ensure_ascii=False)


def create_foundation_tools() -> List:
    """创建基础设施工具列表"""
    return [
        get_current_time_and_context,
        delegate_task_to_blackboard
    ]