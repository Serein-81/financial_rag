"""
智能体提示词基类
统一管理所有智能体的提示词加载

注意：TriageSpecialist 和 ReflectionSpecialist 已迁移到 llm_functions 模块
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


def _normalize_agent_name(agent_name: str) -> str:
    """
    标准化agent名称到目录名
    
    映射规则：
    - "FinanceSpecialist" -> "finance"
    - "TaxSpecialist" -> "tax"
    - "LegalSpecialist" -> "legal"
    - "IntentRouterAgent" -> "intent_router"
    - "ReportGenerator" -> "report"
    - "PolicyNotificationAgent" -> "policy_notification"
    - "ReActAgent" -> "react"
    - 其他 -> 转小写
    
    提示词目录结构：
    - agents/finance/       - 金融专家
    - agents/tax/          - 税务专家
    - agents/legal/         - 法律专家
    - agents/intent_router/ - 意图路由
    - agents/report/       - 报告生成
    - agents/policy_notification/ - 政策通知
    - agents/react/        - ReAct推理
    - agents/output/       - 输出处理
    - agents/plan/         - 计划制定
    - agents/policy/       - 政策专家
    """
    name_mapping = {
        "financespecialist": "finance",
        "taxspecialist": "tax",
        "legalspecialist": "legal",
        "intentrouteragent": "intent_router",
        "reportgenerator": "report",
        "policynotificationagent": "policy_notification",
        "reactagent": "react",
        "planagent": "plan",
        "outputagent": "output",
        "policyspecialist": "policy",
    }
    
    normalized = agent_name.lower().replace("_", "").replace("-", "")
    return name_mapping.get(normalized, agent_name.lower())


class BaseAgentPromptLoader(ABC):
    """
    智能体提示词加载器基类
    
    提供统一的提示词加载机制：
    1. 优先从外部文件加载提示词
    2. 降级到硬编码提示词
    3. 支持运行时热更新
    4. 支持新的统一目录结构
    
    子类需要：
    1. 定义 PROMPT_FILENAME 类属性
    2. 实现 get_prompt_context() 方法提供渲染上下文
    """
    
    PROMPT_FILENAME: str = ""
    PROMPT_DIR: Path = Path(__file__).parent.parent.parent / "prompts" / "agents"
    
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
    
    def _get_agent_name(self) -> str:
        """获取Agent名称（用于加载对应的提示词）"""
        class_name = self.__class__.__name__
        return _normalize_agent_name(class_name)
    
    def _load_system_prompt(self) -> str:
        """
        加载系统提示词
        
        加载顺序（优先级从高到低）：
        1. 环境变量指定的路径
        2. 从统一加载器加载（app/prompts/loader.py）
        3. prompts/agents/{agent_name}/system.md（新结构）
        4. 降级到 _get_fallback_prompt()
        """
        prompt_filename = self._get_prompt_filename()
        
        if not prompt_filename:
            logger.debug(f"[{self.__class__.__name__}] 未指定提示词文件名，尝试从统一加载器加载")
            return self._load_from_unified_loader()
        
        env_path = os.environ.get(f"PROMPT_{self.__class__.__name__.upper()}")
        if env_path:
            try:
                return self._load_from_path(Path(env_path))
            except FileNotFoundError:
                logger.warning(f"⚠️ 环境变量路径不存在: {env_path}")
        
        agent_name = self._get_agent_name()
        logger.debug(f"[{self.__class__.__name__}] 映射后的Agent名称: {agent_name}")
        
        unified_prompt = self._load_from_unified_loader()
        if unified_prompt:
            logger.info(f"✅ 成功从统一加载器加载提示词: {agent_name}")
            return unified_prompt
        
        prompts_root = Path(__file__).parent.parent.parent / "prompts"
        new_path = prompts_root / "agents" / agent_name / "system.md"
        try:
            content = self._load_from_path(new_path)
            logger.info(f"✅ 成功加载提示词（新结构）: {new_path}")
            return content
        except FileNotFoundError:
            logger.debug(f"[{self.__class__.__name__}] 提示词文件不存在，启用内置默认提示词")
            return self._get_fallback_prompt()
    
    def _load_from_unified_loader(self) -> str:
        """从统一加载器加载提示词"""
        try:
            from app.prompts.loader import load_agent_prompt
            agent_name = self._get_agent_name()
            prompt = load_agent_prompt(agent_name)
            if prompt:
                return prompt
        except Exception as e:
            logger.debug(f"[{self.__class__.__name__}] 统一加载器加载失败: {e}")
        return ""
    
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
            渲染后的字符串
        """
        context = self.get_prompt_context()
        
        import re
        
        def replace_match(match):
            var_path = match.group(1)
            keys = var_path.split('.')
            value = context
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key, match.group(0))
                else:
                    return match.group(0)
            return str(value) if value is not None else match.group(0)
        
        pattern = r'\{([^}]+)\}'
        rendered = re.sub(pattern, replace_match, template)
        
        return rendered
    
    def reload_prompt(self):
        """重新加载提示词"""
        self._prompt_cache.clear()
        self._load_prompt()
        logger.info(f"✅ 提示词已重新加载: {self.__class__.__name__}")


def load_agent_prompt(
    agent_name: str,
    filename: str = "system.md",
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    加载Agent提示词的便捷函数
    
    Args:
        agent_name: Agent名称（会进行标准化）
        filename: 提示词文件名（默认system.md）
        context: 渲染上下文
        
    Returns:
        提示词内容
    """
    from app.prompts.loader import load_agent_prompt as unified_load
    
    normalized_name = _normalize_agent_name(agent_name)
    prompt = unified_load(normalized_name)
    
    if context and prompt:
        import re
        
        def replace_match(match):
            var_path = match.group(1)
            keys = var_path.split('.')
            value = context
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key, match.group(0))
                else:
                    return match.group(0)
            return str(value) if value is not None else match.group(0)
        
        pattern = r'\{([^}]+)\}'
        prompt = re.sub(pattern, replace_match, prompt)
    
    return prompt
