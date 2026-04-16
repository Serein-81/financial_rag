# app/agent_framework/core/plan_agent.py

"""
Plan Agent - 计划-执行模式

工作流程：
1. Planning: 分析任务，制定详细计划
2. Execution: 按计划逐步执行
3. Monitoring: 监控执行进度
4. Completion: 汇总结果

适用场景：
- 复杂的多步骤任务
- 需要明确规划的任务
- 对执行顺序有要求的任务
"""

from typing import Dict, List, Optional
import json
import logging

from .base_agent import BaseAgent
from ..llm.base_adapter import BaseLLMAdapter
from ..tools.tool_manager import ToolManager

logger = logging.getLogger(__name__)


class PlanAgent(BaseAgent):
    """
    Plan Agent - 先规划后执行
    
    相比 ReAct 的优势：
    - 有明确的执行计划
    - 避免重复或无效的工具调用
    - 更适合复杂任务
    
    提示词加载：
    - 通过 agent_name 从 app/prompts/agents/{agent_name}/system.md 加载
    - 如果没有指定 agent_name，回退到静态 system_prompt
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        agent_name: str = None,
        max_iterations: int = 10,
        max_steps: int = 10,
        **kwargs
    ):
        """
        初始化 Plan Agent
        
        Args:
            llm_adapter: LLM 适配器
            tool_manager: 工具管理器
            agent_name: Agent名称，用于加载结构化提示词（可选）
            max_iterations: 最大执行步骤数
            max_steps: 计划最大步骤数
        """
        super().__init__(llm_adapter, tool_manager, agent_name=agent_name, max_iterations=max_iterations, **kwargs)
        
        self.max_steps = max_steps
        
        logger.info("✅ Plan Agent 初始化完成")
        logger.info("   - 模式: Plan-Execute")
        logger.info(f"   - 最大步骤: {max_iterations}")
        logger.info(f"   - 计划最大步数: {max_steps}")
    
    def _build_planning_prompt(self, task: str, tools: List[Dict]) -> str:
        """
        构建规划阶段的提示词（使用模板系统）
        
        Args:
            task: 用户任务
            tools: 可用工具列表
            
        Returns:
            规划提示词
        """
        tools_desc = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in tools
        ])
        
        context = {
            "phase": "planning",
            "task": task,
            "tools_description": tools_desc,
            "max_steps": self.max_steps
        }
        
        return self._render_system_prompt(context)
    
    def _build_execution_prompt(
        self,
        task: str,
        plan: Dict,
        current_step: int,
        history: List[Dict]
    ) -> str:
        """
        构建执行阶段的提示词（使用模板系统）
        
        Args:
            task: 用户任务
            plan: 执行计划
            current_step: 当前步骤
            history: 执行历史
            
        Returns:
            执行提示词
        """
        step_info = plan["steps"][current_step - 1] if current_step <= len(plan["steps"]) else None
        
        context = {
            "phase": "execution",
            "task": task,
            "plan_json": json.dumps(plan, ensure_ascii=False, indent=2),
            "history": history,
            "current_step": current_step,
            "current_step_info": step_info,
            "current_step_info_action": step_info.get("action") if step_info else None,
            "current_step_info_tool": step_info.get("tool") if step_info else None,
            "current_step_info_input": step_info.get("input") if step_info else None
        }
        
        return self._render_system_prompt(context)
    
    def _build_completion_prompt(
        self,
        task: str,
        plan: Dict,
        history: List[Dict]
    ) -> str:
        """
        构建完成阶段的提示词（使用模板系统）
        
        Args:
            task: 用户任务
            plan: 执行计划
            history: 执行历史
            
        Returns:
            完成提示词
        """
        context = {
            "phase": "completion",
            "task": task,
            "plan_json": json.dumps(plan, ensure_ascii=False, indent=2),
            "history": history
        }
        
        return self._render_system_prompt(context)
    
    async def run(self, task: str, context: Optional[Dict] = None) -> str:
        """
        执行 Plan Agent
        
        Args:
            task: 用户任务
            context: 上下文信息
            
        Returns:
            最终答案
        """
        logger.info(f"🎯 [Plan Agent] 开始执行任务: {task}")
        
        try:
            # 阶段1：制定计划
            logger.info("📋 [Plan Agent] 阶段1: 制定计划")
            plan = await self._make_plan(task)
            logger.info(f"   计划步骤数: {len(plan['steps'])}")
            
            # 阶段2：执行计划
            logger.info("⚙️ [Plan Agent] 阶段2: 执行计划")
            history = await self._execute_plan(task, plan)
            
            # 阶段3：汇总结果
            logger.info("📊 [Plan Agent] 阶段3: 汇总结果")
            final_answer = await self._complete_task(task, plan, history)
            
            logger.info("✅ [Plan Agent] 任务完成")
            return final_answer
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ [Plan Agent] 执行数据错误: {e}")
            return f"抱歉，执行任务时遇到数据错误: {str(e)}"
        except (OSError, IOError) as e:
            logger.error(f"❌ [Plan Agent] 执行IO错误: {e}")
            return f"抱歉，执行任务时遇到IO错误: {str(e)}"
        except Exception as e:
            logger.error(f"❌ [Plan Agent] 执行失败: {e}")
            return f"抱歉，执行任务时遇到错误: {str(e)}"
    
    async def _make_plan(self, task: str) -> Dict:
        """
        制定执行计划
        
        Args:
            task: 用户任务
            
        Returns:
            执行计划
        """
        tools = self.tool_manager.get_all_tools()
        prompt = self._build_planning_prompt(task, tools)
        
        response = await self.llm_adapter.generate(prompt, temperature=0.1)
        
        # 解析计划
        try:
            # 提取 JSON
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                plan = json.loads(json_str)
                return plan
            else:
                raise ValueError("未找到有效的 JSON 格式")
        except (ValueError, KeyError) as e:
            logger.error(f"解析计划数据错误: {e}")
        except (OSError, IOError) as e:
            logger.error(f"解析计划IO错误: {e}")
        except Exception as e:
            logger.error(f"解析计划失败: {e}")
            # 返回默认计划
            return {
                "analysis": "无法解析计划",
                "steps": [
                    {
                        "step": 1,
                        "action": "直接回答",
                        "tool": "none",
                        "input": task,
                        "expected_output": "答案"
                    }
                ]
            }
    
    async def _execute_plan(self, task: str, plan: Dict) -> List[Dict]:
        """
        执行计划
        
        Args:
            task: 用户任务
            plan: 执行计划
            
        Returns:
            执行历史
        """
        history = []
        
        for i, step_info in enumerate(plan["steps"], 1):
            logger.info(f"   执行步骤 {i}/{len(plan['steps'])}: {step_info['action']}")
            
            # 如果不需要工具，直接记录
            if step_info.get("tool") == "none":
                history.append({
                    "step": i,
                    "action": step_info["action"],
                    "tool": "none",
                    "result": step_info.get("expected_output", "完成")
                })
                continue
            
            # 执行工具调用
            try:
                tool_name = step_info["tool"]
                tool_input = step_info["input"]
                
                # 调用工具
                result = await self.tool_manager.execute_tool(
                    tool_name,
                    input=tool_input
                )
                
                history.append({
                    "step": i,
                    "action": step_info["action"],
                    "tool": tool_name,
                    "input": tool_input,
                    "result": result
                })
                
                logger.info(f"   ✓ 步骤 {i} 完成")
                
            except (ValueError, KeyError) as e:
                logger.error(f"   ✗ 步骤 {i} 数据错误: {e}")
                history.append({
                    "step": i,
                    "action": step.get("action"),
                    "status": "error",
                    "error": f"数据错误: {str(e)}"
                })
            except (OSError, IOError) as e:
                logger.error(f"   ✗ 步骤 {i} IO错误: {e}")
                history.append({
                    "step": i,
                    "action": step.get("action"),
                    "status": "error",
                    "error": f"IO错误: {str(e)}"
                })
            except Exception as e:
                logger.error(f"   ✗ 步骤 {i} 失败: {e}")
                history.append({
                    "step": i,
                    "action": step_info["action"],
                    "tool": step_info.get("tool"),
                    "error": str(e)
                })
        
        return history
    
    async def _complete_task(
        self,
        task: str,
        plan: Dict,
        history: List[Dict]
    ) -> str:
        """
        汇总任务结果
        
        Args:
            task: 用户任务
            plan: 执行计划
            history: 执行历史
            
        Returns:
            最终答案
        """
        prompt = self._build_completion_prompt(task, plan, history)
        answer = await self.llm_adapter.generate(prompt, temperature=0.1)
        
        return answer
