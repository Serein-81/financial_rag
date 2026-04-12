"""测试新的 Agent 模板"""

import sys
import os
import re
import json
from pathlib import Path
from typing import Dict, Any, List

class SimplePromptEngine:
    """简化的 PromptEngine，支持 Jinja2 风格的模板语法"""

    def __init__(self, templates_dir: Path = None):
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "app" / "prompts" / "templates"
        self.templates_dir = templates_dir
        self.templates_cache = {}

    def render(self, template_name: str, context: dict = None, load_skills: bool = False) -> str:
        """渲染模板"""
        if context is None:
            context = {}

        template = self._load_template(template_name, use_cache=True)

        if not template:
            return f"[模板不存在: {template_name}]"

        template = self._process_for_loops(template, context)
        template = self._process_conditions(template, context)
        template = self._replace_variables(template, context)
        template = self._clean_whitespace(template)

        return template.strip()

    def _load_template(self, template_name: str, use_cache: bool = True) -> str:
        if use_cache and template_name in self.templates_cache:
            return self.templates_cache[template_name]

        template_path = self.templates_dir / f"{template_name}.txt"

        if not template_path.exists():
            print(f"❌ 模板文件不存在: {template_path}")
            return ""

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()

            if use_cache:
                self.templates_cache[template_name] = template

            return template

        except Exception as e:
            print(f"❌ 加载模板失败: {template_name} | 错误: {e}")
            return ""

    def _process_for_loops(self, template: str, context: dict) -> str:
        """处理 {% for item in items %} ... {% endfor %} 循环"""
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

    def _process_conditions(self, template: str, context: dict) -> str:
        """处理 {% if %} ... {% elif %} ... {% else %} ... {% endif %} 条件"""
        pattern = r'{%\s*if\s+([^%]+?)\s*%}(.*?)(?:{%\s*elif\s+([^%]+?)\s*%}(.*?))*(?:{%\s*else\s*%}(.*?))?{%\s*endif\s*%}'

        def replace_condition(match):
            if_condition = match.group(1).strip()
            if_content = match.group(2)

            elif_conditions = []
            elif_contents = []

            temp_str = match.group(3)
            if temp_str:
                elif_conditions.append(temp_str.strip())
                elif_contents.append(match.group(4))

            else_content = match.group(5) if match.group(5) else ""

            if self._evaluate_condition(if_condition, context):
                return if_content

            for i, elif_cond in enumerate(elif_conditions):
                if self._evaluate_condition(elif_cond, context):
                    return elif_contents[i]

            return else_content

        return re.sub(pattern, replace_condition, template, flags=re.DOTALL)

    def _evaluate_condition(self, condition: str, context: dict) -> bool:
        """评估条件表达式"""
        condition = condition.strip()

        if "==" in condition:
            parts = condition.split("==")
            if len(parts) == 2:
                var_name = parts[0].strip()
                expected_value = parts[1].strip().strip('"').strip("'")
                actual_value = str(context.get(var_name, ""))
                return actual_value == expected_value

        elif "!=" in condition:
            parts = condition.split("!=")
            if len(parts) == 2:
                var_name = parts[0].strip()
                expected_value = parts[1].strip().strip('"').strip("'")
                actual_value = str(context.get(var_name, ""))
                return actual_value != expected_value

        else:
            var_name = condition
            value = context.get(var_name)
            return bool(value)

        return False

    def _replace_variables(self, template: str, context: dict) -> str:
        """替换 {variable} 和 {object.property} 变量"""
        pattern = r'\{([^}]+)\}'

        def replace_var(match):
            var_path = match.group(1).strip()

            if '.' in var_path:
                parts = var_path.split('.')
                value = context

                for part in parts:
                    if isinstance(value, dict):
                        value = value.get(part, "")
                    else:
                        value = ""
                        break

                return str(value)

            value = context.get(var_path)
            if value is None:
                return match.group(0)
            return str(value)

        return re.sub(pattern, replace_var, template)

    def _clean_whitespace(self, template: str) -> str:
        """清理多余空行"""
        lines = template.split('\n')
        cleaned_lines = []
        prev_empty = False

        for line in lines:
            is_empty = not line.strip()

            if is_empty:
                if not prev_empty:
                    cleaned_lines.append('')
                prev_empty = True
            else:
                cleaned_lines.append(line)
                prev_empty = False

        return '\n'.join(cleaned_lines)


def test_react_template():
    """测试 ReAct Agent 模板"""
    print("\n" + "="*60)
    print("测试 1: ReAct Agent 模板")
    print("="*60)

    engine = SimplePromptEngine()

    context = {
        "max_iterations": 10,
        "tools_description": "- search: 搜索工具\n- calculator: 计算工具",
        "history_section": "\n对话历史:\n用户: 你好\n助手: 你好！\n",
        "user_input": "你好，今天天气怎么样？",
        "user_input_simple": True
    }

    result = engine.render("react_agent", context)

    print(f"\n📋 渲染结果：")
    print("-" * 60)
    print(result)
    print("-" * 60)

    print(f"\n🔍 变量替换检查：")
    checks = [
        ("{max_iterations}" not in result, "max_iterations (10)"),
        ("{tools_description}" not in result, "tools_description"),
        ("{history_section}" not in result, "history_section"),
        ("{user_input}" not in result, "user_input"),
        ("{user_input_simple}" not in result, "user_input_simple"),
    ]

    for check, name in checks:
        print(f"   {'✅' if check else '❌'} {name}")

    return all(c[0] for c in checks)

def test_plan_template_planning_phase():
    """测试 Plan Agent 模板 - 规划阶段"""
    print("\n" + "="*60)
    print("测试 2: Plan Agent 模板 - 规划阶段")
    print("="*60)

    engine = SimplePromptEngine()

    context = {
        "phase": "planning",
        "task": "帮我分析公司2023年的财务状况",
        "tools_description": "- read_excel: 读取Excel文件\n- analyze_data: 分析数据\n- generate_report: 生成报告",
        "max_steps": 5
    }

    result = engine.render("plan_agent", context)

    print(f"\n📋 渲染结果：")
    print("-" * 60)
    print(result[:1000])  # 只打印前1000字符
    print("-" * 60)

    print(f"\n🔍 变量替换检查：")
    checks = [
        ("{phase}" not in result, "phase"),
        ("{task}" not in result, "task"),
        ("{tools_description}" not in result, "tools_description"),
        ("{max_steps}" not in result, "max_steps"),
    ]

    for check, name in checks:
        print(f"   {'✅' if check else '❌'} {name}")

    return all(c[0] for c in checks)

def test_plan_template_execution_phase():
    """测试 Plan Agent 模板 - 执行阶段"""
    print("\n" + "="*60)
    print("测试 3: Plan Agent 模板 - 执行阶段")
    print("="*60)

    engine = SimplePromptEngine()

    plan = {
        "analysis": "分析公司财务需要三个步骤",
        "steps": [
            {
                "step": 1,
                "action": "读取Excel文件",
                "tool": "read_excel",
                "input": "finance_2023.xlsx",
                "expected_output": "财务数据"
            },
            {
                "step": 2,
                "action": "分析财务数据",
                "tool": "analyze_data",
                "input": "财务数据",
                "expected_output": "分析结果"
            },
            {
                "step": 3,
                "action": "生成报告",
                "tool": "generate_report",
                "input": "分析结果",
                "expected_output": "完整报告"
            }
        ]
    }

    history = [
        {"step": 1, "action": "读取Excel文件", "result": "成功读取到500行数据"},
        {"step": 2, "action": "分析财务数据", "result": "计算出收入增长率15%"}
    ]

    context = {
        "phase": "execution",
        "task": "帮我分析公司2023年的财务状况",
        "plan_json": json.dumps(plan, ensure_ascii=False, indent=4),
        "history": history,
        "current_step": 3,
        "current_step_info": plan["steps"][2]
    }

    result = engine.render("plan_agent", context)

    print(f"\n📋 渲染结果：")
    print("-" * 60)
    print(result[:1200])  # 只打印前1200字符
    print("-" * 60)

    print(f"\n🔍 变量替换检查：")
    checks = [
        ("{phase}" not in result, "phase"),
        ("{task}" not in result, "task"),
        ("{plan_json}" not in result, "plan_json"),
        ("{history}" not in result, "history"),
        ("{current_step}" not in result, "current_step"),
        ("{current_step_info}" not in result, "current_step_info"),
        ("步骤 1: 读取Excel文件" in result, "历史步骤1渲染"),
        ("步骤 2: 分析财务数据" in result, "历史步骤2渲染"),
        ("当前步骤（第 3 步）" in result, "当前步骤显示"),
    ]

    for check, name in checks:
        print(f"   {'✅' if check else '❌'} {name}")

    return all(c[0] for c in checks)

def test_plan_template_completion_phase():
    """测试 Plan Agent 模板 - 完成阶段"""
    print("\n" + "="*60)
    print("测试 4: Plan Agent 模板 - 完成阶段")
    print("="*60)

    engine = SimplePromptEngine()

    plan = {
        "analysis": "分析公司财务需要三个步骤",
        "steps": [
            {"step": 1, "action": "读取Excel文件", "tool": "read_excel"},
            {"step": 2, "action": "分析财务数据", "tool": "analyze_data"},
            {"step": 3, "action": "生成报告", "tool": "generate_report"}
        ]
    }

    history = [
        {"step": 1, "action": "读取Excel文件", "result": "成功读取到500行数据"},
        {"step": 2, "action": "分析财务数据", "result": "计算出收入增长率15%"},
        {"step": 3, "action": "生成报告", "result": "报告已生成"}
    ]

    context = {
        "phase": "completion",
        "task": "帮我分析公司2023年的财务状况",
        "plan_json": json.dumps(plan, ensure_ascii=False, indent=4),
        "history": history
    }

    result = engine.render("plan_agent", context)

    print(f"\n📋 渲染结果：")
    print("-" * 60)
    print(result[:1000])  # 只打印前1000字符
    print("-" * 60)

    print(f"\n🔍 变量替换检查：")
    checks = [
        ("{phase}" not in result, "phase"),
        ("{task}" not in result, "task"),
        ("{plan_json}" not in result, "plan_json"),
        ("{history}" not in result, "history"),
        ("步骤 1: 读取Excel文件" in result, "历史渲染"),
        ("最终答案" in result, "完成提示"),
    ]

    for check, name in checks:
        print(f"   {'✅' if check else '❌'} {name}")

    return all(c[0] for c in checks)

def test_react_template_complex():
    """测试 ReAct Agent 模板 - 复杂问题"""
    print("\n" + "="*60)
    print("测试 5: ReAct Agent 模板 - 复杂问题")
    print("="*60)

    engine = SimplePromptEngine()

    context = {
        "max_iterations": 5,
        "tools_description": "- search_knowledge: 搜索知识库\n  参数: query (搜索关键词)\n- calculator: 执行计算\n  参数: expression (数学表达式)",
        "history_section": "",
        "user_input": "请帮我计算 (125 + 347) * 12 的结果",
        "user_input_simple": False
    }

    result = engine.render("react_agent", context)

    print(f"\n📋 渲染结果：")
    print("-" * 60)
    print(result)
    print("-" * 60)

    print(f"\n🔍 变量替换检查：")
    checks = [
        ("{max_iterations}" not in result, "max_iterations"),
        ("{tools_description}" not in result, "tools_description"),
        ("{user_input}" not in result, "user_input"),
        ("{user_input_simple}" not in result, "user_input_simple"),
        ("125 + 347) * 12" in result, "用户输入内容"),
        ("只有当问题明确需要查询" in result, "复杂问题提示"),
        ("最多进行 5 轮思考" in result, "基本规则渲染"),
    ]

    for check, name in checks:
        print(f"   {'✅' if check else '❌'} {name}")

    return all(c[0] for c in checks)

def main():
    print("\n" + "="*60)
    print("🧪 Agent 模板测试")
    print("="*60)

    tests = [
        ("ReAct Agent 模板", test_react_template),
        ("Plan Agent - 规划阶段", test_plan_template_planning_phase),
        ("Plan Agent - 执行阶段", test_plan_template_execution_phase),
        ("Plan Agent - 完成阶段", test_plan_template_completion_phase),
        ("ReAct Agent - 复杂问题", test_react_template_complex),
    ]

    results = []

    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)

    for name, passed in results:
        print(f"   {'✅' if passed else '❌'} 通过: {name}")

    all_passed = all(p for _, p in results)

    print("\n" + "="*60)
    if all_passed:
        print("🎉 所有测试通过！")
    else:
        print("❌ 部分测试失败")
    print("="*60)

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
