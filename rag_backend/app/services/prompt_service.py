# app/services/prompt_service.py

"""
自定义提示词管理系统

核心功能：
1. 从文件加载模板
2. 变量替换 {variable_name}
3. 条件渲染 {% if condition %} ... {% endif %}
4. 列表渲染 {% for item in items %} ... {% endfor %}
5. 动态加载工具 Skills
6. 缓存优化
"""

import re
from typing import Dict, Any, Optional, List
from pathlib import Path


class PromptEngine:
    """
    提示词引擎 - 支持动态 Skills 加载
    
    使用示例：
        engine = PromptEngine()
        
        result = engine.render(
            template_name="agent_base",
            context={
                "role": "企业AI助手",
                "tools": [
                    {"name": "search_knowledge"},
                    {"name": "get_weather"}
                ],
                "user_level": "normal"
            },
            load_skills=True
        )
    """
    
    def __init__(self, templates_dir: Optional[str] = None, skills_dir: Optional[str] = None, prompts_root: Optional[str] = None, verbose: bool = False):
        """初始化提示词引擎"""
        import os
        verbose = verbose or os.environ.get("PROMPT_ENGINE_VERBOSE", "0") == "1"
        
        if templates_dir is None:
            current_dir = Path(__file__).parent.parent
            templates_dir = current_dir / "prompts" / "templates"
        
        if skills_dir is None:
            current_dir = Path(__file__).parent.parent
            skills_dir = current_dir / "prompts" / "skills"
        
        if prompts_root is None:
            current_dir = Path(__file__).parent.parent
            prompts_root = current_dir / "prompts"
        
        self.templates_dir = Path(templates_dir)
        self.skills_dir = Path(skills_dir)
        self.prompts_root = Path(prompts_root)
        self.templates_cache: Dict[str, str] = {}
        self.skills_cache: Dict[str, str] = {}
        self.root_prompts_cache: Dict[str, str] = {}
        
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        
        if verbose:
            print("📝 [PromptEngine] 初始化完成")
            print(f"   ├─ 模板目录: {self.templates_dir}")
            print(f"   ├─ Skills 目录: {self.skills_dir}")
            print(f"   └─ 根目录: {self.prompts_root}")
    
    def render(
        self, 
        template_name: str, 
        context: Dict[str, Any],
        use_cache: bool = True,
        load_skills: bool = True,
        include_shared: List[str] = None
    ) -> str:
        """
        渲染提示词模板
        
        Args:
            template_name: 模板名称（不含扩展名）
            context: 上下文变量字典
            use_cache: 是否使用缓存
            load_skills: 是否自动加载工具的 skill 文件
            include_shared: 需要加载的共享组件名称列表
        
        Returns:
            渲染后的提示词字符串
        """
        # 1. 加载模板
        template = self._load_template(template_name, use_cache)
        
        if not template:
            print(f"⚠️ [PromptEngine] 模板不存在: {template_name}")
            return ""
        
        # 2. 加载共享组件
        if include_shared:
            shared_parts = []
            for shared_name in include_shared:
                shared_content = self._load_shared_component(shared_name, use_cache)
                if shared_content:
                    shared_parts.append(shared_content)
                    print(f"✅ [PromptEngine] 已加载共享组件: {shared_name}")
            
            if shared_parts:
                template = template + "\n\n" + "\n\n".join(shared_parts)
        
        # 3. 动态加载 Skills
        if load_skills and "tools" in context:
            tools_list = context["tools"]
            
            if isinstance(tools_list, dict):
                tools_list = [{"name": name, **info} for name, info in tools_list.items()]
            elif isinstance(tools_list, list) and tools_list and isinstance(tools_list[0], str):
                tools_list = [{"name": tool} for tool in tools_list]
            
            skills_content = self._load_skills_for_tools(tools_list, use_cache)
            if skills_content:
                template = template + "\n\n" + skills_content
        
        # 4. 处理循环渲染
        template = self._process_for_loops(template, context)
        
        # 5. 处理条件渲染
        template = self._process_conditions(template, context)
        
        # 6. 替换变量
        template = self._replace_variables(template, context)
        
        # 7. 清理多余空行
        template = self._clean_whitespace(template)
        
        return template.strip()
    
    def _load_shared_component(self, component_name: str, use_cache: bool) -> str:
        """加载共享组件"""
        cache_key = f"shared:{component_name}"
        
        if use_cache and cache_key in self.skills_cache:
            return self.skills_cache[cache_key]
        
        shared_dir = self.prompts_root / "shared"
        component_path = shared_dir / f"{component_name}.yaml"
        
        if not component_path.exists():
            component_path = shared_dir / f"{component_name}.md"
        
        if not component_path.exists():
            print(f"⚠️ [PromptEngine] 共享组件不存在: {component_name}")
            return ""
        
        try:
            with open(component_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if use_cache:
                self.skills_cache[cache_key] = content
            
            return content
        
        except Exception as e:
            print(f"❌ [PromptEngine] 加载共享组件失败: {component_name} | 错误: {e}")
            return ""
    
    def _load_template(self, template_name: str, use_cache: bool) -> str:
        """从文件加载模板
        
        加载顺序：
        1. 优先从 agents/{template_name}/system.md 加载（结构化提示词）
        2. 回退到 templates/{template_name}.txt
        """
        # 检查缓存
        cache_key = f"agent:{template_name}"
        if use_cache and cache_key in self.templates_cache:
            return self.templates_cache[cache_key]
        
        # 1. 优先从 agents 目录加载
        agent_prompt_path = self.prompts_root / "agents" / template_name / "system.md"
        if agent_prompt_path.exists():
            try:
                with open(agent_prompt_path, 'r', encoding='utf-8') as f:
                    template = f.read()
                
                if use_cache:
                    self.templates_cache[cache_key] = template
                
                return template
            except Exception as e:
                print(f"❌ [PromptEngine] 加载Agent提示词失败: {template_name} | 错误: {e}")
        
        # 2. 回退到 templates 目录
        template_path = self.templates_dir / f"{template_name}.txt"
        
        if not template_path.exists():
            return ""
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            # 缓存模板
            if use_cache:
                self.templates_cache[cache_key] = template
            
            return template
        
        except Exception as e:
            print(f"❌ [PromptEngine] 加载模板失败: {template_name} | 错误: {e}")
            return ""
    
    def _process_for_loops(self, template: str, context: Dict) -> str:
        """
        处理循环渲染
        
        语法：{% for item in items %} ... {% endfor %}
        """
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
                else:
                    temp_context[item_name] = item
                
                rendered = self._replace_variables(loop_content, temp_context)
                result.append(rendered)
            
            return "\n".join(result)
        
        return re.sub(pattern, replace_loop, template, flags=re.DOTALL)
    
    def _process_conditions(self, template: str, context: Dict) -> str:
        """
        处理条件渲染
        
        语法：{% if condition %} ... {% elif ... %} ... {% else %} ... {% endif %}
        """
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
    
    def _evaluate_condition(self, condition: str, context: Dict) -> bool:
        """评估条件表达式"""
        # 处理 == 比较
        if "==" in condition:
            parts = condition.split("==")
            if len(parts) == 2:
                var_name = parts[0].strip()
                expected_value = parts[1].strip().strip('"').strip("'")
                actual_value = str(context.get(var_name, ""))
                return actual_value == expected_value
        
        # 处理 != 比较
        elif "!=" in condition:
            parts = condition.split("!=")
            if len(parts) == 2:
                var_name = parts[0].strip()
                expected_value = parts[1].strip().strip('"').strip("'")
                actual_value = str(context.get(var_name, ""))
                return actual_value != expected_value
        
        # 处理简单的存在性检查
        else:
            var_name = condition.strip()
            value = context.get(var_name)
            return bool(value)
        
        return False
    
    def _replace_variables(self, template: str, context: Dict) -> str:
        """
        替换变量
        
        支持：{variable_name} 和 {object.property}
        """
        pattern = r'\{([^}]+)\}'
        
        def replace_var(match):
            var_path = match.group(1).strip()
            
            # 处理嵌套属性（如 tool.name）
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
            
            # 简单变量
            else:
                value = context.get(var_path, "")
                return str(value)
        
        return re.sub(pattern, replace_var, template)
    
    def _clean_whitespace(self, text: str) -> str:
        """清理多余的空行和空白"""
        # 移除连续的空行
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # 移除行尾空白
        lines = [line.rstrip() for line in text.split('\n')]
        
        return '\n'.join(lines)
    
    def _load_skills_for_tools(self, tools: List[Dict], use_cache: bool) -> str:
        """为工具列表加载对应的 skill 文件"""
        skills_parts = []
        
        for tool in tools:
            tool_name = tool.get("name")
            if not tool_name:
                continue
            
            skill_content = self._load_skill(tool_name, use_cache)
            
            if skill_content:
                skills_parts.append(skill_content)
                print(f"✅ [PromptEngine] 已加载 Skill: {tool_name}")
            else:
                print(f"⚠️ [PromptEngine] Skill 文件不存在: {tool_name}.txt")
        
        if skills_parts:
            return "\n\n".join(skills_parts)
        
        return ""
    
    def _load_skill(self, tool_name: str, use_cache: bool) -> str:
        """加载单个工具的 skill 文件"""
        # 检查缓存
        if use_cache and tool_name in self.skills_cache:
            return self.skills_cache[tool_name]
        
        # 从文件加载
        skill_path = self.skills_dir / f"{tool_name}.txt"
        
        if not skill_path.exists():
            return ""
        
        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 缓存
            if use_cache:
                self.skills_cache[tool_name] = content
            
            return content
        
        except Exception as e:
            print(f"❌ [PromptEngine] 加载 Skill 失败: {tool_name} | 错误: {e}")
            return ""
    
    def reload_templates(self):
        """重新加载所有模板（清除缓存）"""
        self.templates_cache.clear()
        self.skills_cache.clear()
        self.root_prompts_cache.clear()
        print("🔄 [PromptEngine] 模板和 Skills 缓存已清除")
    
    def load_prompt(self, filename: str) -> str:
        """
        通用提示词加载函数（兼容简单版 prompt_loader.py）
        
        Args:
            filename: 提示词文件名（如 "agent_system.txt"）
        
        Returns:
            提示词内容字符串
        
        Raises:
            FileNotFoundError: 如果文件不存在
        """
        if filename in self.root_prompts_cache:
            return self.root_prompts_cache[filename]
        
        filepath = self.prompts_root / filename
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
            
            self.root_prompts_cache[filename] = content
            return content
        except FileNotFoundError:
            raise FileNotFoundError(
                f"❌ 提示词文件未找到: {filepath}。"
                f"请检查文件是否存在！"
            )
    
    def load_agent_system_prompt(self) -> str:
        """
        专门用于加载 Agent 核心系统提示词（兼容简单版）
        
        Returns:
            Agent 系统提示词内容
        """
        return self.load_prompt("agent_system.txt")
    
    def list_skills(self) -> List[str]:
        """列出所有可用的 skills"""
        if not self.skills_dir.exists():
            return []
        
        skills = []
        for file_path in self.skills_dir.glob("*.txt"):
            skills.append(file_path.stem)
        
        return sorted(skills)
    
    def create_skill(self, tool_name: str, content: str):
        """创建新的 skill 文件"""
        skill_path = self.skills_dir / f"{tool_name}.txt"
        
        try:
            with open(skill_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ [PromptEngine] 已创建 Skill: {tool_name}.txt")
            
            # 清除缓存
            self.skills_cache.pop(tool_name, None)
        
        except Exception as e:
            print(f"❌ [PromptEngine] 创建 Skill 失败: {tool_name} | 错误: {e}")


# 全局单例
prompt_engine = PromptEngine()


# 便捷函数
def render_prompt(template_name: str, **kwargs) -> str:
    """便捷的提示词渲染函数"""
    return prompt_engine.render(template_name, kwargs)


def reload_prompts():
    """重新加载所有提示词模板"""
    prompt_engine.reload_templates()


def load_prompt(filename: str) -> str:
    """
    通用提示词加载函数（兼容简单版 prompt_loader.py）
    
    Args:
        filename: 提示词文件名（如 "agent_system.txt"）
    
    Returns:
        提示词内容字符串
    """
    return prompt_engine.load_prompt(filename)


def load_agent_system_prompt() -> str:
    """
    专门用于加载 Agent 核心系统提示词（兼容简单版）
    
    Returns:
        Agent 系统提示词内容
    """
    return prompt_engine.load_agent_system_prompt()
