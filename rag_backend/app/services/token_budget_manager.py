"""
Token 预算管理器

使用 tiktoken 进行精确的 token 计数和预算管理

功能：
1. 动态 token 计数
2. 预算分配和监控
3. 上下文窗口管理
4. 自动压缩和清理
"""

import tiktoken
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class TokenBudget:
    """Token 预算配置"""
    total_budget: int
    system_reserved: int = 2000
    context_reserved: int = 1000
    available_for_user: int = 0
    
    def __post_init__(self):
        self.available_for_user = max(
            0, 
            self.total_budget - self.system_reserved - self.context_reserved
        )


@dataclass
class TokenUsage:
    """Token 使用记录"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TokenAllocation:
    """Token 分配详情"""
    component: str
    tokens: int
    percentage: float
    priority: int = 0


class TokenBudgetManager:
    """
    Token 预算管理器
    
    特点：
    1. 基于 tiktoken 的精确计数
    2. 动态预算分配
    3. 多组件管理
    4. 实时监控和告警
    """
    
    def __init__(
        self,
        model: str = "gpt-4",
        total_budget: int = 128000,
        system_reserved: int = 2000,
        context_reserved: int = 1000,
        warning_threshold: float = 0.8,
        critical_threshold: float = 0.95
    ):
        """
        初始化 Token 预算管理器
        
        Args:
            model: 模型名称（用于 tiktoken 编码）
            total_budget: 总 token 预算
            system_reserved: 系统提示保留 token 数
            context_reserved: 上下文保留 token 数
            warning_threshold: 警告阈值（百分比）
            critical_threshold: 严重警告阈值（百分比）
        """
        self.model = model
        self.total_budget = TokenBudget(total_budget, system_reserved, context_reserved)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        
        self._usage_history: List[TokenUsage] = []
        self._current_usage: TokenUsage = TokenUsage()
        self._allocations: Dict[str, TokenAllocation] = {}
        self._max_history_size = 100
        
        try:
            self._encoder = tiktoken.encoding_for_model(model)
        except KeyError:
            logger.warning(f"未找到模型 {model} 的编码器，使用 cl100k_base")
            self._encoder = tiktoken.get_encoding("cl100k_base")
        
        logger.info("✅ Token 预算管理器初始化完成")
        logger.info(f"   模型: {model}")
        logger.info(f"   总预算: {total_budget} tokens")
        logger.info(f"   可用预算: {self.total_budget.available_for_user} tokens")
    
    def count_tokens(self, text: str) -> int:
        """
        计算文本的 token 数量
        
        Args:
            text: 输入文本
            
        Returns:
            token 数量
        """
        if not text:
            return 0
        
        return len(self._encoder.encode(text))
    
    def count_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        计算消息列表的 token 数量
        
        Args:
            messages: 消息列表
            
        Returns:
            token 数量
        """
        if not messages:
            return 0
        
        num_tokens = 0
        
        for message in messages:
            num_tokens += 4
            
            for key, value in message.items():
                if isinstance(value, str):
                    num_tokens += self.count_tokens(value)
                
                if key == "name":
                    num_tokens -= 1
            
            if value is None:
                num_tokens -= 1
        
        num_tokens += 2
        
        return num_tokens
    
    def allocate_budget(
        self,
        component: str,
        priority: int = 0
    ) -> TokenAllocation:
        """
        分配预算给组件
        
        Args:
            component: 组件名称
            priority: 优先级（越高越优先保留）
            
        Returns:
            分配详情
        """
        remaining = self.get_remaining_budget()
        
        if remaining <= 0:
            return TokenAllocation(
                component=component,
                tokens=0,
                percentage=0.0,
                priority=priority
            )
        
        total_priority = sum(a.priority for a in self._allocations.values()) + priority
        
        if total_priority == 0:
            allocation = remaining
        else:
            allocation = int(remaining * priority / total_priority)
        
        percentage = (allocation / self.total_budget.total_budget * 100) if self.total_budget.total_budget > 0 else 0
        
        token_allocation = TokenAllocation(
            component=component,
            tokens=allocation,
            percentage=percentage,
            priority=priority
        )
        
        self._allocations[component] = token_allocation
        
        return token_allocation
    
    def record_usage(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0
    ):
        """
        记录 token 使用
        
        Args:
            prompt_tokens: 提示 token 数
            completion_tokens: 完成 token 数
        """
        self._current_usage.prompt_tokens += prompt_tokens
        self._current_usage.completion_tokens += completion_tokens
        self._current_usage.total_tokens += (prompt_tokens + completion_tokens)
        
        logger.debug(
            f"Token 使用记录: prompt={prompt_tokens}, "
            f"completion={completion_tokens}, "
            f"total={self._current_usage.total_tokens}"
        )
    
    def commit_usage(self):
        """
        提交当前使用记录到历史
        """
        if self._current_usage.total_tokens > 0:
            self._usage_history.append(self._current_usage)
            
            if len(self._usage_history) > self._max_history_size:
                self._usage_history = self._usage_history[-self._max_history_size:]
            
            self._current_usage = TokenUsage()
    
    def get_remaining_budget(self) -> int:
        """
        获取剩余预算
        
        Returns:
            剩余 token 数
        """
        allocated = sum(a.tokens for a in self._allocations.values())
        return max(0, self.total_budget.available_for_user - allocated)
    
    def get_usage_percentage(self) -> float:
        """
        获取已使用百分比
        
        Returns:
            使用百分比（0.0 - 1.0）
        """
        if self.total_budget.total_budget == 0:
            return 0.0
        
        total_used = sum(u.total_tokens for u in self._usage_history)
        return total_used / self.total_budget.total_budget
    
    def get_usage_status(self) -> str:
        """
        获取使用状态
        
        Returns:
            状态描述
        """
        percentage = self.get_usage_percentage()
        
        if percentage >= self.critical_threshold:
            return "critical"
        elif percentage >= self.warning_threshold:
            return "warning"
        else:
            return "normal"
    
    def estimate_compression_ratio(self, target_tokens: int) -> float:
        """
        估算压缩比例
        
        Args:
            target_tokens: 目标 token 数
            
        Returns:
            需要压缩的比例（0.0 - 1.0）
        """
        remaining = self.get_remaining_budget()
        
        if remaining >= target_tokens:
            return 0.0
        
        return 1.0 - (target_tokens / remaining) if remaining > 0 else 1.0
    
    def should_warn(self, tokens_to_add: int) -> Tuple[bool, str]:
        """
        检查是否需要警告
        
        Args:
            tokens_to_add: 计划添加的 token 数
            
        Returns:
            (是否警告, 警告信息)
        """
        remaining = self.get_remaining_budget()
        new_total = remaining + tokens_to_add
        
        if new_total > self.total_budget.available_for_user:
            exceeded = new_total - self.total_budget.available_for_user
            percentage = (exceeded / self.total_budget.available_for_user * 100) if self.total_budget.available_for_user > 0 else 100
            
            if percentage >= (self.critical_threshold * 100):
                return True, f"⚠️ 严重: 将超出预算 {exceeded} tokens ({percentage:.1f}%)"
            elif percentage >= (self.warning_threshold * 100):
                return True, f"⚠️ 警告: 将接近预算上限 {exceeded} tokens ({percentage:.1f}%)"
        
        return False, ""
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        total_used = sum(u.total_tokens for u in self._usage_history)
        avg_usage = total_used / len(self._usage_history) if self._usage_history else 0
        
        return {
            "budget": {
                "total": self.total_budget.total_budget,
                "system_reserved": self.total_budget.system_reserved,
                "context_reserved": self.total_budget.context_reserved,
                "available": self.total_budget.available_for_user
            },
            "usage": {
                "current": self._current_usage.total_tokens,
                "total_used": total_used,
                "average": avg_usage,
                "remaining": self.get_remaining_budget(),
                "percentage": self.get_usage_percentage(),
                "status": self.get_usage_status()
            },
            "allocations": {
                name: {
                    "tokens": alloc.tokens,
                    "percentage": alloc.percentage,
                    "priority": alloc.priority
                }
                for name, alloc in self._allocations.items()
            },
            "history": {
                "count": len(self._usage_history),
                "max_size": self._max_history_size
            }
        }
    
    def reset(self):
        """
        重置预算管理器
        """
        self._usage_history = []
        self._current_usage = TokenUsage()
        self._allocations = {}
        
        logger.info("✅ Token 预算管理器已重置")


token_budget_manager = TokenBudgetManager()
