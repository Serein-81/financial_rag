# app/agent_framework/core/base_agent.py

"""
Agent 抽象基类

定义所有 Agent 的通用接口和基础功能
每个 Agent 有一份主系统提示词，通过 agent_name 从结构化提示词系统加载
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator
import time
from ..tools.tool_manager import ToolManager
from ..llm.base_adapter import BaseLLMAdapter
from app.services.agent_tracer import agent_tracer


class BaseAgent(ABC):
    """
    Agent 抽象基类
    
    所有具体的 Agent 实现都应该继承这个类
    
    提示词加载规则：
    - 每个 Agent 有一份主系统提示词
    - 通过 agent_name 从 app/prompts/agents/{agent_name}/system.md 加载
    - 如果 agent_name 不存在，使用传入的 system_prompt
    """
    
    def __init__(
        self, 
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        agent_name: str = None,
        system_prompt: str = "",
        max_iterations: int = 10,
        timeout: float = 300.0
    ):
        """
        初始化 Agent
        
        Args:
            llm_adapter: 大模型适配器
            tool_manager: 工具管理器
            agent_name: Agent名称，用于从结构化提示词系统加载提示词
            system_prompt: 系统提示词（静态模式，回退方案）
            max_iterations: 最大迭代次数（防止死循环）
            timeout: 超时时间（秒）
        """
        self.llm = llm_adapter
        self.llm_adapter = llm_adapter
        self.tool_manager = tool_manager
        self.max_iterations = max_iterations
        self.timeout = timeout
        
        # 提示词配置
        self.agent_name = agent_name
        self.system_prompt = system_prompt
        
        # 运行时状态
        self.current_iteration = 0
        self.start_time = 0.0
        self.execution_log = []
        
        # 追踪器
        self.tracer = agent_tracer
        self.current_trace_id = None
        self.enable_tracing = True
        
        print(f"[OK] {self.__class__.__name__} 初始化完成")
        print(f"   - Agent名称: {agent_name or '未指定'}")
        print(f"   - 提示词来源: {'结构化系统' if agent_name else '静态提示词'}")
        print(f"   - 可用工具: {len(self.tool_manager.tools)} 个")
        print(f"   - 最大迭代: {self.max_iterations} 次")
        print(f"   - 超时设置: {self.timeout} 秒")
        print(f"   - 追踪功能: {'启用' if self.enable_tracing else '禁用'}")
    
    def _render_system_prompt(self, context: Dict[str, Any] = None, **render_kwargs) -> str:
        """
        渲染系统提示词

        加载顺序：
        1. 从 agent_name 对应的结构化提示词系统加载（优先）
        2. 使用 self.system_prompt（静态提示词，作为回退）

        Args:
            context: 渲染上下文，包含需要替换的变量（可选）
            **render_kwargs: 传递给 PromptEngine.render() 的额外参数
                          支持: load_skills, include_shared 等

        Returns:
            系统提示词
        """
        # 1. 优先使用结构化提示词系统
        if self.agent_name:
            from app.services.prompt_service import PromptEngine

            # 使用 PromptEngine 渲染变量
            engine = PromptEngine()
            rendered = engine.render(
                template_name=self.agent_name,
                context=context or {},
                use_cache=True,
                load_skills=render_kwargs.get('load_skills', False),
                include_shared=render_kwargs.get('include_shared')
            )
            
            if rendered:
                return rendered

        # 2. 使用静态提示词（回退方案）
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
    
    def _reset_state(self):
        """
        重置运行状态
        """
        self.current_iteration = 0
        self.start_time = time.time()
        self.execution_log = []
        self.current_trace_id = None
    
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