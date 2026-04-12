"""
智能体能力加载器
从配置文件动态加载能力描述，并注册到 CapabilityRegistry
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from .agent_capability_registry import (
    AgentCapabilityRegistry,
    AgentCapability,
    get_capability_registry
)

logger = logging.getLogger(__name__)


class CapabilityLoader:
    """
    能力配置加载器

    从 YAML 文件加载智能体能力配置，并注册到注册表

    使用示例：
        loader = CapabilityLoader()
        loader.load_from_file("config/agent_capabilities.yaml")
        loader.register_all(registry)
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self._config: Dict[str, Any] = {}

    def _get_default_config_path(self) -> Path:
        """获取默认配置文件路径"""
        base_dir = Path(__file__).parent
        return base_dir / "config" / "agent_capabilities.yaml"

    def load_from_file(self, path: Optional[str] = None) -> Dict[str, Any]:
        """
        从 YAML 文件加载配置

        Args:
            path: 配置文件路径，如果为 None 则使用默认路径

        Returns:
            解析后的配置字典
        """
        config_path = Path(path) if path else self.config_path

        if not config_path.exists():
            logger.warning(f"⚠️ [能力加载器] 配置文件不存在: {config_path}")
            return {}

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}

            logger.info(f"✅ [能力加载器] 已加载配置: {config_path}")
            return self._config

        except yaml.YAMLError as e:
            logger.error(f"❌ [能力加载器] YAML 解析失败: {e}")
            return {}
        except Exception as e:
            logger.error(f"❌ [能力加载器] 加载失败: {e}")
            return {}

    def load_from_dict(self, config: Dict[str, Any]) -> None:
        """
        从字典加载配置

        Args:
            config: 配置字典
        """
        self._config = config

    def create_agent_capability(self, agent_type: str, agent_config: Dict[str, Any]) -> AgentCapability:
        """
        根据配置创建 AgentCapability 对象

        Args:
            agent_type: 智能体类型 (finance, tax, legal, etc.)
            agent_config: 智能体配置

        Returns:
            AgentCapability 对象
        """
        domains = [d['name'] for d in agent_config.get('domains', [])]

        all_keywords = []
        keyword_weights = {}

        for kw in agent_config.get('keywords', {}).get('high_weight', []):
            all_keywords.append(kw)
            keyword_weights[kw.lower()] = 1.0

        for kw in agent_config.get('keywords', {}).get('medium_weight', []):
            all_keywords.append(kw)
            keyword_weights[kw.lower()] = 0.6

        patterns = agent_config.get('patterns', [])
        entities = agent_config.get('entities', [])

        capability = AgentCapability(
            agent_id=agent_config.get('agent_id', f'{agent_type}_default'),
            agent_name=agent_config.get('agent_name', agent_type),
            agent_type=agent_type,
            domains=domains,
            entities=entities,
            keywords=all_keywords,
            patterns=patterns,
            actions=[],
            confidence_threshold=agent_config.get('confidence_threshold', 0.7),
            max_concurrent_tasks=agent_config.get('max_concurrent_tasks', 5),
            avg_response_time=agent_config.get('avg_response_time', 2.0),
            priority=agent_config.get('priority', 5),
            enabled=agent_config.get('enabled', True),
            metadata={
                'keyword_weights': keyword_weights,
                'display_name': agent_config.get('agent_name'),
                'description': agent_config.get('description', '')
            }
        )

        return capability

    def register_all(self, registry: Optional[AgentCapabilityRegistry] = None) -> AgentCapabilityRegistry:
        """
        将所有配置的智能体能力注册到注册表

        Args:
            registry: 能力注册表，如果为 None 则使用全局单例

        Returns:
            注册后的注册表
        """
        if registry is None:
            registry = get_capability_registry()

        if not self._config:
            self.load_from_file()

        agents_config = self._config.get('agents', {})

        for agent_type, agent_config in agents_config.items():
            try:
                capability = self.create_agent_capability(agent_type, agent_config)
                registry.register(capability)
                logger.info(f"✅ [能力加载器] 已注册: {agent_type}")

            except Exception as e:
                logger.error(f"❌ [能力加载器] 注册 {agent_type} 失败: {e}")

        return registry

    def get_intent_mapping(self) -> Dict[str, str]:
        """
        获取意图到专家的映射配置

        Returns:
            {意图类型: 专家类型} 的映射字典
        """
        if not self._config:
            self.load_from_file()

        routing_config = self._config.get('routing', {})
        return routing_config.get('intent_to_specialist', {})

    def get_routing_config(self) -> Dict[str, Any]:
        """
        获取路由配置

        Returns:
            路由配置字典
        """
        if not self._config:
            self.load_from_file()

        return self._config.get('routing', {})


_global_loader: Optional[CapabilityLoader] = None


def get_capability_loader() -> CapabilityLoader:
    """获取全局能力加载器单例"""
    global _global_loader
    if _global_loader is None:
        _global_loader = CapabilityLoader()
    return _global_loader


def load_and_register_capabilities() -> AgentCapabilityRegistry:
    """
    便捷函数：加载并注册所有能力

    Returns:
        已注册的 CapabilityRegistry
    """
    loader = get_capability_loader()
    loader.load_from_file()
    return loader.register_all()
