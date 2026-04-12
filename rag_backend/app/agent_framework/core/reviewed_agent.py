"""
带输出审查的 ReAct Agent

在生成最终答案后，使用 Output Agent 进行质量审查
如果审查不通过，可以选择重新生成或使用优化后的答案
"""

import re
from typing import List, Dict, AsyncGenerator, Optional, Any
from .react_agent import ReActAgent
from .output_agent import OutputAgent, OutputReviewResult


class ReviewedReActAgent(ReActAgent):
    """
    带输出审查的 ReAct Agent
    
    继承自 ReActAgent，增加了 Output Agent 的质量审查功能
    """
    
    def __init__(self, *args, **kwargs):
        self.enable_output_review = kwargs.pop('enable_output_review', True)
        self.max_review_attempts = kwargs.pop('max_review_attempts', 2)
        
        super().__init__(*args, **kwargs)
        
        self.output_agent = OutputAgent(llm_adapter=self.llm)
    
    async def stream_run_with_review(
        self, 
        user_input: str, 
        history: List[Dict] = None, 
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        带审查的流式执行
        
        流程：
        1. ReAct Agent 生成答案
        2. Output Agent 审查答案
        3. 如果不通过，提供反馈并可能重新生成
        4. 最多重试 max_review_attempts 次
        
        Args:
            user_input: 用户输入
            history: 对话历史
            **kwargs: 其他参数
            
        Yields:
            逐步生成的内容
        """
        self._reset_state()
        self._log_action("🌊 开始带审查的 ReAct 流式执行", {"user_input": user_input})
        
        if not self.enable_output_review:
            async for chunk in self.stream_run(user_input, history, **kwargs):
                yield chunk
            return
        
        best_answer = ""
        best_score = 0.0
        attempt = 0
        
        while attempt < self.max_review_attempts:
            attempt += 1
            self._log_action(f"📝 开始第 {attempt} 次生成和审查")
            
            current_response = ""
            
            prompt = self._build_react_prompt(user_input, history, **kwargs)
            if attempt > 1 and best_answer:
                prompt = self._add_revision_hint(prompt, best_answer, attempt)
            
            current_prompt = prompt
            
            while self.current_iteration < self.max_iterations:
                self.current_iteration += 1
                
                if self._check_timeout():
                    yield self.output_agent.output_formatter.format_error_answer("执行超时")
                    return
                
                try:
                    response_text = ""
                    
                    async for chunk in self.llm.stream_generate(current_prompt, temperature=0.1):
                        if isinstance(chunk, dict):
                            if "delta" in chunk:
                                response_text += chunk["delta"]
                            elif "usage" in chunk:
                                usage_info = chunk["usage"]
                        else:
                            response_text += str(chunk)
                        
                        tool_call = self.tool_manager.parse_tool_call_from_text(response_text)
                        if tool_call and "Action Input:" in response_text:
                            if not tool_call["parameters"]:
                                continue
                            
                            self._update_history(response_text, tool_call)
                            
                            tool_result = await self.call_tool(
                                tool_call["tool_name"],
                                **tool_call["parameters"]
                            )
                            
                            if self._check_consecutive_failures(tool_result):
                                self._log_action("🛑 连续工具调用失败")
                                break
                            
                            observation = f"Observation: {tool_result}\nThought:"
                            current_prompt = current_prompt + response_text + "\n" + observation
                            break
                    else:
                        if "Final Answer:" in response_text:
                            current_response = self._extract_final_answer(response_text)
                            if current_response:
                                break
                        
                        self._update_history(response_text)
                        current_prompt = current_prompt + response_text + "\n"
                        continue
                    
                    break
                    
                except Exception as e:
                    self._log_action("❌ 执行出错", {"error": str(e)})
                    current_response = ""
                    break
            
            if not current_response:
                yield self.output_agent.output_formatter.format_no_result_answer()
                return
            
            cleaned_response = self.output_agent.output_formatter.clean_output(current_response)
            
            self._log_action(f"🔍 开始审查第 {attempt} 次答案", {"answer": cleaned_response[:100]})
            
            review_result = await self.output_agent.deep_review(cleaned_response, user_input)
            
            self._log_action(f"📊 审查结果", {
                "score": review_result.score,
                "approved": review_result.is_approved,
                "issues": review_result.issues
            })
            
            if review_result.is_approved:
                self._log_action("✅ 答案通过审查")
                for char in cleaned_response:
                    yield char
                return
            
            if attempt >= self.max_review_attempts:
                self._log_action("⚠️ 达到最大审查次数，使用当前最佳答案")
                if cleaned_response:
                    for char in cleaned_response:
                        yield char
                else:
                    yield self.output_agent.output_formatter.format_no_result_answer()
                return
            
            best_answer = cleaned_response
            best_score = review_result.score
            self._log_action(f"🔄 答案未通过审查，准备第 {attempt + 1} 次生成")
        
        yield self.output_agent.output_formatter.format_no_result_answer()
    
    def _add_revision_hint(self, prompt: str, previous_answer: str, attempt: int) -> str:
        """
        添加修订提示到提示词中
        
        Args:
            prompt: 原始提示词
            previous_answer: 上一次生成的答案
            attempt: 当前尝试次数
            
        Returns:
            添加了修订提示的新提示词
        """
        revision_note = f"""

【重要提示 - 第 {attempt} 次生成】
这是第 {attempt} 次尝试。上一次的答案存在质量问题，请特别注意：
1. 确保回答直接、简洁
2. 不要使用内部标记或调试信息
3. 不要包含任何敏感信息
4. 开头要友好、自然

【上一次的答案（有问题）】
{previous_answer}

请生成一个改进后的答案。"""
        
        if "【用户问题】" in prompt:
            parts = prompt.split("【用户问题】")
            return parts[0] + revision_note + "\n【用户问题】" + parts[1]
        
        return prompt + revision_note


def create_reviewed_agent(*args, **kwargs) -> ReviewedReActAgent:
    """
    工厂函数：创建带审查的 Agent
    
    使用方式：
        agent = create_reviewed_agent(...)
        async for chunk in agent.stream_run_with_review(user_input, history):
            yield chunk
    """
    return ReviewedReActAgent(*args, **kwargs)
