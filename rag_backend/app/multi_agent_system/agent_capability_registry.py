"""
智能体能力注册表 (Agent Capability Registry)
智能体的能力元数据中心，支持智能路由和能力匹配
"""

from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CapabilityType(str, Enum):
    """能力类型"""
    DOMAIN = "domain"           # 领域能力
    ENTITY = "entity"           # 实体识别能力
    ACTION = "action"          # 行动能力
    KEYWORD = "keyword"         # 关键词匹配
    PATTERN = "pattern"         # 模式匹配


@dataclass
class CapabilitySpec:
    """能力规范"""
    capability_type: CapabilityType
    name: str
    weight: float = 1.0        # 匹配权重
    description: str = ""
    examples: List[str] = field(default_factory=list)


@dataclass
class AgentCapability:
    """
    智能体能力描述
    
    包含智能体的所有能力信息，用于智能路由匹配
    """
    agent_id: str
    agent_name: str
    agent_type: str            # finance, tax, legal, etc.
    domains: List[str] = field(default_factory=list)          # 专业领域
    entities: List[str] = field(default_factory=list)        # 可识别的实体类型
    keywords: List[str] = field(default_factory=list)        # 关键词列表
    patterns: List[str] = field(default_factory=list)        # 匹配模式
    actions: List[str] = field(default_factory=list)         # 可执行的操作
    confidence_threshold: float = 0.7
    max_concurrent_tasks: int = 5
    avg_response_time: float = 2.0     # 平均响应时间（秒）
    priority: int = 1                  # 优先级（数字越小优先级越高）
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_capabilities(self) -> List[CapabilitySpec]:
        """获取所有能力规范"""
        capabilities = []
        
        for domain in self.domains:
            capabilities.append(CapabilitySpec(
                capability_type=CapabilityType.DOMAIN,
                name=domain,
                weight=1.0,
                description=f"{self.agent_name} 的专业领域"
            ))
        
        for entity in self.entities:
            capabilities.append(CapabilitySpec(
                capability_type=CapabilityType.ENTITY,
                name=entity,
                weight=0.8,
                description=f"{self.agent_name} 可识别的实体"
            ))
        
        for keyword in self.keywords:
            capabilities.append(CapabilitySpec(
                capability_type=CapabilityType.KEYWORD,
                name=keyword,
                weight=0.6,
                description=f"{self.agent_name} 的关键词"
            ))
        
        return capabilities


class AgentCapabilityRegistry:
    """
    智能体能力注册表
    
    管理所有智能体的能力注册、查询和匹配
    
    使用示例：
        registry = AgentCapabilityRegistry()
        
        # 注册智能体能力
        registry.register(AgentCapability(
            agent_id="finance_1",
            agent_name="财务专家",
            agent_type="finance",
            domains=["risk_analysis", "statement_review"],
            keywords=["财务", "报表", "风险"]
        ))
        
        # 查询最佳匹配智能体
        best_match = registry.find_best_match("分析财务风险")
    """
    
    def __init__(self):
        self._capabilities: Dict[str, AgentCapability] = {}
        self._keyword_index: Dict[str, Set[str]] = {}  # 关键词 -> 智能体ID集合
        self._domain_index: Dict[str, Set[str]] = {}   # 领域 -> 智能体ID集合
        self._initialized = False
        
        logger.info("🗂️ [能力注册表] 初始化完成")
    
    def register(self, capability: AgentCapability) -> bool:
        """
        注册智能体能力
        
        Args:
            capability: 智能体能力描述
            
        Returns:
            注册是否成功
        """
        try:
            self._capabilities[capability.agent_id] = capability
            
            # 构建关键词索引
            for keyword in capability.keywords:
                keyword_lower = keyword.lower()
                if keyword_lower not in self._keyword_index:
                    self._keyword_index[keyword_lower] = set()
                self._keyword_index[keyword_lower].add(capability.agent_id)
            
            # 构建领域索引
            for domain in capability.domains:
                domain_lower = domain.lower()
                if domain_lower not in self._domain_index:
                    self._domain_index[domain_lower] = set()
                self._domain_index[domain_lower].add(capability.agent_id)
            
            self._initialized = True
            logger.info(f"✅ [能力注册表] 注册智能体: {capability.agent_name} ({capability.agent_id})")
            return True
            
        except Exception as e:
            logger.error(f"❌ [能力注册表] 注册失败: {e}")
            return False
    
    def unregister(self, agent_id: str) -> bool:
        """
        注销智能体
        
        Args:
            agent_id: 智能体ID
            
        Returns:
            注销是否成功
        """
        if agent_id not in self._capabilities:
            return False
        
        capability = self._capabilities[agent_id]
        
        # 清理索引
        for keyword in capability.keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in self._keyword_index:
                self._keyword_index[keyword_lower].discard(agent_id)
        
        for domain in capability.domains:
            domain_lower = domain.lower()
            if domain_lower in self._domain_index:
                self._domain_index[domain_lower].discard(agent_id)
        
        del self._capabilities[agent_id]
        logger.info(f"🗑️ [能力注册表] 注销智能体: {agent_id}")
        return True
    
    def get_capability(self, agent_id: str) -> Optional[AgentCapability]:
        """获取智能体能力"""
        return self._capabilities.get(agent_id)
    
    def get_all_capabilities(self) -> List[AgentCapability]:
        """获取所有已注册的能力"""
        return list(self._capabilities.values())
    
    def find_by_keyword(self, keyword: str) -> List[AgentCapability]:
        """通过关键词查找智能体"""
        keyword_lower = keyword.lower()
        agent_ids = self._keyword_index.get(keyword_lower, set())
        return [self._capabilities[aid] for aid in agent_ids if aid in self._capabilities]
    
    def find_by_domain(self, domain: str) -> List[AgentCapability]:
        """通过领域查找智能体"""
        domain_lower = domain.lower()
        agent_ids = self._domain_index.get(domain_lower, set())
        return [self._capabilities[aid] for aid in agent_ids if aid in self._capabilities]
    
    def find_best_match(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        required_domains: Optional[List[str]] = None,
        min_confidence: float = 0.5
    ) -> List[AgentCapability]:
        """
        查找最佳匹配的智能体
        
        Args:
            query: 查询文本
            context: 上下文信息
            required_domains: 必需的领域列表
            min_confidence: 最小置信度
            
        Returns:
            排序后的智能体列表（按匹配度降序）
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scores: Dict[str, float] = {}
        
        for agent_id, capability in self._capabilities.items():
            if not capability.enabled:
                continue
            
            score = 0.0
            matched_keywords = []
            
            # 1. 关键词匹配（基础分）
            for keyword in capability.keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in query_lower:
                    score += 1.0 * capability.metadata.get('keyword_weight', 1.0)
                    matched_keywords.append(keyword)
                elif any(word in keyword_lower for word in query_words):
                    score += 0.5
            
            # 2. 领域匹配（高分）
            for domain in capability.domains:
                domain_lower = domain.lower()
                if domain_lower in query_lower:
                    score += 2.0
                    # 如果是必需领域，加权
                    if required_domains and domain_lower in [d.lower() for d in required_domains]:
                        score += 3.0
            
            # 3. 实体匹配
            for entity in capability.entities:
                entity_lower = entity.lower()
                if entity_lower in query_lower:
                    score += 1.5
            
            # 4. 优先级加权
            score *= (1.0 + (10 - capability.priority) * 0.1)
            
            # 5. 响应时间惩罚（响应慢的降权）
            if capability.avg_response_time > 5.0:
                score *= 0.8
            
            # 6. 上下文加权
            if context:
                user_intent = context.get('intent', '')
                if user_intent and any(kw in user_intent.lower() for kw in capability.keywords):
                    score *= 1.2
            
            # 7. 并发能力检查
            current_load = self._get_agent_load(agent_id)
            if current_load >= capability.max_concurrent_tasks:
                score *= 0.5  # 高负载降权
            
            if score >= min_confidence * 10:
                scores[agent_id] = score
        
        # 排序返回
        sorted_agents = sorted(
            [(aid, score) for aid, score in scores.items()],
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            (self._capabilities[aid], score)
            for aid, score in sorted_agents
            if aid in self._capabilities
        ]
    
    def _get_agent_load(self, agent_id: str) -> int:
        """获取智能体当前负载（子类可覆盖）"""
        return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取注册表统计信息"""
        return {
            "total_agents": len(self._capabilities),
            "enabled_agents": sum(1 for c in self._capabilities.values() if c.enabled),
            "keyword_index_size": len(self._keyword_index),
            "domain_index_size": len(self._domain_index),
            "agents_by_type": self._group_by_type()
        }
    
    def _group_by_type(self) -> Dict[str, int]:
        """按类型分组统计"""
        groups = {}
        for capability in self._capabilities.values():
            agent_type = capability.agent_type
            groups[agent_type] = groups.get(agent_type, 0) + 1
        return groups
    
    def clear(self):
        """清空所有注册"""
        self._capabilities.clear()
        self._keyword_index.clear()
        self._domain_index.clear()
        self._initialized = False
        logger.info("🗑️ [能力注册表] 已清空")


# 全局单例
_global_registry: Optional[AgentCapabilityRegistry] = None


def get_capability_registry() -> AgentCapabilityRegistry:
    """获取全局能力注册表单例"""
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentCapabilityRegistry()
    return _global_registry
