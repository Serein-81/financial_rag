"""
预算管理器

动态管理 Token 预算，支持组件级别的预算分配
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import logging
from datetime import datetime

from .token_tracker import TokenTracker
from app.memory_system.model_context_manager import model_context_manager
from app.core.config import settings

logger = logging.getLogger(__name__)


class BudgetStrategy(Enum):
    """预算分配策略"""
    FIXED = "fixed"
    DYNAMIC = "dynamic"
    PRIORITY = "priority"
    ADAPTIVE = "adaptive"


@dataclass
class BudgetConfig:
    """预算配置"""
    model_name: Optional[str] = None
    total_budget: int = 128000
    system_prompt_tokens: int = 4000
    max_context_tokens: int = 0
    reserved_response_tokens: int = 4000
    min_component_tokens: int = 500
    warning_threshold: float = 0.8
    critical_threshold: float = 0.95
    
    def __post_init__(self):
        """初始化后自动计算 max_context_tokens"""
        if self.model_name is None:
            self.model_name = self._get_default_model_name()
        
        if self.max_context_tokens == 0:
            self.max_context_tokens = model_context_manager.get_context_limit(self.model_name)
    
    def _get_default_model_name(self) -> str:
        """获取默认模型名称"""
        if settings.LLM_PROVIDER_DEFAULT:
            provider = settings.LLM_PROVIDER_DEFAULT
        else:
            provider = settings.LLM_PROVIDER
        
        provider_to_model = {
            "zhipu": settings.ZHIPU_MODEL if hasattr(settings, "ZHIPU_MODEL") else "glm-4-flash",
            "openai": settings.OPENAI_MODEL if hasattr(settings, "OPENAI_MODEL") else "gpt-4o-mini",
            "claude": settings.CLAUDE_MODEL if hasattr(settings, "CLAUDE_MODEL") else "claude-3-sonnet",
            "deepseek": settings.DEEPSEEK_MODEL if hasattr(settings, "DEEPSEEK_MODEL") else "deepseek/deepseek-chat-v3-0324",
            "qwen": settings.QWEN_MODEL if hasattr(settings, "QWEN_MODEL") else "qwen/qwen3.6-plus:free",
            "minimax": settings.MINIMAX_MODEL if hasattr(settings, "MINIMAX_MODEL") else "MiniMax-Text-01",
            "baichuan": settings.BAICHUAN_MODEL if hasattr(settings, "BAICHUAN_MODEL") else "baichuan4",
            "gpt": settings.GPT_MODEL if hasattr(settings, "GPT_MODEL") else "openai/gpt-4o-mini",
        }
        
        return provider_to_model.get(provider.lower(), "glm-4-flash")
    

@dataclass
class ComponentBudget:
    """组件预算"""
    name: str
    min_tokens: int = 500
    max_tokens: int = 50000
    priority: int = 1
    weight: float = 1.0
    allocated: int = 0
    used: int = 0
    
    @property
    def remaining(self) -> int:
        return self.allocated - self.used
    
    @property
    def usage_ratio(self) -> float:
        if self.allocated == 0:
            return 0.0
        return self.used / self.allocated


class BudgetManager:
    """
    Token 预算管理器
    
    功能：
    1. 动态分配组件预算
    2. 监控预算使用
    3. 警告和截断机制
    4. 组件级别预算追踪
    """
    
    def __init__(
        self,
        config: Optional[BudgetConfig] = None,
        tracker: Optional[TokenTracker] = None
    ):
        self.config = config or BudgetConfig()
        self.tracker = tracker or TokenTracker()
        
        self._components: Dict[str, ComponentBudget] = {}
        self._callbacks: Dict[str, List[Callable]] = {
            "warning": [],
            "critical": [],
            "exceeded": []
        }
        
        self._last_warning_time: Dict[str, datetime] = {}
        self._warning_cooldown_seconds = 60
    
    def register_component(
        self,
        name: str,
        min_tokens: int = 500,
        max_tokens: int = 50000,
        priority: int = 1,
        weight: float = 1.0
    ) -> ComponentBudget:
        """
        注册组件
        
        Args:
            name: 组件名称
            min_tokens: 最小保留 Token 数
            max_tokens: 最大可用 Token 数
            priority: 优先级 (1-10)
            weight: 权重系数
            
        Returns:
            组件预算对象
        """
        component = ComponentBudget(
            name=name,
            min_tokens=min_tokens,
            max_tokens=max_tokens,
            priority=priority,
            weight=weight
        )
        self._components[name] = component
        return component
    
    def register_callback(
        self,
        event: str,
        callback: Callable[[str, ComponentBudget], None]
    ):
        """
        注册预算事件回调
        
        Args:
            event: 事件类型 ("warning", "critical", "exceeded")
            callback: 回调函数
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def allocate_budgets(
        self,
        strategy: BudgetStrategy = BudgetStrategy.DYNAMIC,
        available_for_components: Optional[int] = None
    ) -> Dict[str, int]:
        """
        分配组件预算
        
        Args:
            strategy: 分配策略
            available_for_components: 可分配给组件的总 Token 数
            
        Returns:
            组件名称到分配 Token 数的映射
        """
        if available_for_components is None:
            available_for_components = self._calculate_available_budget()
        
        allocations = {}
        
        if strategy == BudgetStrategy.FIXED:
            allocations = self._allocate_fixed(available_for_components)
        elif strategy == BudgetStrategy.DYNAMIC:
            allocations = self._allocate_dynamic(available_for_components)
        elif strategy == BudgetStrategy.PRIORITY:
            allocations = self._allocate_priority(available_for_components)
        elif strategy == BudgetStrategy.ADAPTIVE:
            allocations = self._allocate_adaptive(available_for_components)
        
        for name, tokens in allocations.items():
            if name in self._components:
                self._components[name].allocated = tokens
        
        return allocations
    
    def _calculate_available_budget(self) -> int:
        """计算可用于组件的总预算"""
        reserved = (
            self.config.system_prompt_tokens +
            self.config.reserved_response_tokens
        )
        available = self.config.total_budget - reserved
        return max(0, available)
    
    def _allocate_fixed(self, available: int) -> Dict[str, int]:
        """固定分配策略"""
        if not self._components:
            return {}
        
        per_component = available // len(self._components)
        
        return {
            name: min(max_tokens, per_component)
            for name, comp in self._components.items()
            for max_tokens in [min(comp.max_tokens, per_component)]
        }
    
    def _allocate_dynamic(self, available: int) -> Dict[str, int]:
        """动态分配策略（基于权重）"""
        if not self._components:
            return {}
        
        total_weight = sum(c.weight for c in self._components.values())
        
        allocations = {}
        for name, comp in self._components.items():
            share = (comp.weight / total_weight) * available
            allocated = int(min(comp.max_tokens, max(comp.min_tokens, share)))
            allocations[name] = allocated
        
        return allocations
    
    def _allocate_priority(self, available: int) -> Dict[str, int]:
        """优先级分配策略"""
        if not self._components:
            return {}
        
        sorted_components = sorted(
            self._components.items(),
            key=lambda x: x[1].priority,
            reverse=True
        )
        
        allocations = {}
        remaining = available
        
        for name, comp in sorted_components:
            if remaining <= 0:
                allocations[name] = comp.min_tokens
                continue
            
            allocated = int(min(comp.max_tokens, max(comp.min_tokens, remaining * comp.weight)))
            allocations[name] = min(allocated, remaining)
            remaining -= allocations[name]
        
        return allocations
    
    def _allocate_adaptive(self, available: int) -> Dict[str, int]:
        """自适应分配策略（基于历史使用）"""
        if not self._components:
            return {}
        
        total_weight = 0
        adjusted_weights = {}
        
        for name, comp in self._components.items():
            if comp.used > 0:
                efficiency = comp.used / comp.allocated if comp.allocated > 0 else 1.0
                adjusted_weights[name] = comp.weight * efficiency
            else:
                adjusted_weights[name] = comp.weight * 0.5
            total_weight += adjusted_weights[name]
        
        allocations = {}
        for name, comp in self._components.items():
            share = (adjusted_weights[name] / total_weight) * available
            allocated = int(min(comp.max_tokens, max(comp.min_tokens, share)))
            allocations[name] = allocated
        
        return allocations
    
    def track_usage(self, component: str, tokens: int):
        """
        追踪组件 Token 使用
        
        Args:
            component: 组件名称
            tokens: 新增使用的 Token 数
        """
        if component not in self._components:
            logger.warning(f"[BudgetManager] 未注册的组件: {component}")
            return
        
        comp = self._components[component]
        comp.used += tokens
        
        self._check_thresholds(comp)
    
    def _check_thresholds(self, comp: ComponentBudget):
        """检查阈值并触发回调"""
        usage_ratio = comp.usage_ratio
        
        if usage_ratio >= self.config.critical_threshold:
            self._trigger_callbacks("critical", comp)
        elif usage_ratio >= self.config.warning_threshold:
            if self._can_trigger_warning(comp.name):
                self._trigger_callbacks("warning", comp)
                self._last_warning_time[comp.name] = datetime.now()
    
    def _can_trigger_warning(self, component_name: str) -> bool:
        """检查是否可以触发警告（防止频繁警告）"""
        if component_name not in self._last_warning_time:
            return True
        
        elapsed = (datetime.now() - self._last_warning_time[component_name]).total_seconds()
        return elapsed >= self._warning_cooldown_seconds
    
    def _trigger_callbacks(self, event: str, comp: ComponentBudget):
        """触发回调"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(event, comp)
            except (ValueError, KeyError) as e:
                logger.error(f"[BudgetManager] 回调执行数据错误: {e}")
            except (OSError, IOError) as e:
                logger.error(f"[BudgetManager] 回调执行IO错误: {e}")
            except Exception as e:
                logger.error(f"[BudgetManager] 回调执行失败: {e}")
    
    def truncate_to_budget(
        self,
        component: str,
        text: str,
        priority: str = "end"
    ) -> str:
        """
        截断文本以适应预算
        
        Args:
            component: 组件名称
            text: 待截断文本
            priority: 保留优先级 ("start", "end", "balanced")
            
        Returns:
            截断后的文本
        """
        if component not in self._components:
            return text
        
        comp = self._components[component]
        max_tokens = comp.remaining
        
        if max_tokens <= 0:
            return ""
        
        current_tokens = self.tracker.count_tokens(text)
        
        if current_tokens <= max_tokens:
            return text
        
        return self.tracker.truncate_to_tokens(text, max_tokens, direction=priority)
    
    def get_budget_status(self) -> Dict[str, Any]:
        """
        获取预算状态
        
        Returns:
            预算状态字典
        """
        total_allocated = sum(c.allocated for c in self._components.values())
        total_used = sum(c.used for c in self._components.values())
        
        return {
            "config": {
                "total_budget": self.config.total_budget,
                "max_context": self.config.max_context_tokens,
                "reserved_response": self.config.reserved_response_tokens
            },
            "total": {
                "allocated": total_allocated,
                "used": total_used,
                "remaining": self._calculate_available_budget() - total_used,
                "usage_ratio": total_used / self.config.total_budget if self.config.total_budget > 0 else 0
            },
            "components": {
                name: {
                    "allocated": comp.allocated,
                    "used": comp.used,
                    "remaining": comp.remaining,
                    "usage_ratio": comp.usage_ratio,
                    "priority": comp.priority
                }
                for name, comp in self._components.items()
            }
        }
    
    def should_allocate_more(self, component: str, needed_tokens: int) -> bool:
        """
        检查是否应该为组件分配更多预算
        
        Args:
            component: 组件名称
            needed_tokens: 需要的额外 Token 数
            
        Returns:
            是否应该分配
        """
        if component not in self._components:
            return False
        
        comp = self._components[component]
        current_remaining = comp.remaining
        
        if current_remaining >= needed_tokens:
            return False
        
        free_tokens = self._get_free_tokens()
        return free_tokens > self.config.min_component_tokens
    
    def _get_free_tokens(self) -> int:
        """获取未分配的空闲 Token"""
        total_allocated = sum(c.allocated for c in self._components.values())
        return self._calculate_available_budget() - total_allocated
    
    def reallocate(
        self,
        from_component: str,
        to_component: str,
        tokens: int
    ) -> bool:
        """
        从一个组件重新分配预算到另一个组件
        
        Args:
            from_component: 来源组件
            to_component: 目标组件
            tokens: 重新分配的 Token 数
            
        Returns:
            是否成功
        """
        if from_component not in self._components or to_component not in self._components:
            return False
        
        from_comp = self._components[from_component]
        to_comp = self._components[to_component]
        
        available = from_comp.remaining
        to_transfer = min(tokens, available)
        
        if to_transfer <= 0:
            return False
        
        if from_comp.allocated - to_transfer < from_comp.min_tokens:
            to_transfer = from_comp.allocated - from_comp.min_tokens
        
        if to_transfer <= 0:
            return False
        
        from_comp.allocated -= to_transfer
        to_comp.allocated += to_transfer
        
        return True
    
    def reset(self):
        """重置所有组件的已使用 Token"""
        for comp in self._components.values():
            comp.used = 0
        self._last_warning_time.clear()


budget_manager = BudgetManager()
