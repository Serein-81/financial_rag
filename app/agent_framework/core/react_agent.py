# app/agent_framework/core/react_agent.py

"""
ReAct Agent 实现

基于 Reasoning and Acting 模式的智能体
"""

from typing import List, Dict, AsyncGenerator, Optional, Any
import re
import json
import hashlib
import time
from difflib import SequenceMatcher
from .base_agent import BaseAgent


class ReActAgent(BaseAgent):
    """
    ReAct (Reasoning and Acting) Agent
    
    实现思考-行动-观察的循环推理模式
    """
    
    def __init__(self, *args, **kwargs):
        """
        初始化 ReAct Agent
        """
        # 提取ReAct特有的参数
        self.similarity_threshold = kwargs.pop('similarity_threshold', 0.8)
        self.max_consecutive_failures = kwargs.pop('max_consecutive_failures', 3)
        self.early_stop_enabled = kwargs.pop('early_stop_enabled', True)
        
        # 调用父类初始化
        super().__init__(*args, **kwargs)
        
        # 状态跟踪
        self.iteration_history = []  # 迭代历史记录
        self.tool_call_history = []  # 工具调用历史
        self.consecutive_failures = 0  # 连续失败计数
        self.last_responses = []  # 最近的响应记录
        
        # ReAct 特定的提示词模板
        self.react_template = """
你是一个智能助手，可以使用工具来帮助回答问题。请按照以下格式进行思考和行动：

Thought: 分析当前情况，决定下一步行动
Action: 工具名称
Action Input: {{"参数名": "参数值"}}
Observation: [工具返回的结果]
... (可以重复 Thought/Action/Observation)
Thought: 我现在知道最终答案了
Final Answer: 最终答案

重要规则：
1. 每次只能调用一个工具
2. Action Input 必须是有效的 JSON 格式，且包含工具所需的全部参数
3. 如果不需要工具，直接给出 Final Answer
4. 最多进行 {max_iterations} 轮思考
5. 如果工具调用连续失败，请直接基于已有信息给出答案
6. 对于问候语、闲聊、感谢等简单对话（如"你好"、"谢谢"、"再见"等），必须直接给出 Final Answer，禁止调用任何工具
7. 只有当问题明确需要查询知识库或外部信息时，才允许调用工具；若无法确定查询内容，请直接回答

{tools_description}

{history_section}

现在开始回答问题：
Question: {user_input}
Thought:"""
    
    async def run(self, user_input: str, history: List[Dict] = None, **kwargs) -> str:
        """
        执行 ReAct 循环
        
        Args:
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数
            
        Returns:
            最终答案
        """
        self._reset_state()
        self._log_action("🚀 开始 ReAct 执行", {"user_input": user_input})
        
        # 开始追踪
        if self.enable_tracing:
            try:
                self.current_trace_id = await self.tracer.start_trace(
                    agent_type="ReAct",
                    user_query=user_input,
                    session_id=kwargs.get("session_id"),
                    message_id=kwargs.get("message_id")
                )
            except Exception as e:
                print(f"⚠️ 开始追踪失败: {e}")
        
        # 构建初始提示词
        prompt = self._build_react_prompt(user_input, history, **kwargs)
        
        current_prompt = prompt
        final_answer = None
        
        try:
            while self.current_iteration < self.max_iterations:
                self.current_iteration += 1
                
                if self._check_timeout():
                    self._log_action("⏰ 执行超时")
                    final_answer = "抱歉，处理时间过长，请稍后重试。"
                    break
                
                try:
                    # 调用 LLM 生成回应
                    self._log_action(f"🤖 LLM 调用 (第 {self.current_iteration} 轮)")
                    response = await self.llm.generate(current_prompt, temperature=0.1)
                    
                    self._log_action("📝 LLM 响应", {"response": response})
                    
                    # 解析响应
                    parsed = self._parse_response(response)
                    
                    if parsed["type"] == "final_answer":
                        # 记录最终答案步骤
                        await self._log_step(
                            step_type="final_answer",
                            content=parsed["content"]
                        )
                        
                        self._log_action("✅ 获得最终答案", {"answer": parsed["content"]})
                        final_answer = parsed["content"]
                        break
                    
                    elif parsed["type"] == "tool_call":
                        # 记录思考步骤（从响应中提取思考部分）
                        thought_content = self._extract_thought_from_response(response)
                        if thought_content:
                            await self._log_step(
                                step_type="thought",
                                content=thought_content
                            )
                        
                        # 记录行动步骤
                        await self._log_step(
                            step_type="action",
                            content=f"调用工具: {parsed['tool_name']}",
                            tool_name=parsed["tool_name"],
                            tool_input=parsed["parameters"]
                        )
                        
                        # 更新历史记录
                        tool_call_info = {
                            "tool_name": parsed["tool_name"],
                            "parameters": parsed["parameters"]
                        }
                        self._update_history(response, tool_call_info)
                        
                        # 执行工具调用
                        start_time = time.time()
                        tool_result = await self.call_tool(
                            parsed["tool_name"], 
                            **parsed["parameters"]
                        )
                        tool_duration = (time.time() - start_time) * 1000  # 转换为毫秒
                        
                        # 记录观察步骤
                        await self._log_step(
                            step_type="observation",
                            content=tool_result,
                            tool_name=parsed["tool_name"],
                            tool_output=tool_result,
                            tool_duration=tool_duration
                        )
                        
                        # 检查是否应该强制结束
                        force_check = self._should_force_final_answer(response, tool_result)
                        if force_check["should_stop"]:
                            self._log_action("🛑 触发早停机制", {
                                "reasons": force_check["reasons"],
                                "iteration": self.current_iteration
                            })
                            
                            # 尝试生成基于现有信息的答案
                            fallback_prompt = (
                                f"{current_prompt}{response}\nObservation: {tool_result}\n\n"
                                f"由于检测到循环或重复失败，请基于已有信息直接给出最终答案：\n"
                                f"Final Answer:"
                            )
                            
                            try:
                                fallback_response = await self.llm.generate(fallback_prompt, temperature=0.1)
                                fallback_answer = self._extract_final_answer(fallback_response)
                                if fallback_answer:
                                    final_answer = fallback_answer
                                else:
                                    final_answer = force_check["suggestion"]
                            except:
                                final_answer = force_check["suggestion"]
                            
                            break
                        
                        # 更新提示词，添加观察结果
                        observation = f"Observation: {tool_result}\nThought:"
                        current_prompt = current_prompt + response + "\n" + observation
                        
                        self._log_action("🔄 继续循环", {"observation": tool_result[:100]})
                    
                    elif parsed["type"] == "thinking":
                        # 记录思考步骤
                        await self._log_step(
                            step_type="thought",
                            content=parsed["content"]
                        )
                        
                        # 更新历史记录
                        self._update_history(response)
                        
                        # 检查循环
                        loop_check = self._check_loop_detection(response)
                        if loop_check["should_stop"]:
                            self._log_action("🛑 检测到思考循环", {"reason": loop_check["reason"]})
                            final_answer = self._generate_fallback_answer()
                            break
                        
                        # 纯思考，继续等待行动或最终答案
                        current_prompt = current_prompt + response + "\n"
                        self._log_action("💭 继续思考")
                    
                    else:
                        # 无法解析，尝试引导
                        guidance = "\n请按照格式继续：\nThought: [你的思考]\nAction: [工具名] 或 Final Answer: [最终答案]"
                        current_prompt = current_prompt + response + guidance
                        self._log_action("❓ 响应格式不正确，添加引导")
                
                except Exception as e:
                    self._log_action("❌ 执行出错", {"error": str(e)})
                    final_answer = f"抱歉，处理过程中出现错误：{str(e)}"
                    break
            
            # 如果没有得到最终答案
            if final_answer is None:
                self._log_action("🔄 达到最大迭代次数")
                final_answer = "抱歉，问题比较复杂，我需要更多时间思考。请尝试简化问题或稍后重试。"
        
        finally:
            # 结束追踪
            if self.enable_tracing and self.current_trace_id:
                try:
                    await self.tracer.end_trace(
                        trace_id=self.current_trace_id,
                        final_answer=final_answer or "执行未完成",
                        success=final_answer is not None
                    )
                except Exception as e:
                    print(f"⚠️ 结束追踪失败: {e}")
        
        return final_answer
    
    async def stream_run(self, user_input: str, history: List[Dict] = None, **kwargs) -> AsyncGenerator[str, None]:
        """
        流式执行 ReAct 循环
        
        Args:
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数
            
        Yields:
            逐步生成的内容
        """
        self._reset_state()
        self._log_action("🌊 开始 ReAct 流式执行", {"user_input": user_input})
        
        # 构建初始提示词
        prompt = self._build_react_prompt(user_input, history, **kwargs)
        current_prompt = prompt
        
        while self.current_iteration < self.max_iterations:
            self.current_iteration += 1
            
            if self._check_timeout():
                yield "\n\n[执行超时，请稍后重试]"
                return
            
            try:
                self._log_action(f"🤖 LLM 流式调用 (第 {self.current_iteration} 轮)")
                
                response_text = ""

                # 流式获取 LLM 响应（仅在此阶段收集工具调用信号）
                async for chunk in self.llm.stream_generate(current_prompt, temperature=0.1):
                    response_text += chunk

                    # 🔧 注意：不在此处检查 Final Answer
                    # 原因：流式传输中途 response_text 不完整，提取会截断答案
                    # 例如收到 "Final Answer: 你\n" 时提取只得到"你"，后续"好！..."全部丢失

                    # 检查是否需要工具调用（可在流式中途判断，有完整 Action Input 即可）
                    tool_call = self.tool_manager.parse_tool_call_from_text(response_text)
                    if tool_call and "Action Input:" in response_text:
                        # 🔧 参数为空说明 Action Input 的 JSON 尚未接收完整（如只到达了"{"）
                        # 继续等待更多 chunks，直到 JSON 完整（parameters 非空）再执行
                        if not tool_call["parameters"]:
                            continue

                        # 更新历史记录
                        self._update_history(response_text, tool_call)

                        # 检查是否应该强制结束
                        force_check = self._should_force_final_answer(response_text)
                        if force_check["should_stop"]:
                            self._log_action("🛑 流式执行触发早停", {
                                "reasons": force_check["reasons"]
                            })
                            yield f"\n\n[检测到循环，基于现有信息回答]\n{force_check['suggestion']}"
                            return

                        # 执行工具调用
                        self._log_action("🔧 检测到工具调用", tool_call)

                        tool_result = await self.call_tool(
                            tool_call["tool_name"],
                            **tool_call["parameters"]
                        )

                        # 检查连续失败
                        if self._check_consecutive_failures(tool_result):
                            self._log_action("🛑 连续工具调用失败，强制结束")
                            yield f"\n\n[工具调用多次失败，基于现有信息回答]\n{self._generate_fallback_answer()}"
                            return

                        # 更新提示词
                        observation = f"Observation: {tool_result}\nThought:"
                        current_prompt = current_prompt + response_text + "\n" + observation

                        # 继续下一轮循环
                        break

                else:
                    # 🔧 流式响应完整接收后，统一检查 Final Answer
                    # 此时 response_text 是完整的，提取结果不会被截断
                    if "Final Answer:" in response_text:
                        final_answer = self._extract_final_answer(response_text)
                        if final_answer:
                            for char in final_answer:
                                yield char
                            self._log_action("✅ 流式输出完成")
                            return

                    # 没有 Final Answer 也没有工具调用，检查是否陷入循环
                    # 🔧 必须先检测再存入：若先 _update_history 后检测，
                    #    last_responses 已含当前响应，会与自身比较得到 1.00 的误判相似度
                    loop_check = self._check_loop_detection(response_text)
                    self._update_history(response_text)
                    if loop_check["should_stop"]:
                        self._log_action("🛑 流式执行检测到循环", {"reason": loop_check["reason"]})
                        yield f"\n\n[检测到重复思考，直接回答]\n{self._generate_fallback_answer()}"
                        return

                    # 继续累积响应
                    current_prompt = current_prompt + response_text + "\n"
            
            except Exception as e:
                self._log_action("❌ 流式执行出错", {"error": str(e)})
                yield f"\n\n[处理出错: {str(e)}]"
                return
        
        yield f"\n\n[达到最大迭代次数，基于现有信息回答]\n{self._generate_fallback_answer()}"
    
    def _build_react_prompt(self, user_input: str, history: List[Dict] = None, **kwargs) -> str:
        """
        构建 ReAct 提示词
        
        Args:
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数
            
        Returns:
            完整的提示词
        """
        # 获取工具描述
        tools_description = self.tool_manager.get_tools_description()
        if not tools_description:
            tools_description = "当前没有可用的工具，请直接回答问题。"
        
        # 格式化历史记录
        history_section = ""
        if history:
            history_text = self._format_history(history)
            history_section = f"\n对话历史:\n{history_text}\n"
        
        # 填充模板
        prompt = self.react_template.format(
            max_iterations=self.max_iterations,
            tools_description=tools_description,
            history_section=history_section,
            user_input=user_input
        )
        
        return prompt
    
    def _parse_response(self, response: str) -> Dict[str, any]:
        """
        解析 LLM 响应
        
        Args:
            response: LLM 的响应文本
            
        Returns:
            解析结果
        """
        # 检查是否包含最终答案
        if "Final Answer:" in response:
            final_answer = self._extract_final_answer(response)
            if final_answer:
                return {
                    "type": "final_answer",
                    "content": final_answer
                }
        
        # 检查是否包含工具调用
        tool_call = self.tool_manager.parse_tool_call_from_text(response)
        if tool_call:
            return {
                "type": "tool_call",
                "tool_name": tool_call["tool_name"],
                "parameters": tool_call["parameters"]
            }
        
        # 默认为思考状态
        return {
            "type": "thinking",
            "content": response
        }
    
    def _extract_final_answer(self, text: str) -> Optional[str]:
        """
        从文本中提取最终答案
        
        Args:
            text: 包含最终答案的文本
            
        Returns:
            最终答案，如果没有找到则返回 None
        """
        # 🔧 Bug3修复：匹配到下一个 ReAct 关键词或字符串结尾，支持多行答案
        pattern = r'Final Answer:\s*(.*?)(?=\nThought:|\nAction:|\nObservation:|$)'
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        return None
    
    def _extract_thought_from_response(self, response: str) -> Optional[str]:
        """
        从响应中提取思考内容
        
        Args:
            response: LLM响应文本
            
        Returns:
            思考内容，如果没有找到则返回 None
        """
        # 匹配 Thought: 到 Action: 之间的内容
        pattern = r'Thought:\s*(.*?)(?=Action:|$)'
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
        
        if match:
            thought = match.group(1).strip()
            # 清理可能的换行和多余空格
            thought = re.sub(r'\s+', ' ', thought)
            return thought
        
        return None
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度
        
        Args:
            text1: 第一个文本
            text2: 第二个文本
            
        Returns:
            相似度分数 (0-1)
        """
        if not text1 or not text2:
            return 0.0
        
        # 使用序列匹配器计算相似度
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _generate_response_hash(self, response: str) -> str:
        """
        生成响应的哈希值用于快速比较
        
        Args:
            response: 响应文本
            
        Returns:
            哈希值
        """
        # 提取关键部分：Action 和 Action Input
        action_pattern = r'Action:\s*(\w+)'
        input_pattern = r'Action Input:\s*(\{.*?\})'
        
        action_match = re.search(action_pattern, response, re.IGNORECASE)
        input_match = re.search(input_pattern, response, re.DOTALL)
        
        key_content = ""
        if action_match:
            key_content += action_match.group(1)
        if input_match:
            key_content += input_match.group(1)
        
        return hashlib.md5(key_content.encode()).hexdigest()
    
    def _check_loop_detection(self, current_response: str) -> Dict[str, Any]:
        """
        检测是否陷入循环
        
        Args:
            current_response: 当前响应
            
        Returns:
            检测结果字典
        """
        if not self.early_stop_enabled:
            return {"should_stop": False, "reason": ""}
        
        # 1. 检查响应历史长度
        if len(self.last_responses) < 2:
            return {"should_stop": False, "reason": ""}
        
        # 2. 生成当前响应的哈希
        current_hash = self._generate_response_hash(current_response)
        
        # 3. 检查是否与最近的响应重复
        for i, (prev_response, prev_hash) in enumerate(self.last_responses[-3:]):
            similarity = self._calculate_similarity(current_response, prev_response)
            
            # 如果相似度过高，认为是循环
            if similarity > self.similarity_threshold or current_hash == prev_hash:
                return {
                    "should_stop": True,
                    "reason": f"检测到循环：与第{len(self.last_responses)-i}轮响应相似度{similarity:.2f}",
                    "similarity": similarity
                }
        
        # 4. 检查工具调用模式
        tool_call = self.tool_manager.parse_tool_call_from_text(current_response)
        if tool_call:
            # 检查是否重复调用相同工具且参数相似
            for prev_call in self.tool_call_history[-3:]:
                if (prev_call["tool_name"] == tool_call["tool_name"] and 
                    self._calculate_similarity(
                        str(prev_call["parameters"]), 
                        str(tool_call["parameters"])
                    ) > 0.7):
                    return {
                        "should_stop": True,
                        "reason": f"检测到重复工具调用：{tool_call['tool_name']}",
                        "similarity": 0.8
                    }
        
        return {"should_stop": False, "reason": ""}
    
    def _check_consecutive_failures(self, tool_result: str) -> bool:
        """
        检查连续失败次数
        
        Args:
            tool_result: 工具执行结果
            
        Returns:
            是否应该停止
        """
        # 判断是否为失败结果
        failure_indicators = ["错误", "失败", "未找到", "无法", "缺少必需参数"]
        is_failure = any(indicator in tool_result for indicator in failure_indicators)
        
        if is_failure:
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0
        
        return self.consecutive_failures >= self.max_consecutive_failures
    
    def _should_force_final_answer(self, current_response: str, tool_result: str = None) -> Dict[str, Any]:
        """
        判断是否应该强制输出最终答案
        
        Args:
            current_response: 当前响应
            tool_result: 工具结果（如果有）
            
        Returns:
            判断结果
        """
        reasons = []
        
        # 1. 循环检测
        loop_check = self._check_loop_detection(current_response)
        if loop_check["should_stop"]:
            reasons.append(loop_check["reason"])
        
        # 2. 连续失败检测
        if tool_result and self._check_consecutive_failures(tool_result):
            reasons.append(f"连续{self.consecutive_failures}次工具调用失败")
        
        # 3. 迭代次数检查
        if self.current_iteration >= self.max_iterations * 0.8:  # 80%时开始警告
            reasons.append(f"接近最大迭代次数({self.current_iteration}/{self.max_iterations})")
        
        should_stop = len(reasons) > 0
        
        return {
            "should_stop": should_stop,
            "reasons": reasons,
            "suggestion": self._generate_fallback_answer() if should_stop else ""
        }
    
    def _generate_fallback_answer(self) -> str:
        """
        生成备用答案
        
        Returns:
            备用答案
        """
        return ("抱歉，我在处理您的问题时遇到了一些困难。"
                "基于目前的信息，我建议您：\n"
                "1. 尝试重新表述问题\n"
                "2. 提供更具体的信息\n"
                "3. 或者稍后再试")
    
    def _update_history(self, response: str, tool_call: Dict = None):
        """
        更新历史记录
        
        Args:
            response: 当前响应
            tool_call: 工具调用信息
        """
        # 更新响应历史
        response_hash = self._generate_response_hash(response)
        self.last_responses.append((response, response_hash))
        
        # 只保留最近5次响应
        if len(self.last_responses) > 5:
            self.last_responses.pop(0)
        
        # 更新工具调用历史
        if tool_call:
            self.tool_call_history.append(tool_call)
            if len(self.tool_call_history) > 5:
                self.tool_call_history.pop(0)
        
        # 更新迭代历史
        self.iteration_history.append({
            "iteration": self.current_iteration,
            "response": response[:200],  # 只保留前200字符
            "tool_call": tool_call,
            "timestamp": time.time()
        })
    
    def _reset_state(self):
        """
        重置运行状态
        """
        super()._reset_state()
        
        # 重置循环检测相关状态
        self.iteration_history = []
        self.tool_call_history = []
        self.consecutive_failures = 0
        self.last_responses = []