"""
工作记忆 (Working Memory)

模拟人类的短期记忆，用于存储当前对话上下文
特点：
- 容量小（5-9条，符合米勒定律）
- 访问速度快
- 不持久化
- 自动淘汰旧记忆
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
from .base_memory import BaseMemory, MemoryItem


class WorkingMemory(BaseMemory):
    """
    工作记忆 - 当前对话的短期上下文
    
    实现策略：
    1. FIFO 队列（先进先出）
    2. 容量限制（默认 7 条，符合认知科学）
    3. 不需要向量检索（直接返回全部）
    4. 自动过期（超过 30 分钟未访问）
    """
    
    def __init__(self, capacity: int = 50, expire_minutes: int = 30):
        """
        初始化工作记忆
        
        Args:
            capacity: 容量（默认 50，支持更长的对话上下文）
            expire_minutes: 过期时间（分钟）
        """
        super().__init__(capacity)
        self.expire_minutes = expire_minutes
        print(f"🧠 [工作记忆] 初始化完成 | 容量: {capacity} | 过期时间: {expire_minutes}分钟")
    
    async def add(self, item: MemoryItem) -> None:
        """
        添加记忆到工作记忆
        
        策略：
        1. 如果已满，删除最旧的记忆（FIFO）
        2. 添加新记忆
        3. 清理过期记忆
        """
        # 清理过期记忆
        await self._cleanup_expired()
        
        # 如果已满，删除最旧的
        if self.is_full():
            removed = self.memories.pop(0)
            print(f"🗑️ [工作记忆] 容量已满，移除最旧记忆: {removed.content[:30]}...")
        
        # 添加新记忆
        self.memories.append(item)
        print(f"➕ [工作记忆] 添加记忆 | 当前数量: {len(self.memories)}/{self.capacity}")
    
    async def retrieve(self, query: str = None, top_k: int = None) -> List[MemoryItem]:
        """
        检索工作记忆
        
        工作记忆不需要复杂检索，直接返回所有有效记忆
        按时间顺序排列（最新的在后面）
        """
        await self._cleanup_expired()
        
        # 更新访问统计
        for memory in self.memories:
            memory.access()
        
        # 返回所有记忆（如果指定了 top_k，则返回最近的 k 条）
        if top_k:
            return self.memories[-top_k:]
        return self.memories.copy()
    
    async def update(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆项"""
        for memory in self.memories:
            if memory.id == item_id:
                for key, value in updates.items():
                    if hasattr(memory, key):
                        setattr(memory, key, value)
                return True
        return False
    
    async def forget(self, item_id: str) -> bool:
        """删除指定记忆"""
        for i, memory in enumerate(self.memories):
            if memory.id == item_id:
                self.memories.pop(i)
                print(f"🗑️ [工作记忆] 删除记忆: {item_id}")
                return True
        return False
    
    async def _cleanup_expired(self) -> None:
        """清理过期记忆"""
        now = datetime.now()
        expire_threshold = timedelta(minutes=self.expire_minutes)
        
        original_count = len(self.memories)
        self.memories = [
            m for m in self.memories
            if now - m.last_access < expire_threshold
        ]
        
        removed_count = original_count - len(self.memories)
        if removed_count > 0:
            print(f"🧹 [工作记忆] 清理过期记忆: {removed_count} 条")
    
    def get_context_window(self) -> List[Dict[str, str]]:
        """
        获取对话上下文窗口
        
        返回格式化的对话历史，用于传递给 LLM
        """
        return [
            {"role": m.role, "content": m.content}
            for m in self.memories
        ]
    
    def get_recent_summary(self, max_length: int = 200) -> str:
        """
        获取最近对话的摘要
        
        用于生成简短的上下文描述
        """
        if not self.memories:
            return "暂无对话历史"
        
        recent = self.memories[-3:]  # 最近 3 条
        summary_parts = []
        
        for m in recent:
            content = m.content[:50] + "..." if len(m.content) > 50 else m.content
            summary_parts.append(f"{m.role}: {content}")
        
        summary = " | ".join(summary_parts)
        
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
        
        return summary
