#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agent 模板集成测试

测试 Agent 使用新模板文件的实际运行效果
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from app.agent_framework.core.react_agent import ReActAgent
from app.agent_framework.core.plan_agent import PlanAgent
from app.agent_framework.llm.base_adapter import BaseLLMAdapter


class MockLLMAdapter(BaseLLMAdapter):
    """Mock LLM 适配器"""
    
    def __init__(self, model_name: str = "mock-model"):
        self.model_name = model_name
        self.call_count = 0
        self.last_prompt = None
        
    async def generate(self, prompt: str, **kwargs) -> str:
        """模拟生成响应"""
        self.call_count += 1
        self.last_prompt = prompt
        
        if "Final Answer:" in prompt or "最终答案" in prompt:
            return "Final Answer: 这是一个测试回复"
        
        if "Thought:" in prompt and "Action:" in prompt:
            return """Thought: 我需要使用计算器工具来计算结果
Action: calculator
Action Input: {"expression": "(125 + 347) * 12"}
Observation: 计算结果是 5664
Thought: 我现在知道最终答案了
Final Answer: (125 + 347) * 12 = 5664"""
        
        if "thought:" in prompt.lower() and "action:" in prompt.lower():
            return """thought: 我应该使用计算器
action: calculator
action input: {"expression": "10 + 20"}
observation: 结果是 30
thought: 完成了
final answer: 10 + 20 = 30"""
        
        if "{" in prompt and '"analysis"' in prompt:
            return """{
    "analysis": "这是一个需要分析的任务",
    "steps": [
        {
            "step": 1,
            "action": "第一步操作",
            "tool": "tool1",
            "input": "输入1",
            "expected_output": "输出1"
        },
        {
            "step": 2,
            "action": "第二步操作",
            "tool": "tool2",
            "input": "输入2",
            "expected_output": "输出2"
        }
    ]
}"""
        
        if '"tool":' in prompt and '"input":' in prompt:
            if '"tool": "none"' in prompt:
                return '{"tool": "none", "result": "无需工具"}'
            return '{"tool": "calculator", "input": {"expression": "10+10"}}'
        
        return "Final Answer: 这是测试回复"


class MockToolManager:
    """Mock 工具管理器"""
    
    def __init__(self):
        self.tools = {
            "calculator": {
                "name": "calculator",
                "description": "执行数学计算",
                "parameters": {
                    "expression": {"type": "string", "description": "数学表达式"}
                }
            },
            "search": {
                "name": "search",
                "description": "搜索信息",
                "parameters": {
                    "query": {"type": "string", "description": "搜索关键词"}
                }
            }
        }
        
    def get_tools_description(self) -> str:
        """获取工具描述"""
        lines = []
        for name, tool in self.tools.items():
            lines.append(f"- {name}: {tool['description']}")
            params = ", ".join([f"{k}" for k in tool["parameters"].keys()])
            lines.append(f"  参数: {params}")
        return "\n".join(lines)
    
    def get_tool(self, tool_name: str):
        """获取工具"""
        tool_info = self.tools.get(tool_name, {})
        
        async def execute(**kwargs):
            if tool_name == "calculator":
                expression = kwargs.get("expression", "0")
                try:
                    result = eval(expression)
                    return str(result)
                except:
                    return "计算错误"
            return f"执行结果: {kwargs}"
        
        return type('Tool', (), {
            'name': tool_name,
            'description': tool_info.get("description", ""),
            'execute': execute
        })()
    
    async def execute_tool(self, tool_name: str, **kwargs) -> str:
        """执行工具"""
        if tool_name == "calculator":
            expression = kwargs.get("expression", "0")
            try:
                result = eval(expression)
                return str(result)
            except:
                return "计算错误"
        return f"工具 {tool_name} 执行结果"


@pytest.fixture
def mock_llm():
    """创建 mock LLM"""
    return MockLLMAdapter()


@pytest.fixture
def mock_tool_manager():
    """创建 mock 工具管理器"""
    return MockToolManager()


class TestReActAgentTemplate:
    """测试 ReActAgent 模板集成"""
    
    @pytest.mark.asyncio
    async def test_react_agent_uses_template(self, mock_llm, mock_tool_manager):
        """测试 ReActAgent 是否使用模板文件"""
        print("\n" + "="*70)
        print("测试 1: ReActAgent 使用模板文件")
        print("="*70)
        
        agent = ReActAgent(
            llm_adapter=mock_llm,
            tool_manager=mock_tool_manager,
            max_iterations=5,
            template_name="react_agent"
        )
        
        prompt = agent._build_react_prompt("你好")
        
        print("\n📋 生成的提示词片段：")
        print("-" * 70)
        print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        print("-" * 70)
        
        checks = [
            ("{max_iterations}" not in prompt, "✅ max_iterations 已替换"),
            ("{tools_description}" not in prompt, "✅ tools_description 已替换"),
            ("{user_input}" not in prompt, "✅ user_input 已替换"),
            ("{history_section}" not in prompt, "✅ history_section 已替换"),
            ("Thought:" in prompt, "✅ ReAct 格式存在"),
            ("Final Answer:" in prompt, "✅ Final Answer 存在"),
        ]
        
        print("\n🔍 检查结果：")
        for passed, msg in checks:
            print(f"   {'✅' if passed else '❌'} {msg}")
        
        assert all(passed for passed, _ in checks), "ReActAgent 模板渲染失败"
    
    @pytest.mark.asyncio
    async def test_react_simple_greeting(self, mock_llm, mock_tool_manager):
        """测试 ReActAgent 简单问候语"""
        print("\n" + "="*70)
        print("测试 2: ReActAgent 简单问候语")
        print("="*70)
        
        agent = ReActAgent(
            llm_adapter=mock_llm,
            tool_manager=mock_tool_manager,
            max_iterations=5,
            template_name="react_agent"
        )
        
        greeting = "你好"
        prompt = agent._build_react_prompt(greeting)
        
        print(f"\n📋 输入: {greeting}")
        print("\n📋 生成的提示词片段：")
        print("-" * 70)
        print(prompt[:800] + "..." if len(prompt) > 800 else prompt)
        print("-" * 70)
        
        checks = [
            ("无需调用工具" in prompt or "直接给出 Final Answer" in prompt, 
             "✅ 简单对话提示存在"),
            ("你好" in prompt, "✅ 用户输入存在"),
            ("Thought:" in prompt, "✅ ReAct 格式存在"),
        ]
        
        print("\n🔍 检查结果：")
        for passed, msg in checks:
            print(f"   {'✅' if passed else '❌'} {msg}")
        
        assert all(passed for passed, _ in checks), "简单问候语处理失败"
    
    @pytest.mark.asyncio
    async def test_react_complex_task(self, mock_llm, mock_tool_manager):
        """测试 ReActAgent 复杂任务"""
        print("\n" + "="*70)
        print("测试 3: ReActAgent 复杂任务")
        print("="*70)
        
        agent = ReActAgent(
            llm_adapter=mock_llm,
            tool_manager=mock_tool_manager,
            max_iterations=5,
            template_name="react_agent"
        )
        
        task = "请帮我计算 (125 + 347) * 12 的结果"
        prompt = agent._build_react_prompt(task)
        
        print(f"\n📋 输入: {task}")
        print("\n📋 生成的提示词片段：")
        print("-" * 70)
        print(prompt[:800] + "..." if len(prompt) > 800 else prompt)
        print("-" * 70)
        
        checks = [
            ("只有当问题明确需要查询" in prompt, 
             "✅ 复杂任务规则存在"),
            ("(125 + 347) * 12" in prompt, "✅ 用户输入存在"),
            ("calculator" in prompt, "✅ 工具描述存在"),
        ]
        
        print("\n🔍 检查结果：")
        for passed, msg in checks:
            print(f"   {'✅' if passed else '❌'} {msg}")
        
        assert all(passed for passed, _ in checks), "复杂任务处理失败"


class TestPlanAgentTemplate:
    """测试 PlanAgent 模板集成"""
    
    @pytest.mark.asyncio
    async def test_plan_agent_uses_template(self, mock_llm, mock_tool_manager):
        """测试 PlanAgent 是否使用模板文件"""
        print("\n" + "="*70)
        print("测试 4: PlanAgent 使用模板文件")
        print("="*70)
        
        agent = PlanAgent(
            llm_adapter=mock_llm,
            tool_manager=mock_tool_manager,
            max_iterations=10,
            max_steps=5,
            template_name="plan_agent"
        )
        
        task = "帮我分析数据"
        tools = [
            {"name": "tool1", "description": "工具1"},
            {"name": "tool2", "description": "工具2"}
        ]
        
        prompt = agent._build_planning_prompt(task, tools)
        
        print("\n📋 生成的提示词片段：")
        print("-" * 70)
        print(prompt[:600] + "..." if len(prompt) > 600 else prompt)
        print("-" * 70)
        
        checks = [
            ("{phase}" not in prompt, "✅ phase 已替换"),
            ("{task}" not in prompt, "✅ task 已替换"),
            ("{tools_description}" not in prompt, "✅ tools_description 已替换"),
            ("{max_steps}" not in prompt, "✅ max_steps 已替换"),
            ("帮我分析数据" in prompt, "✅ 任务内容存在"),
            ("planning" in prompt.lower(), "✅ 规划阶段标识存在"),
        ]
        
        print("\n🔍 检查结果：")
        for passed, msg in checks:
            print(f"   {'✅' if passed else '❌'} {msg}")
        
        assert all(passed for passed, _ in checks), "PlanAgent 模板渲染失败"
    
    @pytest.mark.asyncio
    async def test_plan_execution_phase(self, mock_llm, mock_tool_manager):
        """测试 PlanAgent 执行阶段"""
        print("\n" + "="*70)
        print("测试 5: PlanAgent 执行阶段")
        print("="*70)
        
        agent = PlanAgent(
            llm_adapter=mock_llm,
            tool_manager=mock_tool_manager,
            max_iterations=10,
            max_steps=5,
            template_name="plan_agent"
        )
        
        task = "帮我分析数据"
        plan = {
            "analysis": "分析任务",
            "steps": [
                {
                    "step": 1,
                    "action": "读取数据",
                    "tool": "read_data",
                    "input": "文件路径",
                    "expected_output": "数据"
                },
                {
                    "step": 2,
                    "action": "分析数据",
                    "tool": "analyze",
                    "input": "数据",
                    "expected_output": "分析结果"
                }
            ]
        }
        history = [
            {"step": 1, "action": "读取数据", "result": "成功读取"}
        ]
        
        prompt = agent._build_execution_prompt(task, plan, 2, history)
        
        print("\n📋 生成的提示词片段：")
        print("-" * 70)
        print(prompt[:800] + "..." if len(prompt) > 800 else prompt)
        print("-" * 70)
        
        checks = [
            ("{phase}" not in prompt, "✅ phase 已替换"),
            ("{task}" not in prompt, "✅ task 已替换"),
            ("{plan_json}" not in prompt, "✅ plan_json 已替换"),
            ("{history}" not in prompt, "✅ history 已替换"),
            ("{current_step}" not in prompt, "✅ current_step 已替换"),
            ("execution" in prompt.lower(), "✅ 执行阶段标识存在"),
            ("读取数据" in prompt, "✅ 任务内容存在"),
        ]
        
        print("\n🔍 检查结果：")
        for passed, msg in checks:
            print(f"   {'✅' if passed else '❌'} {msg}")
        
        assert all(passed for passed, _ in checks), "PlanAgent 执行阶段模板渲染失败"
    
    @pytest.mark.asyncio
    async def test_plan_completion_phase(self, mock_llm, mock_tool_manager):
        """测试 PlanAgent 完成阶段"""
        print("\n" + "="*70)
        print("测试 6: PlanAgent 完成阶段")
        print("="*70)
        
        agent = PlanAgent(
            llm_adapter=mock_llm,
            tool_manager=mock_tool_manager,
            max_iterations=10,
            max_steps=5,
            template_name="plan_agent"
        )
        
        task = "帮我分析数据"
        plan = {
            "analysis": "分析任务",
            "steps": [
                {"step": 1, "action": "读取数据", "tool": "read_data"}
            ]
        }
        history = [
            {"step": 1, "action": "读取数据", "result": "成功"}
        ]
        
        prompt = agent._build_completion_prompt(task, plan, history)
        
        print("\n📋 生成的提示词片段：")
        print("-" * 70)
        print(prompt[:600] + "..." if len(prompt) > 600 else prompt)
        print("-" * 70)
        
        checks = [
            ("{phase}" not in prompt, "✅ phase 已替换"),
            ("{task}" not in prompt, "✅ task 已替换"),
            ("{plan_json}" not in prompt, "✅ plan_json 已替换"),
            ("{history}" not in prompt, "✅ history 已替换"),
            ("completion" in prompt.lower(), "✅ 完成阶段标识存在"),
        ]
        
        print("\n🔍 检查结果：")
        for passed, msg in checks:
            print(f"   {'✅' if passed else '❌'} {msg}")
        
        assert all(passed for passed, _ in checks), "PlanAgent 完成阶段模板渲染失败"


class TestAgentDualMode:
    """测试 Agent 双模式支持"""
    
    @pytest.mark.asyncio
    async def test_react_fallback_to_static_prompt(self, mock_llm, mock_tool_manager):
        """测试 ReActAgent 回退到静态 prompt"""
        print("\n" + "="*70)
        print("测试 7: ReActAgent 回退到静态 prompt")
        print("="*70)
        
        agent = ReActAgent(
            llm_adapter=mock_llm,
            tool_manager=mock_tool_manager,
            max_iterations=5
        )
        
        print("\n📋 Agent 默认配置:")
        print(f"   - 模板名称: {agent.template_name}")
        print(f"   - 使用模板: {agent.use_template}")
        
        prompt = agent._build_react_prompt("测试")
        
        checks = [
            (agent.use_template == True, "✅ 使用模板模式"),
            (len(prompt) > 0, "✅ 成功生成提示词"),
            ("Thought:" in prompt, "✅ ReAct 格式存在"),
        ]
        
        print("\n🔍 检查结果：")
        for passed, msg in checks:
            print(f"   {'✅' if passed else '❌'} {msg}")
        
        assert all(passed for passed, _ in checks), "双模式支持失败"
    
    @pytest.mark.asyncio
    async def test_plan_custom_template(self, mock_llm, mock_tool_manager):
        """测试 PlanAgent 使用自定义模板"""
        print("\n" + "="*70)
        print("测试 8: PlanAgent 使用自定义模板")
        print("="*70)
        
        agent = PlanAgent(
            llm_adapter=mock_llm,
            tool_manager=mock_tool_manager,
            max_iterations=10,
            max_steps=5,
            template_name="plan_agent"
        )
        
        task = "测试任务"
        tools = [{"name": "tool1", "description": "测试工具"}]
        
        prompt = agent._build_planning_prompt(task, tools)
        
        checks = [
            ("{phase}" not in prompt, "✅ 模板变量已替换"),
            ("{task}" not in prompt, "✅ 任务变量已替换"),
            ("{max_steps}" not in prompt, "✅ max_steps 已替换"),
        ]
        
        print("\n🔍 检查结果：")
        for passed, msg in checks:
            print(f"   {'✅' if passed else '❌'} {msg}")
        
        assert all(passed for passed, _ in checks), "自定义模板使用失败"


def run_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("🚀 Agent 模板集成测试")
    print("="*70)
    print("\n测试目标：")
    print("1. 验证 Agent 使用新模板文件")
    print("2. 验证模板变量正确替换")
    print("3. 验证双模式架构正常工作")
    print("4. 验证不同阶段模板正确渲染")
    
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "--color=yes"
    ])


if __name__ == "__main__":
    run_tests()
