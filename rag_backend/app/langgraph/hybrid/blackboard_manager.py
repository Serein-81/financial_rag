"""
黑板模式管理器

实现 Agent 间共享信息的黑板模式

功能：
1. 提供共享的黑板空间供 Agent 发布和读取信息
2. 管理信息的生命周期
3. 支持信息订阅和通知
4. 维护 Agent 参与状态
"""

import logging
import uuid
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class EntryType(str, Enum):
    """黑板条目类型"""
    OBSERVATION = "observation"  # 观察结果
    OPINION = "opinion"  # 观点
    QUESTION = "question"  # 问题
    ANSWER = "answer"  # 回答
    DECISION = "decision"  # 决策
    COMMENT = "comment"  # 评论
    EVIDENCE = "evidence"  # 证据


class EntryPriority(int, Enum):
    """条目优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class BlackboardEntry:
    """
    黑板条目
    
    表示黑板上的单个信息条目
    """
    id: str
    agent_name: str
    entry_type: EntryType
    content: Any
    timestamp: datetime = field(default_factory=datetime.now)
    round_number: int = 0
    priority: EntryPriority = EntryPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None  # 用于回复/引用
    tags: List[str] = field(default_factory=list)
    is_public: bool = True  # 是否对所有 Agent 可见
    is_final: bool = False  # 是否是最终决定
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "entry_type": self.entry_type.value if isinstance(self.entry_type, EntryType) else self.entry_type,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "round_number": self.round_number,
            "priority": self.priority.value if isinstance(self.priority, EntryPriority) else self.priority,
            "metadata": self.metadata,
            "parent_id": self.parent_id,
            "tags": self.tags,
            "is_public": self.is_public,
            "is_final": self.is_final
        }


class BlackboardManager:
    """
    黑板模式管理器
    
    提供 Agent 间共享信息的黑板空间。
    
    设计原则：
    1. **透明性**：所有 Agent 都能看到黑板上的公开信息
    2. **异步性**：Agent 可以随时发布和读取信息
    3. **可追溯性**：保留所有历史记录
    4. **组织性**：通过类型、轮次、标签等方式组织信息
    
    使用示例：
    ```python
    blackboard = BlackboardManager()
    
    # Agent A 发布观点
    blackboard.post("agent_a", "我认为应该这样做...", EntryType.OPINION)
    
    # Agent B 读取所有观点
    opinions = blackboard.get_by_type(EntryType.OPINION)
    
    # Agent B 发布评论
    blackboard.post("agent_b", "同意 A 的观点，但是...", EntryType.COMMENT)
    ```
    """
    
    def __init__(
        self,
        max_entries: int = 1000,
        entry_ttl_seconds: Optional[int] = None
    ):
        """
        初始化黑板管理器
        
        Args:
            max_entries: 最大条目数量
            entry_ttl_seconds: 条目过期时间（秒），None 表示不过期
        """
        self.max_entries = max_entries
        self.entry_ttl_seconds = entry_ttl_seconds
        
        # 黑板条目存储
        self._entries: Dict[str, BlackboardEntry] = {}
        
        # 按 Agent 索引
        self._by_agent: Dict[str, List[str]] = defaultdict(list)
        
        # 按类型索引
        self._by_type: Dict[EntryType, List[str]] = defaultdict(list)
        
        # 按轮次索引
        self._by_round: Dict[int, List[str]] = defaultdict(list)
        
        # 订阅者
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        
        # 锁（用于线程安全）
        import asyncio
        self._lock = asyncio.Lock()
        
        logger.info(f"[Blackboard] 初始化完成: max_entries={max_entries}")
    
    def post(
        self,
        agent_name: str,
        content: Any,
        entry_type: EntryType = EntryType.OBSERVATION,
        round_number: int = 0,
        priority: EntryPriority = EntryPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_public: bool = True
    ) -> str:
        """
        发布条目到黑板
        
        Args:
            agent_name: 发布者 Agent 名称
            content: 内容
            entry_type: 条目类型
            round_number: 轮次号
            priority: 优先级
            metadata: 元数据
            parent_id: 父条目 ID（用于回复/引用）
            tags: 标签列表
            is_public: 是否公开
            
        Returns:
            条目 ID
        """
        entry_id = str(uuid.uuid4())
        
        entry = BlackboardEntry(
            id=entry_id,
            agent_name=agent_name,
            entry_type=entry_type,
            content=content,
            round_number=round_number,
            priority=priority,
            metadata=metadata or {},
            parent_id=parent_id,
            tags=tags or [],
            is_public=is_public
        )
        
        # 添加到存储
        self._entries[entry_id] = entry
        
        # 更新索引
        self._by_agent[agent_name].append(entry_id)
        self._by_type[entry_type].append(entry_id)
        self._by_round[round_number].append(entry_id)
        
        # 触发订阅者通知
        self._notify_subscribers(entry)
        
        logger.debug(
            f"[Blackboard] 发布条目: id={entry_id}, "
            f"agent={agent_name}, type={entry_type.value}"
        )
        
        return entry_id
    
    def get(
        self,
        entry_id: str,
        agent_name: Optional[str] = None
    ) -> Optional[BlackboardEntry]:
        """
        获取单个条目
        
        Args:
            entry_id: 条目 ID
            agent_name: 请求者 Agent（用于权限检查）
            
        Returns:
            条目对象，如果不存在或无权访问则返回 None
        """
        entry = self._entries.get(entry_id)
        
        if not entry:
            return None
        
        # 权限检查
        if not entry.is_public and agent_name and entry.agent_name != agent_name:
            return None
        
        return entry
    
    def get_history(
        self,
        agent_name: Optional[str] = None,
        include_private: bool = False
    ) -> List[BlackboardEntry]:
        """
        获取黑板历史记录
        
        Args:
            agent_name: Agent 名称（用于过滤）
            include_private: 是否包含私有条目
            
        Returns:
            按时间排序的条目列表
        """
        entries = []
        
        for entry in self._entries.values():
            # 过滤私有条目
            if not entry.is_public and not include_private:
                if agent_name and entry.agent_name != agent_name:
                    continue
            
            # 过滤特定 Agent 的条目
            if agent_name and entry.agent_name != agent_name:
                continue
            
            entries.append(entry)
        
        # 按时间排序
        entries.sort(key=lambda e: e.timestamp)
        
        return entries
    
    def get_by_type(
        self,
        entry_type: EntryType,
        agent_name: Optional[str] = None,
        include_private: bool = False
    ) -> List[BlackboardEntry]:
        """
        按类型获取条目
        
        Args:
            entry_type: 条目类型
            agent_name: Agent 名称（用于过滤）
            include_private: 是否包含私有条目
            
        Returns:
            符合条件的条目列表
        """
        entry_ids = self._by_type.get(entry_type, [])
        entries = []
        
        for entry_id in entry_ids:
            entry = self._entries.get(entry_id)
            if not entry:
                continue
            
            # 过滤私有条目
            if not entry.is_public and not include_private:
                if agent_name and entry.agent_name != agent_name:
                    continue
            
            # 过滤特定 Agent
            if agent_name and entry.agent_name != agent_name:
                continue
            
            entries.append(entry)
        
        return entries
    
    def get_by_round(
        self,
        round_number: int,
        agent_name: Optional[str] = None
    ) -> List[BlackboardEntry]:
        """
        按轮次获取条目
        
        Args:
            round_number: 轮次号
            agent_name: Agent 名称（用于过滤）
            
        Returns:
            符合条件的条目列表
        """
        entry_ids = self._by_round.get(round_number, [])
        entries = []
        
        for entry_id in entry_ids:
            entry = self._entries.get(entry_id)
            if not entry:
                continue
            
            if agent_name and entry.agent_name != agent_name:
                continue
            
            entries.append(entry)
        
        return entries
    
    def get_replies(
        self,
        parent_id: str
    ) -> List[BlackboardEntry]:
        """
        获取对某个条目的所有回复
        
        Args:
            parent_id: 父条目 ID
            
        Returns:
            回复列表
        """
        return [
            entry for entry in self._entries.values()
            if entry.parent_id == parent_id
        ]
    
    def get_by_tag(
        self,
        tag: str,
        agent_name: Optional[str] = None
    ) -> List[BlackboardEntry]:
        """
        按标签获取条目
        
        Args:
            tag: 标签
            agent_name: Agent 名称（用于过滤）
            
        Returns:
            符合条件的条目列表
        """
        entries = []
        
        for entry in self._entries.values():
            if tag in entry.tags:
                if agent_name and entry.agent_name != agent_name:
                    continue
                entries.append(entry)
        
        return entries
    
    def get_latest(
        self,
        entry_type: Optional[EntryType] = None,
        agent_name: Optional[str] = None,
        limit: int = 10
    ) -> List[BlackboardEntry]:
        """
        获取最新的条目
        
        Args:
            entry_type: 条目类型过滤
            agent_name: Agent 名称过滤
            limit: 返回数量限制
            
        Returns:
            最新的条目列表
        """
        if entry_type:
            entries = self.get_by_type(entry_type, agent_name)
        else:
            entries = self.get_history(agent_name)
        
        # 排序并返回最新的
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        
        return entries[:limit]
    
    def search(
        self,
        query: str,
        agent_name: Optional[str] = None
    ) -> List[BlackboardEntry]:
        """
        搜索条目
        
        Args:
            query: 搜索关键词
            agent_name: Agent 名称过滤
            
        Returns:
            匹配的条目列表
        """
        query_lower = query.lower()
        results = []
        
        for entry in self._entries.values():
            # 搜索内容
            if isinstance(entry.content, str):
                if query_lower not in entry.content.lower():
                    continue
            else:
                # 非字符串内容转为字符串搜索
                if query_lower not in str(entry.content).lower():
                    continue
            
            # 过滤 Agent
            if agent_name and entry.agent_name != agent_name:
                continue
            
            results.append(entry)
        
        return results
    
    def subscribe(
        self,
        agent_name: str,
        callback: Callable[[BlackboardEntry], None]
    ):
        """
        订阅新条目
        
        Args:
            agent_name: Agent 名称
            callback: 回调函数
        """
        self._subscribers[agent_name].append(callback)
        logger.debug(f"[Blackboard] Agent {agent_name} 订阅了黑板")
    
    def unsubscribe(
        self,
        agent_name: str,
        callback: Callable[[BlackboardEntry], None]
    ):
        """
        取消订阅
        
        Args:
            agent_name: Agent 名称
            callback: 回调函数
        """
        if agent_name in self._subscribers:
            if callback in self._subscribers[agent_name]:
                self._subscribers[agent_name].remove(callback)
    
    def _notify_subscribers(self, entry: BlackboardEntry):
        """通知订阅者"""
        for agent_name, callbacks in self._subscribers.items():
            # 如果条目不是公开的，只有发布者和订阅者相同才通知
            if not entry.is_public and entry.agent_name != agent_name:
                continue
            
            for callback in callbacks:
                try:
                    callback(entry)
                except Exception as e:
                    logger.error(f"[Blackboard] 通知订阅者失败: {e}")
    
    def clear_round(self, round_number: int):
        """
        清除指定轮次的所有条目
        
        Args:
            round_number: 轮次号
        """
        entry_ids = self._by_round.get(round_number, []).copy()
        
        for entry_id in entry_ids:
            self._delete_entry(entry_id)
        
        if round_number in self._by_round:
            del self._by_round[round_number]
        
        logger.info(f"[Blackboard] 清除轮次 {round_number} 的条目: {len(entry_ids)} 条")
    
    def _delete_entry(self, entry_id: str):
        """删除条目"""
        entry = self._entries.get(entry_id)
        if not entry:
            return
        
        # 从存储删除
        del self._entries[entry_id]
        
        # 从索引删除
        if entry_id in self._by_agent.get(entry.agent_name, []):
            self._by_agent[entry.agent_name].remove(entry_id)
        
        if entry_id in self._by_type.get(entry.entry_type, []):
            self._by_type[entry.entry_type].remove(entry_id)
        
        if entry_id in self._by_round.get(entry.round_number, []):
            self._by_round[entry.round_number].remove(entry_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取黑板统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "total_entries": len(self._entries),
            "by_agent": {
                agent: len(entry_ids)
                for agent, entry_ids in self._by_agent.items()
            },
            "by_type": {
                entry_type.value: len(entry_ids)
                for entry_type, entry_ids in self._by_type.items()
            },
            "by_round": {
                round_num: len(entry_ids)
                for round_num, entry_ids in self._by_round.items()
            },
            "subscribers": len(self._subscribers)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        导出黑板状态
        
        Returns:
            包含所有条目的字典
        """
        return {
            "entries": [entry.to_dict() for entry in self._entries.values()],
            "statistics": self.get_statistics()
        }
