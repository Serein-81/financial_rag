"""
统一Agent提示词加载器

提供智能的提示词加载、管理和渲染功能
支持配置缓存、热更新和变量替换
"""

import logging
import json
import re
import yaml
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

PROMPTS_ROOT = Path(__file__).parent
AGENTS_DIR = PROMPTS_ROOT / "agents"
SHARED_DIR = PROMPTS_ROOT / "shared"

GREETING_PROMPT = """# 问候语Agent系统提示词

## 角色定义
你是一个专业、友好的AI助手，专门负责处理用户的问候和闲聊。

## 核心职责
1. 友好地回应用户的问候
2. 识别用户的意图（问候、闲聊、寻求帮助）
3. 提供温暖的交互体验

## 回复原则
1. **温暖友好**：用亲切的语言回应
2. **简洁得体**：回复不宜过长，简洁明了
3. **积极引导**：自然地引导对话进入下一步

## 能力范围
- 问候语回应
- 闲聊互动
- 基本问题回答
- 引导用户说明需求

## 回复示例
- "您好！很高兴见到您。有什么我可以帮助您的吗？"
- "您好！我是您的财务系统智能助手，请问有什么需要帮助的？"
- "嗨！今天过得怎么样？需要我帮您做些什么吗？"

## 限制
- 不处理复杂的技术问题（转交专业Agent）
- 不做价值判断或敏感话题讨论
- 始终保持专业和友好的态度
"""


def load_greeting_prompt() -> str:
    """加载问候语提示词"""
    return GREETING_PROMPT


class AgentPromptLoader:
    """统一Agent提示词加载器（单例模式）"""

    _instance: Optional['AgentPromptLoader'] = None
    _config_cache: Dict[str, Dict[str, Any]] = {}
    _prompt_cache: Dict[str, str] = {}

    def __new__(cls) -> 'AgentPromptLoader':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.prompts_root = PROMPTS_ROOT
        self.agents_dir = AGENTS_DIR
        self.shared_dir = SHARED_DIR
        self._initialized = True

        logger.info("AgentPromptLoader initialized")
        logger.info(f"  - Prompts root: {self.prompts_root}")
        logger.info(f"  - Agents dir: {self.agents_dir}")

    def load_agent_config(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        加载Agent配置

        Args:
            agent_name: Agent名称

        Returns:
            Agent配置字典，失败返回None
        """
        cache_key = f"config:{agent_name}"
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]

        agent_dir = self.agents_dir / agent_name
        config_file = agent_dir / "agent.yaml"

        if not config_file.exists():
            logger.warning(f"Agent config not found: {config_file}")
            return None

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            self._config_cache[cache_key] = config
            return config

        except Exception as e:
            logger.error(f"Failed to load agent config {agent_name}: {e}")
            return None

    def load_system_prompt(self, agent_name: str) -> Optional[str]:
        """
        加载系统提示词

        Args:
            agent_name: Agent名称

        Returns:
            系统提示词文本，失败返回None
        """
        cache_key = f"prompt:{agent_name}"
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]

        config = self.load_agent_config(agent_name)
        if not config:
            return None

        prompt_file_name = self._get_system_prompt_file(config)
        agent_dir = self.agents_dir / agent_name
        prompt_file = agent_dir / prompt_file_name

        if not prompt_file.exists():
            logger.warning(f"System prompt not found: {prompt_file}")
            return None

        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt = f.read()

            prompt = self._append_configured_includes(prompt, config)

            self._prompt_cache[cache_key] = prompt
            return prompt

        except Exception as e:
            logger.error(f"Failed to load system prompt {agent_name}: {e}")
            return None

    def _append_configured_includes(self, prompt: str, config: Dict[str, Any]) -> str:
        includes = self._get_prompt_includes(config)
        if not includes:
            return prompt

        include_parts = []
        for include_name in includes:
            content = self.load_shared_component(str(include_name))
            if content:
                include_parts.append(content)

        if not include_parts:
            return prompt

        return "\n\n".join([prompt, *include_parts])

    def _get_prompt_includes(self, config: Dict[str, Any]) -> List[str]:
        includes = (
            config.get("agent", {})
            .get("prompts", {})
            .get("includes")
        )
        if includes is None:
            includes = config.get("prompt", {}).get("includes")

        if not includes:
            return []

        if isinstance(includes, str):
            return [includes]

        if isinstance(includes, list):
            return [str(item) for item in includes if item]

        logger.warning(f"Invalid prompt includes config: {includes}")
        return []

    def _get_system_prompt_file(self, config: Dict[str, Any]) -> str:
        """
        Resolve the configured system prompt file.

        Supported schemas:
        - agent.prompts.system: system.md
        - prompt.system_file: system.md

        The second form exists in several newer agent configs, so keeping both
        here makes the loader the compatibility boundary.
        """
        agent_prompt_file = (
            config.get("agent", {})
            .get("prompts", {})
            .get("system")
        )
        if agent_prompt_file:
            return str(agent_prompt_file)

        prompt_file = config.get("prompt", {}).get("system_file")
        if prompt_file:
            return str(prompt_file)

        return "system.md"

    def load_shared_component(self, component_name: str) -> Optional[str]:
        """
        加载共享组件

        Args:
            component_name: 组件名称（如 'common_rules', 'output_style'）

        Returns:
            组件内容，失败返回None
        """
        component_path = Path(component_name)
        if component_path.suffix:
            component_file = self.prompts_root / component_path
            if not component_file.exists():
                component_file = self.shared_dir / component_path.name
        else:
            component_file = self.shared_dir / f"{component_name}.yaml"

        if not component_file.exists() and not component_path.suffix:
            component_file = self.shared_dir / f"{component_name}.md"

        if not component_file.exists():
            logger.warning(f"Shared component not found: {component_name}")
            return None

        try:
            with open(component_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load shared component {component_name}: {e}")
            return None

    def render_prompt(
        self,
        agent_name: str,
        context: Dict[str, Any],
        use_cache: bool = True
    ) -> Optional[str]:
        """
        渲染提示词（替换变量）

        Args:
            agent_name: Agent名称
            context: 变量上下文
            use_cache: 是否使用缓存

        Returns:
            渲染后的提示词
        """
        cache_key = f"render:{agent_name}:{self._make_context_cache_key(context)}"

        if use_cache and cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]

        prompt = self.load_system_prompt(agent_name)
        if not prompt:
            return None

        try:
            rendered = self.render_text(prompt, context)

            if use_cache:
                self._prompt_cache[cache_key] = rendered

            return rendered

        except Exception as e:
            logger.error(f"Failed to render prompt {agent_name}: {e}")
            return prompt

    def render_text(self, template: str, context: Dict[str, Any]) -> str:
        """
        Render prompt variables without treating every brace as a template.

        This intentionally supports only identifier-style placeholders:
        {name}, {object.property}, {{ name }}, and {{ object.property }}.
        JSON examples such as {"field": "value"} are left unchanged.
        Unknown variables are also left unchanged so prompt files do not lose
        information when a caller provides a partial context.
        """
        if not template:
            return template

        double_brace_pattern = re.compile(
            r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*\}\}"
        )
        single_brace_pattern = re.compile(
            r"(?<!\{)\{\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*\}(?!\})"
        )

        def replace(match: re.Match) -> str:
            var_path = match.group(1)
            found, value = self._lookup_context_value(context, var_path)
            if not found:
                return match.group(0)
            return str(value)

        rendered = double_brace_pattern.sub(replace, template)
        rendered = single_brace_pattern.sub(replace, rendered)
        return rendered

    def _lookup_context_value(self, context: Dict[str, Any], var_path: str) -> tuple[bool, Any]:
        value: Any = context
        for key in var_path.split("."):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return False, None
        return True, "" if value is None else value

    def _make_context_cache_key(self, context: Dict[str, Any]) -> str:
        try:
            return json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)
        except TypeError:
            return repr(sorted((str(k), repr(v)) for k, v in context.items()))

    def get_available_agents(self) -> List[str]:
        """获取所有可用的Agent列表"""
        if not self.agents_dir.exists():
            return []

        agents = []
        for item in self.agents_dir.iterdir():
            if item.is_dir() and (item / "agent.yaml").exists():
                agents.append(item.name)

        return sorted(agents)

    def clear_cache(self):
        """清空所有缓存"""
        self._config_cache.clear()
        self._prompt_cache.clear()
        logger.info("Prompt cache cleared")

    def reload_agent(self, agent_name: str):
        """重新加载指定Agent的配置和提示词"""
        keys_to_remove = [k for k in self._config_cache if k.startswith(f"config:{agent_name}")]
        for key in keys_to_remove:
            del self._config_cache[key]

        keys_to_remove = [k for k in self._prompt_cache if k.startswith(f"prompt:{agent_name}")]
        for key in keys_to_remove:
            del self._prompt_cache[key]

        keys_to_remove = [k for k in self._prompt_cache if k.startswith(f"render:{agent_name}:")]
        for key in keys_to_remove:
            del self._prompt_cache[key]

        logger.info(f"Reloaded agent: {agent_name}")


_agent_prompt_loader: Optional[AgentPromptLoader] = None


def get_agent_prompt_loader() -> AgentPromptLoader:
    """获取全局提示词加载器实例"""
    global _agent_prompt_loader
    if _agent_prompt_loader is None:
        _agent_prompt_loader = AgentPromptLoader()
    return _agent_prompt_loader


def load_agent_prompt(agent_name: str) -> Optional[str]:
    """
    快捷函数：加载指定Agent的系统提示词

    Args:
        agent_name: Agent名称

    Returns:
        系统提示词文本
    """
    loader = get_agent_prompt_loader()
    return loader.load_system_prompt(agent_name)


def get_all_agents() -> List[str]:
    """获取所有可用的Agent列表"""
    loader = get_agent_prompt_loader()
    return loader.get_available_agents()


class PromptLoader:
    """
    简单的提示词加载器（向后兼容）
    
    功能与 AgentPromptLoader 相同，提供统一的加载接口
    """
    
    _cache: Dict[str, str] = {}
    
    def __init__(self, prompts_dir: Optional[Path] = None):
        if prompts_dir is None:
            self.prompts_dir = PROMPTS_ROOT
        else:
            self.prompts_dir = prompts_dir
    
    def load(self, file_path: str, use_cache: bool = True) -> str:
        """
        加载提示词文件
        
        Args:
            file_path: 相对于 prompts_dir 的路径
            use_cache: 是否使用缓存
            
        Returns:
            提示词内容
        """
        full_path = self.prompts_dir / file_path
        cache_key = str(full_path.resolve())
        
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]
        
        if not full_path.exists():
            raise FileNotFoundError(f"提示词文件不存在: {full_path}")
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if use_cache:
            self._cache[cache_key] = content
        
        return content
    
    def load_template(self, file_path: str, **kwargs) -> str:
        """
        加载提示词模板并替换占位符
        
        Args:
            file_path: 文件路径
            **kwargs: 替换参数
            
        Returns:
            格式化后的提示词
        """
        content = self.load(file_path)
        return AgentPromptLoader().render_text(content, kwargs)
    
    @classmethod
    def clear_cache(cls):
        """清空缓存"""
        cls._cache.clear()
    
    @classmethod
    def reload(cls, file_path: str, prompts_dir: Optional[Path] = None) -> str:
        """
        强制重新加载提示词（清除缓存）
        
        Args:
            file_path: 文件路径
            prompts_dir: 提示词目录
            
        Returns:
            重新加载的内容
        """
        if prompts_dir is None:
            prompts_dir = PROMPTS_ROOT
        full_path = prompts_dir / file_path
        cache_key = str(full_path.resolve())
        
        if cache_key in cls._cache:
            del cls._cache[cache_key]
        
        loader = PromptLoader(prompts_dir)
        return loader.load(file_path, use_cache=False)


def load_prompt_file(file_path: str, prompts_dir: Optional[Path] = None) -> str:
    """
    快捷函数：加载任意提示词文件
    
    Args:
        file_path: 相对于 PROMPTS_ROOT 的路径
        prompts_dir: 可选的提示词目录
        
    Returns:
        提示词内容
    """
    loader = PromptLoader(prompts_dir)
    return loader.load(file_path)


def load_prompt_template(file_path: str, prompts_dir: Optional[Path] = None, **kwargs) -> str:
    """
    快捷函数：加载并渲染提示词模板
    
    Args:
        file_path: 相对于 PROMPTS_ROOT 的路径
        prompts_dir: 可选的提示词目录
        **kwargs: 模板变量
        
    Returns:
        渲染后的提示词
    """
    loader = PromptLoader(prompts_dir)
    return loader.load_template(file_path, **kwargs)


AgentPromptRegistry = AgentPromptLoader


def get_prompt_registry() -> AgentPromptLoader:
    """
    获取提示词注册表（向后兼容）
    
    Returns:
        AgentPromptLoader 实例
    """
    return get_agent_prompt_loader()


def list_available_agents() -> List[str]:
    """列出所有可用的Agent（向后兼容）"""
    return get_all_agents()
