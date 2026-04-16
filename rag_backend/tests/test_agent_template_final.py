#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agent 模板集成测试（完全独立版本）

复制 PromptEngine 核心逻辑，直接测试模板文件渲染
"""

import sys
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional


class SimplePromptEngine:
    """简化版提示词引擎（从 prompt_service.py 复制核心逻辑）"""
    
    def __init__(self, templates_dir: Optional[str] = None):
        if templates_dir is None:
            current_dir = Path(__file__).parent
            templates_dir = current_dir / "app" / "prompts" / "templates"
        
        self.templates_dir = Path(templates_dir)
        self.templates_cache: Dict[str, str] = {}
        
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📝 [SimplePromptEngine] 初始化完成")
        print(f"   └─ 模板目录: {self.templates_dir}")
    
    def render(
        self, 
        template_name: str, 
        context: Dict[str, Any],
        use_cache: bool = True
    ) -> str:
        """
        渲染提示词模板
        """
        template = self._load_template(template_name, use_cache)
        
        if not template:
            print(f"⚠️ [SimplePromptEngine] 模板不存在: {template_name}")
            return ""
        
        template = self._process_for_loops(template, context)
        template = self._process_conditions(template, context)
        template = self._replace_variables(template, context)
        template = self._clean_whitespace(template)
        
        return template.strip()
    
    def _load_template(self, template_name: str, use_cache: bool) -> str:
        """从文件加载模板"""
        if use_cache and template_name in self.templates_cache:
            return self.templates_cache[template_name]
        
        template_path = self.templates_dir / f"{template_name}.txt"
        
        if not template_path.exists():
            print(f"❌ [SimplePromptEngine] 模板文件不存在: {template_path}")
            return ""
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            if use_cache:
                self.templates_cache[template_name] = template
            
            return template
        
        except Exception as e:
            print(f"❌ [SimplePromptEngine] 加载模板失败: {template_name} | 错误: {e}")
            return ""
    
    def _process_for_loops(self, template: str, context: Dict) -> str:
        """处理循环渲染"""
        pattern = r'{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%}(.*?){%\s*endfor\s*%}'
        
        def replace_loop(match):
            item_name = match.group(1)
            list_name = match.group(2)
            loop_content = match.group(3)
            
            items = context.get(list_name, [])
            
            if not isinstance(items, list):
                return ""
            
            result = []
            for item in items:
                temp_context = context.copy()
                
                if isinstance(item, dict):
                    for key, value in item.items():
                        temp_context[f"{item_name}.{key}"] = value
                        temp_context[item_name] = item
                else:
                    temp_context[item_name] = item
                
                rendered = self._replace_variables(loop_content, temp_context)
                result.append(rendered)
            
            return "\n".join(result)
        
        return re.sub(pattern, replace_loop, template, flags=re.DOTALL)
    
    def _process_conditions(self, template: str, context: Dict) -> str:
        """处理条件渲染"""
        pattern = r'{%\s*if\s+(.*?)\s*%}(.*?)(?:{%\s*else\s*%}(.*?))?{%\s*endif\s*%}'
        
        def replace_condition(match):
            condition = match.group(1).strip()
            true_block = match.group(2)
            false_block = match.group(3) if match.group(3) else ""
            
            if self._evaluate_condition(condition, context):
                return true_block
            else:
                return false_block
        
        return re.sub(pattern, replace_condition, template, flags=re.DOTALL)
    
    def _evaluate_condition(self, condition: str, context: Dict) -> bool:
        """评估条件"""
        condition = condition.strip()
        
        if '==' in condition:
            parts = condition.split('==')
            if len(parts) == 2:
                var_name = parts[0].strip()
                expected_value = parts[1].strip().strip('"\'')
                actual_value = str(context.get(var_name, '')).strip()
                return actual_value == expected_value
        
        if condition in context:
            value = context[condition]
            if isinstance(value, bool):
                return value
            return bool(value)
        
        return False
    
    def _replace_variables(self, template: str, context: Dict) -> str:
        """替换变量 {variable_name}"""
        def replace(match):
            var_name = match.group(1).strip()
            value = context.get(var_name, match.group(0))
            return str(value)
        
        pattern = r'\{(\w+(?:\.\w+)*)\}'
        return re.sub(pattern, replace, template)
    
    def _clean_whitespace(self, template: str) -> str:
        """清理多余空行"""
        lines = template.split('\n')
        cleaned_lines = []
        prev_empty = False
        
        for line in lines:
            is_empty = len(line.strip()) == 0
            
            if is_empty and prev_empty:
                continue
            
            cleaned_lines.append(line)
            prev_empty = is_empty
        
        return '\n'.join(cleaned_lines)


def test_react_template_rendering():
    """测试 ReAct 模板渲染"""
    print("\n" + "="*70)
    print("测试 1: ReAct 模板渲染")
    print("="*70)
    
    engine = SimplePromptEngine()
    
    context = {
        "max_iterations": 5,
        "tools_description": "- calculator: 执行数学计算\n  参数: expression",
        "history_section": "\n对话历史:\n用户: 你好\n助手: 你好！有什么可以帮你的吗？\n",
        "user_input": "请帮我计算 (125 + 347) * 12 的结果",
        "user_input_simple": False
    }
    
    result = engine.render("react_agent", context)
    
    print("\n📋 渲染结果片段：")
    print("-" * 70)
    print(result[:600] + "..." if len(result) > 600 else result)
    print("-" * 70)
    
    checks = [
        ("{max_iterations}" not in result, "✅ max_iterations 已替换"),
        ("{tools_description}" not in result, "✅ tools_description 已替换"),
        ("{user_input}" not in result, "✅ user_input 已替换"),
        ("{history_section}" not in result, "✅ history_section 已替换"),
        ("{user_input_simple}" not in result, "✅ user_input_simple 已替换"),
        ("Thought:" in result, "✅ ReAct 格式存在"),
        ("Final Answer:" in result, "✅ Final Answer 存在"),
        ("最多进行 5 轮思考" in result, "✅ max_iterations 值正确"),
        ("只有当问题明确需要查询" in result, "✅ 复杂任务规则正确"),
        ("calculator" in result, "✅ 工具描述存在"),
    ]
    
    print("\n🔍 检查结果：")
    for passed, msg in checks:
        print(f"   {'✅' if passed else '❌'} {msg}")
    
    return all(passed for passed, _ in checks)


def test_react_simple_greeting():
    """测试 ReAct 简单问候语"""
    print("\n" + "="*70)
    print("测试 2: ReAct 简单问候语")
    print("="*70)
    
    engine = SimplePromptEngine()
    
    context = {
        "max_iterations": 5,
        "tools_description": "- calculator: 执行数学计算",
        "history_section": "",
        "user_input": "你好",
        "user_input_simple": True
    }
    
    result = engine.render("react_agent", context)
    
    print(f"\n📋 渲染结果片段：")
    print("-" * 70)
    print(result[:600] + "..." if len(result) > 600 else result)
    print("-" * 70)
    
    checks = [
        ("无需调用工具" in result or "直接给出 Final Answer" in result, 
         "✅ 简单对话规则正确"),
        ("你好" in result, "✅ 用户输入存在"),
        ("Thought:" in result, "✅ ReAct 格式存在"),
    ]
    
    print("\n🔍 检查结果：")
    for passed, msg in checks:
        print(f"   {'✅' if passed else '❌'} {msg}")
    
    return all(passed for passed, _ in checks)


def test_plan_planning_phase():
    """测试 Plan 规划阶段"""
    print("\n" + "="*70)
    print("测试 3: Plan 规划阶段")
    print("="*70)
    
    engine = SimplePromptEngine()
    
    context = {
        "phase": "planning",
        "task": "帮我分析公司2023年的财务状况",
        "tools_description": "- read_excel: 读取Excel文件\n- analyze_data: 分析数据",
        "max_steps": 10
    }
    
    result = engine.render("plan_agent", context)
    
    print("\n📋 渲染结果片段：")
    print("-" * 70)
    print(result[:600] + "..." if len(result) > 600 else result)
    print("-" * 70)
    
    checks = [
        ("{phase}" not in result, "✅ phase 已替换"),
        ("{task}" not in result, "✅ task 已替换"),
        ("{tools_description}" not in result, "✅ tools_description 已替换"),
        ("{max_steps}" not in result, "✅ max_steps 已替换"),
        ("帮我分析公司2023年的财务状况" in result, "✅ 任务内容存在"),
        ("planning" in result.lower(), "✅ 规划阶段标识正确"),
    ]
    
    print("\n🔍 检查结果：")
    for passed, msg in checks:
        print(f"   {'✅' if passed else '❌'} {msg}")
    
    return all(passed for passed, _ in checks)


def test_plan_execution_phase():
    """测试 Plan 执行阶段"""
    print("\n" + "="*70)
    print("测试 4: Plan 执行阶段")
    print("="*70)
    
    engine = SimplePromptEngine()
    
    step_info = {
        "step": 3,
        "action": "生成报告",
        "tool": "generate_report",
        "input": "分析结果"
    }
    
    context = {
        "phase": "execution",
        "task": "帮我分析公司2023年的财务状况",
        "plan_json": '{\n  "analysis": "分析公司财务",\n  "steps": []\n}',
        "history": [
            {"step": 1, "action": "读取Excel文件", "result": "成功读取到500行数据"},
            {"step": 2, "action": "分析财务数据", "result": "计算出收入增长率15%"}
        ],
        "current_step": 3,
        "current_step_info": step_info,
        "current_step_info_action": step_info.get("action", ""),
        "current_step_info_tool": step_info.get("tool", ""),
        "current_step_info_input": step_info.get("input", "")
    }
    
    result = engine.render("plan_agent", context)
    
    print("\n📋 渲染结果片段：")
    print("-" * 70)
    print(result[:800] + "..." if len(result) > 800 else result)
    print("-" * 70)
    
    checks = [
        ("{phase}" not in result, "✅ phase 已替换"),
        ("{task}" not in result, "✅ task 已替换"),
        ("{plan_json}" not in result, "✅ plan_json 已替换"),
        ("{history}" not in result, "✅ history 已替换"),
        ("{current_step}" not in result, "✅ current_step 已替换"),
        ("{current_step_info}" not in result, "✅ current_step_info 已替换"),
        ("execution" in result.lower(), "✅ 执行阶段标识正确"),
        ("读取Excel文件" in result, "✅ 历史步骤1存在"),
        ("分析财务数据" in result, "✅ 历史步骤2存在"),
        ("当前步骤（第 3 步）" in result, "✅ 当前步骤正确"),
        ("生成报告" in result, "✅ 当前步骤信息正确"),
    ]
    
    print("\n🔍 检查结果：")
    for passed, msg in checks:
        print(f"   {'✅' if passed else '❌'} {msg}")
    
    return all(passed for passed, _ in checks)


def test_plan_completion_phase():
    """测试 Plan 完成阶段"""
    print("\n" + "="*70)
    print("测试 5: Plan 完成阶段")
    print("="*70)
    
    engine = SimplePromptEngine()
    
    context = {
        "phase": "completion",
        "task": "帮我分析公司2023年的财务状况",
        "plan_json": '{\n  "analysis": "分析公司财务",\n  "steps": []\n}',
        "history": [
            {"step": 1, "action": "读取Excel文件", "result": "成功读取"},
            {"step": 2, "action": "分析数据", "result": "分析完成"},
            {"step": 3, "action": "生成报告", "result": "报告已生成"}
        ]
    }
    
    result = engine.render("plan_agent", context)
    
    print("\n📋 渲染结果片段：")
    print("-" * 70)
    print(result[:600] + "..." if len(result) > 600 else result)
    print("-" * 70)
    
    checks = [
        ("{phase}" not in result, "✅ phase 已替换"),
        ("{task}" not in result, "✅ task 已替换"),
        ("{plan_json}" not in result, "✅ plan_json 已替换"),
        ("{history}" not in result, "✅ history 已替换"),
        ("completion" in result.lower(), "✅ 完成阶段标识正确"),
    ]
    
    print("\n🔍 检查结果：")
    for passed, msg in checks:
        print(f"   {'✅' if passed else '❌'} {msg}")
    
    return all(passed for passed, _ in checks)


def main():
    """运行所有测试"""
    print("\n" + "="*70)
    print("🚀 Agent 模板集成测试")
    print("="*70)
    print("\n测试目标：")
    print("1. 验证模板文件正确加载")
    print("2. 验证模板变量正确替换")
    print("3. 验证条件渲染正常工作")
    print("4. 验证循环渲染正常工作")
    
    tests = [
        ("ReAct 模板渲染", test_react_template_rendering),
        ("ReAct 简单问候语", test_react_simple_greeting),
        ("Plan 规划阶段", test_plan_planning_phase),
        ("Plan 执行阶段", test_plan_execution_phase),
        ("Plan 完成阶段", test_plan_completion_phase),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ 测试 {name} 失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "="*70)
    print("📊 测试结果汇总")
    print("="*70)
    
    passed_count = 0
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"   {status}: {name}")
        if passed:
            passed_count += 1
    
    print("\n" + "="*70)
    if passed_count == len(results):
        print("🎉 所有测试通过！")
    else:
        print(f"⚠️  通过 {passed_count}/{len(results)} 个测试")
    print("="*70)
    
    return passed_count == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
