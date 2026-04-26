import asyncio
import sys
from typing import Any, AsyncGenerator

sys.path.insert(0, "d:/Python/Codebase/My_rag/rag_backend")

from app.agent_framework.core.react_agent import ReActAgent


class DummyLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def stream_generate(
        self,
        prompt: str,
        temperature: float = 0.1
    ) -> AsyncGenerator[dict[str, str], None]:
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            yield {
                "delta": (
                    "我需要搜索嘉应学院的准确位置信息。\n\n"
                    "Action: search_web\n"
                    "Action Input: {\"query\": \"嘉应学院在哪里 地理位置\"}"
                )
            }
            yield {"type": "done", "content": ""}
            return

        if "Observation: 嘉应学院位于广东省梅州市。" not in prompt:
            raise AssertionError("第二轮推理未携带工具观察结果")

        yield {"delta": "Final Answer: 嘉应学院位于广东省梅州市。"}
        yield {"type": "done", "content": ""}

    async def generate(self, prompt: str, temperature: float = 0.1) -> str:
        raise AssertionError("该场景不应触发非流式 generate")


class DummyToolManager:
    def __init__(self) -> None:
        self.tools: dict[str, dict[str, Any]] = {
            "search_web": {"description": "搜索网络"}
        }

    def get_tools_description(self) -> str:
        return "- search_web: 搜索网络"

    def parse_tool_call_from_text(self, text: str) -> dict[str, Any] | None:
        if "Action: search_web" not in text:
            return None
        return {
            "tool_name": "search_web",
            "parameters": {"query": "嘉应学院在哪里 地理位置"}
        }

    async def call_tool(self, tool_name: str, **kwargs: Any) -> str:
        if tool_name != "search_web":
            raise AssertionError(f"unexpected tool: {tool_name}")
        return "嘉应学院位于广东省梅州市。"


class DuplicateFinalAnswerLLM(DummyLLM):
    async def stream_generate(
        self,
        prompt: str,
        temperature: float = 0.1
    ) -> AsyncGenerator[dict[str, str], None]:
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            yield {
                "delta": (
                    "我需要搜索嘉应学院的准确位置信息。\n\n"
                    "Action: search_web\n"
                    "Action Input: {\"query\": \"嘉应学院在哪里 地理位置\"}"
                )
            }
            yield {"type": "done", "content": ""}
            return

        if "Observation: 嘉应学院位于广东省梅州市。" not in prompt:
            raise AssertionError("第二轮推理未携带工具观察结果")

        duplicated_answer = (
            "嘉应学院位于广东省梅州市。\n\n"
            "嘉应学院基本信息：\n\n"
            "地理位置：广东省梅州市\n\n"
            "嘉应学院位于广东省梅州市。\n\n"
            "嘉应学院基本信息：\n\n"
            "地理位置：广东省梅州市"
        )
        yield {"delta": f"Final Answer: {duplicated_answer}"}
        yield {"type": "done", "content": ""}


async def run_scenario(llm: DummyLLM, expected_output: str) -> None:
    agent = ReActAgent(
        llm_adapter=llm,
        tool_manager=DummyToolManager(),
        system_prompt="test",
        max_iterations=3,
        timeout=10.0
    )
    agent.enable_tracing = False
    agent.enable_prompt_optimization = False
    agent._build_react_prompt = lambda *args, **kwargs: "系统提示\n"

    async def fake_should_force_final_answer(
        response: str,
        tool_result: str
    ) -> dict[str, Any]:
        return {"should_stop": False, "reasons": [], "suggestion": ""}

    agent._should_force_final_answer = fake_should_force_final_answer

    chunks = [chunk async for chunk in agent.stream_run("嘉应学院在哪里", history=[])]
    output = "".join(chunks)

    assert output == expected_output
    assert len(agent.llm.prompts) == 2


def test_stream_run_continues_after_tool_call() -> None:
    asyncio.run(run_scenario(DummyLLM(), "嘉应学院位于广东省梅州市。"))


def test_stream_run_deduplicates_repeated_final_answer() -> None:
    asyncio.run(
        run_scenario(
            DuplicateFinalAnswerLLM(),
            "嘉应学院位于广东省梅州市。\n\n嘉应学院基本信息：\n\n地理位置：广东省梅州市"
        )
    )


if __name__ == "__main__":
    asyncio.run(run_scenario(DummyLLM(), "嘉应学院位于广东省梅州市。"))
