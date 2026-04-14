"""
结构化提示词注册表

支持新的 agents/ 目录结构，同时保持向后兼容。
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml
import logging

logger = logging.getLogger(__name__)


class AgentPromptRegistry:
    """
    智能体提示词注册表
    
    管理所有智能体的提示词配置和文件。
    支持新的结构化格式和向后兼容。
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls, prompts_root: Optional[str] = None):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, prompts_root: Optional[str] = None):
        """初始化注册表"""
        if AgentPromptRegistry._initialized:
            return
        
        if prompts_root is None:
            prompts_root = Path(__file__).parent
        
        self.prompts_root = Path(prompts_root)
        self.agents_dir = self.prompts_root / "agents"
        self.templates_dir = self.prompts_root / "templates"
        
        self._configs: Dict[str, Dict] = {}
        self._config_cache: Dict[str, Dict] = {}
        
        AgentPromptRegistry._initialized = True
        self._load_all_configs()
    
    def _load_all_configs(self):
        """加载所有智能体的配置文件"""
        if not self.agents_dir.exists():
            logger.warning(f"agents 目录不存在: {self.agents_dir}")
            return
        
        for agent_dir in self.agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue
            
            config_file = agent_dir / "agent.yaml"
            if config_file.exists():
                agent_name = agent_dir.name
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                    
                    self._configs[agent_name] = config
                    self._config_cache[agent_name] = config
                    logger.info(f"✅ 已加载智能体配置: {agent_name}")
                
                except Exception as e:
                    logger.error(f"❌ 加载智能体配置失败: {agent_name} | 错误: {e}")
    
    def get_agent(self, agent_name: str) -> Optional[Dict]:
        """
        获取智能体配置
        
        Args:
            agent_name: 智能体名称
        
        Returns:
            智能体配置字典，如果不存在返回 None
        """
        if agent_name in self._configs:
            return self._configs[agent_name]
        
        # 尝试从缓存加载
        config_file = self.agents_dir / agent_name / "agent.yaml"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                self._configs[agent_name] = config
                return config
            except Exception as e:
                logger.error(f"❌ 重新加载配置失败: {agent_name} | 错误: {e}")
        
        return None
    
    def get_prompt_path(self, agent_name: str) -> Optional[Path]:
        """
        获取智能体系统提示词文件路径
        
        Args:
            agent_name: 智能体名称
        
        Returns:
            系统提示词文件路径，如果不存在返回 None
        """
        agent_dir = self.agents_dir / agent_name
        
        if not agent_dir.exists():
            return None
        
        config = self.get_agent(agent_name)
        if config and 'prompt' in config:
            system_file = config['prompt'].get('system_file', 'system.md')
            prompt_path = agent_dir / system_file
            
            if prompt_path.exists():
                return prompt_path
        
        # 默认路径
        default_path = agent_dir / "system.md"
        if default_path.exists():
            return default_path
        
        return None
    
    def get_fallback_path(self, agent_name: str) -> Optional[Path]:
        """
        获取回退文件路径（向后兼容）
        
        Args:
            agent_name: 智能体名称
        
        Returns:
            回退文件路径，如果不存在返回 None
        """
        config = self.get_agent(agent_name)
        if not config:
            return None
        
        # 检查兼容性配置
        compat_config = config.get('compatibility_mode', {})
        if compat_config.get('enabled'):
            fallback_file = compat_config.get('fallback_file')
            if fallback_file:
                fallback_path = self.prompts_root / fallback_file
                if fallback_path.exists():
                    return fallback_path
        
        # 检查 prompt 配置中的 fallback
        prompt_config = config.get('prompt', {})
        fallback_file = prompt_config.get('fallback_file')
        if fallback_file:
            fallback_path = self.prompts_root / fallback_file
            if fallback_path.exists():
                return fallback_path
        
        return None
    
    def load_system_prompt(self, agent_name: str) -> Optional[str]:
        """
        加载智能体系统提示词
        
        优先级：
        1. agents/{agent_name}/system.md (新结构)
        2. agents/{agent_name}/agent.yaml 指定的 fallback_file (向后兼容)
        3. templates/{agent_name}.txt (旧结构)
        
        Args:
            agent_name: 智能体名称
        
        Returns:
            系统提示词内容，如果不存在返回 None
        """
        # 尝试新结构
        prompt_path = self.get_prompt_path(agent_name)
        if prompt_path:
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"❌ 加载提示词失败: {agent_name} | 错误: {e}")
        
        # 尝试回退
        fallback_path = self.get_fallback_path(agent_name)
        if fallback_path:
            try:
                with open(fallback_path, 'r', encoding='utf-8') as f:
                    logger.info(f"📝 使用回退文件: {fallback_path}")
                    return f.read()
            except Exception as e:
                logger.error(f"❌ 加载回退提示词失败: {agent_name} | 错误: {e}")
        
        # 尝试旧结构作为最后手段
        old_path = self.templates_dir / f"{agent_name}.txt"
        if old_path.exists():
            try:
                with open(old_path, 'r', encoding='utf-8') as f:
                    logger.info(f"📝 使用旧模板文件: {old_path}")
                    return f.read()
            except Exception as e:
                logger.error(f"❌ 加载旧模板失败: {agent_name} | 错误: {e}")
        
        logger.debug(f"未找到提示词: {agent_name}")
        return None
    
    def list_agents(self) -> List[str]:
        """
        列出所有已注册的智能体
        
        Returns:
            智能体名称列表
        """
        return sorted(self._configs.keys())
    
    def agent_exists(self, agent_name: str) -> bool:
        """
        检查智能体是否存在
        
        Args:
            agent_name: 智能体名称
        
        Returns:
            如果存在返回 True
        """
        return agent_name in self._configs or (self.agents_dir / agent_name).exists()
    
    def get_agent_metadata(self, agent_name: str) -> Optional[Dict]:
        """
        获取智能体元数据
        
        Args:
            agent_name: 智能体名称
        
        Returns:
            元数据字典
        """
        config = self.get_agent(agent_name)
        if config:
            return config.get('metadata', {})
        return None
    
    def reload(self):
        """重新加载所有配置"""
        self._configs.clear()
        self._load_all_configs()
        logger.info("🔄 提示词注册表已重新加载")


class StructuredPromptEngine:
    """
    结构化提示词引擎
    
    在 AgentPromptRegistry 基础上提供提示词渲染功能。
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls, prompts_root: Optional[str] = None):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, prompts_root: Optional[str] = None):
        """初始化引擎"""
        if StructuredPromptEngine._initialized:
            return
        self.registry = AgentPromptRegistry(prompts_root)
        StructuredPromptEngine._initialized = True
    
    def render(
        self,
        agent_name: str,
        context: Dict[str, Any],
        use_cache: bool = True
    ) -> str:
        """
        渲染智能体提示词
        
        Args:
            agent_name: 智能体名称
            context: 渲染上下文
            use_cache: 是否使用缓存
        
        Returns:
            渲染后的提示词
        """
        from app.services.prompt_service import PromptEngine
        
        # 获取系统提示词
        system_prompt = self.registry.load_system_prompt(agent_name)
        
        if not system_prompt:
            logger.debug(f"未找到提示词模板: {agent_name}")
            return ""
        
        # 使用现有的 PromptEngine 进行渲染
        engine = PromptEngine()
        return engine.render(
            template_name=agent_name,
            context=context,
            use_cache=use_cache,
            load_skills=False
        )
    
    def get_agent_config(self, agent_name: str) -> Optional[Dict]:
        """获取智能体配置"""
        return self.registry.get_agent(agent_name)
    
    def list_available_agents(self) -> List[str]:
        """列出所有可用的智能体"""
        return self.registry.list_agents()


def get_prompt_registry() -> AgentPromptRegistry:
    """获取提示词注册表单例"""
    return AgentPromptRegistry()


def get_structured_prompt_engine() -> StructuredPromptEngine:
    """获取结构化提示词引擎单例"""
    return StructuredPromptEngine()


# 便捷函数
def load_agent_prompt(agent_name: str) -> Optional[str]:
    """加载智能体提示词"""
    return get_prompt_registry().load_system_prompt(agent_name)


def list_available_agents() -> List[str]:
    """列出所有可用的智能体"""
    return get_prompt_registry().list_agents()
