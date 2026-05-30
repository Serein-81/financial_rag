"""
回归测试：ReActAgent.stream_run 的"真流式"行为。

重点覆盖 DeepSeek 类适配器——其 stream_generate 直接 yield **字符串**（非 dict），
历史上这些字符串 chunk 落到 else 分支只累加、不输出，导致 ## Final Answer 正文
只能靠末尾整段 replay 刷出。本测试锁定：
1. 字符串 chunk 也能在检测到 ## Final Answer 后逐字增量输出（流式 yield 次数 > 1）；
2. 内部推理标记（## Thought / ## Final Answer 头）不泄漏给用户；
3. 末尾不重复（streamed_content 命中去重，整段 replay 被跳过）。
"""

import pytest

from app.agent_framework.core.react_agent import ReActAgent


class _StrChunkLLM:
    """模拟 DeepSeek：stream_generate 逐字符 yield 字符串增量。"""

    def __init__(self, full_text: str):
        self._full = full_text

    async def stream_generate(self, prompt: str, temperature: float = 0.1, **kwargs):
        for ch in self._full:
            yield ch


class _NoToolManager:
    def parse_tool_call_from_text(self, text):
        return None


def _make_agent(full_text: str) -> ReActAgent:
    agent = ReActAgent.__new__(ReActAgent)
    agent.llm = _StrChunkLLM(full_text)
    agent.tool_manager = _NoToolManager()
    agent.max_iterations = 5
    agent.timeout = 60
    # 跳过 prompt 构建（依赖模板/工具描述）
    agent._build_react_prompt = lambda *a, **k: ""
    return agent


@pytest.mark.asyncio
async def test_string_chunks_stream_final_answer_incrementally():
    answer = "支付宝是移动支付的一种具体实现形式，移动支付是更广泛的概念。"
    full = f"## Thought\n这是通用知识问题，直接回答。\n\n## Final Answer\n{answer}"
    agent = _make_agent(full)

    chunks = [c async for c in agent.stream_run("支付宝和移动支付什么关系")]
    output = "".join(chunks)

    # 1. 逐字流式：产生了多次 yield（而非末尾一次性整段）
    assert len(chunks) > 1
    # 2. 正文完整输出
    assert answer in output
    # 3. 内部标记不泄漏
    assert "## Thought" not in output
    assert "## Final Answer" not in output
    assert "这是通用知识问题" not in output
    # 4. 末尾去重：正文只出现一次（replay 被跳过）
    assert output.count(answer) == 1
