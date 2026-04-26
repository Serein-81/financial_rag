"""
Orchestrator Agent (协调者/主路由智能体)

真正的 LLM 智能体，有自己专门的提示词。
负责理解用户宏大目标、拆解任务、协调专家团队、生成最终报告。
"""

import logging
from typing import Dict, List, Any, Optional, AsyncGenerator

from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from app.agent_framework.core.base_agent import BaseAgent
from app.multi_agent_system.agents.base_agent_prompt import load_agent_prompt
from app.prompts.loader import get_agent_prompt_loader

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator Agent（协调者/主路由智能体）

    核心职责：
    1. 理解用户宏大目标
    2. 使用 breakdown_task_to_blackboard 拆解为 DAG 子任务
    3. 协调专家 Agent 执行任务
    4. 使用 summarize_final_report 生成最终报告

    工具箱：
    - breakdown_task_to_blackboard: 任务拆解
    - summarize_final_report: 报告生成
    """

    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        tenant_id: str = "default",
        max_iterations: int = 10,
        timeout: float = 180.0
    ):
        """
        初始化 Orchestrator Agent

        Args:
            llm_adapter: LLM 适配器
            tool_manager: 工具管理器
            tenant_id: 租户 ID
            max_iterations: 最大迭代次数
            timeout: 超时时间（秒）
        """
        system_prompt = self._load_system_prompt()

        super().__init__(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            timeout=timeout
        )

        self.tenant_id = tenant_id
        self.agent_name = "orchestrator"
        self.tools = self._register_tools()

        logger.info(f"[OrchestratorAgent] 初始化完成，tenant_id={tenant_id}")

    def _load_system_prompt(self) -> str:
        """从外部文件加载系统提示词"""
        try:
            loader = get_agent_prompt_loader()
            system_prompt = loader.load_system_prompt("orchestrator")
            if system_prompt:
                logger.info("[OrchestratorAgent] 成功加载提示词: orchestrator/system.md")
                return system_prompt
        except Exception as e:
            logger.warning(f"[OrchestratorAgent] 加载提示词失败: {e}")

        logger.info("[OrchestratorAgent] 使用默认提示词")
        return self._build_default_prompt()

    def _build_default_prompt(self) -> str:
        """构建默认提示词"""
        return """# Orchestrator Agent (协调者/主路由智能体)

## 角色定位
你是企业智能体系统的唯一"大脑"和"包工头"。你是系统唯一直接面对用户的高级协调者。

## 核心职责

### 1. 任务拆解（使用 breakdown_task_to_blackboard 或 delegate_task_to_blackboard）
当你收到用户的宏大目标时，必须拆解为可执行的子任务，写入黑板供专家执行。

### 2. 报告汇总（使用 summarize_final_report）
当所有专家完成任务后，负责收集结论并生成最终交付报告。

### 3. 时间锚定（使用 get_current_time_and_context）
当用户查询涉及相对时间（如"今年"、"上个月"、"本季度"）时，必须先调用此工具获取准确时间基准。

## 可用工具

### breakdown_task_to_blackboard (传统拆解工具)
- 用途：将宏大目标拆解为多个子任务
- 输出：创建任务列表，但不支持精细的 DAG 依赖关系

### delegate_task_to_blackboard (高级派单印章 - 【新】)
- 用途：将宏大目标拆解为具有精确依赖关系的子任务
- 特点：
  - 构建有向无环图 (DAG)
  - 支持任务依赖关系 (depends_on_task_ids)
  - 支持角色白名单 (仅 Finance_Agent, Tax_Agent, Legal_Agent)
  - 自动验证依赖循环
- 这是系统唯一允许状态写操作的强大工具，请谨慎使用

### get_current_time_and_context (时间锚点 - 【新】)
- 用途：获取绝对物理时间、日期、星期和时区信息
- 必要性：大模型没有生物钟，当用户问"今年政策"或"上个月营收"时，必须调用此工具锚定时间
- 输出：当前年、月、季度、星期及相对时间映射表

### summarize_final_report (报告生成工具)
- 用途：汇总专家结论，生成最终报告

## 工作流
1. 理解用户目标
2. 如有时间相关查询，先调用 get_current_time_and_context 锚定时间
3. 调用 delegate_task_to_blackboard 将目标拆解为 DAG 任务
4. 专家 Agent 执行任务
5. 调用 summarize_final_report 生成报告

## 关键原则
- 你是协调者，不是执行者
- DAG 思维：考虑任务间的依赖关系
- 用户导向：报告要简洁易懂
- 时间感知：所有相对时间词必须锚定到绝对时间
"""

    def _register_tools(self) -> List[str]:
        """注册 Orchestrator 专用工具"""
        return [
            "breakdown_task_to_blackboard",
            "summarize_final_report",
            "delegate_task_to_blackboard",
            "get_current_time_and_context"
        ]

    async def process_user_goal(
        self,
        user_goal: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理用户宏大目标

        执行完整的工作流：
        1. 拆解任务
        2. 协调专家（如果需要）
        3. 生成报告

        Args:
            user_goal: 用户的宏大目标
            context: 额外上下文

        Returns:
            处理结果
        """
        logger.info(f"[OrchestratorAgent] 处理目标: {user_goal[:50]}...")

        from app.mcp.orchestrator_tools import breakdown_task_to_blackboard

        breakdown_result = await breakdown_task_to_blackboard(
            user_goal=user_goal,
            session_id=f"orch_{self.tenant_id}_{hash(user_goal) % 10000}",
            tenant_id=self.tenant_id,
            required_expertise=context.get("required_expertise") if context else None,
            priority_tasks=context.get("priority_tasks") if context else None
        )

        if breakdown_result.get("status") == "error":
            return {
                "status": "error",
                "message": f"任务拆解失败: {breakdown_result.get('error')}",
                "next_action": "retry"
            }

        created_tasks = breakdown_result.get("created_tasks", [])
        task_ids = [t["task_id"] for t in created_tasks]

        logger.info(f"[OrchestratorAgent] 已拆解 {len(created_tasks)} 个任务")

        return {
            "status": "success",
            "phase": "task_breakdown",
            "breakdown_result": breakdown_result,
            "task_ids": task_ids,
            "message": f"成功拆解为 {len(created_tasks)} 个子任务",
            "next_action": "wait_for_experts" if task_ids else "generate_report"
        }

    async def collect_and_report(
        self,
        session_id: str,
        user_query: str,
        report_title: Optional[str] = None,
        format: str = "markdown"
    ) -> Dict[str, Any]:
        """
        收集专家结论并生成报告

        Args:
            session_id: 会话 ID
            user_query: 用户原始查询
            report_title: 报告标题
            format: 报告格式

        Returns:
            报告结果
        """
        logger.info(f"[OrchestratorAgent] 生成最终报告: {session_id}")

        from app.mcp.orchestrator_tools import summarize_final_report

        report_result = await summarize_final_report(
            session_id=session_id,
            tenant_id=self.tenant_id,
            user_query=user_query,
            report_title=report_title,
            include_executive_summary=True,
            include_recommendations=True,
            format=format
        )

        if report_result.get("status") == "error":
            return {
                "status": "error",
                "message": f"报告生成失败: {report_result.get('error')}"
            }

        logger.info(f"[OrchestratorAgent] 报告生成完成")

        return {
            "status": "success",
            "phase": "report_generation",
            "report": report_result.get("report_content") or report_result.get("report_text"),
            "metadata": report_result.get("metadata"),
            "sections": report_result.get("sections", []),
            "message": "报告生成成功"
        }

    def get_capabilities(self) -> Dict[str, Any]:
        """获取 Agent 能力描述"""
        return {
            "name": self.agent_name,
            "type": "orchestrator",
            "role": "coordinator",
            "tools": self.tools,
            "capabilities": [
                "task_decomposition",
                "dag_planning",
                "multi_agent_coordination",
                "report_summarization"
            ],
            "expertise_domains": [
                "coordination",
                "task_planning",
                "report_generation"
            ]
        }

    async def run(
        self,
        user_input: str,
        history: List[Dict] = None,
        **kwargs
    ) -> str:
        """
        执行 Orchestrator Agent 主循环

        Args:
            user_input: 用户输入（可以是宏大目标或查询）
            history: 对话历史
            **kwargs: 其他参数

        Returns:
            处理结果
        """
        logger.info(f"[OrchestratorAgent] run() 被调用，输入: {user_input[:50]}...")

        result = await self.process_user_goal(
            user_goal=user_input,
            context=kwargs
        )

        return str(result)

    async def stream_run(
        self,
        user_input: str,
        history: List[Dict] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式执行 Orchestrator Agent

        Args:
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数

        Yields:
            流式输出片段
        """
        logger.info(f"[OrchestratorAgent] stream_run() 被调用")

        result = await self.process_user_goal(
            user_goal=user_input,
            context=kwargs
        )

        result_str = str(result)
        yield result_str


orchestrator_agent: Optional[OrchestratorAgent] = None


def get_orchestrator_agent(
    llm_adapter: Optional[BaseLLMAdapter] = None,
    tool_manager: Optional[ToolManager] = None,
    tenant_id: str = "default"
) -> OrchestratorAgent:
    """
    获取全局 OrchestratorAgent 实例（单例模式）

    Args:
        llm_adapter: LLM 适配器
        tool_manager: 工具管理器
        tenant_id: 租户 ID

    Returns:
        OrchestratorAgent 实例
    """
    global orchestrator_agent

    if orchestrator_agent is None:
        if llm_adapter is None:
            from app.agent_framework.llm.factory import LLMAdapterFactory
            llm_adapter = LLMAdapterFactory.create_adapter(provider="zhipu")

        if tool_manager is None:
            tool_manager = ToolManager()

        orchestrator_agent = OrchestratorAgent(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            tenant_id=tenant_id
        )

    return orchestrator_agent
