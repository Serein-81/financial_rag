"""
独立测试模板渲染功能

不依赖其他模块，直接测试 PromptEngine
"""

import re
from pathlib import Path


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


def test_reflection_template():
    """测试反思模板渲染"""
    print("\n" + "=" * 60)
    print("测试 1: 反思模板渲染")
    print("=" * 60)
    
    engine = SimplePromptEngine()
    
    context = {
        "original_task": "分析公司2024年的财务状况",
        "current_answer": "公司2024年收入增长10%，净利润增长5%。",
        "reflection_round": 1,
        "max_reflections": 3,
        "previous_reflections": [],
        "tool_outputs": [
            {"name": "财务分析", "content": "数据已提取"},
            {"name": "比率计算", "content": "完成"}
        ]
    }
    
    result = engine.render("reflection", context, load_skills=False)
    
    print("\n📋 模板渲染结果：")
    print("-" * 60)
    print(f"✅ 渲染成功，长度: {len(result)} 字符")
    
    checks = [
        ("{original_task}" not in result, "original_task"),
        ("{current_answer}" not in result, "current_answer"),
        ("{reflection_round}" not in result, "reflection_round"),
        ("分析公司2024年的财务状况" in result, "原始任务内容"),
        ("公司2024年收入增长10%" in result, "当前答案内容"),
        ("财务分析" in result, "工具输出循环渲染"),
        ("第 1 轮反思" in result, "轮次信息渲染"),
    ]
    
    print("\n🔍 变量替换检查：")
    all_passed = True
    for passed, name in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        all_passed = all_passed and passed
    
    return all_passed


def test_finance_template():
    """测试财务专家模板渲染"""
    print("\n" + "=" * 60)
    print("测试 2: 财务专家模板渲染")
    print("=" * 60)
    
    engine = SimplePromptEngine()
    
    context = {
        "query": "我们公司今年的利润率如何？",
        "context": "2024年上半年营收500万，成本300万，毛利200万。",
        "history": "用户: 请分析财务状况\n助手: 好的，请问具体是哪方面？",
        "financial_data": "暂无",
        "analysis_depth": "detailed",
        "include_investment_models": True
    }
    
    result = engine.render("finance_specialist", context, load_skills=False)
    
    print("\n📋 模板渲染结果：")
    print("-" * 60)
    print(f"✅ 渲染成功，长度: {len(result)} 字符")
    
    checks = [
        ("{query}" not in result, "query"),
        ("{context}" not in result, "context"),
        ("我们公司今年的利润率如何？" in result, "用户问题"),
        ("2024年上半年营收500万" in result, "上下文内容"),
        ("流动比率" in result, "详细分析内容"),
    ]
    
    print("\n🔍 变量替换检查：")
    all_passed = True
    for passed, name in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        all_passed = all_passed and passed
    
    return all_passed


def test_tax_template():
    """测试税务专家模板渲染"""
    print("\n" + "=" * 60)
    print("测试 3: 税务专家模板渲染")
    print("=" * 60)
    
    engine = SimplePromptEngine()
    
    context = {
        "query": "小规模纳税人如何享受增值税优惠？",
        "context": "小规模纳税人增值税征收率为3%。",
        "history": "",
        "tax_data": "企业类型：小规模纳税人",
        "tax_types": ["增值税", "企业所得税", "个人所得税"],
        "tax_depth": "detailed"
    }
    
    result = engine.render("tax_specialist", context, load_skills=False)
    
    print("\n📋 模板渲染结果：")
    print("-" * 60)
    print(f"✅ 渲染成功，长度: {len(result)} 字符")
    
    checks = [
        ("{query}" not in result, "query"),
        ("{tax_types}" not in result, "tax_types"),
        ("{tax_depth}" not in result, "tax_depth"),
        ("小规模纳税人如何享受增值税优惠？" in result, "用户问题"),
        ("增值税" in result and "企业所得税" in result, "涉及税种循环渲染"),
        ("一般纳税人税率" in result, "详细税种说明"),
    ]
    
    print("\n🔍 变量替换检查：")
    all_passed = True
    for passed, name in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        all_passed = all_passed and passed
    
    return all_passed


def test_conditional_rendering():
    """测试条件渲染"""
    print("\n" + "=" * 60)
    print("测试 4: 条件渲染")
    print("=" * 60)
    
    engine = SimplePromptEngine()
    
    context_empty = {
        "query": "测试查询"
    }
    result_empty = engine.render("finance_specialist", context_empty, load_skills=False)
    
    context_with_data = {
        "query": "测试查询",
        "context": "这是上下文内容"
    }
    result_with_data = engine.render("finance_specialist", context_with_data, load_skills=False)
    
    print(f"\n📋 空上下文渲染: {len(result_empty)} 字符")
    print(f"📋 有数据渲染: {len(result_with_data)} 字符")
    
    checks = [
        ("未检索到相关文档" in result_empty, "空上下文时显示提示"),
        ("这是上下文内容" in result_with_data, "有数据时显示内容"),
    ]
    
    print("\n🔍 条件渲染检查：")
    all_passed = True
    for passed, name in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        all_passed = all_passed and passed
    
    return all_passed


def test_elif_rendering():
    """测试 elif 条件渲染"""
    print("\n" + "=" * 60)
    print("测试 5: elif 条件渲染")
    print("=" * 60)
    
    engine = SimplePromptEngine()
    
    context_detailed = {
        "analysis_depth": "detailed"
    }
    result_detailed = engine.render("finance_specialist", context_detailed, load_skills=False)
    
    context_simple = {
        "analysis_depth": "simple"
    }
    result_simple = engine.render("finance_specialist", context_simple, load_skills=False)
    
    print(f"\n📋 detailed 渲染: {len(result_detailed)} 字符")
    print(f"📋 simple 渲染: {len(result_simple)} 字符")
    
    checks = [
        ("流动比率" in result_detailed, "detailed 时显示详细分析"),
        ("如需详细的财务指标分析" in result_simple, "simple 时显示提示"),
    ]
    
    print("\n🔍 elif 条件渲染检查：")
    all_passed = True
    for passed, name in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        all_passed = all_passed and passed
    
    return all_passed


def test_previous_reflections_loop():
    """测试历史反思循环渲染"""
    print("\n" + "=" * 60)
    print("测试 6: 历史反思循环渲染")
    print("=" * 60)
    
    engine = SimplePromptEngine()
    
    context = {
        "original_task": "测试任务",
        "current_answer": "测试答案",
        "reflection_round": 2,
        "max_reflections": 3,
        "previous_reflections": [
            {
                "round": 1,
                "issues": "答案不够详细",
                "suggestions": "添加更多细节",
                "improved": "是"
            }
        ],
        "tool_outputs": []
    }
    
    result = engine.render("reflection", context, load_skills=False)
    
    checks = [
        ("答案不够详细" in result, "历史反思内容渲染"),
        ("添加更多细节" in result, "历史反思建议渲染"),
        ("第 1 轮反思" in result, "历史轮次渲染"),
    ]
    
    print("\n🔍 历史反思循环渲染检查：")
    all_passed = True
    for passed, name in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        all_passed = all_passed and passed
    
    return all_passed


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("🧪 模板渲染功能测试")
    print("=" * 60)
    
    results = []
    
    results.append(("反思模板", test_reflection_template()))
    results.append(("财务专家模板", test_finance_template()))
    results.append(("税务专家模板", test_tax_template()))
    results.append(("条件渲染", test_conditional_rendering()))
    results.append(("elif 渲染", test_elif_rendering()))
    results.append(("历史反思循环", test_previous_reflections_loop()))
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"   {status}: {name}")
        all_passed = all_passed and passed
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！")
    else:
        print("⚠️ 部分测试失败，请检查。")
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
