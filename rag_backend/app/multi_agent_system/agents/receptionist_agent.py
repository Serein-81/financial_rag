"""
接待智能体 (Receptionist Agent)
企业智能体系统的统一入口，负责用户接待和智能路由
"""

import asyncio
import re
from typing import Dict, List, Any, Optional
from pathlib import Path

from app.agent_framework.core.base_agent import BaseAgent
from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from app.services.prompt_service import PromptEngine
from app.multi_agent_system.agents.base_agent_prompt import load_agent_prompt
from ..message_bus import MessageBus, MessageType


class ConversationMode:
    """对话模式枚举"""
    DIRECT_ANSWER = "direct_answer"      # 直接回答
    RAG_RETRIEVAL = "rag_retrieval"     # RAG检索
    ROUTE_TO_SPECIALIST = "route"       # 路由到专家
    ESCALATE = "escalate"               # 转人工


class ReceptionistAgent(BaseAgent):
    """
    接待智能体
    
    核心职责：
    1. 用户接待与自然语言理解
    2. 简单问题直接回答
    3. 复杂问题智能路由
    4. 多轮对话管理
    5. RAG知识检索
    """
    
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        message_bus: Optional[MessageBus] = None,
        system_prompt: str = "",
        max_iterations: int = 5,
        timeout: float = 60.0
    ):
        """
        初始化接待智能体
        
        Args:
            llm_adapter: 大模型适配器
            tool_manager: 工具管理器
            message_bus: 消息总线
            system_prompt: 系统提示词
            max_iterations: 最大迭代次数
            timeout: 超时时间
        """
        self.prompt_engine = PromptEngine()
        self.message_bus = message_bus or MessageBus()
        
        # 对话上下文（必须在_load_system_prompt之前初始化）
        self.conversation_context: Dict[str, Any] = {}
        
        # 加载系统提示词
        if not system_prompt:
            system_prompt = self._load_system_prompt()
        
        super().__init__(
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            timeout=timeout
        )
        
        # 简单问题模式
        self.simple_patterns = {
            "greeting": r"^(你好|您好|hi|hello|嗨|hey)[\s,，.]*",
            "weather": r".*?(天气|weather).*",
            "time": r".*?(时间|time|现在几点).*",
            "help": r".*?(help|帮助|怎么用|如何使用).*",
            "thanks": r"^.*?(谢谢|thanks|感谢)[\s,，.]*",
        }
        
        print("🤝 [接待智能体] 初始化完成")
        print("   - 系统模式: 企业AI助手")
        print("   - 路由功能: 启用")
        print("   - RAG检索: 启用")
    
    def _load_system_prompt(self) -> str:
        """从外部文件加载系统提示词"""
        try:
            return load_agent_prompt(
                agent_name="receptionist",
                filename="receptionist_agent.md",
                context=self._get_prompt_context()
            )
        except Exception as e:
            print(f"⚠️ [接待智能体] 加载提示词失败，使用默认提示词: {e}")
            return self._build_default_prompt()
    
    def _get_prompt_context(self) -> Dict[str, Any]:
        """获取提示词渲染上下文"""
        return {
            "available_specialists": list(self.conversation_context.keys()) if self.conversation_context else ["finance", "legal", "tax"],
        }
    
    def _build_default_prompt(self) -> str:
        """构建默认提示词"""
        return """# 企业智能助手 - 接待智能体

## 角色定位
你是一个专业、友好的企业AI助手，代表企业形象，负责接待来访的所有用户。

## 核心能力

### 1. 用户接待
- 热情友好地欢迎用户
- 理解用户需求
- 提供专业解答

### 2. 问题分类
你能够识别并处理以下类型的问题：

#### 直接回答的问题
- 问候语、寒暄
- 天气、时间查询
- 简单计算
- 公司基本信息介绍
- 使用帮助

#### RAG检索的问题
- 企业规章制度查询
- 历史文档内容查询
- 流程规范查询
- 产品服务介绍
- 常见问题解答

#### 需要路由的问题
- 财务分析、报表问题 → 财务专家
- 税务计算、申报问题 → 税务专家
- 合同审查、法律咨询 → 法务专家
- 投资建议、风险评估 → 综合评估
- 任何需要专业领域知识的问题

## 工作流程

### 步骤1：理解用户输入
接收用户的自然语言输入

### 步骤2：问题分类
根据输入内容判断问题类型

### 步骤3：处理问题
- 直接回答：立即给出答案
- RAG检索：调用企业知识库
- 路由转发：传递给对应的专家智能体

### 步骤4：返回结果
提供清晰的回答，必要时引导下一步操作

## 输出格式

### 直接回答模式
```
[回答内容]
```

### RAG检索模式
```
正在为您检索相关信息...
[检索到的答案]
来源：[文档名称]
```

### 路由模式
```
好的，我来帮您转接专业顾问...
正在连接【{专家类型}专家】...
[简要说明将要咨询的问题]
```

## 重要原则
1. 简洁专业，不要过度解释
2. 不确定的问题不要瞎猜
3. 专业问题及时转给专家
4. 保持友好和耐心
5. 遇到危险内容及时预警
"""
    
    async def run(self, user_input: str, history: List[Dict] = None, **kwargs) -> str:
        """
        执行接待主流程
        
        Args:
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数（tenant_id, user_id等）
            
        Returns:
            接待结果
        """
        print(f"🤝 [接待智能体] 接收用户输入: {user_input[:50]}...")
        
        tenant_id = kwargs.get("tenant_id", "default")
        user_id = kwargs.get("user_id", "default")
        
        # 步骤1：更新对话上下文
        self._update_context(tenant_id, user_id)
        
        # 步骤2：检测简单问题
        simple_result = await self._handle_simple_queries(user_input)
        if simple_result:
            print(f"✅ [接待智能体] 直接回答问题")
            return simple_result
        
        # 步骤3：检测业务问题关键词
        business_keywords = self._detect_business_keywords(user_input)
        if business_keywords:
            print(f"📤 [接待智能体] 检测到业务问题，准备路由")
            routing_result = await self._prepare_routing(user_input, business_keywords, history)
            return routing_result
        
        # 步骤4：执行RAG检索
        print(f"🔍 [接待智能体] 执行RAG检索")
        rag_result = await self._handle_rag_query(user_input, tenant_id)
        
        if rag_result and rag_result.get("has_result"):
            print(f"✅ [接待智能体] RAG检索成功")
            return self._format_rag_response(rag_result)
        
        # 步骤5：无法处理，返回友好提示
        print(f"🤔 [接待智能体] 无法识别问题类型")
        return self._build_fallback_response(user_input)
    
    async def stream_run(self, user_input: str, history: List[Dict] = None, **kwargs):
        """
        流式执行接待
        
        Args:
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数
        """
        # 实现流式输出
        result = await self.run(user_input, history, **kwargs)
        yield result
    
    async def _handle_simple_queries(self, user_input: str) -> Optional[str]:
        """
        处理简单问题
        
        Args:
            user_input: 用户输入
            
        Returns:
            回答内容，如果不能处理则返回None
        """
        # 检测问候语
        if re.search(self.simple_patterns["greeting"], user_input.lower()):
            return self._build_greeting_response()
        
        # 检测感谢
        if re.search(self.simple_patterns["thanks"], user_input.lower()):
            return "不客气！很高兴能帮助您。请问还有什么其他问题吗？"
        
        # 检测天气查询
        if re.search(self.simple_patterns["weather"], user_input):
            try:
                weather_info = await self.call_tool("get_weather", city="北京")
                return f"当前北京天气：{weather_info}"
            except (ValueError, KeyError):
                return "抱歉，暂时无法查询天气信息。"
            except (OSError, IOError):
                return "抱歉，暂时无法查询天气信息。"
            except TimeoutError:
                return "抱歉，暂时无法查询天气信息（请求超时）。"
            except Exception:
                return "抱歉，暂时无法查询天气信息。"
        
        # 检测时间查询
        if re.search(self.simple_patterns["time"], user_input):
            from datetime import datetime
            current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
            return f"现在是：{current_time}"
        
        # 检测帮助请求
        if re.search(self.simple_patterns["help"], user_input.lower()):
            return self._build_help_response()
        
        return None
    
    def _detect_business_keywords(self, text: str) -> Dict[str, Any]:
        """
        检测业务问题关键词
        
        Args:
            text: 用户输入文本
            
        Returns:
            检测结果字典
        """
        text_lower = text.lower()
        
        # 财务关键词
        finance_keywords = ["财务", "报表", "利润", "资产负债", "现金流", "投资", "成本", "预算", "财务分析"]
        has_finance = any(kw in text_lower for kw in finance_keywords)
        
        # 税务关键词
        tax_keywords = ["税务", "税", "发票", "增值税", "所得税", "个税", "报税", "抵扣", "税务筹划"]
        has_tax = any(kw in text_lower for kw in tax_keywords)
        
        # 法务关键词
        legal_keywords = ["合同", "法务", "法律", "合规", "条款", "协议", "纠纷", "诉讼", "知识产权"]
        has_legal = any(kw in text_lower for kw in legal_keywords)
        
        # 报告生成关键词
        report_keywords = ["报告", "分析报告", "审查报告", "生成报告", "导出报告"]
        has_report = any(kw in text_lower for kw in report_keywords)
        
        return {
            "has_finance": has_finance,
            "has_tax": has_tax,
            "has_legal": has_legal,
            "has_report": has_report,
            "is_business": has_finance or has_tax or has_legal,
            "specialists_needed": self._determine_specialists(has_finance, has_tax, has_legal)
        }
    
    def _determine_specialists(
        self,
        has_finance: bool,
        has_tax: bool,
        has_legal: bool
    ) -> List[str]:
        """
        确定需要调用的专家智能体
        
        Args:
            has_finance: 是否涉及财务
            has_tax: 是否涉及税务
            has_legal: 是否涉及法务
            
        Returns:
            专家列表
        """
        specialists = []
        
        if has_finance:
            specialists.append("finance")
        if has_tax:
            specialists.append("tax")
        if has_legal:
            specialists.append("legal")
        
        if not specialists:
            specialists = ["general"]  # 默认专家
        
        return specialists
    
    async def _prepare_routing(
        self,
        user_input: str,
        business_keywords: Dict[str, Any],
        history: List[Dict] = None
    ) -> str:
        """
        准备路由信息
        
        Args:
            user_input: 用户输入
            business_keywords: 业务关键词检测结果
            history: 对话历史
            
        Returns:
            路由准备结果
        """
        specialists_needed = business_keywords["specialists_needed"]
        
        # 构建路由消息
        routing_info = {
            "original_query": user_input,
            "detected_domains": specialists_needed,
            "confidence": self._calculate_confidence(business_keywords),
            "requires_report": business_keywords.get("has_report", False)
        }
        
        # 通过消息总线发送路由请求
        await self.message_bus.publish(
            from_agent="receptionist",
            to_agent="intent",
            message_type=MessageType.REQUEST,
            content=routing_info
        )
        
        # 返回友好的路由提示
        specialist_names = {
            "finance": "财务",
            "tax": "税务",
            "legal": "法务",
            "general": "综合"
        }
        
        domain_names = [specialist_names.get(s, s) for s in specialists_needed]
        domain_str = "、".join(domain_names)
        
        response = f"""好的，我了解您的问题涉及【{domain_str}】领域。

正在为您连接专业顾问，请稍候...

🔄 您的请求已路由至：{', '.join(specialists_needed)}
⏱️ 预计等待时间：3-5秒

在等待期间，您可以：
- 补充更多细节
- 提供相关文档
- 调整问题范围
"""
        
        # 存储路由上下文
        self.conversation_context["current_routing"] = routing_info
        
        return response
    
    def _calculate_confidence(self, business_keywords: Dict[str, Any]) -> float:
        """
        计算路由置信度
        
        Args:
            business_keywords: 业务关键词检测结果
            
        Returns:
            置信度 (0-1)
        """
        count = sum([
            business_keywords.get("has_finance", False),
            business_keywords.get("has_tax", False),
            business_keywords.get("has_legal", False)
        ])
        
        # 置信度随关键词数量增加
        if count >= 2:
            return 0.9
        elif count == 1:
            return 0.8
        else:
            return 0.5
    
    async def _handle_rag_query(
        self,
        user_input: str,
        tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        处理RAG检索
        
        Args:
            user_input: 用户输入
            tenant_id: 租户ID
            
        Returns:
            RAG检索结果
        """
        try:
            # 调用RAG工具
            rag_result = await self.call_tool(
                "search_enterprise_knowledge",
                query=user_input,
                top_k=3,
                tenant_id=tenant_id
            )
            
            if rag_result and rag_result.strip():
                return {
                    "has_result": True,
                    "content": rag_result,
                    "source": "enterprise_knowledge_base"
                }
            
        except Exception as e:
            print(f"⚠️ [接待智能体] RAG检索失败: {e}")
        
        return None
    
    def _format_rag_response(self, rag_result: Dict[str, Any]) -> str:
        """
        格式化RAG响应
        
        Args:
            rag_result: RAG检索结果
            
        Returns:
            格式化后的响应
        """
        response = "🔍 根据企业知识库，我为您找到以下信息：\n\n"
        response += rag_result.get("content", "未找到相关信息")
        response += "\n\n如果您需要更详细的解答，请告诉我！"
        
        return response
    
    def _build_greeting_response(self) -> str:
        """构建问候响应"""
        from datetime import datetime
        
        hour = datetime.now().hour
        
        if hour < 12:
            greeting = "早上好"
        elif hour < 18:
            greeting = "下午好"
        else:
            greeting = "晚上好"
        
        return f"""{greeting}！👋

欢迎使用企业智能助手！

我可以帮您：
- 📚 解答企业相关问题
- 💼 处理财务、税务、法务咨询
- 📋 生成专业分析报告
- 🔍 检索企业知识库

请问有什么可以帮到您的？"""
    
    def _build_help_response(self) -> str:
        """构建帮助响应"""
        return """📖 **企业智能助手使用指南**

### 快速开始
您可以直接向我提问，例如：
- "公司年假制度是什么？"
- "如何报销差旅费？"
- "这个月的财务情况如何？"

### 专业咨询
涉及专业领域的问题，我会为您转接专家：
- 💰 **财务问题** → 财务专家
- 📝 **税务问题** → 税务专家  
- ⚖️ **法律问题** → 法务专家

### 报告生成
输入"生成XX报告"，例如：
- "生成季度财务分析报告"
- "生成税务健康检查报告"

### 文档上传
您也可以上传文档，我会帮您分析处理。

---

还有其他问题吗？😊"""
    
    def _build_fallback_response(self, user_input: str) -> str:
        """
        构建无法识别时的响应
        
        Args:
            user_input: 用户输入
            
        Returns:
            友好的提示响应
        """
        return f"""我理解您的问题是："{user_input}"

抱歉，我目前无法准确理解您的问题类型。

请尝试：
1. 换一种更明确的表达方式
2. 提供更多背景信息
3. 明确说明您需要的帮助类型

或者，您可以直接告诉我您需要：
- 📊 财务分析
- 📝 税务咨询
- ⚖️ 法律支持
- 📋 报告生成

希望这些选项对您有帮助！😊"""
    
    def _update_context(self, tenant_id: str, user_id: str):
        """
        更新对话上下文
        
        Args:
            tenant_id: 租户ID
            user_id: 用户ID
        """
        self.conversation_context.update({
            "tenant_id": tenant_id,
            "user_id": user_id,
            "last_interaction": asyncio.get_event_loop().time()
        })
    
    async def get_conversation_summary(self) -> Dict[str, Any]:
        """
        获取对话摘要
        
        Returns:
            对话摘要信息
        """
        return {
            "context": self.conversation_context,
            "current_mode": self.conversation_context.get("mode", "unknown"),
            "routing_info": self.conversation_context.get("current_routing", None)
        }
