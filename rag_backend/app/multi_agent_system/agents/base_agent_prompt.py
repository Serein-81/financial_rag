"""
智能体提示词基类
统一管理所有智能体的提示词加载
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseAgentPromptLoader(ABC):
    """
    智能体提示词加载器基类
    
    提供统一的提示词加载机制：
    1. 优先从外部文件加载提示词
    2. 降级到硬编码提示词
    3. 支持运行时热更新
    
    子类需要：
    1. 定义 PROMPT_FILENAME 类属性
    2. 实现 get_prompt_context() 方法提供渲染上下文
    """
    
    PROMPT_FILENAME: str = ""
    PROMPT_DIR: Path = Path(__file__).parent.parent.parent / "prompts" / "system"
    
    _prompt_cache: Dict[str, str] = {}
    _use_cache: bool = True
    
    def __init__(self):
        self._system_prompt: Optional[str] = None
        self._load_prompt()
    
    def _load_prompt(self):
        """加载提示词"""
        self._system_prompt = self._load_system_prompt()
    
    def _get_prompt_filename(self) -> str:
        """获取提示词文件名（可被子类覆盖）"""
        return self.PROMPT_FILENAME
    
    def _load_system_prompt(self) -> str:
        """
        加载系统提示词
        
        优先级：
        1. 环境变量指定的路径
        2. prompts/system/{agent_name}.md
        3. 降级到 _get_fallback_prompt()
        """
        prompt_filename = self._get_prompt_filename()
        
        if not prompt_filename:
            logger.warning(f"⚠️ [{self.__class__.__name__}] 未指定提示词文件名")
            return self._get_fallback_prompt()
        
        env_path = os.environ.get(f"PROMPT_{self.__class__.__name__.upper()}")
        if env_path:
            try:
                return self._load_from_path(Path(env_path))
            except FileNotFoundError:
                logger.warning(f"⚠️ 环境变量路径不存在: {env_path}")
        
        default_path = self.PROMPT_DIR / prompt_filename
        
        try:
            return self._load_from_path(default_path)
        except FileNotFoundError:
            logger.warning(f"⚠️ [{self.__class__.__name__}] 提示词文件不存在: {default_path}")
            return self._get_fallback_prompt()
    
    def _load_from_path(self, path: Path) -> str:
        """从指定路径加载提示词"""
        if self._use_cache and str(path) in self._prompt_cache:
            return self._prompt_cache[str(path)]
        
        if not path.exists():
            raise FileNotFoundError(f"提示词文件不存在: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if self._use_cache:
            self._prompt_cache[str(path)] = content
        
        return content
    
    def _get_fallback_prompt(self) -> str:
        """
        获取降级提示词（子类必须实现）
        
        当外部文件不存在时使用
        """
        return self._build_default_prompt()
    
    def _build_default_prompt(self) -> str:
        """
        构建默认提示词（子类应该重写此方法）
        
        Returns:
            默认提示词内容
        """
        return """你是一个智能助手。"""
    
    @abstractmethod
    def get_prompt_context(self) -> Dict[str, Any]:
        """
        获取提示词渲染上下文（子类必须实现）
        
        Returns:
            包含模板变量的字典
        """
        pass
    
    def get_system_prompt(self) -> str:
        """
        获取系统提示词
        
        Returns:
            系统提示词内容
        """
        if self._system_prompt is None:
            self._load_prompt()
        
        return self._render_prompt(self._system_prompt)
    
    def _render_prompt(self, template: str) -> str:
        """
        渲染提示词模板
        
        Args:
            template: 模板字符串
            
        Returns:
            渲染后的提示词
        """
        context = self.get_prompt_context()
        
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            if placeholder in template:
                if isinstance(value, (list, dict)):
                    import json
                    template = template.replace(placeholder, json.dumps(value, ensure_ascii=False, indent=2))
                else:
                    template = template.replace(placeholder, str(value))
        
        return template
    
    def reload_prompt(self):
        """重新加载提示词（热更新）"""
        cache_key = str(self.PROMPT_DIR / self._get_prompt_filename())
        if cache_key in self._prompt_cache:
            del self._prompt_cache[cache_key]
        
        self._load_prompt()
        logger.info(f"🔄 [{self.__class__.__name__}] 提示词已重新加载")
    
    @classmethod
    def clear_cache(cls):
        """清空所有缓存"""
        cls._prompt_cache.clear()
        logger.info("🗑️ 提示词缓存已清空")
    
    @classmethod
    def set_cache_enabled(cls, enabled: bool):
        """设置是否启用缓存"""
        cls._use_cache = enabled


def load_agent_prompt(
    agent_name: str,
    filename: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    通用提示词加载函数
    
    Args:
        agent_name: 智能体名称
        filename: 提示词文件名（默认为 {agent_name}_agent.md）
        context: 渲染上下文
        
    Returns:
        提示词内容
    """
    if filename is None:
        filename = f"{agent_name}_agent.md"
    
    prompt_dir = Path(__file__).parent.parent.parent / "prompts" / "system"
    prompt_path = prompt_dir / filename
    
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        logger.warning(f"⚠️ 提示词文件不存在: {prompt_path}")
        return ""
    
    if context:
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            if placeholder in content:
                if isinstance(value, (list, dict)):
                    import json
                    content = content.replace(placeholder, json.dumps(value, ensure_ascii=False, indent=2))
                else:
                    content = content.replace(placeholder, str(value))
    
    return content
