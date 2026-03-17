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

        # 🆕 话题频率统计（方案二）
        self.topic_frequency: Dict[str, int] = {}
        self.topic_first_seen: Dict[str, datetime] = {}

        # 🆕 用户意图关键词库（方案一）
        self.intent_keywords = [
            "记住", "记下", "别忘了", "提醒我", "一定要记住",
            "重要", "关键", "务必", "千万", "注意"
        ]

        # 🆕 重要话题关键词库（方案一）
        self.important_topic_keywords = {
            "health": ["过敏", "疾病", "糖尿病", "高血压", "心脏病", "癌症", 
                      "手术", "住院", "药物", "治疗", "诊断", "症状"],
            "finance": ["密码", "账号", "银行卡", "信用卡", "支付", "转账", 
                       "贷款", "投资", "理财"],
            "personal": ["生日", "纪念日", "地址", "电话", "身份证", "护照"],
            "preference": ["喜欢", "讨厌", "偏好", "习惯", "爱好"],
            "work": ["项目", "任务", "截止日期", "会议", "客户", "合同"]
        }

        print("=" * 60)
        print("🧠 记忆管理器初始化完成")
        print(f"   Session: {session_id[:8]}...")
        print(f"   User: {user_id}")
        print(f"   工作记忆: {self.working_memory.capacity} 条")
        print(f"   情景记忆: {self.episodic_memory.capacity} 条")
        print(f"   语义记忆: {self.semantic_memory.capacity} 条")
        print(f"   🆕 智能巩固: 关键词识别 + 频率统计")
        print("=" * 60)

    
    async def add_message(self, role: str, content: str, 
                         importance: float = 0.5,
                         metadata: Optional[Dict[str, Any]] = None) -> MemoryItem:
        """
        添加消息到记忆系统（增强版）
        
        流程：
        1. 创建记忆项
        2. 🆕 智能评估重要性（关键词识别 + 频率统计）
        3. 添加到工作记忆（当前对话）
        4. 添加到情景记忆（持久化）
        5. 如果是重要知识，添加到语义记忆
        
        Args:
            role: 角色（user/assistant/system）
            content: 内容
            importance: 基础重要性（0.0-1.0），建议值：
                       - 0.3-0.4: 纯闲聊（"你好"、"再见"）
                       - 0.5-0.6: 普通对话（"今天天气真好"）
                       - 0.7-0.8: 有信息量的对话
                       - 0.9+: 明确的重要信息
            metadata: 元数据
            
        Returns:
            创建的记忆项
        """
        # 🆕 智能评估重要性（方案一 + 方案二）
        importance = await self._evaluate_importance(content, role, importance)
        
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
            print(f"⭐ [记忆管理器] 高重要性知识已添加到语义记忆 (importance={importance:.2f})")
        
        return item
    
    async def _evaluate_importance(self, content: str, role: str, base_importance: float) -> float:
        """
        🆕 智能评估记忆重要性（方案一 + 方案二）
        
        策略：
        1. 方案一：检测用户意图关键词（"记住"、"重要"等）
        2. 方案一：检测重要话题关键词（健康、财务等）
        3. 方案二：统计话题频率，高频话题提升重要性
        
        Args:
            content: 消息内容
            role: 角色
            base_importance: 基础重要性
            
        Returns:
            调整后的重要性（0.0-1.0）
        """
        importance = base_importance
        content_lower = content.lower()
        boost_reasons = []
        
        # 🔍 方案一：用户意图关键词检测
        has_intent = any(keyword in content_lower for keyword in self.intent_keywords)
        if has_intent:
            importance = max(importance, 0.9)
            boost_reasons.append("用户明确意图")
            print(f"🎯 [智能巩固] 检测到用户意图关键词")
        
        # 🔍 方案一：重要话题关键词检测
        detected_categories = []
        for category, keywords in self.important_topic_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                detected_categories.append(category)
                importance = max(importance, 0.85)
        
        if detected_categories:
            boost_reasons.append(f"重要话题({','.join(detected_categories)})")
            print(f"🏷️ [智能巩固] 检测到重要话题: {', '.join(detected_categories)}")
        
        # 🔍 方案二：话题频率统计
        keywords = self._extract_keywords(content)
        high_freq_topics = []
        
        for keyword in keywords:
            # 更新频率统计
            if keyword not in self.topic_frequency:
                self.topic_frequency[keyword] = 0
                self.topic_first_seen[keyword] = datetime.now()
            
            self.topic_frequency[keyword] += 1
            
            # 检查是否为高频话题
            if self.topic_frequency[keyword] >= 3:
                high_freq_topics.append(keyword)
                importance = max(importance, 0.88)
        
        if high_freq_topics:
            boost_reasons.append(f"高频话题({','.join(high_freq_topics[:2])})")
            print(f"🔥 [智能巩固] 检测到高频话题: {', '.join(high_freq_topics[:3])}")
            print(f"   频率统计: {', '.join([f'{t}({self.topic_frequency[t]}次)' for t in high_freq_topics[:3]])}")
        
        # 📊 输出评估结果
        if boost_reasons:
            print(f"📈 [重要性评估] {base_importance:.2f} → {importance:.2f} | 原因: {', '.join(boost_reasons)}")
        
        return min(1.0, importance)  # 确保不超过 1.0
    
    def _extract_keywords(self, content: str, max_keywords: int = 10) -> List[str]:
        """
        🆕 提取内容关键词（改进版）
        
        策略：
        1. 提取2-4字的中文词
        2. 提取英文词
        3. 过滤停用词
        4. 去重并限制数量
        
        Args:
            content: 内容
            max_keywords: 最大关键词数量
            
        Returns:
            关键词列表
        """
        # 停用词列表（简化版）
        stopwords = {
            "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
            "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
            "自己", "这", "那", "里", "就是", "可以", "这个", "什么", "吗", "呢", "啊",
            "还是", "得", "越来越", "厉害", "需要", "最近", "有点", "走路"
        }
        
        import re
        
        # 方法1：提取单个中文词（2-4个字）
        chinese_words_2 = re.findall(r'[\u4e00-\u9fa5]{2}', content)  # 2字词
        chinese_words_3 = re.findall(r'[\u4e00-\u9fa5]{3}', content)  # 3字词
        chinese_words_4 = re.findall(r'[\u4e00-\u9fa5]{4}', content)  # 4字词
        
        # 方法2：提取英文词
        english_words = re.findall(r'[a-zA-Z]+', content.lower())
        
        # 合并所有词（优先长词）
        all_words = chinese_words_4 + chinese_words_3 + chinese_words_2 + english_words
        
        # 过滤和去重
        keywords = []
        seen = set()
        for word in all_words:
            if word in stopwords or word in seen or word.isdigit():
                continue
            if len(word) >= 2:
                keywords.append(word)
                seen.add(word)
        
        # 限制数量
        return keywords[:max_keywords]
    
    def get_topic_frequency_stats(self) -> Dict[str, Any]:
        """
        🆕 获取话题频率统计
        
        Returns:
            统计信息
        """
        # 按频率排序
        sorted_topics = sorted(
            self.topic_frequency.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return {
            "total_topics": len(self.topic_frequency),
            "top_topics": [
                {
                    "keyword": topic,
                    "frequency": freq,
                    "first_seen": self.topic_first_seen.get(topic, datetime.now()).isoformat()
                }
                for topic, freq in sorted_topics[:10]
            ],
            "high_frequency_topics": [
                topic for topic, freq in sorted_topics if freq >= 3
            ]
        }
    
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
                                   max_tokens: int = 2000,
                                   knowledge_context: str = "",
                                   system_instructions: str = "") -> str:
        """
        获取格式化的上下文 (使用增强版上下文构建器)
        
        Args:
            query: 查询内容
            max_tokens: 最大token数
            knowledge_context: 知识库上下文
            system_instructions: 系统指令
            
        Returns:
            结构化的上下文字符串
        """
        try:
            # 使用增强版上下文构建器
            from .context_builder import EnhancedContextBuilder, ContextConfig
            
            config = ContextConfig(max_tokens=max_tokens)
            builder = EnhancedContextBuilder(config)
            
            return await builder.build_context(
                user_query=query,
                memory_manager=self,
                knowledge_context=knowledge_context,
                system_instructions=system_instructions,
                max_tokens=max_tokens
            )
            
        except Exception as e:
            print(f"⚠️ [记忆管理器] 上下文构建失败，使用备用方案: {e}")
            
            # 备用方案：使用原有逻辑
            memories = await self.retrieve_context(query)
            
            context_parts = []
            current_length = 0
            
            # 工作记忆
            if memories["working"]:
                working_context = "【当前对话】\n"
                for m in memories["working"]:
                    working_context += f"{m.role}: {m.content}\n"
                context_parts.append(working_context)
                current_length += len(working_context)
            
            # 知识库上下文
            if knowledge_context and current_length < max_tokens:
                context_parts.append(f"\n【知识库】\n{knowledge_context}")
                current_length += len(knowledge_context)
            
            # 语义记忆
            if memories["semantic"] and current_length < max_tokens:
                semantic_context = "\n【相关知识】\n"
                for m in memories["semantic"][:3]:
                    if current_length + len(m.content) > max_tokens:
                        break
                    semantic_context += f"- {m.content}\n"
                    current_length += len(m.content)
                
                if len(semantic_context) > len("\n【相关知识】\n"):
                    context_parts.append(semantic_context)
            
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
