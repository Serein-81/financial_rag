"""
智能体调度器 (Agent Orchestrator)

负责协调多个专业智能体，决定：
1. 当前任务应该由哪个智能体处理？
2. 是否需要多个智能体协作？
3. 输出是否需要经过输出智能体审查？

使用示例：
    orchestrator = AgentOrchestrator()
    orchestrator.register_all_agents()
    
    result = await orchestrator.execute_stream("帮我生成一份销售报表")
    async for chunk in result["stream"]:
        yield chunk
"""

from enum import Enum
from typing import List, Dict, Optional, Any, AsyncGenerator, Tuple
from pydantic import BaseModel
import re


class TaskType(Enum):
    """任务类型枚举"""
    CHAT = "chat"
    REPORT = "report"
    DATA_QUERY = "data_query"
    CODE = "code"
    ANALYSIS = "analysis"
    TOOL_CALL = "tool_call"
    CREATIVE = "creative"
    OTHER = "other"


class AgentCapability(BaseModel):
    """智能体能力描述"""
    name: str
    description: str
    task_types: List[TaskType]
    requires_review: bool = True
    priority: int = 1


class TaskContext(BaseModel):
    """任务上下文"""
    user_input: str
    intent: Optional[TaskType] = None
    metadata: Dict[str, Any] = {}
    requires_report: bool = False
    requires_data: bool = False


class AgentOrchestrator:
    """
    智能体调度器
    
    核心决策流程：
    1. 意图识别 → 确定任务类型
    2. 智能体匹配 → 选择最适合的智能体
    3. 执行 → 可能需要多个智能体协作
    4. 审查 → 输出智能体进行质量把控
    """
    
    def __init__(self):
        self.agents: Dict[str, Any] = {}
        self.capabilities: List[AgentCapability] = []
        self.output_agent = None
        self._initialized = False
    
    def _register_default_capabilities(self):
        """注册默认能力"""
        self.capabilities = [
            AgentCapability(
                name="ReportAgent",
                description="生成各类报表（销售报表、财务报表、数据报表等）",
                task_types=[TaskType.REPORT],
                requires_review=True,
                priority=1
            ),
            AgentCapability(
                name="DataAgent",
                description="数据查询和分析",
                task_types=[TaskType.DATA_QUERY, TaskType.ANALYSIS],
                requires_review=True,
                priority=1
            ),
            AgentCapability(
                name="ReActAgent",
                description="通用问答和任务执行",
                task_types=[TaskType.CHAT, TaskType.CODE, TaskType.TOOL_CALL, TaskType.CREATIVE],
                requires_review=True,
                priority=2
            ),
        ]
        
        self.capabilities.sort(key=lambda x: x.priority)
    
    def initialize(self, llm_adapter=None):
        """
        初始化并注册所有智能体
        
        Args:
            llm_adapter: LLM 适配器
        """
        if self._initialized:
            return
        
        from .output_agent import OutputAgent
        from .report_agent import ReportAgent
        from .react_agent import ReActAgent
        
        self.output_agent = OutputAgent(llm_adapter=llm_adapter)
        
        report_agent = ReportAgent(llm_adapter=llm_adapter)
        report_agent.set_output_agent(self.output_agent)
        self.agents["ReportAgent"] = report_agent
        
        try:
            from app.agent_framework.tools.tool_manager import ToolManager
            tool_manager = ToolManager()
            
            react_agent = ReActAgent(
                llm=llm_adapter,
                tool_manager=tool_manager,
                enable_output_review=False
            )
            self.agents["ReActAgent"] = react_agent
        except (ValueError, KeyError) as e:
            print(f"⚠️ ReActAgent 初始化数据错误: {e}")
            self.agents["ReActAgent"] = None
        except (OSError, IOError) as e:
            print(f"⚠️ ReActAgent 初始化IO错误: {e}")
            self.agents["ReActAgent"] = None
        except Exception as e:
            print(f"⚠️ ReActAgent 初始化失败: {e}")
            self.agents["ReActAgent"] = None
        
        self._register_default_capabilities()
        self._initialized = True
    
    def recognize_intent(self, user_input: str) -> TaskContext:
        """
        意图识别 - 决定任务类型
        
        Args:
            user_input: 用户输入
            
        Returns:
            任务上下文
        """
        context = TaskContext(user_input=user_input)
        
        intent_patterns = {
            TaskType.REPORT: [
                r'生成.*?报表',
                r'生成.*?报告',
                r'做.*?统计',
                r'.*?汇总',
                r'做.*?报表',
                r'给我.*?报表',
            ],
            TaskType.DATA_QUERY: [
                r'查询.*?数据',
                r'.*?有多少',
                r'统计.*?数据',
            ],
            TaskType.CODE: [
                r'写.*?代码',
                r'生成.*?代码',
                r'.*?脚本',
                r'帮我.*?程序',
            ],
            TaskType.ANALYSIS: [
                r'分析.*?',
                r'比较.*?',
                r'评估.*?',
                r'预测.*?',
            ],
            TaskType.CHAT: [
                r'.*?怎么样',
                r'什么是.*?',
                r'.*?怎么办',
                r'.*?是什么',
            ],
        }
        
        for task_type, patterns in intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, user_input):
                    context.intent = task_type
                    break
            if context.intent:
                break
        
        if '报表' in user_input or '报告' in user_input:
            context.requires_report = True
            context.intent = TaskType.REPORT
        
        if any(kw in user_input for kw in ['数据', '数量', '金额', '销量']):
            context.requires_data = True
        
        if not context.intent:
            context.intent = TaskType.CHAT
        
        return context
    
    def select_agent(self, context: TaskContext) -> Optional[str]:
        """
        选择最适合的智能体
        
        Args:
            context: 任务上下文
            
        Returns:
            智能体名称
        """
        if not context.intent:
            return None
        
        for capability in self.capabilities:
            if context.intent in capability.task_types:
                if capability.name in self.agents and self.agents[capability.name]:
                    return capability.name
        
        if "ReActAgent" in self.agents and self.agents["ReActAgent"]:
            return "ReActAgent"
        
        return None
    
    async def execute_stream(
        self, 
        user_input: str, 
        history: List[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行任务 - 流式输出
        
        Args:
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数
            
        Returns:
            执行结果，包含流式输出生成器
        """
        if not self._initialized:
            self.initialize()
        
        context = self.recognize_intent(user_input)
        agent_name = self.select_agent(context)
        
        result = {
            "context": context,
            "selected_agent": agent_name,
            "intent": context.intent.value if context.intent else "unknown",
            "stream": None,
            "error": None
        }
        
        if not agent_name:
            result["error"] = "没有可用的智能体处理此请求"
            result["stream"] = self._error_stream(result["error"])
            return result
        
        agent = self.agents.get(agent_name)
        if not agent:
            result["error"] = f"智能体 {agent_name} 未初始化"
            result["stream"] = self._error_stream(result["error"])
            return result
        
        result["stream"] = self._stream_with_review(
            agent, user_input, history, **kwargs
        )
        
        return result
    
    async def _stream_with_review(
        self,
        agent: Any,
        user_input: str,
        history: List[Dict] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        带审查的流式输出
        
        Args:
            agent: 智能体实例
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数
            
        Yields:
            审查后的输出内容
        """
        if not hasattr(agent, 'stream_run'):
            response = await agent.generate_report(user_input, **kwargs)
            content = response.get("content", "")
            for char in content:
                yield char
            return
        
        output_buffer = []
        
        try:
            async for chunk in agent.stream_run(user_input, history, **kwargs):
                output_buffer.append(chunk)
                yield chunk
        except (ValueError, KeyError) as e:
            print(f"⚠️ Agent 执行数据异常: {e}")
            for char in await self._get_default_answer("error"):
                yield char
        except (OSError, IOError) as e:
            print(f"⚠️ Agent 执行IO异常: {e}")
            for char in await self._get_default_answer("error"):
                yield char
        except Exception as e:
            print(f"⚠️ Agent 执行异常: {e}")
            for char in await self._get_default_answer("error"):
                yield char
            return
        
        full_output = "".join(output_buffer)
        
        if self.output_agent:
            review_result = await self.output_agent.quick_review(full_output, user_input)
            
            if not review_result.is_approved:
                print(f"⚠️ [调度器] 输出审查未通过: {review_result.issues}")
                
                should_regen, reason = self.output_agent.should_regenerate(review_result, 1)
                
                if should_regen and hasattr(agent, 'stream_run'):
                    print(f"📝 [调度器] 根据反馈重新生成...")
                    regenerated = await self.output_agent.regenerate_with_hint(
                        full_output, user_input, review_result.suggestion
                    )
                    
                    if regenerated != full_output:
                        cleaned = self.output_agent.output_formatter.clean_output(regenerated)
                        for char in cleaned:
                            yield char
                        return
                
                default_answer = self.output_agent.format_default_answer("no_result")
                yield default_answer
                return
    
    async def _stream_without_review(
        self,
        agent: Any,
        user_input: str,
        history: List[Dict] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        不带审查的流式输出
        
        Args:
            agent: 智能体实例
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数
            
        Yields:
            原始输出内容
        """
        try:
            async for chunk in agent.stream_run(user_input, history, **kwargs):
                yield chunk
        except (ValueError, KeyError) as e:
            print(f"⚠️ Agent 执行数据异常: {e}")
            for char in await self._get_default_answer("error"):
                yield char
        except (OSError, IOError) as e:
            print(f"⚠️ Agent 执行IO异常: {e}")
            for char in await self._get_default_answer("error"):
                yield char
        except Exception as e:
            print(f"⚠️ Agent 执行异常: {e}")
            for char in await self._get_default_answer("error"):
                yield char
    
    async def _get_default_answer(self, answer_type: str = "default") -> List[str]:
        """获取默认回答"""
        if self.output_agent:
            answer = self.output_agent.format_default_answer(answer_type)
        else:
            answers = [
                "抱歉，我暂时没有找到相关信息，能否请您换个方式描述您的问题？",
                "对不起，暂时无法处理您的请求，请稍后重试。",
            ]
            answer = answers[0]
        
        return list(answer)
    
    async def _error_stream(self, error: str) -> AsyncGenerator[str, None]:
        """错误流"""
        if self.output_agent:
            yield self.output_agent.format_default_answer("error")
        else:
            yield "抱歉，处理您的请求时遇到了一些问题，请稍后重试。"


orchestrator = AgentOrchestrator()


def create_orchestrated_agent(llm_adapter=None) -> AgentOrchestrator:
    """
    创建配置好的调度器
    
    Args:
        llm_adapter: LLM 适配器
        
    Returns:
        配置好的 AgentOrchestrator 实例
    """
    orch = AgentOrchestrator()
    orch.initialize(llm_adapter)
    return orch
