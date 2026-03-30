"""
基础记忆类 - 所有记忆类型的抽象基类
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
import uuid


@dataclass
class MemoryItem:
    """
    记忆项 - 记忆系统的基本单元
    
    模拟人类记忆的基本属性：
    - 内容 (content)
    - 时间戳 (timestamp)
    - 重要性 (importance)
    - 访问次数 (access_count)
    - 最后访问时间 (last_access)
    - 衰减因子 (decay_factor)
    """
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    role: str = "user"  # user, assistant, system
    timestamp: datetime = field(default_factory=datetime.now)
    importance: float = 1.0  # 0.0 - 1.0
    access_count: int = 0
    last_access: datetime = field(default_factory=datetime.now)
    decay_factor: float = 1.0  # 记忆衰减因子
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    
    def access(self):
        """访问记忆项，更新访问统计"""
        self.access_count += 1
        self.last_access = datetime.now()
        # 每次访问增强记忆（减缓衰减）
        self.decay_factor = min(1.0, self.decay_factor + 0.1)
    
    def decay(self, time_delta_hours: float):
        """
        记忆衰减
        
        模拟艾宾浩斯遗忘曲线：
        R = e^(-t/S)
        R: 记忆保持率
        t: 时间间隔
        S: 记忆强度
        """
        import math
        # 记忆强度与重要性和访问次数相关
        strength = self.importance * (1 + math.log(1 + self.access_count))
        # 计算衰减
        self.decay_factor = math.exp(-time_delta_hours / (strength * 24))
    
    def get_relevance_score(self, query_embedding: List[float]) -> float:
        """
        计算与查询的相关性分数
        
        综合考虑：
        1. 语义相似度（向量余弦相似度）
        2. 时间衰减
        3. 重要性
        4. 访问频率
        """
        # 💡 终极修复：完美兼容 Python 列表和 NumPy 数组
        if self.embedding is None or len(self.embedding) == 0 or query_embedding is None or len(query_embedding) == 0:
            return 0.0
        
        # 1. 计算余弦相似度
        import math
        dot_product = sum(a * b for a, b in zip(self.embedding, query_embedding))
        norm_a = math.sqrt(sum(a * a for a in self.embedding))
        norm_b = math.sqrt(sum(b * b for b in query_embedding))
        
        if norm_a == 0 or norm_b == 0:
            similarity = 0.0
        else:
            similarity = dot_product / (norm_a * norm_b)
        
        # 2. 综合评分
        # 语义相似度 (40%) + 衰减因子 (30%) + 重要性 (20%) + 访问频率 (10%)
        access_score = min(1.0, self.access_count / 10)
        
        final_score = (
            similarity * 0.4 +
            self.decay_factor * 0.3 +
            self.importance * 0.2 +
            access_score * 0.1
        )
        
        return final_score
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "role": self.role,
            "timestamp": self.timestamp.isoformat(),
            "importance": self.importance,
            "access_count": self.access_count,
            "last_access": self.last_access.isoformat(),
            "decay_factor": self.decay_factor,
            "metadata": self.metadata
        }


class BaseMemory(ABC):
    """
    记忆基类 - 定义所有记忆类型的通用接口
    """
    
    def __init__(self, capacity: int = 100):
        """
        初始化记忆
        
        Args:
            capacity: 记忆容量（最多存储多少条记忆）
        """
        self.capacity = capacity
        self.memories: List[MemoryItem] = []
    
    @abstractmethod
    async def add(self, item: MemoryItem) -> None:
        """添加记忆"""
        pass
    
    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        """检索记忆"""
        pass
    
    @abstractmethod
    async def update(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆"""
        pass
    
    @abstractmethod
    async def forget(self, item_id: str) -> bool:
        """遗忘记忆"""
        pass
    
    async def clear(self) -> None:
        """清空所有记忆"""
        self.memories.clear()
    
    def get_size(self) -> int:
        """获取当前记忆数量"""
        return len(self.memories)
    
    def is_full(self) -> bool:
        """判断记忆是否已满"""
        return len(self.memories) >= self.capacity
    
    async def consolidate(self) -> None:
        """
        记忆巩固
        
        模拟人类睡眠时的记忆整理过程：
        1. 删除衰减严重的记忆
        2. 合并相似记忆
        3. 提升重要记忆的优先级
        """
        # 1. 删除衰减严重的记忆（衰减因子 < 0.1）
        self.memories = [m for m in self.memories if m.decay_factor >= 0.1]
        
        # 2. 按重要性和衰减因子排序
        self.memories.sort(
            key=lambda m: m.importance * m.decay_factor * (1 + m.access_count),
            reverse=True
        )
        
        # 3. 如果超过容量，删除最不重要的记忆
        if len(self.memories) > self.capacity:
            self.memories = self.memories[:self.capacity]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        if not self.memories:
            return {
                "total": 0,
                "avg_importance": 0.0,
                "avg_decay": 0.0,
                "avg_access": 0.0
            }
        
        return {
            "total": len(self.memories),
            "avg_importance": sum(m.importance for m in self.memories) / len(self.memories),
            "avg_decay": sum(m.decay_factor for m in self.memories) / len(self.memories),
            "avg_access": sum(m.access_count for m in self.memories) / len(self.memories),
            "capacity": self.capacity,
            "usage_rate": len(self.memories) / self.capacity
        }
