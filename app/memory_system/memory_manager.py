"""
记忆管理器 (Memory Manager)

统一管理所有类型的记忆，协调工作记忆、情景记忆和语义记忆
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from .base_memory import MemoryItem
from .working_memory import WorkingMemory
from .episodic_memory import EpisodicMemory
from .semantic_memory import SemanticMemory
from app.services.embedding_service import embedding_service


class MemoryManager:
    """
    记忆管理器 - 协调三层记忆系统
    
    架构：
    ┌─────────────────────────────────────────┐
    │         Memory Manager                   │
    ├─────────────────────────────────────────┤
    │  ┌──────────┐  ┌──────────┐  ┌────────┐│
    │  │ Working  │  │ Episodic │  │Semantic││
    │  │ Memory   │  │  Memory  │  │ Memory ││
    │  │ (短期)   │  │  (中期)  │  │ (长期) ││
    │  │  7条     │  │  100条   │  │ 1000条 ││
    │  └──────────┘  └──────────┘  └────────┘│
    └─────────────────────────────────────────┘
    
    工作流程：
    1. 新消息 → 工作记忆
    2. 会话结束 → 情景记忆
    3. 知识提取 → 语义记忆
    4. 检索时：工作记忆 → 情景记忆 → 语义记忆
    """
    
    def __init__(self, session_id: str, user_id: str):
        """
        初始化记忆管理器
        
        Args:
            session_id: 会话ID
            user_id: 用户ID
        """
        self.session_id = session_id
        self.user_id = user_id
        
        # 初始化三层记忆
        self.working_memory = WorkingMemory(capacity=10, expire_minutes=30)
        self.episodic_memory = EpisodicMemory(session_id, user_id, capacity=100)
        self.semantic_memory = SemanticMemory(user_id, capacity=1000)
        
        print("=" * 60)
        print("🧠 记忆管理器初始化完成")
        print(f"   Session: {session_id[:8]}...")
        print(f"   User: {user_id}")
        print(f"   工作记忆: {self.working_memory.capacity} 条")
        print(f"   情景记忆: {self.episodic_memory.capacity} 条")
        print(f"   语义记忆: {self.semantic_memory.capacity} 条")
        print("=" * 60)
    
    async def add_message(self, role: str, content: str, 
                         importance: float = 1.0,
                         metadata: Optional[Dict[str, Any]] = None) -> MemoryItem:
        """
        添加消息到记忆系统
        
        流程：
        1. 创建记忆项
        2. 添加到工作记忆（当前对话）
        3. 添加到情景记忆（持久化）
        4. 如果是重要知识，添加到语义记忆
        
        Args:
            role: 角色（user/assistant/system）
            content: 内容
            importance: 重要性（0.0-1.0）
            metadata: 元数据
            
        Returns:
            创建的记忆项
        """
        # 创建记忆项
        item = MemoryItem(
            content=content,
            role=role,
            importance=importance,
            metadata=metadata or {}
        )
        
        # 1. 添加到工作记忆
        await self.working_memory.add(item)
        
        # 2. 添加到情景记忆（持久化）
        await self.episodic_memory.add(item)
        
        # 3. 如果是高重要性知识，添加到语义记忆
        if importance >= 0.8:
            # 生成向量嵌入
            item.embedding = await embedding_service.get_embedding(content)
            await self.semantic_memory.add(item)
            print(f"⭐ [记忆管理器] 高重要性知识已添加到语义记忆")
        
        return item
    
    async def retrieve_context(self, query: str, 
                              use_working: bool = True,
                              use_episodic: bool = True,
                              use_semantic: bool = True,
                              top_k: int = 5) -> Dict[str, List[MemoryItem]]:
        """
        检索相关上下文
        
        策略：
        1. 工作记忆：返回全部（当前对话）
        2. 情景记忆：检索相似历史对话
        3. 语义记忆：检索相关知识
        
        Args:
            query: 查询内容
            use_working: 是否使用工作记忆
            use_episodic: 是否使用情景记忆
            use_semantic: 是否使用语义记忆
            top_k: 每层记忆返回的数量
            
        Returns:
            分层的记忆结果
        """
        results = {
            "working": [],
            "episodic": [],
            "semantic": []
        }
        
        # 生成查询向量（一次性生成，多处使用）
        query_embedding = await embedding_service.get_embedding(query)
        
        # 1. 工作记忆（当前对话上下文）
        if use_working:
            results["working"] = await self.working_memory.retrieve()
            print(f"🔍 [工作记忆] 检索到 {len(results['working'])} 条")
        
        # 2. 情景记忆（历史对话）
        if use_episodic:
            results["episodic"] = await self.episodic_memory.retrieve(
                query, top_k=top_k, query_embedding=query_embedding
            )
            print(f"🔍 [情景记忆] 检索到 {len(results['episodic'])} 条")
        
        # 3. 语义记忆（长期知识）
        if use_semantic:
            results["semantic"] = await self.semantic_memory.retrieve(
                query, top_k=top_k, query_embedding=query_embedding
            )
            print(f"🔍 [语义记忆] 检索到 {len(results['semantic'])} 条")
        
        return results
    
    async def get_formatted_context(self, query: str, 
                                   max_tokens: int = 2000) -> str:
        """
        获取格式化的上下文
        
        用于传递给 LLM，包含：
        1. 当前对话（工作记忆）
        2. 相关历史（情景记忆）
        3. 相关知识（语义记忆）
        
        Args:
            query: 查询内容
            max_tokens: 最大 token 数（粗略估算）
            
        Returns:
            格式化的上下文字符串
        """
        # 检索记忆
        memories = await self.retrieve_context(query)
        
        context_parts = []
        current_length = 0
        
        # 1. 工作记忆（优先级最高，完整保留）
        if memories["working"]:
            working_context = "【当前对话】\n"
            for m in memories["working"]:
                working_context += f"{m.role}: {m.content}\n"
            
            context_parts.append(working_context)
            current_length += len(working_context)
        
        # 2. 语义记忆（相关知识）
        if memories["semantic"] and current_length < max_tokens:
            semantic_context = "\n【相关知识】\n"
            for m in memories["semantic"][:3]:  # 最多 3 条
                if current_length + len(m.content) > max_tokens:
                    break
                semantic_context += f"- {m.content}\n"
                current_length += len(m.content)
            
            if len(semantic_context) > len("\n【相关知识】\n"):
                context_parts.append(semantic_context)
        
        # 3. 情景记忆（历史对话）
        if memories["episodic"] and current_length < max_tokens:
            episodic_context = "\n【相关历史】\n"
            for m in memories["episodic"][:2]:  # 最多 2 条
                if current_length + len(m.content) > max_tokens:
                    break
                episodic_context += f"{m.role}: {m.content[:100]}...\n"
                current_length += len(m.content)
            
            if len(episodic_context) > len("\n【相关历史】\n"):
                context_parts.append(episodic_context)
        
        return "\n".join(context_parts)
    
    async def consolidate_memories(self) -> None:
        """
        记忆巩固
        
        定期执行的记忆整理任务：
        1. 清理过期的工作记忆
        2. 压缩情景记忆
        3. 从情景记忆提取知识到语义记忆
        4. 清理低价值记忆
        """
        print("🔄 [记忆管理器] 开始记忆巩固...")
        
        # 1. 工作记忆巩固
        await self.working_memory.consolidate()
        
        # 2. 情景记忆巩固
        await self.episodic_memory.consolidate()
        
        # 3. 从情景记忆提取知识
        await self.episodic_memory.load_from_db()
        await self.semantic_memory.extract_knowledge(self.episodic_memory.memories)
        
        # 4. 语义记忆巩固
        await self.semantic_memory.consolidate()
        
        print("✅ [记忆管理器] 记忆巩固完成")
    
    async def get_memory_statistics(self) -> Dict[str, Any]:
        """
        获取记忆系统统计信息
        
        Returns:
            统计信息字典
        """
        # 加载情景记忆
        await self.episodic_memory.load_from_db()
        
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "working_memory": self.working_memory.get_statistics(),
            "episodic_memory": self.episodic_memory.get_statistics(),
            "semantic_memory": self.semantic_memory.get_statistics(),
            "total_memories": (
                self.working_memory.get_size() +
                self.episodic_memory.get_size() +
                self.semantic_memory.get_size()
            )
        }
    
    async def export_session_summary(self) -> Dict[str, Any]:
        """
        导出会话摘要
        
        用于会话结束时生成报告
        """
        await self.episodic_memory.load_from_db()
        
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "start_time": self.episodic_memory.memories[0].timestamp.isoformat() if self.episodic_memory.memories else None,
            "end_time": datetime.now().isoformat(),
            "total_messages": self.episodic_memory.get_size(),
            "session_summary": await self.episodic_memory.get_session_summary(),
            "working_context": self.working_memory.get_recent_summary(),
            "knowledge_extracted": self.semantic_memory.get_knowledge_summary(),
            "statistics": await self.get_memory_statistics()
        }
    
    async def search_current_conversation(self, 
                                        keywords: List[str] = None,
                                        role: str = None,
                                        content_pattern: str = None,
                                        importance_min: float = None,
                                        top_k: int = 10) -> List[MemoryItem]:
        """
        在当前对话中搜索记忆
        
        Args:
            keywords: 关键词列表，支持多个关键词
            role: 角色过滤 (user/assistant/system)
            content_pattern: 内容模式匹配
            importance_min: 最小重要性阈值
            top_k: 返回结果数量限制
            
        Returns:
            匹配的记忆项列表
        """
        print(f"🔍 [记忆搜索] 开始搜索当前对话")
        print(f"   关键词: {keywords}")
        print(f"   角色: {role}")
        print(f"   重要性: >={importance_min}")
        
        results = []
        
        # 1. 搜索工作记忆（当前对话）
        working_results = await self._search_memory_list(
            self.working_memory.memories, keywords, role, content_pattern, importance_min
        )
        results.extend(working_results)
        
        # 2. 搜索情景记忆（当前会话的历史）
        await self.episodic_memory.load_from_db()
        episodic_results = await self._search_memory_list(
            self.episodic_memory.memories, keywords, role, content_pattern, importance_min
        )
        results.extend(episodic_results)
        
        # 3. 去重（基于内容和时间戳）
        unique_results = []
        seen_content = set()
        for item in results:
            content_key = f"{item.content[:100]}_{item.timestamp}"
            if content_key not in seen_content:
                seen_content.add(content_key)
                unique_results.append(item)
        
        # 4. 按相关性和时间排序
        unique_results.sort(key=lambda x: (
            self._calculate_relevance_score(x, keywords),
            x.timestamp
        ), reverse=True)
        
        # 5. 限制返回数量
        final_results = unique_results[:top_k]
        
        print(f"🎯 [记忆搜索] 找到 {len(final_results)} 条匹配记忆")
        return final_results
    
    async def _search_memory_list(self, 
                                 memories: List[MemoryItem],
                                 keywords: List[str] = None,
                                 role: str = None,
                                 content_pattern: str = None,
                                 importance_min: float = None) -> List[MemoryItem]:
        """
        在记忆列表中搜索
        """
        results = []
        
        for memory in memories:
            # 角色过滤
            if role and memory.role != role:
                continue
            
            # 重要性过滤
            if importance_min and memory.importance < importance_min:
                continue
            
            # 关键词匹配
            if keywords:
                content_lower = memory.content.lower()
                keyword_match = any(
                    keyword.lower() in content_lower 
                    for keyword in keywords
                )
                if not keyword_match:
                    continue
            
            # 内容模式匹配
            if content_pattern:
                import re
                if not re.search(content_pattern, memory.content, re.IGNORECASE):
                    continue
            
            # 更新访问统计
            memory.access()
            results.append(memory)
        
        return results
    
    def _calculate_relevance_score(self, memory: MemoryItem, keywords: List[str] = None) -> float:
        """
        计算记忆项的相关性分数
        """
        score = memory.importance  # 基础分数为重要性
        
        if keywords:
            content_lower = memory.content.lower()
            keyword_matches = sum(
                1 for keyword in keywords 
                if keyword.lower() in content_lower
            )
            # 关键词匹配度加分
            score += keyword_matches * 0.2
        
        # 访问频率加分
        score += min(memory.access_count * 0.1, 0.5)
        
        # 衰减因子影响
        score *= memory.decay_factor
        
        return score

    def get_context_for_llm(self) -> List[Dict[str, str]]:
        """
        获取用于 LLM 的上下文
        
        返回标准的对话格式
        """
        return self.working_memory.get_context_window()
