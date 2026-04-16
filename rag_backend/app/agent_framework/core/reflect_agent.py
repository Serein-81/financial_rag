# app/agent_framework/core/reflect_agent.py

"""
Reflect Agent - 反思-改进模式

工作流程：
1. Action: 执行任务
2. Observation: 观察结果
3. Reflection: 反思质量
4. Refinement: 改进优化
5. Final: 输出最终结果

适用场景：
- 对质量要求高的任务
- 需要自我修正的任务
- 复杂推理任务

提示词模式：
- 使用模板引擎动态渲染反思提示词
- 支持 {original_task}, {current_answer}, {reflection_round} 等变量
"""

from typing import Dict, List, Optional
import logging

from .base_agent import BaseAgent
from ..llm.base_adapter import BaseLLMAdapter
from ..tools.tool_manager import ToolManager

logger = logging.getLogger(__name__)


class ReflectAgent(BaseAgent):
    """
    Reflect Agent - 执行-反思-改进
    
    相比 ReAct 的优势：
    - 有自我反思和改进机制
    - 输出质量更高
    - 更适合需要精确答案的场景
    
    缺点：
    - Token 消耗较大
    - 响应时间较长
    
    提示词加载：
    - 通过 agent_name 从 app/prompts/agents/{agent_name}/system.md 加载
    - 如果没有指定 agent_name，回退到静态 system_prompt
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        agent_name: str = None,
        max_iterations: int = 5,
        max_reflections: int = 2,
        **kwargs
    ):
        """
        初始化 Reflect Agent
        
        Args:
            llm_adapter: LLM 适配器
            tool_manager: 工具管理器
            agent_name: Agent名称，用于加载结构化提示词（可选）
            max_iterations: 最大执行迭代数
            max_reflections: 最大反思次数
        """
        super().__init__(
            llm_adapter,
            tool_manager,
            agent_name=agent_name,
            max_iterations=max_iterations,
            **kwargs
        )
        self.max_reflections = max_reflections
        
        logger.info("✅ Reflect Agent 初始化完成")
        logger.info("   - 模式: Reflect-Refine")
        logger.info(f"   - 模板: {self.template_name}")
        logger.info(f"   - 最大迭代: {max_iterations}")
        logger.info(f"   - 最大反思: {max_reflections}")
    
    def _build_action_prompt(self, task: str, tools: List[Dict]) -> str:
        """
        构建执行阶段的提示词
        
        Args:
            task: 用户任务
            tools: 可用工具列表
            
        Returns:
            执行提示词
        """
        tools_desc = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in tools
        ])
        
        prompt = f"""你是一个智能助手，请完成以下任务。

## 任务
{task}

## 可用工具
{tools_desc}

## 执行要求
1. 分析任务需求
2. 选择合适的工具
3. 执行并获取结果
4. 给出初步答案

请按照以下格式输出：

**思考**: 我需要做什么？
**工具**: 工具名称
**输入**: 工具输入
**观察**: 工具输出结果
**答案**: 基于结果的初步答案

现在开始执行："""
        
        return prompt
    
    def _build_reflection_prompt(
        self,
        task: str,
        initial_answer: str,
        reflection_round: int
    ) -> str:
        """
        使用模板构建反思阶段的提示词
        
        Args:
            task: 用户任务
            initial_answer: 初步答案
            reflection_round: 反思轮次
            
        Returns:
            反思提示词
        """
        context = {
            "original_task": task,
            "current_answer": initial_answer,
            "reflection_round": reflection_round,
            "max_reflections": self.max_reflections,
            "previous_reflections": [],  # TODO: 后续可以传入历史反思
            "tool_outputs": {}
        }
        
        return self._render_system_prompt(context)
    
    def _build_refinement_prompt(
        self,
        task: str,
        initial_answer: str,
        reflection: str,
        tools: List[Dict]
    ) -> str:
        """
        构建改进阶段的提示词
        
        Args:
            task: 用户任务
            initial_answer: 初步答案
            reflection: 反思结果
            tools: 可用工具列表
            
        Returns:
            改进提示词
        """
        tools_desc = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in tools
        ])
        
        prompt = f"""基于反思结果，请改进答案。

## 原始任务
{task}

## 初步答案
{initial_answer}

## 反思结果
{reflection}

## 可用工具
{tools_desc}

## 改进要求
1. 根据反思结果进行改进
2. 必要时使用工具获取补充信息
3. 确保答案准确、完整
4. 优化表达方式

请输出改进后的答案："""
        
        return prompt
    
    async def run(self, task: str, context: Optional[Dict] = None) -> str:
        """
        执行 Reflect Agent
        
        Args:
            task: 用户任务
            context: 上下文信息
            
        Returns:
            最终答案
        """
        logger.info(f"🎯 [Reflect Agent] 开始执行任务: {task}")
        
        try:
            # 阶段1：初步执行
            logger.info("⚙️ [Reflect Agent] 阶段1: 初步执行")
            initial_answer = await self._initial_action(task)
            logger.info(f"   初步答案长度: {len(initial_answer)} 字符")
            
            # 阶段2：反思-改进循环
            current_answer = initial_answer
            for i in range(self.max_reflections):
                logger.info(f"🤔 [Reflect Agent] 阶段2: 反思轮次 {i+1}/{self.max_reflections}")
                
                # 反思
                reflection = await self._reflect(task, current_answer, i+1)
                
                # 检查是否需要改进
                if "需要改进: No" in reflection or "需要改进：No" in reflection:
                    logger.info("   ✓ 答案已达标，无需改进")
                    break
                
                # 改进
                logger.info("   ↻ 进行改进")
                current_answer = await self._refine(task, current_answer, reflection)
            
            logger.info("✅ [Reflect Agent] 任务完成")
            return current_answer
            
        except Exception as e:
            logger.error(f"❌ [Reflect Agent] 执行失败: {e}")
            return f"抱歉，执行任务时遇到错误: {str(e)}"
    
    async def _initial_action(self, task: str) -> str:
        """
        初步执行任务
        
        Args:
            task: 用户任务
            
        Returns:
            初步答案
        """
        tools = self.tool_manager.get_all_tools()
        prompt = self._build_action_prompt(task, tools)
        
        response = await self.llm_adapter.generate(prompt, temperature=0.1)
        
        # 解析响应，提取答案部分
        if "答案:" in response or "答案：" in response:
            # 提取答案部分
            answer_start = max(
                response.find("答案:"),
                response.find("答案：")
            )
            if answer_start != -1:
                answer = response[answer_start:].split("\n")[0]
                answer = answer.replace("答案:", "").replace("答案：", "").strip()
                return answer if answer else response
        
        return response
    
    async def _reflect(
        self,
        task: str,
        answer: str,
        reflection_round: int
    ) -> str:
        """
        反思答案质量
        
        Args:
            task: 用户任务
            answer: 当前答案
            reflection_round: 反思轮次
            
        Returns:
            反思结果
        """
        prompt = self._build_reflection_prompt(task, answer, reflection_round)
        reflection = await self.llm_adapter.generate(prompt, temperature=0.2)
        
        logger.info(f"   反思结果: {reflection[:100]}...")
        return reflection
    
    async def _refine(
        self,
        task: str,
        answer: str,
        reflection: str
    ) -> str:
        """
        改进答案
        
        Args:
            task: 用户任务
            answer: 当前答案
            reflection: 反思结果
            
        Returns:
            改进后的答案
        """
        tools = self.tool_manager.get_all_tools()
        prompt = self._build_refinement_prompt(task, answer, reflection, tools)
        
        refined_answer = await self.llm_adapter.generate(prompt, temperature=0.1)
        
        logger.info(f"   改进后答案长度: {len(refined_answer)} 字符")
        return refined_answer
