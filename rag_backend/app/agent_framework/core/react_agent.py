# app/agent_framework/core/react_agent.py

"""
ReAct Agent 实现

基于 Reasoning and Acting 模式的智能体
"""

from typing import List, Dict, AsyncGenerator, Optional, Any, TYPE_CHECKING
import re
import hashlib
import time
import numpy as np
from difflib import SequenceMatcher
from .base_agent import BaseAgent
from app.utils.output_formatter import output_formatter
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    pass


class ReActAgent(BaseAgent):
    """
    ReAct (Reasoning and Acting) Agent
    
    实现思考-行动-观察的循环推理模式
    
    提示词加载：
    - 通过 agent_name 从 app/prompts/agents/{agent_name}/system.md 加载
    - 如果没有指定 agent_name，回退到静态 system_prompt
    """
    
    def __init__(self, *args, agent_name: str = None, **kwargs):
        """
        初始化 ReAct Agent
        
        Args:
            agent_name: Agent名称，用于加载结构化提示词（可选）
            *args, **kwargs: 传递给父类 BaseAgent 的其他参数
        """
        # 提取ReAct特有的参数
        self.similarity_threshold = kwargs.pop('similarity_threshold', 0.8)
        self.max_consecutive_failures = kwargs.pop('max_consecutive_failures', 3)
        self.early_stop_enabled = kwargs.pop('early_stop_enabled', True)
        
        # 调用父类初始化，传递 agent_name
        super().__init__(*args, agent_name=agent_name, **kwargs)
        
        # 状态跟踪
        self.iteration_history = []  # 迭代历史记录
        self.tool_call_history = []  # 工具调用历史
        self.tool_result_history = []  # 工具结果历史
        self.consecutive_failures = 0  # 连续失败计数
        self.last_responses = []  # 最近的响应记录
        self.last_successful_tool_result = None  # 最后一次成功的工具结果
        
        # 结果合成器延迟初始化（避免循环导入）
        self._result_synthesizer = None
        self._synthesizer_strategy = "NARRATIVE"
    
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
            except (ValueError, KeyError) as e:
                print(f"⚠️ 开始追踪数据错误: {e}")
            except (OSError, IOError) as e:
                print(f"⚠️ 开始追踪IO错误: {e}")
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
                        
                        # 检查是否应该强制结束（使用语义嵌入）
                        force_check = await self._should_force_final_answer(response, tool_result)
                        if force_check["should_stop"]:
                            self._log_action("🛑 触发早停机制", {
                                "reasons": force_check["reasons"],
                                "iteration": self.current_iteration
                            })
                            
                            # 策略1：优化：判断工具结果是否为自然语言格式
                            if tool_result and len(tool_result) > 10:
                                failure_indicators = ["错误", "失败", "未找到", "无法", "找不到", "不存在"]
                                is_failure = any(indicator in tool_result for indicator in failure_indicators)
                                if not is_failure:
                                    cleaned_result = re.sub(r'^📝\s*答案摘要：\s*', '', tool_result)
                                    
                                    # 判断是否为自然语言格式
                                    is_natural = bool(re.search(r'[。！？\n]', cleaned_result))
                                    
                                    if is_natural:
                                        self._log_action("直接使用工具结果（自然语言格式）", {"length": len(cleaned_result)})
                                        final_answer = cleaned_result
                                        break
                                    else:
                                        self._log_action("工具结果为结构化数据，使用 Final Output 转换")
                                        final_output = await self._generate_final_output(
                                            user_input=user_input,
                                            tool_result=cleaned_result
                                        )
                                        if final_output and len(final_output) > 5:
                                            self._log_action("Final Output 生成答案（早停）", {"length": len(final_output)})
                                            final_answer = final_output
                                            break
                            
                            # 策略2：生成 fallback
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
                            except (ValueError, KeyError) as e:
                                logger.error(f"LLM fallback 生成数据错误: {e}")
                                final_answer = force_check["suggestion"]
                            except (OSError, IOError) as e:
                                logger.error(f"LLM fallback 生成IO错误: {e}")
                                final_answer = force_check["suggestion"]
                            except Exception as e:
                                logger.error(f"LLM fallback 生成失败: {e}")
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
                        
                        # 检查循环（使用语义嵌入）
                        loop_check = await self._check_loop_detection(response)
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
                
                except (ValueError, KeyError) as e:
                    self._log_action("❌ 执行数据错误", {"error": str(e)})
                    final_answer = f"抱歉，处理过程中出现数据错误：{str(e)}"
                except (OSError, IOError) as e:
                    self._log_action("❌ 执行IO错误", {"error": str(e)})
                    final_answer = f"抱歉，处理过程中出现IO错误：{str(e)}"
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
                except (ValueError, KeyError) as e:
                    print(f"⚠️ 结束追踪数据错误: {e}")
                except (OSError, IOError) as e:
                    print(f"⚠️ 结束追踪IO错误: {e}")
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
                yield output_formatter.format_error_answer("执行超时")
                return
            
            try:
                self._log_action(f"🤖 LLM 流式调用 (第 {self.current_iteration} 轮)")
                
                response_text = ""
                streamed_content = ""  # 用于跟踪已流式输出的内容
                usage_info = None
                chunk_count = 0
                
                # 是否应该流式输出内容（无工具调用时）
                should_stream_output = True
                # 缓冲区的最小长度（达到后才开始流式输出，避免过早输出被截断）
                MIN_BUFFER_FOR_STREAM = 20

                async for chunk in self.llm.stream_generate(current_prompt, temperature=0.1):
                    chunk_count += 1
                    logger.debug(f"[Agent] Chunk #{chunk_count}: type={type(chunk).__name__}, value={repr(chunk)[:200]}")
                    
                    if isinstance(chunk, dict):
                        logger.debug(f"[Agent] Chunk keys: {chunk.keys()}")
                        if "delta" in chunk:
                            delta_content = chunk["delta"]
                            response_text += delta_content
                            has_final_answer_marker = (
                                "Final Answer" in response_text or
                                "final answer" in response_text
                            )
                            if has_final_answer_marker:
                                should_stream_output = False
                            # 检查是否需要工具调用（使用更严格的检测）
                            tool_patterns = ["\nAction:", "\naction:", "Action Input:", "action input:"]
                            needs_tool = any(pattern in response_text for pattern in tool_patterns)
                            # 也检测 XML 格式的工具调用（MiniMax 格式）
                            has_xml_invoke = "<invoke" in response_text and "name=" in response_text
                            needs_tool = needs_tool or has_xml_invoke
                            
                            # 检查 JSON 是否完整（如果包含 Action Input）或 XML 格式
                            if needs_tool:
                                tool_call_detected = False
                                try:
                                    import json
                                    # 模式1: ReAct Action Input 格式
                                    json_match = re.search(r'Action Input:\s*([\s\S]*?)(?:\n|$)', response_text)
                                    if json_match:
                                        json_str = json_match.group(1).strip()
                                        if json_str.startswith('{') and json_str.endswith('}'):
                                            json.loads(json_str)  # 验证 JSON 完整性
                                            tool_call_detected = True
                                    
                                    # 模式2: MiniMax XML 格式
                                    if "</invoke>" in response_text:
                                        xml_pattern = r'<invoke\s+name="([^"]+)"'
                                        if re.search(xml_pattern, response_text, re.IGNORECASE):
                                            tool_call_detected = True
                                            
                                except (json.JSONDecodeError, re.error):
                                    pass
                                
                                if tool_call_detected:
                                    should_stream_output = False
                                    logger.info("[Agent] 检测到完整工具调用，停止流式输出")
                            elif has_final_answer_marker:
                                logger.info("[Agent] 检测到 Final Answer 标记，等待完整答案后输出")
                            elif len(response_text) > MIN_BUFFER_FOR_STREAM and should_stream_output:
                                # 流式输出内容（逐字符输出以实现打字机效果）
                                new_content = delta_content
                                for char in new_content:
                                    yield char
                                    streamed_content += char
                        elif "content" in chunk:
                            content = chunk["content"]
                            response_text += content
                            logger.debug(f"[Agent] ✓ Added content: '{content[:30]}...', total: {len(response_text)}")
                        elif "usage" in chunk:
                            usage_info = chunk["usage"]
                            logger.debug(f"[Agent] Got usage info: {usage_info}")
                        elif chunk.get("type") == "error":
                            error_content = chunk.get("content", "")
                            logger.error(f"[Agent] LLM 流式响应错误: {error_content}")
                            response_text += f"\n[错误] {error_content}\n"
                        elif chunk.get("type") == "done":
                            done_content = chunk.get("content", "")
                            logger.info(f"[Agent] ✓ ✓ ✓ 流式响应完成！chunk_count={chunk_count}, collected={len(response_text)}, done_content={len(done_content)}")
                    else:
                        str_chunk = str(chunk)
                        response_text += str_chunk
                        logger.debug(f"[Agent] ✓ Added str chunk: '{str_chunk[:30]}...', total: {len(response_text)}")
                
                #  注意：不在此处检查 Final Answer
                # 原因：流式传输中途 response_text 不完整，提取会截断答案
                # 例如收到 "Final Answer: 你\n" 时提取只得到"你"，后续"好！..."全部丢失

                # 检查是否需要工具调用（可在流式中途判断，有完整 Action Input 或 XML 即可）
                tool_call = self.tool_manager.parse_tool_call_from_text(response_text)
                
                # 提取并记录 Thought 和 Action 信息
                thought_match = re.search(r'##?\s*Thought\s*[\n:]?\s*(.+?)(?=\n##?\s*Action:|\n##?\s*Final Answer:|$)', response_text, re.DOTALL | re.IGNORECASE)
                if thought_match:
                    thought_text = thought_match.group(1).strip()[:200]
                    self._log_action("🧠 思考过程", {"thought": thought_text})
                
                action_match = re.search(r'##?\s*Action\s*[\n:]?\s*(.+?)(?=\n##?\s*Action Input:|\n##?\s*Observation:|\n##?\s*Final Answer:|$)', response_text, re.DOTALL | re.IGNORECASE)
                if action_match:
                    action_text = action_match.group(1).strip()
                    self._log_action("⚡ 行动计划", {"action": action_text})
                
                # 支持 ReAct 格式 (Action Input) 和 MiniMax XML 格式
                has_react_format = "Action Input:" in response_text
                has_xml_format = "<invoke" in response_text and "</invoke>" in response_text
                
                if tool_call and (has_react_format or has_xml_format):
                    # 🔧 Bug1修复：参数为空说明流式接收结束时 JSON 仍未完整
                    # 此时不应 continue（会跳过 current_prompt 更新导致无限循环）
                    # 而应该添加引导让 LLM 重试
                    if not tool_call["parameters"]:
                        self._log_action("⚠️ 工具参数不完整，添加引导让 LLM 重试")
                        guidance = (
                            "\n\n注意：您的工具调用格式不完整。请按照以下格式重新输出：\n"
                            "Thought: [您的思考]\n"
                            "Action: [正确的工具名]\n"
                            "Action Input: [完整的 JSON 参数]\n"
                            "请只输出完整的 ReAct 格式响应：\n"
                        )
                        current_prompt = current_prompt + response_text + guidance
                        break  # 跳出当前迭代，让 LLM 重试

                    # 更新历史记录
                    self._update_history(response_text, tool_call)

                    # 执行工具调用
                    self._log_action("🔧 检测到工具调用", tool_call)

                    tool_result = await self.call_tool(
                        tool_call["tool_name"],
                        **tool_call["parameters"]
                    )

                    # 记录工具调用和结果到历史
                    tool_entry = {
                        "tool_name": tool_call["tool_name"],
                        "parameters": tool_call["parameters"],
                        "result": tool_result,
                        "iteration": self.current_iteration,
                        "timestamp": time.time()
                    }
                    self.tool_result_history.append(tool_entry)

                    # 检查连续失败
                    if self._check_consecutive_failures(tool_result):
                        self._log_action("🛑 连续工具调用失败，强制结束")
                        yield output_formatter.format_no_result_answer()
                        return

                    # 检查是否应该强制结束（使用语义嵌入，在获取 tool_result 后检查）
                    force_check = await self._should_force_final_answer(response_text, tool_result)
                    if force_check["should_stop"]:
                        self._log_action("🛑 流式执行触发早停", {
                            "reasons": force_check["reasons"]
                        })
                        # 策略1：优先使用 LLM 响应中的 Final Answer
                        if "Final Answer" in response_text or "final answer" in response_text:
                            final_answer = self._extract_final_answer(response_text)
                            if final_answer:
                                cleaned_answer = self._prepare_answer_for_output(final_answer)
                                is_dup, msg = self._is_answer_duplicate_with_streamed(
                                    cleaned_answer,
                                    streamed_content
                                )
                                if not is_dup:
                                    self._log_action("📤 使用 Final Answer", {"length": len(cleaned_answer)})
                                    for char in cleaned_answer:
                                        yield char
                                # 修复：确保所有路径都有 return
                                return
                        
                        # 策略2：使用 suggestion
                        suggestion = output_formatter.clean_output(force_check.get('suggestion', ''))
                        suggestion = self._prepare_answer_for_output(suggestion)
                        if suggestion:
                            is_dup, msg = self._is_answer_duplicate_with_streamed(
                                suggestion,
                                streamed_content
                            )
                            if not is_dup:
                                yield suggestion
                            # 修复：确保所有路径都有 return
                            return
                        
                        # 策略3：优化：判断工具结果是否为自然语言格式
                        if tool_result and len(tool_result) > 10:
                            failure_indicators = ["错误", "失败", "未找到", "无法", "找不到", "不存在"]
                            is_failure = any(indicator in tool_result for indicator in failure_indicators)
                            if not is_failure:
                                cleaned_result = output_formatter.clean_output(tool_result)
                                cleaned_result = self._prepare_answer_for_output(cleaned_result)
                                cleaned_result = re.sub(r'^📝\s*答案摘要：\s*', '', cleaned_result)
                                
                                # 判断是否为自然语言格式
                                is_natural = bool(re.search(r'[。！？\n]', cleaned_result))
                                
                                if is_natural:
                                    is_dup, msg = self._is_answer_duplicate_with_streamed(
                                        cleaned_result,
                                        streamed_content
                                    )
                                    if not is_dup:
                                        self._log_action("� 直接使用工具结果（自然语言格式）", {"length": len(cleaned_result)})
                                        for char in cleaned_result:
                                            yield char
                                        return
                                    # 修复：is_dup=True 时也必须 return，避免继续执行策略4
                                    return
                                else:
                                    self._log_action("✨ 工具结果为结构化数据，使用 Final Output 转换")
                                    final_output = await self._generate_final_output(
                                        user_input=user_input,
                                        tool_result=cleaned_result
                                    )
                                    if final_output and len(final_output) > 5:
                                        is_dup, msg = self._is_answer_duplicate_with_streamed(
                                            final_output,
                                            streamed_content
                                        )
                                        if not is_dup:
                                            self._log_action("Final Output 生成答案（早停）", {"length": len(final_output)})
                                            for char in final_output:
                                                yield char
                                            return
                                    # 修复：确保早停策略的所有路径都有 return
                                    self._log_action("📝 Final Output 生成失败或为空，使用工具原始结果")
                                    if tool_result and len(tool_result) > 5:
                                        is_dup, msg = self._is_answer_duplicate_with_streamed(
                                            tool_result,
                                            streamed_content
                                        )
                                        if not is_dup:
                                            for char in tool_result:
                                                yield char
                                            return
                                    return
                    
                    # 更新提示词
                    observation = f"Observation: {tool_result}\nThought:"
                    current_prompt = current_prompt + response_text + "\n" + observation

                    self.last_successful_tool_result = tool_result
                    tool_result_preview = tool_result[:150] + "..." if len(tool_result) > 150 else tool_result
                    self._log_action("🔄 工具调用完成，进入下一轮推理", {
                        "next_iteration": self.current_iteration + 1,
                        "tool_name": tool_call["tool_name"],
                        "result_preview": tool_result_preview
                    })
                    continue

                # 🔧 流式响应完整接收后，统一检查 Final Answer
                # 此时 response_text 是完整的，提取结果不会被截断
                if "Final Answer" in response_text or "final answer" in response_text:
                    final_answer = self._extract_final_answer(response_text)
                    if final_answer and len(final_answer) > 10:
                        # 检查是否包含重复内容（LLM 可能输出了重复的答案）
                        # 如果 Final Answer 前的内容和提取的内容高度相似，说明有重复
                        # 🔧 修复：支持 Markdown 格式标题
                        import re as re_module
                        match = re_module.search(r'##?\s*Final Answer', response_text, re_module.IGNORECASE)
                        if match:
                            before_final = response_text[:match.start()]
                        else:
                            before_final = response_text.split("Final Answer")[0]
                        similarity = self._calculate_similarity(before_final, final_answer)
                        
                        # 计算已输出的内容和 Final Answer 前的重复部分
                        overlap_with_streamed = self._calculate_similarity(streamed_content, before_final)
                        
                        if similarity > 0.8:
                            # 有高度相似内容，说明 LLM 输出了重复答案
                            self._log_action("⚠️ 检测到 LLM 输出重复内容，只输出 Final Answer", {
                                "similarity": similarity
                            })
                            # 只输出 Final Answer 部分
                            cleaned_answer = output_formatter.clean_output(final_answer)
                            cleaned_answer = self._prepare_answer_for_output(cleaned_answer)
                            for char in cleaned_answer:
                                yield char
                        elif overlap_with_streamed > 0.7:
                            # 部分内容已输出，提取未输出的部分
                            self._log_action("📤 部分内容已流式输出，提取剩余 Final Answer")
                            # 找出 Final Answer 中与已输出内容不重复的部分
                            cleaned_answer = output_formatter.clean_output(final_answer)
                            cleaned_answer = self._prepare_answer_for_output(cleaned_answer)
                            already_output = output_formatter.clean_output(streamed_content)
                            # 尝试找到已输出内容的结尾位置
                            if cleaned_answer.startswith(already_output[:min(len(already_output), 50)]):
                                remaining = cleaned_answer[len(already_output):]
                                for char in remaining:
                                    yield char
                            else:
                                for char in cleaned_answer:
                                    yield char
                        else:
                            final_answer_preview = final_answer[:100] + "..." if len(final_answer) > 100 else final_answer
                            self._log_action("📤 提取 Final Answer", {
                                "length": len(final_answer),
                                "preview": final_answer_preview
                            })
                            cleaned_answer = output_formatter.clean_output(final_answer)
                            original_len = len(cleaned_answer)
                            cleaned_answer = self._prepare_answer_for_output(cleaned_answer)

                            if original_len != len(cleaned_answer):
                                self._log_action("📦 Final Answer去重", {
                                    "original": original_len,
                                    "deduplicated": len(cleaned_answer)
                                })
                                streamed_content = cleaned_answer
                            else:
                                streamed_content += cleaned_answer

                            for char in cleaned_answer:
                                yield char
                        self._log_action("✅ 流式输出完成")
                        return
                    else:
                        # Final Answer 标记存在但提取失败，跳过直接回答（可能是 LLM 格式问题）
                        self._log_action("⚠️ Final Answer 标记存在但提取失败，跳过此响应", {
                            "final_answer": final_answer,
                            "has_action": bool(tool_call)
                        })
                        yield output_formatter.format_no_result_answer()
                        return
                
                # 🔧 新增：LLM 直接回答（无工具调用、无 Final Answer 格式）
                # 当 LLM 给出完整答案但没有使用 ReAct 格式时，直接输出
                # 检查是否有 Final Answer 标记，如果有则跳过
                response_stripped = response_text.strip()
                final_answer_indicators = ["Final Answer", "final answer", "Final answer"]
                has_final_answer_indicator = any(kw in response_stripped for kw in final_answer_indicators)
                
                # 检查是否包含工具调用相关关键词（包括 XML 格式）
                has_tool_keywords = any(kw in response_stripped for kw in [
                    "Action:", "action:", "需要搜索", "调用工具", 
                    "<invoke>", "<invoke ", "</invoke>", "<think>", "<think>"
                ])
                
                if (len(response_stripped) > 30 and
                    not tool_call and
                    not has_final_answer_indicator and
                    not has_tool_keywords):
                    self._log_action(f"📤 LLM 直接回答（无工具调用）长度: {len(response_stripped)}")
                    cleaned_answer = output_formatter.clean_output(response_stripped)
                    original_len = len(cleaned_answer)
                    cleaned_answer = self._prepare_answer_for_output(cleaned_answer)

                    if original_len != len(cleaned_answer):
                        self._log_action("📦 LLM直接回答去重", {
                            "original": original_len,
                            "deduplicated": len(cleaned_answer)
                        })
                        streamed_content = cleaned_answer
                        for char in cleaned_answer:
                            yield char
                    else:
                        already_output = output_formatter.clean_output(streamed_content)
                        if cleaned_answer.startswith(already_output[:min(len(already_output), 50)]):
                            remaining = cleaned_answer[len(already_output):]
                            for char in remaining:
                                yield char
                        else:
                            for char in cleaned_answer:
                                yield char
                        streamed_content += cleaned_answer
                    return

                # 没有 Final Answer 也没有工具调用，检查是否陷入循环（使用语义嵌入）
                # 🔧 必须先检测再存入：若先 _update_history 后检测，
                #    last_responses 已含当前响应，会与自身比较得到 1.00 的误判相似度
                loop_check = await self._check_loop_detection(response_text)
                self._update_history(response_text)
                if loop_check["should_stop"]:
                    self._log_action("🛑 流式执行检测到循环", {"reason": loop_check["reason"]})
                    
                    if not response_text or len(response_text.strip()) < 10:
                        logger.warning("[Agent] 响应为空，可能存在 LLM 问题")
                        if "[错误]" in response_text:
                            error_match = re.search(r'\[错误\]\s*(.+?)\n', response_text, re.DOTALL)
                            if error_match:
                                error_msg = error_match.group(1).strip()
                                logger.error(f"[Agent] 检测到 LLM 错误信息: {error_msg}")
                                yield output_formatter.format_error_answer(error_msg)
                                return
                    
                    # 🔧 修复：优先使用工具结果，而不是直接尝试合成
                    # 策略：1. 先尝试从 tool_result_history 获取有效的最新结果
                    #       2. 如果没有有效工具结果，再尝试合成器
                    #       3. 只有在都失败时才输出无结果提示
                    
                    # 🔧 优化策略：减少不必要的 LLM 调用
                    # 策略1：直接从工具结果获取（工具已格式化，直接可读）
                    if self.tool_result_history:
                        for tool_entry in reversed(self.tool_result_history):
                            tool_result = tool_entry.get("result", "")
                            if tool_result and len(tool_result) > 10:
                                failure_indicators = ["错误", "失败", "未找到", "无法", "找不到", "不存在"]
                                is_failure = any(indicator in tool_result for indicator in failure_indicators)
                                if not is_failure:
                                    cleaned_result = output_formatter.clean_output(tool_result)
                                    cleaned_result = self._prepare_answer_for_output(cleaned_result)
                                    cleaned_result = re.sub(r'^📝\s*答案摘要：\s*', '', cleaned_result)
                                    
                                    # 判断是否为自然语言格式（包含句子结尾符号）
                                    is_natural = bool(re.search(r'[。！？\n]', cleaned_result))
                                    
                                    if is_natural:
                                        is_dup, msg = self._is_answer_duplicate_with_streamed(
                                            cleaned_result,
                                            streamed_content
                                        )
                                        if not is_dup:
                                            self._log_action("直接使用工具结果（自然语言格式）", {"length": len(cleaned_result)})
                                            for char in cleaned_result:
                                                yield char
                                            return
                                    else:
                                        self._log_action("✨ 工具结果为结构化数据，使用 Final Output 转换")
                                        final_output = await self._generate_final_output(
                                            user_input=user_input,
                                            tool_result=cleaned_result
                                        )
                                        if final_output and len(final_output) > 5:
                                            is_dup, msg = self._is_answer_duplicate_with_streamed(
                                                final_output,
                                                streamed_content
                                            )
                                            if not is_dup:
                                                self._log_action("📝 Final Output 生成答案", {"length": len(final_output)})
                                                for char in final_output:
                                                    yield char
                                                return
                    
                    # 策略2：尝试使用复杂合成器（备用）
                    if self.last_responses:
                        final_answer = await self._synthesize_final_answer(
                            user_input=user_input,
                            loop_reason=loop_check["reason"]
                        )
                        if final_answer and len(final_answer) > 10:
                            cleaned = output_formatter.clean_output(final_answer)
                            cleaned = self._prepare_answer_for_output(cleaned)
                            is_dup, msg = self._is_answer_duplicate_with_streamed(
                                cleaned,
                                streamed_content
                            )
                            if not is_dup:
                                self._log_action("📝 合成器生成答案", {"length": len(cleaned)})
                                for char in cleaned:
                                    yield char
                                return
                    
                    # 策略3：输出无结果提示
                    yield output_formatter.format_no_result_answer()
                    return

                # 继续累积响应
                current_prompt = current_prompt + response_text + "\n"
            
            except (ValueError, KeyError) as e:
                self._log_action("❌ 流式执行数据错误", {"error": str(e)})
                yield output_formatter.format_error_answer(f"数据错误: {str(e)}")
            except (OSError, IOError) as e:
                self._log_action("❌ 流式执行IO错误", {"error": str(e)})
                yield output_formatter.format_error_answer(f"IO错误: {str(e)}")
            except Exception as e:
                self._log_action("❌ 流式执行出错", {"error": str(e)})
                yield output_formatter.format_error_answer(str(e))
                return
        
        yield output_formatter.format_no_result_answer()
    
    def _build_react_prompt(self, user_input: str, history: List[Dict] = None, **kwargs) -> str:
        """
        构建 ReAct 提示词（使用模板系统）
        
        Args:
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数
            
        Returns:
            完整的提示词
        """
        logger.info("🚨🚨🚨 [_build_react_prompt] 被调用！用户输入: {}".format(user_input[:50]))
        
        # 获取工具描述
        tools_description = self.tool_manager.get_tools_description()
        if not tools_description:
            tools_description = "当前没有可用的工具，请直接回答问题。"
            logger.warning("⚠️ [Agent] 警告：没有可用工具！")
        
        logger.info(f"🔍 [Agent] 工具描述长度: {len(tools_description)} 字符")
        
        # 格式化历史记录
        history_section = ""
        if history:
            history_text = self._format_history(history)
            history_section = f"\n对话历史:\n{history_text}\n"
        
        # 判断是否为简单对话
        user_input_simple = self._is_simple_input(user_input)
        
        # 从kwargs获取额外的context（来自RAG检索结果）
        rag_context = kwargs.get("context", "")
        
        # 判断知识库是否有内容（仅用于信息展示，不影响工具调用决策）
        kb_has_content = "true"
        if not rag_context or rag_context.strip() in ["", "（无相关文档）", "无相关文档"]:
            kb_has_content = "false"
        
        # 构建上下文 - 匹配模板变量名
        context = {
            "max_iterations": self.max_iterations,
            "timeout": self.timeout,
            "available_tools": tools_description,
            "context": rag_context,
            "history_section": history_section,
            "user_input": user_input,
            "knowledge_base_has_content": kb_has_content,
            "user_input_simple": user_input_simple
        }
        
        # 使用模板系统渲染
        prompt = self._render_system_prompt(context)
        
        return prompt
    
    def _is_simple_input(self, user_input: str) -> bool:
        """
        判断是否为简单对话（问候、感谢等）
        
        Args:
            user_input: 用户输入
            
        Returns:
            是否为简单对话
        """
        simple_keywords = [
            '你好', '您好', '嗨', 'hi', 'hello', 'hi!', 'hello!',
            '谢谢', '感谢', '多谢', 'thanks', 'thank you',
            '再见', '拜拜', 'bye', 'bye bye',
            '好的', '行', '可以', '没问题'
        ]
        
        user_input_lower = user_input.lower().strip()
        return any(keyword.lower() in user_input_lower for keyword in simple_keywords)
    
    def _parse_response(self, response: str) -> Dict[str, any]:
        """
        解析 LLM 响应
        
        Args:
            response: LLM 的响应文本
            
        Returns:
            解析结果
        """
        # 检查是否包含最终答案
        if "Final Answer" in response or "final answer" in response:
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
        # 🔧 修复：支持 Markdown 格式标题（## Final Answer）和纯文本格式（Final Answer:）
        # Markdown 格式：## Final Answer\n 或 ## Final Answer 
        # 纯文本格式：Final Answer: 或 final answer:
        patterns = [
            r'##\s*Final Answer\s*\n(.*?)(?=\n##|\nThought:|\nAction:|\nObservation:|$)',
            r'##\s*Final Answer\s*:(.*?)(?=\n##|\nThought:|\nAction:|\nObservation:|$)',
            r'Final Answer:\s*(.*?)(?=\nThought:|\nAction:|\nObservation:|$)',
            r'final answer:\s*(.*?)(?=\nthought:|\naction:|\nobservation:|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
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
    
    async def _calculate_embedding_similarity(
        self, 
        text1: str, 
        text2: str
    ) -> float:
        """
        使用语义嵌入计算两个文本的相似度
        
        Args:
            text1: 第一个文本
            text2: 第二个文本
            
        Returns:
            相似度分数 (0-1)
        """
        if not text1 or not text2:
            return 0.0
        
        try:
            from app.services.embedding_service import EmbeddingService
            
            embedding_service = EmbeddingService()
            
            embeddings = await embedding_service.get_embeddings([text1, text2])
            
            vec1 = np.array(embeddings[0])
            vec2 = np.array(embeddings[1])
            
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            cosine_sim = dot_product / (norm1 * norm2)
            
            return float(cosine_sim)
            
        except (ValueError, KeyError) as e:
            self._log_action("⚠️ 嵌入相似度计算数据错误，降级为字符串匹配", {"error": str(e)})
            return self._calculate_similarity(text1, text2)
        except (OSError, IOError) as e:
            self._log_action("⚠️ 嵌入相似度计算IO错误，降级为字符串匹配", {"error": str(e)})
            return self._calculate_similarity(text1, text2)
        except Exception as e:
            self._log_action("⚠️ 嵌入相似度计算失败，降级为字符串匹配", {"error": str(e)})
            return self._calculate_similarity(text1, text2)
    
    def _generate_response_hash(self, response: str) -> str:
        """
        生成响应的哈希值用于快速比较
        
        Args:
            response: 响应文本
            
        Returns:
            哈希值
        """
        # 🔧 Bug6修复：提取关键部分：Action、Action Input 和 Thought（前50字符）
        action_pattern = r'Action:\s*(\w+)'
        input_pattern = r'Action Input:\s*(\{.*?\})'
        thought_pattern = r'Thought:\s*(.*?)(?=\nAction:|$)'
        
        action_match = re.search(action_pattern, response, re.IGNORECASE)
        input_match = re.search(input_pattern, response, re.DOTALL)
        thought_match = re.search(thought_pattern, response, re.DOTALL | re.IGNORECASE)
        
        key_content = ""
        if action_match:
            key_content += action_match.group(1)
        if input_match:
            key_content += input_match.group(1)
        if thought_match:
            thought_text = thought_match.group(1).strip()[:50]
            key_content += thought_text
        
        return hashlib.md5(key_content.encode()).hexdigest()
    
    def _extract_latest_tool_call(self, response: str) -> Optional[Dict[str, str]]:
        """
        从响应中提取最后一个工具调用部分（用于循环检测）
        
        Args:
            response: LLM 响应文本
            
        Returns:
            包含 Thought 和 Action 的字典，如果没有则返回 None
        """
        tool_patterns = [
            r'Thought:\s*(.*?)(?=\nAction:|\Z)',
            r'Action:\s*(\w+)',
            r'Action Input:\s*(\{[\s\S]*?\})',
        ]
        
        thought_pattern = r'Thought:\s*(.*?)(?=\nAction:|\nObservation:|\Z)'
        action_pattern = r'Action:\s*(\w+)'
        input_pattern = r'Action Input:\s*(\{[\s\S]*?\})'
        
        thought_match = re.search(thought_pattern, response, re.DOTALL | re.IGNORECASE)
        action_match = re.search(action_pattern, response, re.IGNORECASE)
        input_match = re.search(input_pattern, response, re.DOTALL)
        
        if action_match:
            result = {
                "thought": thought_match.group(1).strip()[:100] if thought_match else "",
                "action": action_match.group(1),
                "input": input_match.group(1) if input_match else ""
            }
            return result
        
        return None
    
    async def _check_loop_detection(self, current_response: str) -> Dict[str, Any]:
        """
        检测是否陷入循环（使用语义嵌入相似度）
        
        Args:
            current_response: 当前响应
            
        Returns:
            检测结果字典
        """
        if not self.early_stop_enabled:
            return {"should_stop": False, "reason": ""}
        
        if len(self.last_responses) < 2:
            return {"should_stop": False, "reason": ""}
        
        # 🔧 修复：提取最后一个工具调用进行比较，而不是整个响应
        # 这样可以避免 LLM 输出多个工具调用时导致的误判
        current_latest = self._extract_latest_tool_call(current_response)
        
        for i, (prev_response, prev_hash) in enumerate(self.last_responses[-3:]):
            prev_latest = self._extract_latest_tool_call(prev_response)
            
            if current_latest and prev_latest:
                current_compare = f"{current_latest.get('thought', '')} {current_latest.get('action', '')} {current_latest.get('input', '')}"
                prev_compare = f"{prev_latest.get('thought', '')} {prev_latest.get('action', '')} {prev_latest.get('input', '')}"
                
                similarity = await self._calculate_embedding_similarity(current_compare, prev_compare)
                
                if similarity > self.similarity_threshold:
                    return {
                        "should_stop": True,
                        "reason": f"检测到循环：与第{len(self.last_responses)-i}轮工具调用语义相似度{similarity:.2f}",
                        "similarity": similarity
                    }
                
                current_compare_hash = hashlib.md5(current_compare.encode()).hexdigest()
                prev_compare_hash = hashlib.md5(prev_compare.encode()).hexdigest()
                
                if current_compare_hash == prev_compare_hash:
                    return {
                        "should_stop": True,
                        "reason": f"检测到完全重复：与第{len(self.last_responses)-i}轮工具调用相同",
                        "similarity": 1.0
                    }
            else:
                similarity = await self._calculate_embedding_similarity(current_response, prev_response)
                
                if similarity > self.similarity_threshold:
                    return {
                        "should_stop": True,
                        "reason": f"检测到循环：与第{len(self.last_responses)-i}轮响应语义相似度{similarity:.2f}",
                        "similarity": similarity
                    }
        
        tool_call = self.tool_manager.parse_tool_call_from_text(current_response)
        if tool_call:
            for prev_call in self.tool_call_history[-3:]:
                if (prev_call["tool_name"] == tool_call["tool_name"] and 
                    self._calculate_similarity(
                        str(prev_call["parameters"]), 
                        str(tool_call["parameters"])
                    ) > 0.9):
                    return {
                        "should_stop": True,
                        "reason": f"检测到重复工具调用：{tool_call['tool_name']}",
                        "similarity": 1.0
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
        failure_indicators = ["错误", "失败", "未找到", "无法", "缺少必需参数"]
        is_failure = any(indicator in tool_result for indicator in failure_indicators)

        if is_failure:
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0

        return self.consecutive_failures >= self.max_consecutive_failures

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度（简单基于字符重叠）

        Args:
            text1: 第一个文本
            text2: 第二个文本

        Returns:
            相似度分数 0.0 - 1.0
        """
        if not text1 or not text2:
            return 0.0

        # 清理文本
        clean1 = re.sub(r'\s+', '', text1.lower())
        clean2 = re.sub(r'\s+', '', text2.lower())

        if clean1 == clean2:
            return 1.0

        # 使用简单的 Jaccard 相似度（基于字符 n-gram）
        def get_ngrams(text: str, n: int = 3) -> set:
            return set(text[i:i+n] for i in range(max(1, len(text) - n + 1)))

        ngrams1 = get_ngrams(clean1)
        ngrams2 = get_ngrams(clean2)

        if not ngrams1 or not ngrams2:
            return 0.0

        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)

        return intersection / union if union > 0 else 0.0

    def _is_answer_duplicate_with_streamed(
        self,
        answer: str,
        streamed_content: str,
        similarity_threshold: float = 0.85
    ) -> tuple[bool, str]:
        """
        检查答案是否与已流式输出的内容重复
        
        Args:
            answer: 待输出的答案
            streamed_content: 已流式输出的内容
            similarity_threshold: 相似度阈值
            
        Returns:
            (是否重复, 提示信息)
        """
        if not answer or not streamed_content:
            return False, ""
        
        cleaned_answer = output_formatter.clean_output(answer)
        cleaned_streamed = output_formatter.clean_output(streamed_content)
        
        if not cleaned_answer or not cleaned_streamed:
            return False, ""
        
        similarity = self._calculate_similarity(cleaned_answer, cleaned_streamed)
        
        if similarity > similarity_threshold:
            self._log_action("⚠️ 最终答案与已输出内容重复，跳过输出", {
                "similarity": similarity,
                "answer_length": len(cleaned_answer),
                "streamed_length": len(cleaned_streamed)
            })
            return True, f"内容重复度过高 ({similarity:.2f})，跳过输出"
        
        if cleaned_answer.startswith(cleaned_streamed[:min(len(cleaned_streamed), 50)]):
            remaining_length = len(cleaned_answer) - len(cleaned_streamed)
            if remaining_length > 0:
                self._log_action("📤 提取未输出的剩余内容", {
                    "remaining_length": remaining_length,
                    "similarity": similarity
                })
                return False, f"输出剩余 {remaining_length} 字符"
        
        return False, ""

    def _prepare_answer_for_output(self, answer: str) -> str:
        cleaned_answer = output_formatter.clean_output(answer)
        if not cleaned_answer:
            return ""

        # 🔧 移除 [来自记忆] 等内部标记
        cleaned_answer = re.sub(r'\[来自记忆\]\s*', '', cleaned_answer, flags=re.IGNORECASE)
        cleaned_answer = re.sub(r'\[来源[：:][^\]]*\]\s*', '', cleaned_answer)
        
        cleaned_answer = self._remove_duplicate_full_text(cleaned_answer)
        
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", cleaned_answer)
            if paragraph.strip()
        ]

        if len(paragraphs) >= 2:
            for unit_size in range(1, len(paragraphs) // 2 + 1):
                if len(paragraphs) % unit_size != 0:
                    continue

                units = [
                    paragraphs[index:index + unit_size]
                    for index in range(0, len(paragraphs), unit_size)
                ]

                if len(units) > 1 and all(unit == units[0] for unit in units[1:]):
                    deduplicated = "\n\n".join(units[0]).strip()
                    if deduplicated != cleaned_answer:
                        self._log_action("🧹 检测到重复段落并完成去重", {
                            "original_length": len(cleaned_answer),
                            "deduplicated_length": len(deduplicated),
                            "repeat_count": len(units)
                        })
                    return deduplicated

        return cleaned_answer

    def _remove_duplicate_full_text(self, text: str) -> str:
        """
        检测并移除整个文本的重复内容
        
        如果文本的后半部分与前半部分高度相似（> 85%），说明整个答案重复了，去重保留一份
        """
        if len(text) < 100:
            return text
        
        mid = len(text) // 2
        first_half = text[:mid]
        second_half = text[mid:]
        
        if len(first_half) < 50 or len(second_half) < 50:
            return text
        
        cleaned_first = self._normalize_for_comparison(first_half)
        cleaned_second = self._normalize_for_comparison(second_half)
        similarity = self._calculate_similarity(cleaned_first, cleaned_second)
        
        if similarity > 0.85:
            self._log_action("🧹 检测到全文重复，只保留一份", {
                "similarity": similarity,
                "original_length": len(text),
                "deduplicated_length": len(first_half)
            })
            return first_half
        
        return text
    
    def _normalize_for_comparison(self, text: str) -> str:
        """
        标准化文本用于相似度比较
        - 移除多余空白
        - 统一换行符
        """
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        return text.strip()

    async def _should_force_final_answer(self, current_response: str, tool_result: str = None) -> Dict[str, Any]:
        """
        判断是否应该强制输出最终答案
        
        Args:
            current_response: 当前响应
            tool_result: 工具结果（如果有）
            
        Returns:
            判断结果
        """
        reasons = []
        
        # 1. 循环检测（使用语义嵌入，只有当相似度 > 0.95 时才触发）
        loop_check = await self._check_loop_detection(current_response)
        if loop_check.get("should_stop"):
            similarity = loop_check.get("similarity", 0)
            if similarity > 0.95:
                reasons.append(loop_check["reason"])
        
        # 2. 连续失败检测
        if tool_result and self._check_consecutive_failures(tool_result):
            reasons.append(f"连续{self.consecutive_failures}次工具调用失败")
        
        # 3. 迭代次数检查（只有在真正达到上限时才触发）
        if self.current_iteration >= self.max_iterations:
            reasons.append(f"达到最大迭代次数({self.current_iteration}/{self.max_iterations})")
        
        should_stop = len(reasons) > 0
        
        return {
            "should_stop": should_stop,
            "reasons": reasons,
            "suggestion": self._generate_fallback_answer(tool_result) if should_stop else ""
        }
    
    def _generate_fallback_answer(self, tool_result: str = None) -> str:
        """
        生成备用答案
        
        Args:
            tool_result: 工具检索结果（如果有）
            
        Returns:
            备用答案
        """
        if tool_result and len(tool_result) > 20:
            return f"根据检索到的资料：\n\n{tool_result}\n\n如果以上信息有帮助，请告诉我是否需要进一步解释。"
        return ("抱歉，我在处理您的问题时遇到了一些困难。"
                "基于目前的信息，我建议您：\n"
                "1. 尝试重新表述问题\n"
                "2. 提供更具体的信息\n"
                "3. 或者稍后再试")
    
    def _get_synthesizer(self):
        """延迟获取结果合成器（使用统一的 OutputAgent）"""
        if self._result_synthesizer is None:
            from app.agent_framework.core.output_agent import (
                OutputAgent,
                SynthesisStrategy
            )
            self._result_synthesizer = OutputAgent(
                llm_adapter=self.llm,
                default_strategy=SynthesisStrategy.NARRATIVE
            )
        return self._result_synthesizer
    
    async def _generate_final_output(self, user_input: str, tool_result: str) -> str:
        """
        使用轻量级 Final Output 提示词直接生成最终答案
        
        与 _synthesize_final_answer 的区别：
        - 这个方法直接使用工具结果，不经过复杂的 ResultSynthesizer
        - 适合简单的 RAG 查询场景（如企业知识库问答）
        - 更轻量、更快速、更可靠
        
        Args:
            user_input: 用户原始输入
            tool_result: 工具执行结果
            
        Returns:
            自然语言形式的最终答案
        """
        try:
            prompt = output_formatter.get_final_output_prompt(
                user_query=user_input,
                tool_result=tool_result
            )
            
            response = await self.llm.generate(prompt, temperature=0.3)
            
            if response:
                cleaned = self._prepare_answer_for_output(response)
                if len(cleaned) > 5:
                    self._log_action("✨ Final Output 生成成功", {
                        "input_length": len(user_input),
                        "tool_result_length": len(tool_result),
                        "output_length": len(cleaned)
                    })
                    return cleaned
            
            return ""
            
        except (ValueError, KeyError) as e:
            self._log_action("❌ Final Output 生成数据错误", {"error": str(e)})
            return ""
        except (OSError, IOError) as e:
            self._log_action("❌ Final Output 生成IO错误", {"error": str(e)})
            return ""
        except Exception as e:
            self._log_action("❌ Final Output 生成失败", {"error": str(e)})
            return ""
    
    async def _synthesize_final_answer(self, user_input: str, loop_reason: str = "") -> str:
        """
        使用结果合成器生成最终答案
        
        当检测到循环时，收集所有中间结果交给 LLM 判断最佳答案
        
        Args:
            user_input: 用户原始输入
            loop_reason: 循环检测原因
            
        Returns:
            合成的最终答案
        """
        from app.agent_framework.core.output_agent import SynthesisStrategy
        
        self._log_action("🧩 启动结果合成器", {
            "tool_results_count": len(self.tool_result_history),
            "llm_responses_count": len(self.last_responses),
            "loop_reason": loop_reason
        })
        
        synthesizer = self._get_synthesizer()
        
        # 清空之前的输入
        synthesizer.clear_inputs()
        
        task_id = f"react_loop_exit_{int(time.time())}"
        
        # 收集有效工具结果
        valid_tool_results = []
        for idx, tool_entry in enumerate(self.tool_result_history):
            tool_name = tool_entry.get("tool_name", "unknown")
            tool_result = tool_entry.get("result", "")
            iteration = tool_entry.get("iteration", 0)
            
            # 判断是否为有效结果
            failure_indicators = ["错误", "失败", "未找到", "无法", "找不到", "不存在"]
            is_failure = any(indicator in tool_result for indicator in failure_indicators)
            
            if not is_failure and len(tool_result) > 10:
                valid_tool_results.append({
                    "tool_name": tool_name,
                    "result": tool_result,
                    "iteration": iteration
                })
                synthesizer.add_result(
                    task_id=task_id,
                    source_agent=f"工具_{tool_name}",
                    source_type="tool_result",
                    content=f"【{tool_name} 查询结果】\n{tool_result}",
                    confidence=0.9,
                    metadata={"tool_name": tool_name, "iteration": iteration}
                )
        
        # 添加 LLM 思考内容（提取思考中的关键信息）
        for idx, (response, _) in enumerate(self.last_responses):
            # 提取 Final Answer 如果存在（支持 Markdown 和纯文本格式）
            final_answer_patterns = [
                r'##\s*Final Answer\s*\n(.+?)(?=\n##|\nThought:|\nAction:|\nObservation:|$)',
                r'##\s*Final Answer\s*:(.+?)(?=\n##|\nThought:|\nAction:|\nObservation:|$)',
                r'Final Answer:\s*(.+?)(?=\nThought:|\nAction:|\nObservation:|$)',
            ]
            final_answer_match = None
            for pattern in final_answer_patterns:
                final_answer_match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
                if final_answer_match:
                    break
            
            has_final = bool(final_answer_match) or "Final Answer" in response or "Final answer" in response
            
            # 提取 Thought 部分
            thought_match = re.search(r'Thought:\s*(.+?)(?:\n|$)', response, re.DOTALL)
            thought = thought_match.group(1).strip() if thought_match else ""
            
            content_parts = []
            if has_final and final_answer_match:
                content_parts.append(f"【最终答案候选】{final_answer_match.group(1).strip()}")
            if thought:
                content_parts.append(f"【思考过程 {idx+1}】{thought[:200]}")
            
            if content_parts:
                synthesizer.add_result(
                    task_id=task_id,
                    source_agent=f"LLM_思考_{idx+1}",
                    source_type="llm_reasoning",
                    content="\n".join(content_parts),
                    confidence=0.5,
                    metadata={"order": idx + 1, "has_final": has_final}
                )
        
        # 添加用户输入
        synthesizer.add_result(
            task_id=task_id,
            source_agent="用户",
            source_type="user_input",
            content=f"【用户问题】{user_input}",
            confidence=1.0,
            metadata={"type": "original_query"}
        )
        
        self._log_action("📦 合成器输入准备完成", {
            "tool_results": len(valid_tool_results),
            "llm_thoughts": len(self.last_responses)
        })
        
        # 如果没有有效工具结果，返回默认消息
        if not valid_tool_results:
            # 🔧 修复：当没有工具调用时，检查是否有 LLM 的 Final Answer 或错误信息
            logger.info("🔍 [OutputAgent] 没有工具结果，检查 LLM 响应是否包含 Final Answer")
            logger.info(f"🔍 [OutputAgent] self.last_responses 数量: {len(self.last_responses)}")
            
            if self.last_responses:
                for idx, (resp, _) in enumerate(reversed(self.last_responses)):
                    logger.info(f"🔍 [OutputAgent] 检查响应 {idx}, 长度: {len(resp)}")
                    if resp:
                        logger.info(f"🔍 [OutputAgent] 响应内容前100字符: {resp[:100]}")
                    
                    # 🔧 修复：检查是否包含错误信息
                    if "[错误]" in resp:
                        error_match = re.search(r'\[错误\]\s*(.+?)\n', resp, re.DOTALL)
                        if error_match:
                            error_msg = error_match.group(1).strip()
                            logger.error(f"🔍 [OutputAgent] LLM 返回错误: {error_msg}")
                            return f"抱歉，处理过程中遇到问题：{error_msg}"
                    
                    # 🔧 修复：检查是否包含 Final Answer（支持 Markdown 格式）
                    if "Final Answer" in resp or "final answer" in resp:
                        logger.info("✅ [OutputAgent] 找到 'Final Answer' 字样")
                        answer = self._extract_final_answer(resp)
                        logger.info(f"🔍 [OutputAgent] 提取的 answer: {answer}, 长度: {len(answer) if answer else 0}")
                        
                        if answer and len(answer) > 10:
                            logger.info(f"✅ [OutputAgent] Final Answer 有效，长度 {len(answer)}, 内容: {answer[:50]}...")
                            cleaned = self._prepare_answer_for_output(answer)
                            return cleaned
                        else:
                            logger.warning(f"⚠️ [OutputAgent] 提取的 answer 无效或太短: '{answer}'")
            
            return "抱歉，在处理您的问题时遇到了一些困难，没有找到相关的信息。"
        
        # 调用合成器生成答案
        synthesis_result = await synthesizer.synthesize(
            user_query=user_input,
            strategy=SynthesisStrategy.NARRATIVE
        )
        
        self._log_action("🧩 结果合成完成", {
            "final_response_length": len(synthesis_result.final_response),
            "confidence": synthesis_result.confidence,
            "quality_score": synthesis_result.quality_score
        })
        
        # 返回合成结果
        return self._prepare_answer_for_output(synthesis_result.final_response)
    
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
        self.tool_result_history = []
        self.consecutive_failures = 0
        self.last_responses = []
        self.last_successful_tool_result = None
