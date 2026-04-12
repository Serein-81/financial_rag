# app/agent_framework/core/base_agent.py

"""
Agent 抽象基类

定义所有 Agent 的通用接口和基础功能
支持两种提示词模式：
1. 静态模式：直接使用 system_prompt
2. 动态模板模式：使用 PromptEngine 渲染模板
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator, Optional
from pathlib import Path
import asyncio
import time
import json
from ..tools.tool_manager import ToolManager
from ..llm.base_adapter import BaseLLMAdapter
from app.services.agent_tracer import agent_tracer
from app.services.prompt_service import PromptEngine


class BaseAgent(ABC):
    """
    Agent 抽象基类
    
    所有具体的 Agent 实现都应该继承这个类
    
    支持两种提示词模式：
    - 静态模式：传入 system_prompt
    - 动态模板模式：传入 template_name，通过 render_prompt() 渲染
    """
    
    def __init__(
        self, 
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        system_prompt: str = "",
        template_name: str = None,
        max_iterations: int = 10,
        timeout: float = 300.0
    ):
        """
        初始化 Agent
        
        Args:
            llm_adapter: 大模型适配器
            tool_manager: 工具管理器
            system_prompt: 系统提示词（静态模式）
            template_name: 模板名称（动态模式，二选一）
            max_iterations: 最大迭代次数（防止死循环）
            timeout: 超时时间（秒）
        """
        self.llm = llm_adapter
        self.llm_adapter = llm_adapter
        self.tool_manager = tool_manager
        self.max_iterations = max_iterations
        self.timeout = timeout
        
        # 提示词配置
        self.system_prompt = system_prompt
        self.template_name = template_name
        self.use_template = template_name is not None
        
        # PromptEngine 实例
        self.prompt_engine = PromptEngine()
        
        # 运行时状态
        self.current_iteration = 0
        self.start_time = 0.0
        self.execution_log = []
        
        # 追踪器
        self.tracer = agent_tracer
        self.current_trace_id = None
        self.enable_tracing = True
        
        # Prompt 优化
        self.current_template_id = None
        self.enable_prompt_optimization = True
        
        print(f"[OK] {self.__class__.__name__} 初始化完成")
        print(f"   - 提示词模式: {'模板 [' + template_name + ']' if self.use_template else '静态'}")
        print(f"   - 可用工具: {len(self.tool_manager.tools)} 个")
        print(f"   - 最大迭代: {self.max_iterations} 次")
        print(f"   - 超时设置: {self.timeout} 秒")
        print(f"   - 追踪功能: {'启用' if self.enable_tracing else '禁用'}")
        print(f"   - Prompt优化: {'启用' if self.enable_prompt_optimization else '禁用'}")
    
    def _render_system_prompt(self, context: Dict[str, Any] = None) -> str:
        """
        渲染系统提示词（支持动态模板）
        
        Args:
            context: 渲染上下文，包含需要替换的变量
            
        Returns:
            渲染后的系统提示词
        """
        if self.use_template:
            return self.prompt_engine.render(
                template_name=self.template_name,
                context=context or {},
                load_skills=True
            )
        return self.system_prompt
    
    @abstractmethod
    async def run(self, user_input: str, history: List[Dict] = None, **kwargs) -> str:
        """
        执行 Agent 主循环（子类必须实现）
        
        Args:
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数
            
        Returns:
            Agent 的最终回答
        """
        pass
    
    @abstractmethod
    async def stream_run(self, user_input: str, history: List[Dict] = None, **kwargs) -> AsyncGenerator[str, None]:
        """
        流式执行 Agent（子类必须实现）
        
        Args:
            user_input: 用户输入  
            history: 对话历史
            **kwargs: 其他参数
            
        Yields:
            逐步生成的内容
        """
        pass
    
    async def call_tool(self, tool_name: str, **kwargs) -> str:
        """
        调用工具的通用方法
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            工具执行结果
        """
        try:
            self._log_action(f"🔧 调用工具: {tool_name}", kwargs)
            
            result = await self.tool_manager.call_tool(tool_name, **kwargs)
            
            self._log_action(f"✅ 工具结果: {tool_name}", {"result": result[:100] + "..." if len(result) > 100 else result})
            
            return result
            
        except Exception as e:
            error_msg = f"工具调用失败: {str(e)}"
            self._log_action(f"❌ 工具错误: {tool_name}", {"error": error_msg})
            return error_msg
    
    def build_prompt(self, user_input: str, history: List[Dict] = None, **kwargs) -> str:
        """
        构建完整的提示词
        
        Args:
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数
            
        Returns:
            完整的提示词
        """
        # 1. 系统提示词
        prompt_parts = []
        
        if self.system_prompt:
            prompt_parts.append(self.system_prompt)
        
        # 2. 工具描述
        tools_desc = self.tool_manager.get_tools_description()
        if tools_desc:
            prompt_parts.append(f"\n可用工具:\n{tools_desc}")
        
        # 3. 对话历史
        if history:
            history_text = self._format_history(history)
            prompt_parts.append(f"\n对话历史:\n{history_text}")
        
        # 4. 当前问题
        prompt_parts.append(f"\n用户问题: {user_input}")
        
        return "\n".join(prompt_parts)
    
    def _format_history(self, history: List[Dict]) -> str:
        """
        格式化对话历史
        
        Args:
            history: 对话历史列表
            
        Returns:
            格式化后的历史文本
        """
        if not history:
            return ""
        
        formatted = []
        for msg in history[-10:]:  # 只取最近10条
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            
            if role == "user":
                formatted.append(f"用户: {content}")
            elif role == "assistant":
                formatted.append(f"助手: {content}")
        
        return "\n".join(formatted)
    
    def _check_timeout(self) -> bool:
        """
        检查是否超时
        
        Returns:
            True 如果超时
        """
        if self.start_time == 0:
            return False
        
        elapsed = time.time() - self.start_time
        return elapsed > self.timeout
    
    def _check_max_iterations(self) -> bool:
        """
        检查是否达到最大迭代次数
        
        Returns:
            True 如果达到最大迭代次数
        """
        return self.current_iteration >= self.max_iterations
    
    def _log_action(self, action: str, data: Any = None):
        """
        记录执行日志
        
        Args:
            action: 动作描述
            data: 相关数据
        """
        log_entry = {
            "timestamp": time.time(),
            "iteration": self.current_iteration,
            "action": action,
            "data": data
        }
        self.execution_log.append(log_entry)
        
        # 打印调试信息
        print(f"[{self.current_iteration:02d}] {action}")
        if data and isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and len(value) > 100:
                    print(f"    {key}: {value[:100]}...")
                else:
                    print(f"    {key}: {value}")
    
    async def get_optimized_prompt(
        self,
        agent_type: str,
        use_case: str = "general",
        db_session = None
    ) -> tuple[str, Optional[str]]:
        """
        获取优化后的 Prompt 模板
        
        Args:
            agent_type: Agent 类型
            use_case: 使用场景
            db_session: 数据库会话
            
        Returns:
            (prompt_text, template_id)
        """
        if not self.enable_prompt_optimization or not db_session:
            return self.system_prompt, None
        
        try:
            from app.services.prompt_optimizer import get_prompt_optimizer
            from app.services.prompt_ab_test import get_ab_test_manager
            
            # 1. 检查是否有正在运行的 A/B 测试
            ab_manager = get_ab_test_manager(db_session)
            test_name = f"{agent_type}_{use_case}_test"
            template_id = await ab_manager.select_template(test_name)
            
            if template_id:
                # 使用 A/B 测试选择的模板
                optimizer = get_prompt_optimizer(db_session)
                template = await optimizer.get_template(template_id)
                if template and template.is_active:
                    self.current_template_id = str(template_id)
                    return template.template_text, str(template_id)
            
            # 2. 获取当前激活的最佳模板
            optimizer = get_prompt_optimizer(db_session)
            template = await optimizer.get_active_template(agent_type, use_case)
            
            if template:
                self.current_template_id = str(template.id)
                return template.template_text, str(template.id)
            
            # 3. 回退到默认 Prompt
            return self.system_prompt, None
            
        except Exception as e:
            print(f"[WARNING] Prompt 优化失败，使用默认 Prompt: {e}")
            return self.system_prompt, None
    
    async def record_prompt_execution(
        self,
        user_query: str,
        final_answer: str,
        success: bool,
        execution_time: float,
        iterations_count: int,
        tool_calls_count: int,
        auto_score: float = None,
        error_type: str = None,
        error_message: str = None,
        db_session = None
    ):
        """
        记录 Prompt 执行结果
        
        Args:
            user_query: 用户查询
            final_answer: 最终答案
            success: 是否成功
            execution_time: 执行时间
            iterations_count: 迭代次数
            tool_calls_count: 工具调用次数
            auto_score: 自动评分
            error_type: 错误类型
            error_message: 错误信息
            db_session: 数据库会话
        """
        if not self.enable_prompt_optimization or not self.current_template_id or not db_session:
            return
        
        try:
            from app.services.prompt_optimizer import get_prompt_optimizer
            from uuid import UUID
            
            optimizer = get_prompt_optimizer(db_session)
            
            await optimizer.record_execution(
                template_id=UUID(self.current_template_id),
                user_query=user_query,
                trace_id=UUID(self.current_trace_id) if self.current_trace_id else None,
                final_answer=final_answer,
                execution_time=execution_time,
                iterations_count=iterations_count,
                tool_calls_count=tool_calls_count,
                success=success,
                auto_score=auto_score,
                error_type=error_type,
                error_message=error_message
            )
            
        except Exception as e:
            print(f"[WARNING] 记录 Prompt 执行失败: {e}")
    
    def _reset_state(self):
        """
        重置运行状态
        """
        self.current_iteration = 0
        self.start_time = time.time()
        self.execution_log = []
        self.current_trace_id = None
        self.current_template_id = None
    
    async def _log_step(
        self,
        step_type: str,
        content: str,
        tool_name: str = None,
        tool_input: Dict = None,
        tool_output: str = None,
        tool_duration: float = None,
        confidence: float = None
    ):
        """
        记录 Agent 执行步骤（用于追踪）
        
        Args:
            step_type: 步骤类型（thought/action/observation/final_answer）
            content: 步骤内容
            tool_name: 工具名称（可选）
            tool_input: 工具输入（可选）
            tool_output: 工具输出（可选）
            tool_duration: 工具执行时间（可选）
            confidence: 置信度（可选）
        """
        if not self.enable_tracing or not self.current_trace_id:
            return
        
        try:
            await self.tracer.add_step(
                trace_id=self.current_trace_id,
                step_number=self.current_iteration,
                step_type=step_type,
                content=content,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
                tool_duration=tool_duration,
                confidence=confidence
            )
        except Exception as e:
            # 追踪失败不应影响 Agent 执行
            print(f"[WARNING] 追踪步骤失败: {e}")
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        获取执行摘要
        
        Returns:
            执行摘要信息
        """
        if not self.execution_log:
            return {}
        
        total_time = time.time() - self.start_time if self.start_time > 0 else 0
        
        return {
            "total_iterations": self.current_iteration,
            "total_time": round(total_time, 2),
            "tool_calls": len([log for log in self.execution_log if "调用工具" in log["action"]]),
            "success": not (self._check_timeout() or self._check_max_iterations()),
            "log_entries": len(self.execution_log)
        }